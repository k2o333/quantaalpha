"""
Model workflow with session control.
"""

import time
import hashlib
import json
import pandas as pd
from contextlib import contextmanager
from typing import Any, List

from quantaalpha.pipeline.settings import BaseFacSetting
from quantaalpha.core.developer import Developer
from quantaalpha.core.proposal import (
    Hypothesis2Experiment,
    HypothesisExperiment2Feedback,
    HypothesisGen,
    Trace,
)
from quantaalpha.core.scenario import Scenario
from quantaalpha.core.utils import import_class
from quantaalpha.log import logger
from quantaalpha.log.time import measure_time
from quantaalpha.utils.workflow import LoopBase, LoopMeta
from quantaalpha.core.exception import FactorEmptyError
from quantaalpha.factors.failure_tracker import FactorFailureTracker
from quantaalpha.factors.proposal import AlphaAgentHypothesis, PROPOSE_FACTORS_TOOL
from quantaalpha.llm.client import APIBackend, call_structured
import threading


import datetime
import pickle
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from tqdm.auto import tqdm

from quantaalpha.core.exception import CoderError
from quantaalpha.log import logger
from functools import wraps

# Decorator: check stop_event before invoking the function


def stop_event_check(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if STOP_EVENT is not None and STOP_EVENT.is_set():
            raise Exception("Operation stopped due to stop_event flag.")
        return func(self, *args, **kwargs)

    return wrapper


class AlphaAgentLoop(LoopBase, metaclass=LoopMeta):
    skip_loop_error = (FactorEmptyError,)

    @measure_time
    def __init__(
        self,
        PROP_SETTING: BaseFacSetting,
        potential_direction,
        stop_event: threading.Event,
        use_local: bool = True,
        strategy_suffix: str = "",
        evolution_phase: str = "original",
        trajectory_id: str = "",
        parent_trajectory_ids: list = None,
        direction_id: int = 0,
        round_idx: int = 0,
        quality_gate_config: dict = None,
        step_model_routing: dict | None = None,
        ensemble_config: dict | None = None,
        provider_pool_cfg: dict | None = None,
    ):
        with logger.tag("init"):
            self.use_local = use_local
            # Store initial direction for factor provenance
            self.potential_direction = potential_direction

            # Evolution-related attributes
            self.strategy_suffix = strategy_suffix
            self.evolution_phase = evolution_phase  # original / mutation / crossover
            self.trajectory_id = trajectory_id
            self.parent_trajectory_ids = parent_trajectory_ids or []
            self.direction_id = direction_id
            self.round_idx = round_idx  # 0=original, 1=mutation, 2=crossover, ...

            # Quality gate config
            self.quality_gate_config = quality_gate_config or {}

            # Step-level model routing
            self._step_model_routing = step_model_routing or {}

            # Build provider name → real model name mapping from provider_pool_cfg
            self._provider_name_to_model: dict[str, str] = {}
            if provider_pool_cfg:
                for p in provider_pool_cfg.get("providers", []):
                    name = p.get("name", "")
                    model = p.get("model", "")
                    if name and model:
                        self._provider_name_to_model[name] = model
                logger.info(f"Provider name→model mapping: {self._provider_name_to_model}")

            # Ensemble configuration
            self._ensemble_config = ensemble_config or {}

            # Failure tracking for debug rounds
            self._failure_tracker = FactorFailureTracker(max_debug_rounds=10)  # Default max rounds
            self._current_round_factors = []

            # For trajectory collection
            self._last_hypothesis = None
            self._last_experiment = None
            self._last_feedback = None
            logger.info(f"Initialized AlphaAgentLoop, backtest in {'local' if use_local else 'Docker'}")
            if potential_direction:
                logger.info(f"Initial direction: {potential_direction}")
            if evolution_phase != "original":
                logger.info(f"Evolution phase: {evolution_phase}, round: {round_idx}, trajectory_id: {trajectory_id}")

            consistency_enabled = self.quality_gate_config.get("consistency_enabled", False)
            complexity_enabled = self.quality_gate_config.get("complexity_enabled", True)
            redundancy_enabled = self.quality_gate_config.get("redundancy_enabled", True)
            logger.info(f"Quality gate: consistency={'on' if consistency_enabled else 'off'}, complexity={'on' if complexity_enabled else 'off'}, redundancy={'on' if redundancy_enabled else 'off'}")

            scen: Scenario = import_class(PROP_SETTING.scen)(use_local=use_local)
            logger.log_object(scen, tag="scenario")

            # If strategy suffix is set, append it to the direction
            effective_direction = potential_direction
            if strategy_suffix:
                effective_direction = (potential_direction or "") + "\n" + strategy_suffix

            self.hypothesis_generator: HypothesisGen = import_class(PROP_SETTING.hypothesis_gen)(scen, effective_direction)
            logger.log_object(self.hypothesis_generator, tag="hypothesis generator")

            # Pass consistency check config into factor constructor
            factor_constructor_kwargs = {
                "consistency_enabled": consistency_enabled,
                "complexity_enabled": complexity_enabled,
                "redundancy_enabled": redundancy_enabled,
            }
            for optional_key in (
                "consistency_strict_mode",
                "max_correction_attempts",
                "allowed_inconsistent_severities",
                "data_quality_enabled",
                "data_capabilities",
            ):
                if optional_key in self.quality_gate_config:
                    factor_constructor_kwargs[optional_key] = self.quality_gate_config[optional_key]

            self.factor_constructor: Hypothesis2Experiment = import_class(PROP_SETTING.hypothesis2experiment)(**factor_constructor_kwargs)
            logger.log_object(self.factor_constructor, tag="experiment generation")

            self.coder: Developer = import_class(PROP_SETTING.coder)(scen)
            logger.log_object(self.coder, tag="coder")

            self.runner: Developer = import_class(PROP_SETTING.runner)(scen)
            logger.log_object(self.runner, tag="runner")

            self.summarizer: HypothesisExperiment2Feedback = import_class(PROP_SETTING.summarizer)(scen)
            logger.log_object(self.summarizer, tag="summarizer")
            self.trace = Trace(scen=scen)

            global STOP_EVENT
            STOP_EVENT = stop_event
            super().__init__()

    def _get_model_for_step(self, step_name: str) -> str | None:
        """
        Get the real model name for a specific pipeline step.

        Looks up the provider alias in step_model_routing, then resolves it
        to a real model name via the provider_pool_cfg mapping.

        Args:
            step_name: Step name (e.g. "propose", "construct", "feedback")

        Returns:
            Real model name string (e.g. "mistral-large-2407"), or None.
        """
        if step_name not in self._step_model_routing:
            return None

        provider_alias = self._step_model_routing[step_name]
        if not isinstance(provider_alias, str):
            logger.warning(f"step_model_routing[{step_name}] is not a string: {provider_alias}")
            return None

        # Resolve provider alias → real model name
        real_model = self._provider_name_to_model.get(provider_alias)
        if real_model:
            logger.info(f"Step '{step_name}' routed to model '{real_model}' (via provider '{provider_alias}')")
            return real_model

        # If alias not in mapping, treat it as a raw model name
        logger.info(f"Step '{step_name}' using model '{provider_alias}' directly (no provider mapping found)")
        return provider_alias

    @contextmanager
    def _with_step_model(self, step_name: str):
        """
        Context manager: temporarily override LLM_SETTINGS for a step.

        Overrides BOTH chat_model and reasoning_model, because the framework's
        _create_chat_completion_inner_function defaults reasoning_flag=True
        and reads reasoning_model instead of chat_model in that case.
        """
        model = self._get_model_for_step(step_name)
        if model is None:
            yield
            return

        from quantaalpha.llm.config import LLM_SETTINGS

        original_chat = LLM_SETTINGS.chat_model
        original_reasoning = LLM_SETTINGS.reasoning_model
        LLM_SETTINGS.chat_model = model
        LLM_SETTINGS.reasoning_model = model
        logger.info(f"[model-routing] Step '{step_name}': chat_model='{model}', reasoning_model='{model}' (was: chat='{original_chat}', reasoning='{original_reasoning}')")
        try:
            yield
        finally:
            LLM_SETTINGS.chat_model = original_chat
            LLM_SETTINGS.reasoning_model = original_reasoning
            logger.info(f"[model-routing] Restored: chat_model='{original_chat}', reasoning_model='{original_reasoning}'")

    @classmethod
    def load(cls, path, use_local: bool = True):
        """Load existing session."""
        instance = super().load(path)
        instance.use_local = use_local
        logger.info(f"Loaded AlphaAgentLoop, backtest in {'local' if use_local else 'Docker'}")
        return instance

    @measure_time
    @stop_event_check
    def factor_propose(self, prev_out: dict[str, Any]):
        """Propose hypothesis as the basis for factor construction."""
        with logger.tag("r"):
            if self._ensemble_config.get("enabled"):
                idea = self._propose_with_ensemble()
            else:
                with self._with_step_model("propose"):
                    idea = self.hypothesis_generator.gen(self.trace)
            idea = self._normalize_hypothesis_output(idea)
            logger.log_object(idea, tag="hypothesis generation")
            self._last_hypothesis = idea
        return idea

    def _propose_with_ensemble(self):
        """
        Generate hypothesis using ensemble of models.

        Calls each model in the ensemble config separately and aggregates results.
        """
        from quantaalpha.llm.ensemble import EnsembleAggregator, ModelResponse

        models = self._ensemble_config.get("models", [])
        strategy = self._ensemble_config.get("strategy", "voting")

        aggregator = EnsembleAggregator(strategy=strategy)
        responses = []

        for model_cfg in models:
            model_name = model_cfg.get("name", "")
            if not model_name:
                continue

            try:
                # Resolve provider alias to real model name
                real_model = self._provider_name_to_model.get(model_name, model_name)
                backend = APIBackend(chat_model=real_model)
                start_time = time.time()
                system_prompt, user_prompt, json_flag = self.hypothesis_generator.render_generation_prompts(self.trace)
                messages = backend.build_messages(
                    user_prompt=user_prompt,
                    system_prompt=system_prompt,
                )
                output_dict = call_structured(
                    backend,
                    messages,
                    tools=[PROPOSE_FACTORS_TOOL],
                    tool_choice="required",
                    json_mode=json_flag,
                    allow_text_fallback=True,
                )
                output = json.dumps(output_dict) if output_dict else ""
                latency_ms = (time.time() - start_time) * 1000

                responses.append(
                    ModelResponse(
                        model_name=model_name,
                        raw_output=output,
                        latency_ms=latency_ms,
                    )
                )
            except Exception as e:
                logger.warning(f"Ensemble model {model_name} failed: {e}")

        if not responses:
            return self.hypothesis_generator.gen(self.trace)

        result = aggregator.aggregate(responses)
        raw_output = result.output[0] if result.output else None
        if raw_output is None:
            logger.warning("Ensemble produced no output, falling back to single-model generation")
            return self.hypothesis_generator.gen(self.trace)

        try:
            return self._normalize_hypothesis_output(raw_output)
        except Exception as e:
            logger.error(f"Failed to normalize ensemble output: {e}")
            logger.warning("Falling back to single-model hypothesis generation")
            return self.hypothesis_generator.gen(self.trace)

    def _normalize_hypothesis_output(self, idea: Any) -> AlphaAgentHypothesis:
        """Normalize propose outputs so all paths return AlphaAgentHypothesis."""
        if isinstance(idea, AlphaAgentHypothesis):
            return idea

        if isinstance(idea, str):
            return self.hypothesis_generator.convert_response(idea)
        if isinstance(idea, dict):
            return self.hypothesis_generator.convert_response(json.dumps(idea))

        logger.warning(f"Unexpected hypothesis output type: {type(idea)}")
        return self.hypothesis_generator.convert_response(str(idea))

    @measure_time
    @stop_event_check
    def factor_construct(self, prev_out: dict[str, Any]):
        """Construct multiple factors from the hypothesis."""
        with logger.tag("r"), self._with_step_model("construct"):
            factor = self.factor_constructor.convert(prev_out["factor_propose"], self.trace)
            logger.log_object(factor.sub_tasks, tag="experiment generation")

            # Register factors for failure tracking
            self._register_factors_from_experiment(factor)
        return factor

    @measure_time
    @stop_event_check
    def factor_calculate(self, prev_out: dict[str, Any]):
        """Compute factor values from factor expressions."""
        with logger.tag("d"):  # develop
            factor = self.coder.develop(prev_out["factor_construct"])
            logger.log_object(factor.sub_workspace_list, tag="coder result")

            # Track coder results for failure filtering
            self._track_coder_result(factor)
        return factor

    @measure_time
    @stop_event_check
    def factor_backtest(self, prev_out: dict[str, Any]):
        """Run backtest and feed results into failure tracking."""
        with logger.tag("ef"):  # evaluate and feedback
            exp = self.runner.develop(prev_out["factor_calculate"])
            if exp is None:
                logger.error("Factor extraction failed.")
                raise FactorEmptyError("Factor extraction failed.")
            logger.log_object(exp, tag="runner result")
            self._track_backtest_result(exp)
            self._last_experiment = exp
        return exp

    @measure_time
    @stop_event_check
    def feedback(self, prev_out: dict[str, Any]):
        with self._with_step_model("feedback"):
            feedback = self.summarizer.generate_feedback(prev_out["factor_backtest"], prev_out["factor_propose"], self.trace)
        with logger.tag("ef"):  # evaluate and feedback
            logger.log_object(feedback, tag="feedback")
        self.trace.hist.append((prev_out["factor_propose"], prev_out["factor_backtest"], feedback))

        self._last_feedback = feedback

        # Finalize debug round for failure tracking
        round_summary = self._finalize_debug_round()
        logger.info(f"Debug round {round_summary['round_idx']} completed: {round_summary['successful_count']}/{round_summary['total_factors']} successful")

        if round_summary["all_succeeded"]:
            logger.info("All factors succeeded - debug completed early")
        elif not self._should_continue_debug():
            logger.info("Maximum debug rounds reached or all factors failed")
        else:
            retry_factors = self._get_factors_for_retry()
            logger.info(f"Next round will retry {len(retry_factors)} failed factors")

        # Auto-save factors to unified factor library
        try:
            import os
            from pathlib import Path
            from quantaalpha.factors.library import FactorLibraryManager

            # Project root: loop.py -> pipeline/ -> quantaalpha/ -> project_root/
            project_root = Path(__file__).resolve().parent.parent.parent

            experiment_id = "unknown"
            if hasattr(self, "session_folder") and self.session_folder:
                parts = Path(self.session_folder).parts
                for part in parts:
                    if part.startswith("202") and len(part) > 10:
                        experiment_id = part
                        break

            round_number = self.round_idx

            hypothesis_text = None
            if prev_out.get("factor_propose"):
                hypothesis_text = str(prev_out["factor_propose"])

            planning_direction = getattr(self, "potential_direction", None)
            user_initial_direction = getattr(self, "user_initial_direction", None)

            evolution_phase = getattr(self, "evolution_phase", "original")
            trajectory_id = getattr(self, "trajectory_id", "")
            parent_trajectory_ids = getattr(self, "parent_trajectory_ids", [])

            # Factor library filename can be customized via env FACTOR_LIBRARY_SUFFIX
            library_suffix = os.environ.get("FACTOR_LIBRARY_SUFFIX", "")
            if library_suffix:
                library_filename = f"all_factors_library_{library_suffix}.json"
            else:
                library_filename = "all_factors_library.json"
            factorlib_dir = project_root / "data" / "factorlib"
            factorlib_dir.mkdir(parents=True, exist_ok=True)
            library_path = factorlib_dir / library_filename
            manager = FactorLibraryManager(str(library_path))
            manager.add_factors_from_experiment(
                experiment=prev_out["factor_backtest"],
                experiment_id=experiment_id,
                round_number=round_number,
                hypothesis=hypothesis_text,
                feedback=feedback,
                initial_direction=planning_direction,
                user_initial_direction=user_initial_direction,
                planning_direction=planning_direction,
                evolution_phase=evolution_phase,
                trajectory_id=trajectory_id,
                parent_trajectory_ids=parent_trajectory_ids,
            )
            logger.info(f"Saved factors to library: {library_path} (phase={evolution_phase})")
        except Exception as e:
            logger.warning(f"Failed to save factors to library: {e}")

    def _generate_factor_id(self, factor_name: str, factor_expression: str) -> str:
        """Generate a unique factor ID from name and expression."""
        return hashlib.md5(f"{factor_name}_{factor_expression}".encode()).hexdigest()[:16]

    def _register_factors_from_experiment(self, experiment) -> List[str]:
        """Register all factors from experiment for failure tracking."""
        if not getattr(self._failure_tracker, "_round_in_progress", False):
            self._failure_tracker.start_round()

        retry_ids = set(self._failure_tracker.get_factors_for_retry()) if self._failure_tracker.round_summaries else None
        original_tasks = list(getattr(experiment, "sub_tasks", []) or [])
        if retry_ids is not None:
            filtered_tasks = []
            for task in original_tasks:
                factor_id = self._generate_factor_id(task.factor_name, task.factor_expression)
                if factor_id in retry_ids:
                    filtered_tasks.append(task)
            experiment.sub_tasks = filtered_tasks
        else:
            filtered_tasks = original_tasks

        factor_ids = []
        for task in filtered_tasks:
            factor_id = self._generate_factor_id(task.factor_name, task.factor_expression)
            self._failure_tracker.ensure_factor(
                factor_id=factor_id,
                factor_name=task.factor_name,
                factor_expression=task.factor_expression,
            )
            factor_ids.append(factor_id)
        self._current_round_factors = factor_ids
        return factor_ids

    def _track_coder_result(self, experiment):
        """Track coder results for all factors."""
        from quantaalpha.factors.failure_tracker import FailureReason

        for i, (task, workspace) in enumerate(zip(experiment.sub_tasks, experiment.sub_workspace_list)):
            factor_id = self._current_round_factors[i]
            if workspace is not None:
                self._failure_tracker.mark_coder_success(factor_id)
            else:
                self._failure_tracker.mark_coder_failure(
                    factor_id,
                    reason=FailureReason.CODER_NO_WORKSPACE,
                    detail="No workspace produced by coder",
                )

    def _track_backtest_result(self, experiment):
        """Track backtest results for all factors."""
        from quantaalpha.factors.failure_tracker import FailureReason

        # Assume all factors passed quality gate if we reach backtest
        for factor_id in self._current_round_factors:
            self._failure_tracker.mark_quality_gate_success(factor_id)

        # Track backtest results
        if hasattr(experiment, "sub_results") and experiment.sub_results:
            for factor_name, result in experiment.sub_results.items():
                # Find factor ID by name
                for task, factor_id in zip(experiment.sub_tasks, self._current_round_factors):
                    if task.factor_name == factor_name:
                        if result:
                            self._failure_tracker.mark_backtest_success(factor_id, result)
                        else:
                            self._failure_tracker.mark_backtest_failure(
                                factor_id,
                                reason=FailureReason.BACKTEST_EMPTY_RESULT,
                                detail="Empty backtest result",
                            )
                        break
        elif hasattr(experiment, "result") and experiment.result is not None:
            # QlibFactorRunner.develop() sets exp.result to a DataFrame.
            # A non-None result means the backtest completed successfully for all factors.
            import pandas as pd

            if isinstance(experiment.result, pd.DataFrame) and not experiment.result.empty:
                for factor_id in self._current_round_factors:
                    self._failure_tracker.mark_backtest_success(factor_id, {"result": "backtest_completed"})
            else:
                for factor_id in self._current_round_factors:
                    self._failure_tracker.mark_backtest_failure(
                        factor_id,
                        reason=FailureReason.BACKTEST_EMPTY_RESULT,
                        detail="Backtest result DataFrame is empty",
                    )
        else:
            # If no sub_results and no result, mark all as failed
            for factor_id in self._current_round_factors:
                self._failure_tracker.mark_backtest_failure(
                    factor_id,
                    reason=FailureReason.BACKTEST_EMPTY_RESULT,
                    detail="No backtest results available",
                )

    def _finalize_debug_round(self) -> dict:
        """Finalize the current debug round and return summary."""
        summary = self._failure_tracker.finalize_round()
        return {
            "round_idx": summary.round_idx,
            "total_factors": summary.total_factors,
            "successful_count": summary.successful_count,
            "failed_count": summary.failed_count,
            "factors_to_retry": summary.factors_to_retry,
            "all_succeeded": summary.all_succeeded,
            "all_failed": summary.all_failed,
        }

    def _get_successful_factor_ids(self) -> List[str]:
        """Get IDs of successfully completed factors."""
        return self._failure_tracker.successful_factor_ids

    def _get_failed_factor_ids(self) -> List[str]:
        """Get IDs of failed factors."""
        return self._failure_tracker.failed_factor_ids

    def _get_factors_for_retry(self) -> List[str]:
        """Get factor IDs that should be retried in next round."""
        return self._failure_tracker.get_factors_for_retry()

    def _should_continue_debug(self) -> bool:
        """Determine if debug should continue to next round."""
        return self._failure_tracker.should_continue_debug()

    def _get_trajectory_data(self) -> dict[str, Any]:
        """
        Get trajectory data for the current round (used by evolution controller).
        Method name is prefixed with underscore so the workflow system does not treat it as a step.
        Returns:
            Dict with hypothesis, experiment, feedback, etc.
        """
        return {
            "hypothesis": self._last_hypothesis,
            "experiment": self._last_experiment,
            "feedback": self._last_feedback,
            "direction_id": self.direction_id,
            "evolution_phase": self.evolution_phase,
            "trajectory_id": self.trajectory_id,
            "parent_trajectory_ids": self.parent_trajectory_ids,
            "loop_idx": self.loop_idx,
            "round_idx": self.round_idx,
        }


class BacktestLoop(LoopBase, metaclass=LoopMeta):
    skip_loop_error = (FactorEmptyError,)

    @measure_time
    def __init__(self, PROP_SETTING: BaseFacSetting, factor_path=None):
        with logger.tag("init"):
            self.factor_path = factor_path

            scen: Scenario = import_class(PROP_SETTING.scen)()
            logger.log_object(scen, tag="scenario")

            self.hypothesis_generator: HypothesisGen = import_class(PROP_SETTING.hypothesis_gen)(scen)
            logger.log_object(self.hypothesis_generator, tag="hypothesis generator")

            self.factor_constructor: Hypothesis2Experiment = import_class(PROP_SETTING.hypothesis2experiment)(factor_path=factor_path)
            logger.log_object(self.factor_constructor, tag="experiment generation")

            self.coder: Developer = import_class(PROP_SETTING.coder)(
                scen,
                with_feedback=False,
                with_knowledge=False,
                knowledge_self_gen=False,
            )
            logger.log_object(self.coder, tag="coder")

            self.runner: Developer = import_class(PROP_SETTING.runner)(scen)
            logger.log_object(self.runner, tag="runner")

            self.summarizer: HypothesisExperiment2Feedback = import_class(PROP_SETTING.summarizer)(scen)
            logger.log_object(self.summarizer, tag="summarizer")
            self.trace = Trace(scen=scen)
            super().__init__()

    def factor_propose(self, prev_out: dict[str, Any]):
        """
        Market hypothesis on which factors are built
        """
        with logger.tag("r"):
            idea = self.hypothesis_generator.gen(self.trace)
            logger.log_object(idea, tag="hypothesis generation")
        return idea

    @measure_time
    def factor_construct(self, prev_out: dict[str, Any]):
        """
        Construct a variety of factors that depend on the hypothesis
        """
        with logger.tag("r"):
            factor = self.factor_constructor.convert(prev_out["factor_propose"], self.trace)
            logger.log_object(factor.sub_tasks, tag="experiment generation")
        return factor

    @measure_time
    def factor_calculate(self, prev_out: dict[str, Any]):
        """
        Debug factors and calculate their values
        """
        with logger.tag("d"):  # develop
            factor = self.coder.develop(prev_out["factor_construct"])
            logger.log_object(factor.sub_workspace_list, tag="coder result")
        return factor

    @measure_time
    def factor_backtest(self, prev_out: dict[str, Any]):
        """
        Conduct Backtesting
        """
        with logger.tag("ef"):  # evaluate and feedback
            exp = self.runner.develop(prev_out["factor_calculate"])
            if exp is None:
                logger.error(f"Factor extraction failed.")
                raise FactorEmptyError("Factor extraction failed.")
            logger.log_object(exp, tag="runner result")
        return exp

    @measure_time
    def stop(self, prev_out: dict[str, Any]):
        exit(0)
