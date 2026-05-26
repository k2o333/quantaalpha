"""
Model workflow with session control.
"""

import time
import hashlib
import json
import os
import pandas as pd
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import contextmanager
from typing import Any, Iterable, List, TYPE_CHECKING

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
from quantaalpha.factors.proposal import (
    AlphaAgentHypothesis,
    EnsembleHypothesisBundle,
    PROPOSE_FACTORS_TOOL,
    build_ensemble_hypothesis_bundle,
)
from quantaalpha.llm.client import APIBackend, call_structured
import threading

if TYPE_CHECKING:
    from quantaalpha.llm.ensemble import ModelResponse


import pickle
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from tqdm.auto import tqdm

from quantaalpha.core.exception import CoderError
from quantaalpha.log import logger
from functools import wraps
from quantaalpha.pipeline.persistence import (
    append_combined_backtest_performance_history,
    maybe_compact_after_save,
    save_factors_to_parquet,
)

# Decorator: check stop_event before invoking the function


def stop_event_check(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if STOP_EVENT is not None and STOP_EVENT.is_set():
            raise Exception("Operation stopped due to stop_event flag.")
        return func(self, *args, **kwargs)

    return wrapper


def _prepare_standard_frame(config: dict) -> None:
    prepare_func = globals().get("prepare_data_folder_from_standard_frame")
    if prepare_func is None:
        from quantaalpha.factors.qlib_utils import prepare_data_folder_from_standard_frame as prepare_func

    prepare_func(config)


def _configure_standard_frame_capabilities(
    backtest_noqlib_config: dict,
    quality_gate_config: dict,
) -> None:
    standard_frame_cfg = dict(backtest_noqlib_config.get("standard_frame") or {})
    admission_profile_path = standard_frame_cfg.get("admission_profile_path")
    if admission_profile_path:
        from quantaalpha.backtest.mining_admission import (
            capabilities_from_mining_admission_profile,
            load_mining_admission_profile,
            profile_from_standard_frame_config,
        )

        if standard_frame_cfg.get("admitted_fields") and standard_frame_cfg.get("admission_profile_hash"):
            profile = profile_from_standard_frame_config(standard_frame_cfg)
        else:
            profile_name = str(standard_frame_cfg.get("admission_profile") or "expanded_app5_v1")
            resolved_path = _resolve_profile_path(str(admission_profile_path), backtest_noqlib_config)
            profile = load_mining_admission_profile(resolved_path, profile_name)
            standard_frame_cfg["admission_profile_path"] = str(resolved_path)
            standard_frame_cfg["admission_profile"] = profile.name
            standard_frame_cfg["admission_profile_hash"] = profile.version_hash()
            standard_frame_cfg["admitted_fields"] = [field.identity() for field in profile.fields]
        backtest_noqlib_config["standard_frame"] = standard_frame_cfg
        data_capabilities = capabilities_from_mining_admission_profile(profile)
        if data_capabilities and "data_capabilities" not in quality_gate_config:
            quality_gate_config["data_capabilities"] = data_capabilities
        _prepare_standard_frame(backtest_noqlib_config)
        return

    optional_fields = standard_frame_cfg.get("optional_fields") or ()
    if optional_fields:
        from quantaalpha.factors.data_capability import capabilities_from_standard_frame_optional_fields

        data_capabilities = capabilities_from_standard_frame_optional_fields(
            optional_fields,
            manifest_version=standard_frame_cfg.get("admission_allowlist_hash"),
        )
        if data_capabilities and "data_capabilities" not in quality_gate_config:
            quality_gate_config["data_capabilities"] = data_capabilities
        _prepare_standard_frame(backtest_noqlib_config)


def _resolve_profile_path(path: str, backtest_noqlib_config: dict) -> Path:
    profile_path = Path(path).expanduser()
    if profile_path.is_absolute():
        return profile_path
    project_root = backtest_noqlib_config.get("project_root")
    if project_root:
        return (Path(str(project_root)).expanduser() / profile_path).resolve()
    return profile_path.resolve()


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
        parquet_store_path: str | None = None,
        parquet_compact_config: dict | None = None,
        performance_history_config: dict | None = None,
        factor_value_dir: str | None = None,
        publish_factor_values_on_pass: bool | None = None,
        failed_workspace_retention: str | None = None,
        passed_workspace_retention: str | None = None,
        backtest_backend: str | None = None,
        backtest_noqlib_config: dict | None = None,
    ):
        with logger.tag("init"):
            self.use_local = use_local
            self.backtest_backend = str(backtest_backend or "qlib").strip().lower()
            self.backtest_noqlib_config = backtest_noqlib_config or {}
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
            _configure_standard_frame_capabilities(self.backtest_noqlib_config, self.quality_gate_config)
            factor_coder_runtime = str(self.backtest_noqlib_config.get("factor_coder_runtime") or "").strip()
            if factor_coder_runtime:
                os.environ["QUANTAALPHA_FACTOR_CODER_RUNTIME"] = factor_coder_runtime

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

            # Parquet factor-store configuration
            self._parquet_store_path = parquet_store_path
            self._parquet_compact_config = parquet_compact_config
            self._factor_value_dir = factor_value_dir
            if publish_factor_values_on_pass is None:
                try:
                    from quantaalpha.continuous.artifact_policy import runtime_publish_factor_values_on_pass

                    publish_factor_values_on_pass = runtime_publish_factor_values_on_pass()
                except Exception:
                    publish_factor_values_on_pass = False
            self._publish_factor_values_on_pass = bool(publish_factor_values_on_pass)
            if failed_workspace_retention is None or passed_workspace_retention is None:
                try:
                    from quantaalpha.continuous.artifact_policy import (
                        runtime_failed_workspace_retention,
                        runtime_passed_workspace_retention,
                    )

                    if failed_workspace_retention is None:
                        failed_workspace_retention = runtime_failed_workspace_retention()
                    if passed_workspace_retention is None:
                        passed_workspace_retention = runtime_passed_workspace_retention()
                except Exception:
                    failed_workspace_retention = failed_workspace_retention or "full"
                    passed_workspace_retention = passed_workspace_retention or "keep"
            self._failed_workspace_retention = str(failed_workspace_retention or "full")
            self._passed_workspace_retention = str(passed_workspace_retention or "keep")
            self._performance_history_config = performance_history_config or {}
            self._performance_history_store = None
            if self._performance_history_config.get("enabled", False):
                try:
                    from quantaalpha.factor_ops.performance_history import PerformanceHistoryStore

                    self._performance_history_store = PerformanceHistoryStore(
                        self._performance_history_config.get(
                            "root",
                            "third_party/quantaalpha/data/factorlib/performance_history",
                        ),
                        compression=self._performance_history_config.get("compression", "zstd"),
                    )
                except Exception as e:
                    logger.warning(f"Failed to initialize PerformanceHistoryStore: {e}")

            # Failure tracking for debug rounds
            self._failure_tracker = FactorFailureTracker(max_debug_rounds=10)  # Default max rounds
            self._current_round_factors = []

            # For trajectory collection
            self._last_hypothesis = None
            self._last_experiment = None
            self._last_feedback = None
            self._last_save_result = {}
            logger.info(f"Initialized AlphaAgentLoop, backtest in {'local' if use_local else 'Docker'}, backend={self.backtest_backend}")
            if potential_direction:
                logger.info(f"Initial direction: {potential_direction}")
            if evolution_phase != "original":
                logger.info(f"Evolution phase: {evolution_phase}, round: {round_idx}, trajectory_id: {trajectory_id}")

            consistency_enabled = self.quality_gate_config.get("consistency_enabled", False)
            complexity_enabled = self.quality_gate_config.get("complexity_enabled", True)
            redundancy_enabled = self.quality_gate_config.get("redundancy_enabled", True)
            logger.info(f"Quality gate: consistency={'on' if consistency_enabled else 'off'}, complexity={'on' if complexity_enabled else 'off'}, redundancy={'on' if redundancy_enabled else 'off'}")

            scen_kwargs = {}
            if self.quality_gate_config.get("data_capabilities"):
                scen_kwargs["data_capabilities"] = self.quality_gate_config["data_capabilities"]
            scen: Scenario = import_class(PROP_SETTING.scen)(use_local=use_local, **scen_kwargs)
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
                "max_construct_retries",
                "max_multi_construct_retries",
            ):
                if optional_key in self.quality_gate_config:
                    factor_constructor_kwargs[optional_key] = self.quality_gate_config[optional_key]

            self.factor_constructor: Hypothesis2Experiment = import_class(PROP_SETTING.hypothesis2experiment)(**factor_constructor_kwargs)
            logger.log_object(self.factor_constructor, tag="experiment generation")

            self.coder: Developer = import_class(PROP_SETTING.coder)(scen)
            logger.log_object(self.coder, tag="coder")

            self.runner: Developer = import_class(PROP_SETTING.runner)(scen)
            if hasattr(self.runner, "set_backtest_backend"):
                self.runner.set_backtest_backend(self.backtest_backend)
            if hasattr(self.runner, "set_noqlib_config"):
                self.runner.set_noqlib_config(self.backtest_noqlib_config)
            if hasattr(self.runner, "set_quality_overlay_config"):
                self.runner.set_quality_overlay_config(self.quality_gate_config.get("quality_overlay") or self.quality_gate_config)
            if not hasattr(self.runner, "set_backtest_backend"):
                setattr(self.runner, "_backtest_backend", self.backtest_backend)
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
        if isinstance(provider_alias, dict):
            api_backend = getattr(self, "_api_backend", None)
            if api_backend is not None and hasattr(api_backend, "get_model_for_task"):
                return api_backend.get_model_for_task(
                    required_capabilities=provider_alias.get("require_capabilities"),
                    max_tier=provider_alias.get("max_tier"),
                )
            logger.warning(f"step_model_routing[{step_name}] requires APIBackend task routing but no backend is available")
            return None

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
        model = self.get_model_for_step(step_name)
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

    def _call_ensemble_model(
        self,
        *,
        model_name: str,
        real_model: str,
        system_prompt: str,
        user_prompt: str,
        json_flag: bool,
        timeout_seconds: float | None = None,
    ) -> "ModelResponse":
        """Call a single ensemble model and return a ModelResponse.

        This helper is stateless and safe to run inside worker threads.
        """
        from quantaalpha.llm.ensemble import ModelResponse

        start_time = time.time()
        backend = APIBackend(
            chat_model=real_model,
            request_timeout_seconds=timeout_seconds,
            max_retry_override=1,
        )
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
        output = output_dict if output_dict else ""
        latency_ms = (time.time() - start_time) * 1000
        return ModelResponse(
            model_name=model_name,
            raw_output=output,
            latency_ms=latency_ms,
        )

    def _generate_single_hypothesis_with_routing(self):
        """Generate a single hypothesis through the routed propose model path."""
        with self._with_step_model("propose"):
            return self.hypothesis_generator.gen(self.trace)

    def _summarize_output(self, output_dict: dict | None) -> str:
        """Return a short summary of model output for logging."""
        if not output_dict:
            return "<empty>"
        if isinstance(output_dict, dict):
            hypothesis = output_dict.get("hypothesis", "")
            if isinstance(hypothesis, str) and hypothesis:
                return hypothesis[:80]
            return str(output_dict)[:80]
        return str(output_dict)[:80]

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

        Renders the proposal prompt once, fans out concurrent calls via
        ThreadPoolExecutor (bounded by max_workers), and rebuilds the
        responses list in the original model-config order before aggregation.
        """
        from quantaalpha.llm.ensemble import EnsembleAggregator, ModelResponse

        models = self._ensemble_config.get("models", [])
        strategy = self._ensemble_config.get("strategy", "voting")
        configured_workers = int(self._ensemble_config.get("max_workers", 3) or 3)
        max_wait_seconds_raw = self._ensemble_config.get("max_wait_seconds")
        max_wait_seconds = float(max_wait_seconds_raw) if max_wait_seconds_raw is not None else None
        if max_wait_seconds is not None and max_wait_seconds <= 0:
            max_wait_seconds = None
        early_quorum = bool(self._ensemble_config.get("early_quorum", False))

        aggregator = EnsembleAggregator(strategy=strategy)

        # Build the list of valid model specs
        model_specs = []
        for model_cfg in models:
            model_name = model_cfg.get("name", "")
            if not model_name:
                continue
            real_model = self._provider_name_to_model.get(model_name, model_name)
            model_specs.append((model_name, real_model))

        # Fast-path fallback when no valid models exist
        if not model_specs:
            return self._generate_single_hypothesis_with_routing()

        # Render the prompt once, not once per model
        system_prompt, user_prompt, json_flag = self.hypothesis_generator.render_generation_prompts(self.trace)

        # Fan out concurrent execution with bounded workers
        max_workers = max(1, min(len(model_specs), configured_workers))
        min_responses = int(self._ensemble_config.get("min_responses", len(model_specs)) or len(model_specs))
        min_responses = max(1, min(min_responses, len(model_specs)))
        result_map: dict[str, ModelResponse] = {}

        executor = ThreadPoolExecutor(max_workers=max_workers)
        future_to_model = {
            executor.submit(
                self._call_ensemble_model,
                model_name=model_name,
                real_model=real_model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                json_flag=json_flag,
                timeout_seconds=max_wait_seconds,
            ): model_name
            for model_name, real_model in model_specs
        }
        pending = set(future_to_model)
        deadline = time.time() + max_wait_seconds if max_wait_seconds is not None else None

        try:
            while pending:
                timeout = None
                if deadline is not None:
                    timeout = max(0.0, deadline - time.time())
                    if timeout <= 0:
                        logger.warning(
                            f"[ensemble] max_wait_seconds={max_wait_seconds:.0f} reached; "
                            f"continuing with {len(result_map)}/{len(model_specs)} responses"
                        )
                        break

                done, pending = wait(pending, timeout=timeout, return_when=FIRST_COMPLETED)
                if not done:
                    logger.warning(
                        f"[ensemble] wait timed out after {max_wait_seconds:.0f}s; "
                        f"continuing with {len(result_map)}/{len(model_specs)} responses"
                    )
                    break

                for future in done:
                    model_name = future_to_model[future]
                    try:
                        response = future.result()
                        result_map[model_name] = response
                        latency_ms = response.latency_ms
                        logger.info(
                            f"[ensemble] model={model_name} real_model={self._provider_name_to_model.get(model_name, model_name)} "
                            f"latency_ms={latency_ms:.0f} output={self._summarize_output(response.raw_output)}"
                        )
                    except Exception as exc:
                        logger.warning(f"[ensemble] Model {model_name} failed: {exc}")

                if early_quorum and len(result_map) >= min_responses:
                    logger.info(
                        f"[ensemble] quorum reached: {len(result_map)}/{len(model_specs)} responses; "
                        f"skipping {len(pending)} pending model(s)"
                    )
                    break
        finally:
            for future in pending:
                model_name = future_to_model[future]
                logger.warning(f"[ensemble] skipping slow pending model={model_name}")
                future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)

        # Rebuild responses in original model-config order (deterministic)
        responses = []
        for model_cfg in models:
            model_name = model_cfg.get("name", "")
            if model_name in result_map:
                responses.append(result_map[model_name])

        if not responses:
            return self._generate_single_hypothesis_with_routing()

        result = aggregator.aggregate(responses)
        if strategy == "collect_all":
            aggregate_payload = result.output[0] if result.output else None
            if not isinstance(aggregate_payload, dict):
                logger.warning("Collect-all ensemble returned no structured payload, falling back to single-model generation")
                return self._generate_single_hypothesis_with_routing()
            preferred_model = self._step_model_routing.get("propose")
            return build_ensemble_hypothesis_bundle(
                aggregate_payload,
                preferred_model=preferred_model,
            )

        raw_output = result.output[0] if result.output else None
        if raw_output is None:
            logger.warning("Ensemble produced no output, falling back to single-model generation")
            return self._generate_single_hypothesis_with_routing()

        try:
            return self._normalize_hypothesis_output(raw_output)
        except Exception as e:
            logger.error(f"Failed to normalize ensemble output: {e}")
            logger.warning("Falling back to single-model hypothesis generation")
            return self._generate_single_hypothesis_with_routing()

    def _normalize_hypothesis_output(self, idea: Any) -> AlphaAgentHypothesis:
        """Normalize propose outputs so all paths return AlphaAgentHypothesis."""
        if isinstance(idea, (AlphaAgentHypothesis, EnsembleHypothesisBundle)):
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
            hypothesis = prev_out["factor_propose"]
            if isinstance(hypothesis, EnsembleHypothesisBundle):
                factor = self.factor_constructor.convert_multi_hypothesis(hypothesis, self.trace)
                converter_name = "convert_multi_hypothesis"
            else:
                factor = self.factor_constructor.convert(hypothesis, self.trace)
                converter_name = "convert"

            # Fail-fast: reject empty experiment with diagnostic context
            sub_tasks = getattr(factor, "sub_tasks", []) or []
            if not sub_tasks:
                hypothesis_present = hypothesis is not None
                hypothesis_type = type(hypothesis).__name__ if hypothesis_present else "None"
                factor_type = type(factor).__name__ if factor is not None else "None"

                diagnostic = (
                    f"Factor constructor returned no sub_tasks "
                    f"(converter={converter_name}, "
                    f"hypothesis_type={hypothesis_type}, "
                    f"hypothesis_present={hypothesis_present}, "
                    f"factor_type={factor_type}, "
                    f"sub_tasks_count={len(sub_tasks)}). "
                    f"The LLM failed to produce any valid factor expressions."
                )
                raise FactorEmptyError(diagnostic)

            logger.log_object(factor.sub_tasks, tag="experiment generation")

            # Register factors for failure tracking
            self._register_factors_from_experiment(factor)
        return factor

    @measure_time
    @stop_event_check
    def factor_calculate(self, prev_out: dict[str, Any]):
        """Compute factor values from factor expressions."""
        with logger.tag("d"), self._with_step_model("calculate"):  # develop
            factor = self.coder.develop(prev_out["factor_construct"])

            # Fail-fast: reject None or empty coder output
            if factor is None:
                raise FactorEmptyError(
                    "Coder returned None (no factor workspace produced). "
                    "The coder failed to implement the factor expressions."
                )
            sub_tasks = getattr(factor, "sub_tasks", []) or []
            if not sub_tasks:
                raise FactorEmptyError(
                    "Coder output has no sub_tasks (empty factor experiment). "
                    "The coder failed to produce any valid factor workspaces."
                )

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
        cross_run_best = None
        try:
            parquet_store_path = getattr(self, "_parquet_store_path", None)
            if parquet_store_path:
                from quantaalpha.pipeline.persistence import get_cross_run_historical_best_reference
                cross_run_best = get_cross_run_historical_best_reference(str(parquet_store_path))
        except Exception as exc:
            logger.warning(f"Failed to load cross-run historical best for feedback: {exc}")

        with self._with_step_model("feedback"):
            feedback = self.summarizer.generate_feedback(
                prev_out["factor_backtest"], prev_out["factor_propose"], self.trace,
                cross_run_best=cross_run_best,
            )
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

        # Auto-save factors to unified factor library (Parquet-native)
        try:
            import os
            from pathlib import Path

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

            # Use Parquet store for factor library - resolve from config if available
            parquet_store_path = getattr(self, "_parquet_store_path", None)
            if parquet_store_path is None:
                factorlib_dir = project_root / "data" / "factorlib"
                factorlib_dir.mkdir(parents=True, exist_ok=True)
                parquet_store_path = factorlib_dir / "parquet_store"

            # Get compact config from loop if available
            compact_config = getattr(self, "_parquet_compact_config", None)

            self._last_save_result = save_factors_to_parquet(
                experiment=prev_out["factor_backtest"],
                parquet_store_path=str(parquet_store_path),
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
                compact_config=compact_config,
                round_summary=round_summary,
                quality_gate_config=self.quality_gate_config,
                factor_value_dir=getattr(self, "_factor_value_dir", None),
                publish_factor_values_on_pass=getattr(self, "_publish_factor_values_on_pass", False),
                failed_workspace_retention=getattr(self, "_failed_workspace_retention", "full"),
                passed_workspace_retention=getattr(self, "_passed_workspace_retention", "keep"),
            )
            logger.info(f"Saved factors to Parquet store: {parquet_store_path} (phase={evolution_phase})")

            history_store = getattr(self, "_performance_history_store", None)
            history_config = getattr(self, "_performance_history_config", {}) or {}
            if history_store is not None and history_config.get("write_summary", True):
                written = append_combined_backtest_performance_history(
                    experiment=prev_out["factor_backtest"],
                    store=history_store,
                    performance_history_config=history_config,
                    execution_periods=history_config.get("execution_periods"),
                    round_summary=round_summary,
                    evolution_phase=evolution_phase,
                    trajectory_id=trajectory_id,
                    round_number=round_number,
                )
                if written:
                    logger.info(f"Saved {written} combined backtest performance rows to Parquet history")
        except Exception as e:
            logger.warning(f"Failed to save factors to Parquet store: {e}")

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
        """Track coder results for all factors.

        Validates sub_tasks, sub_workspace_list, and _current_round_factors
        lengths before indexing to prevent IndexError leaks.
        """
        from quantaalpha.factors.failure_tracker import FailureReason

        sub_tasks = list(getattr(experiment, "sub_tasks", []) or [])
        sub_workspaces = list(getattr(experiment, "sub_workspace_list", []) or [])
        factor_ids = list(self._current_round_factors)

        # Validate workspace count matches tasks
        if len(sub_tasks) != len(sub_workspaces):
            raise FactorEmptyError(
                f"Tracking mismatch: sub_tasks count ({len(sub_tasks)}) != sub_workspace_list count ({len(sub_workspaces)}). "
                "Coder output structure is inconsistent."
            )

        # Validate factor IDs match tasks
        if len(factor_ids) != len(sub_tasks):
            raise FactorEmptyError(
                f"Tracking mismatch: _current_round_factors count ({len(factor_ids)}) != sub_tasks count ({len(sub_tasks)}). "
                "Factor registration and experiment task count are inconsistent."
            )

        for i, (task, workspace) in enumerate(zip(sub_tasks, sub_workspaces)):
            factor_id = factor_ids[i]
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
            # QlibFactorRunner.develop() sets exp.result to a DataFrame or Series.
            # A non-None result means the backtest completed successfully for all factors.
            # Note: rdagent QlibFBWorkspace.execute() returns pd.Series (via .iloc[:, 0]),
            # so we must accept both Series and DataFrame.
            import pandas as pd

            result = experiment.result
            is_valid_result = False
            if isinstance(result, pd.DataFrame) and not result.empty:
                is_valid_result = True
            elif isinstance(result, pd.Series) and not result.empty:
                is_valid_result = True

            if is_valid_result:
                for factor_id in self._current_round_factors:
                    self._failure_tracker.mark_backtest_success(factor_id, {"result": "backtest_completed"})
            else:
                for factor_id in self._current_round_factors:
                    self._failure_tracker.mark_backtest_failure(
                        factor_id,
                        reason=FailureReason.BACKTEST_EMPTY_RESULT,
                        detail="Backtest result is empty",
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
            "successful_factor_ids": summary.successful_factor_ids,
            "failed_factor_ids": summary.failed_factor_ids,
            "factors_to_retry": summary.factors_to_retry,
            "failed_reasons": summary.failed_reasons,
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
            "save_result": getattr(self, "_last_save_result", {}),
        }


AlphaAgentLoop.get_model_for_step = AlphaAgentLoop._get_model_for_step


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
