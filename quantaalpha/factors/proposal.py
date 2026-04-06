import json
from pathlib import Path
from typing import List, Tuple

from jinja2 import Environment, StrictUndefined

from quantaalpha.factors.coder.factor import FactorExperiment, FactorTask
from quantaalpha.components.proposal import FactorHypothesis2Experiment, FactorHypothesisGen
from quantaalpha.core.prompts import Prompts
from quantaalpha.core.proposal import Hypothesis, Scenario, Trace
from quantaalpha.core.experiment import Experiment
from quantaalpha.factors.experiment import QlibFactorExperiment
from quantaalpha.llm.client import APIBackend, call_structured, robust_json_parse
import os
import pandas as pd
from quantaalpha.log import logger
from quantaalpha.factors.regulator.factor_regulator import FactorRegulator
from quantaalpha.factors.data_capability import get_data_capabilities, render_financial_pit_panel_preview

PROPOSE_FACTORS_TOOL = {
    "type": "function",
    "function": {
        "name": "propose_hypothesis",
        "description": "Propose a new factor hypothesis with observation, knowledge, justification, and specification.",
        "parameters": {
            "type": "object",
            "properties": {
                "hypothesis": {"type": "string"},
                "concise_observation": {"type": "string"},
                "concise_knowledge": {"type": "string"},
                "concise_justification": {"type": "string"},
                "concise_specification": {"type": "string"},
            },
            "required": ["hypothesis"],
        },
    },
}

CONSTRUCT_FACTORS_TOOL = {
    "type": "function",
    "function": {
        "name": "construct_factors",
        "description": "Construct factor experiments from a hypothesis. Keys are factor names.",
        "parameters": {
            "type": "object",
            "properties": {
                "factors": {
                    "type": "object",
                    "description": "Dynamic keys: each key is a factor name, value has description, formulation, expression, variables.",
                },
            },
            "required": ["factors"],
        },
    },
}

FEEDBACK_TOOL = {
    "type": "function",
    "function": {
        "name": "provide_feedback",
        "description": "Provide feedback on hypothesis and experiment results.",
        "parameters": {
            "type": "object",
            "properties": {
                "Observations": {"type": "string"},
                "Feedback for Hypothesis": {"type": "string"},
                "New Hypothesis": {"type": "string"},
                "Reasoning": {"type": "string"},
                "Replace Best Result": {"type": "string"},
            },
            "required": ["Observations"],
        },
    },
}
DEFAULT_HISTORY_LIMIT = 6
MIN_HISTORY_LIMIT = 1


def build_financial_pit_context_hint(capabilities: dict | None) -> str:
    """Build a compact financial PIT usage hint for proposal-level context."""
    if not capabilities:
        return ""

    registry = get_data_capabilities(capabilities)
    hints: list[str] = []
    for name, spec in registry.items():
        if spec.get("layer") != "financial_pit":
            continue
        fields = ", ".join(spec.get("fields", [])) or "(unspecified)"
        preview = render_financial_pit_panel_preview(name, spec, aliases=list(spec.get("fields", []))[:2] or None)
        hint = f"Financial PIT capability available: {name}; use disclosure-date as-of semantics; fields={fields}."
        if preview:
            hint = f"{hint}\n{preview}"
        hints.append(hint)
    return "\n\n".join(hints)


def normalize_corrected_expression(expression) -> str:
    """Normalize quality-gate corrected expressions to a parser-safe string.

    Handles: dict payloads (code/expression key extraction),
    fenced code blocks, // and # comments, variable assignments
    (extracts RHS), multi-line input (picks first DSL line),
    and DSL pattern fallback.
    """
    import re

    # Handle non-string inputs — dict payloads handled first
    if isinstance(expression, dict):
        for key in ("code", "expression", "factor", "formula"):
            if key in expression:
                expression = str(expression[key])
                break
        else:
            expression = str(expression)

    if not isinstance(expression, str):
        return str(expression)

    # Handle string dict payloads — if the entire string looks like a JSON dict
    stripped = expression.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, dict):
                for key in ("code", "expression", "factor", "formula"):
                    if key in parsed:
                        expression = str(parsed[key])
                        break
                else:
                    expression = str(parsed)
        except (json.JSONDecodeError, ValueError):
            pass  # Fall through to string processing

    # Step 1: Strip fenced code blocks (any fence variant)
    text = re.sub(r"```[\w]*\n?.*?```", "", expression, flags=re.DOTALL)
    text = re.sub(r"`([^`\n]+)`", r"\1", text)  # inline code

    # Step 2: Process each line
    lines = text.split("\n")
    valid_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Skip pure comment lines
        if line.startswith("//") or line.startswith("#"):
            continue

        # Strip // comments (must be on the same line)
        if "//" in line:
            line = line[: line.index("//")]
            line = line.strip()
            if not line:
                continue

        # Strip # comments
        if "#" in line:
            line = line[: line.index("#")]
            line = line.strip()
            if not line:
                continue

        # Handle variable assignment: extract RHS
        # Match: identifier = expression
        # Valid LHS: starts with letter/underscore, contains only word chars and spaces before =
        assign_match = re.match(r"^([a-zA-Z_][a-zA-Z0-9_\s]*?)\s*=\s*(.+)$", line)
        if assign_match:
            lhs = assign_match.group(1).strip()
            rhs = assign_match.group(2).strip()
            # Only extract if LHS looks like a simple variable name (no operators)
            if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", lhs):
                line = rhs

        if line:
            valid_lines.append(line)

    # Step 3: Return single-line result
    if not valid_lines:
        # Fallback: extract first DSL pattern FUNC(...) from original text
        dsl_match = re.search(r"\b([A-Z][A-Z_]*)\s*\([^)]+\)", expression)
        if dsl_match:
            return dsl_match.group(0)
        return expression.strip()

    # Prefer lines that look like DSL expressions (uppercase func)
    for candidate in valid_lines:
        if re.match(r"^[A-Z][A-Z_]*\s*\(", candidate):
            return candidate

    # Strip non-DSL prefixes from lines (e.g. "Option A: STD(...)" -> "STD(...)")
    for candidate in valid_lines:
        dsl_match = re.search(r"([A-Z][A-Z_]*\s*\([^)]+\))", candidate)
        if dsl_match:
            return dsl_match.group(1)

    # Fall back to first valid line
    return valid_lines[0]


def render_hypothesis_and_feedback(prompt_dict, trace: Trace, history_limit: int = DEFAULT_HISTORY_LIMIT) -> str:
    """Render hypothesis_and_feedback with configurable history limit."""
    if len(trace.hist) > 0:
        limited_trace = Trace(scen=trace.scen)
        limited_trace.hist = trace.hist[-history_limit:] if history_limit > 0 else trace.hist
        return Environment(undefined=StrictUndefined).from_string(prompt_dict["hypothesis_and_feedback"]).render(trace=limited_trace)
    else:
        return "No previous hypothesis and feedback available since it's the first round."


def is_input_length_error(error_msg: str) -> bool:
    """Check if error is due to input length limit."""
    error_indicators = ["input length", "context length", "maximum context", "token limit", "InvalidParameter", "Range of input length", "max_tokens", "too long"]
    error_str = str(error_msg).lower()
    return any(indicator.lower() in error_str for indicator in error_indicators)


QlibFactorHypothesis = Hypothesis


class AlphaAgentHypothesis(Hypothesis):
    """
    AlphaAgentHypothesis extends the Hypothesis class to include a potential_direction,
    which represents the initial idea or starting point for the hypothesis.
    """

    def __init__(self, hypothesis: str, concise_observation: str, concise_justification: str, concise_knowledge: str, concise_specification: str) -> None:
        super().__init__(
            hypothesis,
            "",
            "",
            concise_observation,
            concise_justification,
            concise_knowledge,
        )
        self.concise_specification = concise_specification

    def __str__(self) -> str:
        return f"""Hypothesis: {self.hypothesis}
                Concise Observation: {self.concise_observation}
                Concise Justification: {self.concise_justification}
                Concise Knowledge: {self.concise_knowledge}
                concise Specification: {self.concise_specification}
                """


base_prompt_dict = Prompts(file_path=Path(__file__).parent / "prompts" / "prompts.yaml")


class QlibFactorHypothesisGen(FactorHypothesisGen):
    def __init__(self, scen: Scenario) -> Tuple[dict, bool]:
        super().__init__(scen)

    def prepare_context(self, trace: Trace) -> Tuple[dict, bool]:
        hypothesis_and_feedback = (Environment(undefined=StrictUndefined).from_string(base_prompt_dict["hypothesis_and_feedback"]).render(trace=trace)) if len(trace.hist) > 0 else "No previous hypothesis and feedback available since it's the first round."
        context_dict = {
            "hypothesis_and_feedback": hypothesis_and_feedback,
            "RAG": None,
            "hypothesis_output_format": base_prompt_dict["hypothesis_output_format"],
            "hypothesis_specification": base_prompt_dict["factor_hypothesis_specification"],
            "function_lib_description": base_prompt_dict["function_lib_description"],
        }
        return context_dict, True

    def convert_response(self, response: str) -> Hypothesis:
        response_dict = robust_json_parse(response)
        hypothesis = QlibFactorHypothesis(
            hypothesis=response_dict.get("hypothesis", ""),
            reason=response_dict.get("reason", ""),
            concise_reason=response_dict.get("concise_reason", ""),
            concise_observation=response_dict.get("concise_observation", ""),
            concise_justification=response_dict.get("concise_justification", ""),
            concise_knowledge=response_dict.get("concise_knowledge", ""),
        )
        return hypothesis


class QlibFactorHypothesis2Experiment(FactorHypothesis2Experiment):
    def prepare_context(self, hypothesis: Hypothesis, trace: Trace) -> Tuple[dict | bool]:
        scenario = trace.scen.get_scenario_all_desc()
        experiment_output_format = base_prompt_dict["factor_experiment_output_format"]

        hypothesis_and_feedback = (Environment(undefined=StrictUndefined).from_string(base_prompt_dict["hypothesis_and_feedback"]).render(trace=trace)) if len(trace.hist) > 0 else "No previous hypothesis and feedback available since it's the first round."

        experiment_list: List[FactorExperiment] = [t[1] for t in trace.hist]

        factor_list = []
        for experiment in experiment_list:
            factor_list.extend(experiment.sub_tasks)

        return {
            "target_hypothesis": str(hypothesis),
            "scenario": scenario,
            "hypothesis_and_feedback": hypothesis_and_feedback,
            "experiment_output_format": experiment_output_format,
            "target_list": factor_list,
            "RAG": None,
        }, True

    def convert_response(self, response: str, trace: Trace) -> FactorExperiment:
        response_dict = robust_json_parse(response)
        tasks = []

        for factor_name in response_dict:
            factor_data = response_dict.get(factor_name, {})
            if not isinstance(factor_data, dict):
                continue
            description = factor_data.get("description", "")
            formulation = factor_data.get("formulation", "")
            # expression = factor_data.get("expression", "")
            variables = factor_data.get("variables", {})
            tasks.append(
                FactorTask(
                    factor_name=factor_name,
                    factor_description=description,
                    factor_formulation=formulation,
                    # factor_expression=expression,
                    variables=variables,
                )
            )

        exp = QlibFactorExperiment(tasks)
        exp.based_experiments = [QlibFactorExperiment(sub_tasks=[])] + [t[1] for t in trace.hist if t[2]]

        unique_tasks = []

        for task in tasks:
            duplicate = False
            for based_exp in exp.based_experiments:
                for sub_task in based_exp.sub_tasks:
                    if task.factor_name == sub_task.factor_name:
                        duplicate = True
                        break
                if duplicate:
                    break
            if not duplicate:
                unique_tasks.append(task)

        exp.tasks = unique_tasks
        return exp


qa_prompt_dict = Prompts(file_path=Path(__file__).parent / "prompts" / "prompts.yaml")


# prompt_dict not as attribute: class instance is pickled later, prompt_dict cannot be pickled
class AlphaAgentHypothesisGen(FactorHypothesisGen):
    def __init__(self, scen: Scenario, potential_direction: str = None) -> Tuple[dict, bool]:
        super().__init__(scen)
        self.potential_direction = potential_direction

    def _build_fallback_hypothesis(self) -> AlphaAgentHypothesis:
        direction = (self.potential_direction or "daily price-volume relationship").strip()
        return AlphaAgentHypothesis(
            hypothesis=(f"Construct a daily factor from {direction}, using only daily price and volume fields with short rolling windows and cross-sectional normalization."),
            concise_observation=("The current LLM response was empty or unparsable, so a conservative daily price-volume hypothesis is used."),
            concise_knowledge=("If intraday or microstructure data is unavailable, daily price-volume proxies with rolling normalization can still express short-horizon trading pressure."),
            concise_justification=("A constrained daily hypothesis keeps the pipeline executable while remaining aligned with the requested direction."),
            concise_specification=("Use only daily OHLCV-style inputs, avoid intraday or order-book assumptions, and keep the hypothesis testable."),
        )

    def prepare_context(self, trace: Trace, history_limit: int = DEFAULT_HISTORY_LIMIT) -> Tuple[dict, bool]:

        if len(trace.hist) > 0:
            hypothesis_and_feedback = render_hypothesis_and_feedback(qa_prompt_dict, trace, history_limit)

        elif self.potential_direction is not None:
            hypothesis_and_feedback = (
                Environment(undefined=StrictUndefined)
                .from_string(qa_prompt_dict["potential_direction_transformation"])
                .render(
                    potential_direction=self.potential_direction,
                    function_lib_description=qa_prompt_dict["function_lib_description"],
                )
            )  #
        else:
            hypothesis_and_feedback = "No previous hypothesis and feedback available since it's the first round. You are encouraged to propose an innovative hypothesis that diverges significantly from existing perspectives."

        context_dict = {
            "hypothesis_and_feedback": hypothesis_and_feedback,
            "RAG": None,
            "hypothesis_output_format": qa_prompt_dict["hypothesis_output_format"],
            "hypothesis_specification": qa_prompt_dict["factor_hypothesis_specification"],
            "function_lib_description": qa_prompt_dict["function_lib_description"],
        }
        return context_dict, True

    def convert_response(self, response: str) -> AlphaAgentHypothesis:
        """
        Convert LLM JSON to AlphaAgentHypothesis; use default empty string for missing fields to avoid KeyError.
        """
        if not response or not response.strip():
            raise ValueError("Empty hypothesis response from LLM")
        response_dict = robust_json_parse(response)
        # Use get to avoid KeyError on missing fields
        hypothesis = AlphaAgentHypothesis(
            hypothesis=response_dict.get("hypothesis", ""),
            concise_observation=response_dict.get("concise_observation", ""),
            concise_knowledge=response_dict.get("concise_knowledge", ""),
            concise_justification=response_dict.get("concise_justification", ""),
            concise_specification=response_dict.get("concise_specification", ""),
        )
        return hypothesis

    def render_generation_prompts(self, trace: Trace, history_limit: int = DEFAULT_HISTORY_LIMIT) -> tuple[str, str, bool]:
        """Render the structured prompt pair used for hypothesis generation."""
        context_dict, json_flag = self.prepare_context(trace, history_limit)
        system_prompt = (
            Environment(undefined=StrictUndefined)
            .from_string(qa_prompt_dict["hypothesis_gen"]["system_prompt"])
            .render(
                targets=self.targets,
                scenario=self.scen.get_scenario_all_desc(filtered_tag="hypothesis_and_experiment"),
                hypothesis_output_format=context_dict["hypothesis_output_format"],
                hypothesis_specification=context_dict["hypothesis_specification"],
                function_lib_description=context_dict["function_lib_description"],
            )
        )
        user_prompt = (
            Environment(undefined=StrictUndefined)
            .from_string(qa_prompt_dict["hypothesis_gen"]["user_prompt"])
            .render(
                targets=self.targets,
                hypothesis_and_feedback=context_dict["hypothesis_and_feedback"],
                RAG=context_dict["RAG"],
                round=len(trace.hist),
            )
        )
        return system_prompt, user_prompt, json_flag

    def gen(self, trace: Trace) -> AlphaAgentHypothesis:
        """Generate hypothesis; supports dynamic history limit for input length."""
        history_limit = DEFAULT_HISTORY_LIMIT

        while history_limit >= MIN_HISTORY_LIMIT:
            try:
                system_prompt, user_prompt, json_flag = self.render_generation_prompts(trace, history_limit)

                resp = ""
                for attempt in range(3):
                    api = APIBackend() if attempt == 0 else APIBackend(use_chat_cache=False)
                    messages = api.build_messages(user_prompt, system_prompt)
                    resp_dict = call_structured(
                        api,
                        messages,
                        tools=[PROPOSE_FACTORS_TOOL],
                        tool_choice="required",
                        json_mode=json_flag,
                        task_type="hypothesis_generation",
                    )
                    resp = json.dumps(resp_dict) if resp_dict else ""
                    if resp and resp.strip():
                        break
                    logger.warning(f"Empty hypothesis response, retrying... attempt={attempt + 1}")
                hypothesis = self.convert_response(resp)
                return hypothesis

            except Exception as e:
                if is_input_length_error(str(e)) and history_limit > MIN_HISTORY_LIMIT:
                    history_limit -= 1
                    logger.warning(f"Input length exceeded, retrying with history_limit={history_limit}...")
                else:
                    logger.warning(f"Hypothesis generation failed, falling back to deterministic hypothesis: {e}")
                    return self._build_fallback_hypothesis()

        # Last attempt with minimum history limit
        system_prompt, user_prompt, json_flag = self.render_generation_prompts(trace, MIN_HISTORY_LIMIT)
        api = APIBackend()
        messages = api.build_messages(user_prompt, system_prompt)
        resp_dict = call_structured(
            api,
            messages,
            tools=[PROPOSE_FACTORS_TOOL],
            tool_choice="required",
            json_mode=json_flag,
            task_type="hypothesis_generation",
        )
        resp = json.dumps(resp_dict) if resp_dict else ""
        try:
            hypothesis = self.convert_response(resp)
            return hypothesis
        except Exception as e:
            logger.warning(f"Final hypothesis generation attempt failed, using fallback hypothesis: {e}")
            return self._build_fallback_hypothesis()


class EmptyHypothesisGen(FactorHypothesisGen):
    def __init__(self, scen: Scenario) -> Tuple[dict, bool]:
        super().__init__(scen)

    def convert_response(self, *args, **kwargs) -> AlphaAgentHypothesis:
        return super().convert_response(*args, **kwargs)

    def prepare_context(self, *args, **kwargs) -> Tuple[dict | bool]:
        return super().prepare_context(*args, **kwargs)

    def gen(self, trace: Trace) -> AlphaAgentHypothesis:

        hypothesis = AlphaAgentHypothesis(hypothesis="", concise_observation="", concise_justification="", concise_knowledge="", concise_specification="")

        return hypothesis


class AlphaAgentHypothesis2FactorExpression(FactorHypothesis2Experiment):
    def __init__(
        self,
        *args,
        consistency_enabled: bool = False,
        consistency_strict_mode: bool = False,
        max_correction_attempts: int = 3,
        complexity_enabled: bool = True,
        redundancy_enabled: bool = True,
        data_quality_enabled: bool = True,
        allowed_inconsistent_severities: tuple[str, ...] = ("none", "minor"),
        data_capabilities: dict | None = None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        # Initialize FactorRegulator with config settings
        from quantaalpha.factors.coder.config import FACTOR_COSTEER_SETTINGS

        self.factor_regulator = FactorRegulator(factor_zoo_path=FACTOR_COSTEER_SETTINGS.factor_zoo_path, duplication_threshold=FACTOR_COSTEER_SETTINGS.duplication_threshold)

        # Initialize consistency checker if enabled
        self.consistency_enabled = consistency_enabled
        self.consistency_strict_mode = consistency_strict_mode
        self.max_correction_attempts = max_correction_attempts
        self.complexity_enabled = complexity_enabled
        self.redundancy_enabled = redundancy_enabled
        self.data_quality_enabled = data_quality_enabled
        self.allowed_inconsistent_severities = allowed_inconsistent_severities
        self.data_capabilities = data_capabilities
        self._quality_gate = None

    @property
    def quality_gate(self):
        """Lazy-load FactorQualityGate."""
        if self._quality_gate is None and self.consistency_enabled:
            try:
                from quantaalpha.factors.regulator.consistency_checker import (
                    FactorConsistencyChecker,
                    FactorQualityGate,
                )

                self._quality_gate = FactorQualityGate(
                    consistency_checker=FactorConsistencyChecker(
                        enabled=self.consistency_enabled,
                        strict_mode=self.consistency_strict_mode,
                        max_correction_attempts=self.max_correction_attempts,
                        allowed_inconsistent_severities=self.allowed_inconsistent_severities,
                    ),
                    consistency_enabled=self.consistency_enabled,
                    complexity_enabled=self.complexity_enabled,
                    redundancy_enabled=self.redundancy_enabled,
                    data_quality_enabled=self.data_quality_enabled,
                )
            except ImportError as e:
                logger.warning(f"Could not load consistency checker: {e}")
                self._quality_gate = None
        return self._quality_gate

    def _allowed_expression_fields(self, trace: Trace) -> set[str]:
        capabilities = self.data_capabilities
        if capabilities is None:
            capabilities = getattr(trace.scen, "data_capabilities", None)
        registry = get_data_capabilities(capabilities)
        allowed_fields: set[str] = {"$return"}
        for spec in registry.values():
            allowed_fields.update(str(field) for field in spec.get("fields", []))
        return allowed_fields

    def _extract_expression_variables(self, expression: str) -> set[str]:
        from quantaalpha.factors.coder.factor_ast import collect_unique_vars, parse_expression

        tree = parse_expression(expression)
        variables: set[str] = set()
        collect_unique_vars(tree, variables)
        return variables

    def _validate_expression_capabilities(self, expression: str, trace: Trace) -> tuple[bool, str]:
        referenced = self._extract_expression_variables(expression)
        allowed_fields = self._allowed_expression_fields(trace)
        unknown_fields = sorted(field for field in referenced if field not in allowed_fields)
        if not unknown_fields:
            return True, ""
        allowed_preview = ", ".join(sorted(allowed_fields))
        return (
            False,
            "Unsupported fields in expression: " + ", ".join(unknown_fields) + f". Allowed fields: {allowed_preview}",
        )

    def prepare_context(self, hypothesis: Hypothesis, trace: Trace, history_limit: int = DEFAULT_HISTORY_LIMIT) -> Tuple[dict | bool]:
        scenario = trace.scen.get_scenario_all_desc()
        experiment_output_format = qa_prompt_dict["factor_experiment_output_format"]
        function_lib_description = qa_prompt_dict["function_lib_description"]
        hypothesis_and_feedback = render_hypothesis_and_feedback(qa_prompt_dict, trace, history_limit)

        experiment_list: List[FactorExperiment] = [t[1] for t in trace.hist]

        factor_list = []
        for experiment in experiment_list:
            factor_list.extend(experiment.sub_tasks)

        return {
            "target_hypothesis": str(hypothesis),
            "scenario": scenario,
            "hypothesis_and_feedback": hypothesis_and_feedback,
            "function_lib_description": function_lib_description,
            "financial_pit_context_hint": build_financial_pit_context_hint(getattr(trace.scen, "data_capabilities", None)),
            "experiment_output_format": experiment_output_format,
            "target_list": factor_list,
            "RAG": None,
        }, True

    def convert_response(self, response: str, trace: Trace) -> Experiment:
        """Convert LLM response string to FactorExperiment.

        This satisfies the abstract method contract from LLMHypothesis2Experiment.
        It parses the tool-call/JSON response and builds the experiment via
        _build_experiment_from_dict after validation.
        """
        # The response is already parsed by call_structured inside _convert_with_history_limit.
        # When convert_response is called directly (e.g. by parent's convert()),
        # we need to replicate that flow. For backward compatibility with the
        # overridden convert() path, this method parses response_dict from the
        # LLM string and builds the experiment.
        response_dict = robust_json_parse(response)
        if not isinstance(response_dict, dict):
            raise ValueError(f"Expected dict from LLM response, got {type(response_dict).__name__}")
        return self._build_experiment_from_dict(response_dict, trace)

    def _unwrap_construct_response(self, response_dict: dict[str, object]) -> dict[str, dict]:
        """Normalize construct responses to a factor-name keyed mapping."""
        factors_dict = response_dict.get("factors", response_dict)
        if not isinstance(factors_dict, dict):
            return {}
        return {str(name): payload for name, payload in factors_dict.items() if isinstance(payload, dict)}

    def convert(self, hypothesis: Hypothesis, trace: Trace) -> Experiment:
        """Convert hypothesis to factor expressions; supports dynamic history limit."""
        history_limit = DEFAULT_HISTORY_LIMIT

        while history_limit >= MIN_HISTORY_LIMIT:
            try:
                return self._convert_with_history_limit(hypothesis, trace, history_limit)
            except Exception as e:
                if is_input_length_error(str(e)) and history_limit > MIN_HISTORY_LIMIT:
                    history_limit -= 1
                    logger.warning(f"Input length exceeded, retrying with history_limit={history_limit}...")
                else:
                    raise

        # Last attempt with minimum history limit
        return self._convert_with_history_limit(hypothesis, trace, MIN_HISTORY_LIMIT)

    def _convert_with_history_limit(self, hypothesis: Hypothesis, trace: Trace, history_limit: int) -> Experiment:
        """Convert with given history limit."""
        context, json_flag = self.prepare_context(hypothesis, trace, history_limit)
        system_prompt = (
            Environment(undefined=StrictUndefined)
            .from_string(qa_prompt_dict["hypothesis2experiment"]["system_prompt"])
            .render(
                targets=self.targets,
                scenario=trace.scen.background,  # get_scenario_all_desc(filtered_tag="hypothesis_and_experiment"),
                experiment_output_format=context["experiment_output_format"],
            )
        )
        user_prompt = (
            Environment(undefined=StrictUndefined)
            .from_string(qa_prompt_dict["hypothesis2experiment"]["user_prompt"])
            .render(targets=self.targets, target_hypothesis=context["target_hypothesis"], hypothesis_and_feedback=context["hypothesis_and_feedback"], function_lib_description=context["function_lib_description"], target_list=context["target_list"], RAG=context["RAG"], expression_duplication=None)
        )

        # Detect duplicated sub-expressions
        flag = False
        expression_duplication_prompt = None
        MAX_RETRIES = 10
        api = APIBackend()
        final_response_dict = None
        for attempt in range(MAX_RETRIES):
            if flag:
                break

            messages = api.build_messages(user_prompt, system_prompt)
            response_dict = call_structured(
                api,
                messages,
                tools=[CONSTRUCT_FACTORS_TOOL],
                tool_choice="required",
                json_mode=json_flag,
                task_type="factor_construction",
                allow_text_fallback=True,
            )

            # Check for empty response before JSON parsing
            if not response_dict:
                logger.warning(f"Empty LLM response at attempt {attempt + 1}/{MAX_RETRIES}, retrying...")
                continue
            final_response_dict = response_dict
            proposed_names = []
            proposed_exprs = []

            factors_dict = self._unwrap_construct_response(response_dict)

            for i, factor_name in enumerate(factors_dict):
                factor_data = factors_dict.get(factor_name, {})
                if not isinstance(factor_data, dict):
                    continue
                expr = factor_data.get("expression", "")
                description = factor_data.get("description", "")
                formulation = factor_data.get("formulation", "")
                variables = factor_data.get("variables", {})

                # Check if expression is parsable
                if not self.factor_regulator.is_parsable(expr):
                    logger.info(f"Failed to parse expr: {expr}, retrying...")
                    break

                capability_valid, capability_feedback = self._validate_expression_capabilities(expr, trace)
                if not capability_valid:
                    logger.warning(f"{factor_name}: {capability_feedback}")
                    if expression_duplication_prompt is not None:
                        expression_duplication_prompt = "\n\n".join([expression_duplication_prompt, capability_feedback])
                    else:
                        expression_duplication_prompt = capability_feedback
                    user_prompt = (
                        Environment(undefined=StrictUndefined)
                        .from_string(qa_prompt_dict["hypothesis2experiment"]["user_prompt"])
                        .render(
                            targets=self.targets,
                            target_hypothesis=context["target_hypothesis"],
                            hypothesis_and_feedback=context["hypothesis_and_feedback"],
                            function_lib_description=context["function_lib_description"],
                            target_list=context["target_list"],
                            RAG=context["RAG"],
                            expression_duplication=expression_duplication_prompt,
                        )
                    )
                    break

                success, eval_dict = self.factor_regulator.evaluate(expr)
                if not success:
                    break

                # Consistency check (if enabled)
                if self.consistency_enabled and self.quality_gate is not None:
                    try:
                        passed, feedback, results = self.quality_gate.evaluate(hypothesis=str(hypothesis), factor_name=factor_name, factor_description=description, factor_formulation=formulation, factor_expression=expr, variables=variables)

                        # Use corrected expression from consistency check if provided
                        if results.get("corrected_expression") and results["corrected_expression"] != expr:
                            logger.info(f"Consistency check corrected expression: {expr} -> {results['corrected_expression']}")
                            original_expr = expr
                            corrected_expr = normalize_corrected_expression(results["corrected_expression"])

                            # Re-check corrected expression
                            if not self.factor_regulator.is_parsable(corrected_expr):
                                logger.warning(f"Corrected expression could not be parsed, keeping original: {corrected_expr}")
                                expr = original_expr
                            else:
                                success, corrected_eval_dict = self.factor_regulator.evaluate(corrected_expr)
                                if success:
                                    expr = corrected_expr
                                    eval_dict = corrected_eval_dict
                                    factor_data["expression"] = expr
                                    factors_dict[factor_name] = factor_data
                                    if isinstance(response_dict.get("factors"), dict):
                                        response_dict["factors"][factor_name] = factor_data
                                    else:
                                        response_dict[factor_name] = factor_data
                                else:
                                    logger.warning(f"Corrected expression evaluation failed, keeping original: {corrected_expr}")
                                    expr = original_expr

                        if not passed:
                            logger.warning(f"Consistency check failed: {factor_name}, feedback: {feedback}")
                    except Exception as e:
                        logger.warning(f"Consistency check error: {e}")

                # If expression has problems, regenerate with feedback
                if not self.factor_regulator.is_expression_acceptable(eval_dict):
                    # Calculate ratios for feedback
                    num_all_nodes = eval_dict["num_all_nodes"]
                    free_args_ratio = float(eval_dict["num_free_args"]) / float(num_all_nodes) if num_all_nodes > 0 else 0.0
                    unique_vars_ratio = float(eval_dict["num_unique_vars"]) / float(num_all_nodes) if num_all_nodes > 0 else 0.0

                    # Get symbol length and base features count for complexity feedback
                    symbol_length = eval_dict.get("symbol_length", 0)
                    num_base_features = eval_dict.get("num_base_features", 0)
                    symbol_length_threshold = self.factor_regulator.symbol_length_threshold
                    base_features_threshold = self.factor_regulator.base_features_threshold

                    feedback_item = (
                        Environment(undefined=StrictUndefined)
                        .from_string(qa_prompt_dict["expression_duplication"])
                        .render(
                            prev_expression=expr,
                            duplicated_subtree_size=eval_dict["duplicated_subtree_size"],
                            duplication_threshold=self.factor_regulator.duplication_threshold,
                            duplicated_subtree=eval_dict.get("duplicated_subtree", ""),
                            matched_alpha=eval_dict.get("matched_alpha", ""),
                            free_args_ratio=free_args_ratio,
                            num_free_args=eval_dict["num_free_args"],
                            unique_vars_ratio=unique_vars_ratio,
                            num_unique_vars=eval_dict["num_unique_vars"],
                            num_all_nodes=num_all_nodes,
                            symbol_length=symbol_length,
                            symbol_length_threshold=symbol_length_threshold,
                            num_base_features=num_base_features,
                            base_features_threshold=base_features_threshold,
                        )
                    )

                    if expression_duplication_prompt is not None:
                        expression_duplication_prompt = "\n\n".join([expression_duplication_prompt, feedback_item])
                    else:
                        expression_duplication_prompt = feedback_item

                    user_prompt = (
                        Environment(undefined=StrictUndefined)
                        .from_string(qa_prompt_dict["hypothesis2experiment"]["user_prompt"])
                        .render(
                            targets=self.targets,
                            target_hypothesis=context["target_hypothesis"],
                            hypothesis_and_feedback=context["hypothesis_and_feedback"],
                            function_lib_description=context["function_lib_description"],
                            target_list=context["target_list"],
                            RAG=context["RAG"],
                            expression_duplication=expression_duplication_prompt,
                        )
                    )
                    break
                else:
                    proposed_names.append(factor_name)
                    proposed_exprs.append(expr)
                    if i == len(factors_dict) - 1:
                        flag = True
                    else:
                        continue
        else:
            # Loop completed without break (all retries exhausted)
            raise RuntimeError(f"Factor proposal failed after {MAX_RETRIES} retries: persistent empty or invalid LLM response")

        # Add valid factors to the factor regulator
        self.factor_regulator.add_factor(proposed_names, proposed_exprs)

        return self._build_experiment_from_dict(final_response_dict, trace)

    def _build_experiment_from_dict(self, response_dict: dict, trace: Trace) -> FactorExperiment:
        """Build a FactorExperiment from a parsed LLM response dict.

        Handles two possible input shapes:
        1. Tool-call shape: {"factors": {"factor_A": {...}, "factor_B": {...}}}
        2. Direct shape: {"factor_A": {...}, "factor_B": {...}}
        """
        factors_dict = self._unwrap_construct_response(response_dict)

        tasks = []

        for factor_name in factors_dict:
            factor_data = factors_dict.get(factor_name, {})
            if not isinstance(factor_data, dict):
                continue
            description = factor_data.get("description", "")
            formulation = factor_data.get("formulation", "")
            expression = factor_data.get("expression", "")
            variables = factor_data.get("variables", {})
            tasks.append(
                FactorTask(
                    factor_name=factor_name,
                    factor_description=description,
                    factor_formulation=formulation,
                    factor_expression=expression,
                    variables=variables,
                )
            )

        exp = QlibFactorExperiment(tasks)
        exp.based_experiments = [QlibFactorExperiment(sub_tasks=[])] + [t[1] for t in trace.hist if t[2]]

        unique_tasks = []

        for task in tasks:
            duplicate = False
            for based_exp in exp.based_experiments:
                for sub_task in based_exp.sub_tasks:
                    if task.factor_name == sub_task.factor_name:
                        duplicate = True
                        break
                if duplicate:
                    break
            if not duplicate:
                unique_tasks.append(task)

        exp.tasks = unique_tasks
        return exp


class BacktestHypothesis2FactorExpression(FactorHypothesis2Experiment):
    def __init__(self, factor_path, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.factor_path = factor_path

    def convert_response(self, *args, **kwargs) -> FactorExperiment:
        return super().convert_response(*args, **kwargs)

    def prepare_context(self, *args, **kwargs) -> Tuple[dict | bool]:
        return super().prepare_context(*args, **kwargs)

    def convert(self, hypothesis: Hypothesis, trace: Trace) -> FactorExperiment:
        if os.path.exists(self.factor_path):
            tasks = []
            factor_df = pd.read_csv(self.factor_path, usecols=["factor_name", "factor_expression"], index_col=None)
            for index, row in factor_df.iterrows():
                tasks.append(
                    FactorTask(
                        factor_name=row["factor_name"],
                        factor_description="",
                        factor_formulation="",
                        factor_expression=row["factor_expression"],
                        variables="",
                    )
                )

            exp = QlibFactorExperiment(tasks)
            exp.based_experiments = [QlibFactorExperiment(sub_tasks=[])] + [t[1] for t in trace.hist if t[2]]

            unique_tasks = []

            for task in tasks:
                duplicate = False
                for based_exp in exp.based_experiments:
                    for sub_task in based_exp.sub_tasks:
                        if task.factor_name == sub_task.factor_name:
                            duplicate = True
                            break
                    if duplicate:
                        break
                if not duplicate:
                    unique_tasks.append(task)

            exp.tasks = unique_tasks
            return exp

        else:
            raise ValueError(f"File {self.factor_csv_path} does not exist. ")
