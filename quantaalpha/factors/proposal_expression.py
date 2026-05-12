from __future__ import annotations

from .proposal_generation import *
from .proposal_generation import _bound_feedback_accumulation


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
        max_construct_retries: int = 2,
        max_multi_construct_retries: int = 2,
        fallback_on_multi_construct_failure: bool = True,
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
        self.max_construct_retries = max(1, int(max_construct_retries))
        self.max_multi_construct_retries = max(1, int(max_multi_construct_retries))
        self.fallback_on_multi_construct_failure = fallback_on_multi_construct_failure
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

    def _new_factor_experiment(self, tasks: list[FactorTask] | None = None) -> QlibFactorExperiment:
        tasks = tasks or []
        try:
            exp = QlibFactorExperiment(tasks)
        except TypeError:
            try:
                exp = QlibFactorExperiment(sub_tasks=tasks)
            except TypeError:
                exp = QlibFactorExperiment()
                exp.sub_tasks = tasks
        exp.tasks = tasks
        if not hasattr(exp, "sub_tasks"):
            exp.sub_tasks = tasks
        return exp

    def _primary_hypothesis_from_bundle(self, bundle: EnsembleHypothesisBundle) -> AlphaAgentHypothesis:
        primary_payload = bundle.primary_hypothesis.get("hypothesis", {})
        if not isinstance(primary_payload, dict):
            primary_payload = {}
        return AlphaAgentHypothesis(
            hypothesis=primary_payload.get("hypothesis", bundle.hypothesis),
            concise_observation=primary_payload.get("concise_observation", bundle.concise_observation),
            concise_knowledge=primary_payload.get("concise_knowledge", bundle.concise_knowledge),
            concise_justification=primary_payload.get("concise_justification", bundle.concise_justification),
            concise_specification=primary_payload.get("concise_specification", bundle.concise_specification),
        )

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

    def _build_multi_hypothesis_target(self, bundle: EnsembleHypothesisBundle) -> str:
        """Render a compact construct prompt from the collected ensemble hypotheses."""
        sections: list[str] = []
        for idx, item in enumerate(bundle.hypotheses, start=1):
            payload = item.get("hypothesis", {})
            if isinstance(payload, str):
                try:
                    payload = robust_json_parse(payload)
                except Exception:
                    payload = {"hypothesis": payload}
            if not isinstance(payload, dict):
                payload = {"hypothesis": str(payload)}

            sections.append(
                "\n".join(
                    [
                        f"Model {idx}: {item.get('model', 'unknown')}",
                        f"Hypothesis: {payload.get('hypothesis', '')}",
                        f"Observation: {payload.get('concise_observation', '')}",
                        f"Justification: {payload.get('concise_justification', '')}",
                        f"Knowledge: {payload.get('concise_knowledge', '')}",
                        f"Specification: {payload.get('concise_specification', '')}",
                    ]
                )
            )

        return "You received multiple candidate hypotheses from an ensemble. Adopt the strongest ideas, reject weak ones, and output final factor expressions.\n\n" + "\n\n".join(sections)

    def _format_construct_provider_label(self, api: APIBackend) -> str:
        provider = getattr(api, "provider_name", None) or getattr(api, "provider", None) or "unknown_provider"
        model = getattr(api, "chat_model", None) or getattr(api, "model", None) or "unknown_model"
        return f"provider={provider}, model={model}"

    def _format_multi_construct_feedback(
        self,
        category: str,
        factor_name: str | None = None,
        detail: str | None = None,
        expression: str | None = None,
    ) -> str:
        lines = [
            "Multi-Hypothesis Construct Validation Failed:",
            f"- Failure category: {category}",
        ]
        if factor_name:
            lines.append(f"- Factor name: {factor_name}")
        if detail:
            lines.append(f"- Detail: {detail}")
        if expression:
            lines.append(f"- Expression preview: {expression[:500]}")
        lines.extend(
            [
                "- Action required: regenerate only valid factor payloads.",
                "- Each factor must include description, formulation, expression, and variables.",
                "- Keep expressions parsable and simple, preferably 50-150 characters.",
                "- Use only supported input fields and DSL function signatures.",
            ]
        )
        return "\n".join(lines)

    def _validate_multi_construct_factor(
        self,
        factor_name: str,
        factor_data: dict,
        trace: Trace,
    ) -> tuple[bool, str, str, str]:
        expr = factor_data.get("expression", "")
        if not expr:
            return False, "missing_expression", "factor payload has no expression", ""

        parsable, parse_error = self.factor_regulator.parse_diagnostic(expr)
        if not parsable:
            return False, "unparsable_expression", str(parse_error or "unknown parse error"), expr

        capability_valid, capability_feedback = self._validate_expression_capabilities(expr, trace)
        if not capability_valid:
            return False, "capability_validation_failure", capability_feedback, expr

        success, eval_dict = self.factor_regulator.evaluate(expr)
        if not success:
            return False, "evaluation_failure", "factor regulator evaluate() returned failure", expr

        if not self.factor_regulator.is_expression_acceptable(eval_dict):
            symbol_length = eval_dict.get("symbol_length", 0)
            return False, "acceptability_failure", f"symbol_length={symbol_length}", expr

        return True, "", "", expr

    def convert_multi_hypothesis(self, bundle: EnsembleHypothesisBundle, trace: Trace) -> Experiment:
        """Convert an ensemble bundle into factor expressions via call_structured.

        This method now includes:
        - Retry loop for empty/invalid responses.
        - Caller-level validation feedback injected into retries.
        - Partial acceptance of valid factors from mixed-validity responses.
        - Classified terminal failures for runtime diagnosis.
        """
        if not bundle.hypotheses:
            logger.warning("Multi-hypothesis bundle has no hypotheses, falling back to bundle as single hypothesis")
            return self.convert(bundle, trace)

        history_limit = DEFAULT_HISTORY_LIMIT
        max_multi_retries = getattr(self, "max_multi_construct_retries", 2)
        construct_feedback = None
        last_failure_category = "unknown"
        last_failure_factor = None
        last_failure_detail = "no attempts completed"
        last_failure_expression = None
        last_provider_label = "provider=unknown_provider, model=unknown_model"

        while history_limit >= MIN_HISTORY_LIMIT:
            retry_with_reduced_history = False
            for attempt in range(max_multi_retries):
                try:
                    context, json_flag = self.prepare_context(bundle, trace, history_limit)
                    context["target_hypothesis"] = self._build_multi_hypothesis_target(bundle)

                    system_prompt = (
                        Environment(undefined=StrictUndefined)
                        .from_string(qa_prompt_dict["hypothesis2experiment"]["system_prompt"])
                        .render(
                            targets=self.targets,
                            scenario=trace.scen.background,
                            experiment_output_format=context["experiment_output_format"],
                        )
                    )
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
                            expression_duplication=construct_feedback,
                        )
                    )

                    api = APIBackend(max_retry_override=1)
                    last_provider_label = self._format_construct_provider_label(api)
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
                    if not response_dict:
                        last_failure_category = "empty_response"
                        last_failure_factor = None
                        last_failure_detail = "structured call returned an empty response"
                        last_failure_expression = None
                        construct_feedback = _bound_feedback_accumulation(
                            construct_feedback,
                            self._format_multi_construct_feedback(last_failure_category, detail=last_failure_detail),
                        )
                        logger.warning(f"[multi-hypothesis attempt {attempt + 1}/{max_multi_retries}] Empty multi-hypothesis construct response, retrying...")
                        continue

                    # Validate that factors_dict is not empty before building experiment
                    factors_dict = self._unwrap_construct_response(response_dict)
                    if not factors_dict:
                        last_failure_category = "empty_factors"
                        last_failure_factor = None
                        last_failure_detail = "response contained no factor payloads"
                        last_failure_expression = None
                        construct_feedback = _bound_feedback_accumulation(
                            construct_feedback,
                            self._format_multi_construct_feedback(last_failure_category, detail=last_failure_detail),
                        )
                        logger.warning(f"[multi-hypothesis attempt {attempt + 1}/{max_multi_retries}] Multi-hypothesis response yielded empty factors_dict, retrying...")
                        continue

                    valid_factors: dict[str, dict] = {}
                    for factor_name, factor_data in factors_dict.items():
                        if not isinstance(factor_data, dict):
                            last_failure_category = "invalid_payload"
                            last_failure_factor = factor_name
                            last_failure_detail = f"factor payload type is {type(factor_data).__name__}"
                            last_failure_expression = None
                            construct_feedback = _bound_feedback_accumulation(
                                construct_feedback,
                                self._format_multi_construct_feedback(
                                    last_failure_category,
                                    factor_name=factor_name,
                                    detail=last_failure_detail,
                                ),
                            )
                            continue

                        valid, category, detail, expr = self._validate_multi_construct_factor(factor_name, factor_data, trace)
                        if valid:
                            valid_factors[factor_name] = factor_data
                            continue

                        last_failure_category = category
                        last_failure_factor = factor_name
                        last_failure_detail = detail
                        last_failure_expression = expr
                        construct_feedback = _bound_feedback_accumulation(
                            construct_feedback,
                            self._format_multi_construct_feedback(
                                category,
                                factor_name=factor_name,
                                detail=detail,
                                expression=expr,
                            ),
                        )
                        logger.warning(
                            f"[multi-hypothesis attempt {attempt + 1}/{max_multi_retries}] "
                            f"Factor {factor_name} rejected: category={category}, detail={detail[:200]}"
                        )

                    if not valid_factors:
                        continue

                    filtered_response = {"factors": valid_factors}
                    experiment = self._build_experiment_from_dict(filtered_response, trace)
                    if not getattr(experiment, "tasks", None):
                        last_failure_category = "duplicate_or_empty_after_filter"
                        last_failure_factor = None
                        last_failure_detail = "valid factor payloads produced no new experiment tasks after duplicate filtering"
                        last_failure_expression = None
                        construct_feedback = _bound_feedback_accumulation(
                            construct_feedback,
                            self._format_multi_construct_feedback(last_failure_category, detail=last_failure_detail),
                        )
                        logger.warning(
                            f"[multi-hypothesis attempt {attempt + 1}/{max_multi_retries}] "
                            "Valid multi-hypothesis factors produced no new tasks, retrying..."
                        )
                        continue

                    self.factor_regulator.add_factor(
                        list(valid_factors.keys()),
                        [str(factor_data.get("expression", "")) for factor_data in valid_factors.values()],
                    )
                    return experiment

                except Exception as e:
                    if is_input_length_error(str(e)) and history_limit > MIN_HISTORY_LIMIT:
                        history_limit -= 1
                        retry_with_reduced_history = True
                        logger.warning(f"Multi-hypothesis input length exceeded, retrying with history_limit={history_limit}...")
                        break  # Break inner for loop, continue outer while loop
                    last_failure_category = "exception"
                    last_failure_factor = None
                    last_failure_detail = str(e)
                    last_failure_expression = None
                    construct_feedback = _bound_feedback_accumulation(
                        construct_feedback,
                        self._format_multi_construct_feedback(last_failure_category, detail=last_failure_detail),
                    )
                    logger.warning(f"[multi-hypothesis attempt {attempt + 1}/{max_multi_retries}] Multi-hypothesis construct failed: {e}")
                    # Continue retry loop
                    continue

            if retry_with_reduced_history:
                continue

            reason = (
                f"Multi-hypothesis construct failed after {max_multi_retries} attempts: "
                f"category={last_failure_category}, "
                f"factor={last_failure_factor or 'n/a'}, "
                f"detail={last_failure_detail}, "
                f"{last_provider_label}"
            )
            if last_failure_expression:
                reason += f", expression_preview={last_failure_expression[:200]}"
            logger.warning(reason)
            if getattr(self, "fallback_on_multi_construct_failure", True):
                logger.warning(f"{reason}; falling back to primary hypothesis single-factor construction")
                return self.convert(self._primary_hypothesis_from_bundle(bundle), trace)
            raise RuntimeError(reason)

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
        MAX_RETRIES = getattr(self, "max_construct_retries", 2)
        api = APIBackend(max_retry_override=1)
        final_response_dict = None
        last_failure_reason = None
        best_partial_response_dict = None
        best_partial_names = []
        best_partial_exprs = []

        # Track symbol_length for early stopping on non-improving acceptability failures
        recent_symbol_lengths: list[int] = []

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
                last_failure_reason = "empty response"
                logger.warning(f"[retry attempt {attempt + 1}/{MAX_RETRIES}] {last_failure_reason}, retrying...")
                # Inject feedback to guide the LLM away from empty responses
                empty_feedback = "Empty Response Warning:\n- Previous call returned an empty response.\n- Please generate at least one valid factor expression.\n- Keep expressions simple, target 50-150 characters.\n- Use only single-argument cross-sectional functions like MEAN(A).\n"
                if expression_duplication_prompt is not None:
                    expression_duplication_prompt = _bound_feedback_accumulation(expression_duplication_prompt, empty_feedback)
                else:
                    expression_duplication_prompt = empty_feedback
                # Re-render user prompt with the injected feedback
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
                parsable, parse_error = self.factor_regulator.parse_diagnostic(expr)
                if not parsable:
                    feedback_item = (
                        "Expression Syntax Check Failed:\n"
                        f"- Factor name: {factor_name}\n"
                        f"- Parser error: {parse_error or 'unknown parse error'}\n"
                        f"- Expression preview: {expr[:500]}\n"
                        "- Action required: regenerate this factor expression from scratch.\n"
                        "- Ensure every opening parenthesis has exactly one matching closing parenthesis.\n"
                        "- Keep the replacement expression simple, preferably 50-150 characters.\n"
                        "- Do not use square-bracket list literals such as [A,B]; combine expressions with +, -, *, /, MEAN(A), or TS_MEAN(A,N).\n"
                        "- Do not return the same expression again.\n"
                    )
                    last_failure_reason = f"unparsable expression for {factor_name}: {expr[:500]}"
                    logger.warning(f"[retry attempt {attempt + 1}/{MAX_RETRIES}] {last_failure_reason}; parse_error={parse_error}")
                    if proposed_names:
                        best_partial_response_dict = self._filter_construct_response_to_names(response_dict, proposed_names)
                        best_partial_names = list(proposed_names)
                        best_partial_exprs = list(proposed_exprs)
                    if expression_duplication_prompt is not None:
                        expression_duplication_prompt = _bound_feedback_accumulation(expression_duplication_prompt, feedback_item)
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

                capability_valid, capability_feedback = self._validate_expression_capabilities(expr, trace)
                if not capability_valid:
                    last_failure_reason = f"capability validation failure for {factor_name}: {capability_feedback[:240]}"
                    logger.warning(f"[retry attempt {attempt + 1}/{MAX_RETRIES}] {last_failure_reason}")
                    if proposed_names:
                        best_partial_response_dict = self._filter_construct_response_to_names(response_dict, proposed_names)
                        best_partial_names = list(proposed_names)
                        best_partial_exprs = list(proposed_exprs)
                    if expression_duplication_prompt is not None:
                        expression_duplication_prompt = _bound_feedback_accumulation(expression_duplication_prompt, capability_feedback)
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
                    last_failure_reason = f"factor evaluation failure for {factor_name}: {expr[:500]}"
                    logger.warning(f"[retry attempt {attempt + 1}/{MAX_RETRIES}] {last_failure_reason}")
                    if proposed_names:
                        best_partial_response_dict = self._filter_construct_response_to_names(response_dict, proposed_names)
                        best_partial_names = list(proposed_names)
                        best_partial_exprs = list(proposed_exprs)
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

                    # Track symbol_length for early stopping
                    recent_symbol_lengths.append(symbol_length)

                    # Early stopping: if last 3 symbol_lengths show no net improvement, stop early
                    if len(recent_symbol_lengths) >= 3:
                        last_three = recent_symbol_lengths[-3:]
                        # No net improvement if the last value >= the first of the 3
                        # Correctly allows [500, 400, 300] (improving) while stopping on [20, 20, 20] or [300, 350, 400]
                        if last_three[-1] >= last_three[0]:
                            last_failure_reason = (
                                f"expression acceptability failure for {factor_name}: "
                                f"symbol_length={symbol_length} (recent sequence: {last_three}, non-improving), "
                                f"duplicated_subtree_size={eval_dict.get('duplicated_subtree_size')}, "
                                f"num_free_args={eval_dict.get('num_free_args')}, "
                                f"num_unique_vars={eval_dict.get('num_unique_vars')}, "
                                f"num_all_nodes={num_all_nodes}, "
                                f"num_base_features={num_base_features}"
                            )
                            logger.warning(f"[early stop after attempt {attempt + 1}/{MAX_RETRIES}] {last_failure_reason}")
                            raise RuntimeError(f"Factor proposal early-stopped after {attempt + 1} retries: {last_failure_reason}. last failure reason: {last_failure_reason}. symbol_length not improving: {last_three}")

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

                    last_failure_reason = (
                        f"expression acceptability failure for {factor_name}: "
                        f"symbol_length={symbol_length}, "
                        f"duplicated_subtree_size={eval_dict.get('duplicated_subtree_size')}, "
                        f"num_free_args={eval_dict.get('num_free_args')}, "
                        f"num_unique_vars={eval_dict.get('num_unique_vars')}, "
                        f"num_all_nodes={num_all_nodes}, "
                        f"num_base_features={num_base_features}"
                    )
                    logger.warning(f"[retry attempt {attempt + 1}/{MAX_RETRIES}] {last_failure_reason}")
                    if proposed_names:
                        best_partial_response_dict = self._filter_construct_response_to_names(response_dict, proposed_names)
                        best_partial_names = list(proposed_names)
                        best_partial_exprs = list(proposed_exprs)
                    if expression_duplication_prompt is not None:
                        expression_duplication_prompt = _bound_feedback_accumulation(expression_duplication_prompt, feedback_item)
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
            if best_partial_response_dict and best_partial_names:
                logger.warning(
                    f"Factor proposal exhausted retries but salvaged {len(best_partial_names)} valid factor(s); "
                    f"dropping invalid tail. last failure reason: {last_failure_reason or 'unknown failure'}"
                )
                final_response_dict = best_partial_response_dict
                proposed_names = best_partial_names
                proposed_exprs = best_partial_exprs
                flag = True
            else:
                reason_detail = last_failure_reason if last_failure_reason else "persistent empty or invalid LLM response"
                raise RuntimeError(f"Factor proposal failed after {MAX_RETRIES} retries: {reason_detail}. last failure reason: {reason_detail}")

        if not flag:
            reason_detail = last_failure_reason if last_failure_reason else "persistent empty or invalid LLM response"
            raise RuntimeError(f"Factor proposal failed after {MAX_RETRIES} retries: {reason_detail}. last failure reason: {reason_detail}")

        # Add valid factors to the factor regulator
        self.factor_regulator.add_factor(proposed_names, proposed_exprs)

        return self._build_experiment_from_dict(final_response_dict, trace)

    def _filter_construct_response_to_names(self, response_dict: dict, factor_names: list[str]) -> dict:
        """Return a construct response containing only already validated factors."""
        wanted = set(factor_names)
        if isinstance(response_dict.get("factors"), dict):
            return {"factors": {name: data for name, data in response_dict["factors"].items() if name in wanted}}
        return {name: data for name, data in response_dict.items() if name in wanted}

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

        exp = self._new_factor_experiment(tasks)
        exp.based_experiments = [self._new_factor_experiment([])] + [t[1] for t in trace.hist if t[2]]

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
