from __future__ import annotations

from .implementation_shared import *
from .implementation_shared import _translate_factor_expression


class MiningSetupMixin:
    """Responsibility slice for DefaultMiningScheduler."""

    def __init__(
        self,
        max_per_run: int = 5,
        interval_hours: int = 12,
        library_path: Optional[str] = None,
        library_backend: str = "json",
        parquet_library_dir: Optional[str] = None,
        parquet_compact_config: Optional[dict] = None,
        factor_validator: Optional[Callable[[str, dict], Optional[dict]]] = None,
        data_bridge=None,
        execution_periods: Optional[dict] = None,
        min_ic: float = 0.02,
        min_rank_ic: float = 0.01,
        per_factor_timeout_seconds: int = 300,
        monitor_engine=None,
        pipeline_mode: bool = False,
        quality_gate_config: Optional[dict] = None,
        evolution_cfg: Optional[dict] = None,
        state_cfg: Optional[dict] = None,
        escalation_cfg: Optional[dict] = None,
        agent_loop_cfg: Optional[dict] = None,
        ensemble_cfg: Optional[dict] = None,
        provider_pool_cfg: Optional[dict] = None,
        degraded_mode: bool = False,
        direction_planner_cfg: Optional[dict] = None,
        similarity_engine_cfg: Optional[dict] = None,
        orchestration_cfg: Optional[dict] = None,
    ):
        import os

        self.max_per_run = max_per_run
        self.interval_hours = interval_hours
        self.library_path = library_path or os.environ.get("FACTOR_LIBRARY_PATH", "third_party/quantaalpha/data/factorlib/all_factors_library.json")
        self.library_backend = library_backend
        self.parquet_library_dir = parquet_library_dir
        self.parquet_compact_config = parquet_compact_config or {}
        self._factor_validator = factor_validator
        self._data_bridge = data_bridge
        self._execution_periods = execution_periods or {
            "train": ("2020-01-01", "2022-12-31"),
            "valid": ("2023-01-01", "2023-12-31"),
            "test": ("2024-01-01", "2024-12-31"),
        }
        self.min_ic = min_ic
        self.min_rank_ic = min_rank_ic
        self._per_factor_timeout_seconds = per_factor_timeout_seconds
        self._monitor_engine = monitor_engine
        self._next_run: Optional[datetime] = None
        self._running = False
        self._stop_event = Event()
        self._scheduler_thread: Optional[Thread] = None
        self._execution_dataframe_cache = None

        # Pipeline mode settings
        self._pipeline_mode = pipeline_mode
        self._quality_gate_config = quality_gate_config or {}
        self._evolution_cfg = evolution_cfg or {}
        self._state_cfg = state_cfg or {}
        self._state_manager = None
        self._escalation_cfg = escalation_cfg or {"enabled": False}
        self._agent_loop_cfg = agent_loop_cfg or {}
        self._ensemble_cfg = ensemble_cfg or {}
        self._provider_pool_cfg = provider_pool_cfg or {}
        self._degraded_mode = degraded_mode
        self._direction_planner_cfg = direction_planner_cfg or {}
        self._direction_planner = None
        self._similarity_engine_cfg = similarity_engine_cfg or {}
        self._orchestration_cfg = orchestration_cfg or {}

        # 初始化统一相似度引擎
        self._similarity_engine = None
        if self._similarity_engine_cfg and self._similarity_engine_cfg.get("enabled", False):
            try:
                from quantaalpha.factors.similarity_engine import SimilarityEngine

                self._similarity_engine = SimilarityEngine(self._similarity_engine_cfg)
                logger.info(f"SimilarityEngine initialized with metrics: {list(self._similarity_engine._metrics.keys())}")
            except Exception as e:
                logger.warning(f"Failed to initialize SimilarityEngine: {e}, falling back to legacy redundancy check")

        self._escalation_state = None

    def _build_alpha_agent_loop_storage_kwargs(self) -> dict:
        """Build factor-store kwargs for AlphaAgentLoop."""
        if self.library_backend != "parquet":
            return {}
        return {
            "parquet_store_path": self.parquet_library_dir,
            "parquet_compact_config": self.parquet_compact_config,
        }

    def _resolve_escalated_routing(
        self,
        escalation_state,
        base_routing: dict,
    ) -> dict:
        """Return step_model_routing, overridden if escalation is active.

        - tier == start_tier → return base_routing unchanged.
        - API failures (529 etc.) → min_tier=1, pick any available provider.
        - Capability failures → min_tier=current_tier, pick a stronger provider.

        Falls back to base_routing on any error so the pipeline never breaks.
        """
        if escalation_state.current_tier <= 1 or not self._provider_pool_cfg.get("enabled"):
            return base_routing

        try:
            pool = self._get_or_build_provider_pool()
            if pool is None:
                return base_routing

            # Only check the most recent failure to avoid stale decisions (#3).
            last_traj = escalation_state.failed_trajectories[-1] if escalation_state.failed_trajectories else {}
            is_api_failure = last_traj.get("error_type") == "api"
            effective_min_tier = 1 if is_api_failure else escalation_state.current_tier

            candidates = pool.get_by_capability(min_tier=effective_min_tier)
            if not candidates:
                logger.warning(f"[escalation] No provider with tier>={effective_min_tier}; keeping original routing")
                return base_routing

            fallback = candidates[0]
            logger.info(f"[escalation] Routing override: tier>={effective_min_tier} → provider={fallback.name} model={fallback.model}")
            # Override each step key to the fallback provider, preserving step keys.
            return {step: fallback.name for step in base_routing}

        except Exception as exc:
            logger.warning(f"[escalation] ProviderPool override failed: {exc}; keeping original routing")
            return base_routing

    def _get_or_build_provider_pool(self):
        """Lazily build and cache a ProviderPool from _provider_pool_cfg.

        Returns the cached instance on subsequent calls so that latency
        statistics accumulate across loops (fixes least_latency cold-start).
        Returns None if no providers are configured.
        """
        if getattr(self, "_cached_provider_pool", None) is not None:
            return self._cached_provider_pool

        from quantaalpha.llm.provider_pool import ProviderPool

        providers = self._provider_pool_cfg.get("providers", [])
        if not providers:
            return None

        pool = ProviderPool(routing=self._provider_pool_cfg.get("routing", "least_latency"))
        for p in providers:
            pool.add_provider(
                name=p["name"],
                api_keys=p.get("api_keys", []),
                base_url=p.get("base_url"),
                model=p.get("model"),
                tags=p.get("tags", []),
                tier=p.get("tier", 2),
            )
        self._cached_provider_pool = pool
        # Register as default pool for all new APIBackend instances
        from quantaalpha.llm.client import set_default_provider_pool

        set_default_provider_pool(pool)
        logger.info(f"Default ProviderPool registered with {len(providers)} provider(s)")
        return pool

    def _build_escalated_direction(
        self,
        direction: Optional[str],
        escalation_state,
    ) -> Optional[str]:
        """Append failed-trajectory context to mining direction when escalated.

        Activates the previously-dormant get_escalation_context_prompt() method
        so the replacement model can learn from prior failures.

        NOTE: This is safe from prompt accumulation because `direction` is
        freshly obtained from _get_mining_direction() each cycle, and
        escalate() now clears failed_trajectories on tier change.
        """
        if escalation_state.current_tier <= 1 or not escalation_state.failed_trajectories:
            return direction

        failure_ctx = escalation_state.get_escalation_context_prompt()
        if not failure_ctx:
            return direction

        logger.info(f"[escalation] Injected {len(escalation_state.failed_trajectories)} failure trajectories into direction prompt")
        return ((direction or "") + "\n\n" + failure_ctx).strip()

    def start(self) -> None:
        """Start the scheduler with background timer loop."""
        if self._scheduler_thread and self._scheduler_thread.is_alive():
            logger.warning("Mining scheduler already running")
            return
        self._running = True
        self._stop_event.clear()
        self._update_next_run()
        self._scheduler_thread = Thread(target=self._scheduler_loop, daemon=True)
        self._scheduler_thread.start()
        logger.info(f"Mining scheduler started, next run at {self._next_run}")

    def stop(self) -> None:
        """Stop the scheduler."""
        self._stop_event.set()
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=10)
        self._running = False
        logger.info("Mining scheduler stopped")

    def _scheduler_loop(self) -> None:
        """Background scheduler loop that triggers mining."""
        while not self._stop_event.is_set():
            now = datetime.now()
            if self._next_run and now >= self._next_run:
                try:
                    self.run_mining()
                except Exception as e:
                    logger.error(f"Error in mining cycle: {e}")
            self._stop_event.wait(timeout=60)

    def run_mining(self) -> MiningResult:
        """Run one mining cycle."""
        from datetime import datetime as dt

        start_time = dt.now()
        result = MiningResult(timestamp=start_time)

        try:
            if self._pipeline_mode:
                # Pipeline mode: use AlphaAgentLoop or EvolutionController
                budget = self._state_cfg.get("cycle_budget_seconds")
                pipeline_result = self._run_pipeline_mining(budget_seconds=budget)
                result.factors_generated = pipeline_result["factors_generated"]
                result.factors_validated = pipeline_result.get("factors_validated", 0)
                result.factors_added = pipeline_result.get("factors_added", 0)
                result.factor_ids = pipeline_result.get("factor_ids", [])
                result.errors.extend(pipeline_result.get("errors", []))
            else:
                # Legacy mode: use _generate_factors
                context = self._retrieve_context()
                generated = self._generate_factors(context)

                result.factors_generated = len(generated)

                for factor_entry in generated[: self.max_per_run]:
                    factor_id = factor_entry.get("factor_id", "")
                    try:
                        validation_result = self._validate_factor(factor_id, factor_entry)

                        if validation_result is not None and validation_result.get("status") == "success":
                            result.factors_validated += 1

                            redundancy = self._check_redundancy(factor_entry)
                            if redundancy.get("is_redundant", False):
                                logger.info(f"Factor {factor_id} is redundant with {redundancy.get('most_similar_factor_id')} (similarity={redundancy.get('max_similarity', 0):.3f}), skipping admission")
                                result.errors.append(f"{factor_id}: redundant with {redundancy.get('most_similar_factor_id')}")
                                continue

                            result.factor_ids.append(factor_id)
                            self._add_factor_to_library(factor_entry)
                            result.factors_added += 1

                    except Exception as e:
                        logger.error(f"Error validating factor {factor_id}: {e}")
                        result.errors.append(f"{factor_id}: {str(e)}")

        except Exception as e:
            logger.error(f"Error in mining cycle: {e}")
            result.errors.append(str(e))

        result.duration_seconds = (dt.now() - start_time).total_seconds()
        self._update_next_run()

        return result

    def _check_redundancy(self, factor_entry: dict) -> dict:
        """
        Check if a factor is redundant with existing factors.

        优先使用 SimilarityEngine (如果已初始化),否则回退到传统的 library.check_redundancy。

        Args:
            factor_entry: Factor entry to check

        Returns:
            Redundancy check result dict,格式保持与原有接口兼容:
            {
                "is_redundant": bool,
                "most_similar_factor_id": str | None,
                "max_similarity": float,
                "method": "ensemble" | "expression" | None,
                "comparisons_made": int,
            }
        """
        try:
            expression = factor_entry.get("factor_expression", "")
            if not expression:
                return {"is_redundant": False}

            # 优先使用统一相似度引擎
            if self._similarity_engine is not None:
                try:
                    if getattr(self, "library_backend", "json") == "parquet":
                        from quantaalpha.factors.factor_store_facade import FactorStoreFacade

                        facade = FactorStoreFacade(store_path=self.parquet_library_dir)
                        result = self._similarity_engine.check_against_library_data(
                            new_expression=expression,
                            library=facade.as_legacy_library(),
                            max_comparisons=50,
                        )
                    else:
                        result = self._similarity_engine.check_against_library(
                            new_expression=expression,
                            library_path=self.library_path,
                            max_comparisons=50,
                        )

                    # 从 dimension_results 中提取最相似因子信息
                    most_similar_factor_id = None
                    for dim_result in result.dimension_results:
                        if dim_result.raw_detail.get("most_similar_factor_id"):
                            most_similar_factor_id = dim_result.raw_detail["most_similar_factor_id"]
                            break

                    return {
                        "is_redundant": result.is_redundant,
                        "most_similar_factor_id": most_similar_factor_id,
                        "max_similarity": result.final_score,
                        "method": "ensemble",
                        "comparisons_made": result.comparisons_made,
                    }
                except Exception as e:
                    logger.warning(f"SimilarityEngine check failed: {e}, falling back to legacy check")

            # 回退到传统的 library.check_redundancy
            if getattr(self, "library_backend", "json") == "parquet":
                # Parquet backend: use FactorStoreFacade records for redundancy check
                from quantaalpha.factors.factor_store_facade import FactorStoreFacade

                facade = FactorStoreFacade(store_path=self.parquet_library_dir)
                records = facade.read_effective_factor_records()
                expressions = [r.get("factor_expression", "") for r in records if r.get("factor_expression")]
                # Simple redundancy check: exact expression match
                for expr in expressions:
                    if expr == expression:
                        return {"is_redundant": True, "most_similar_factor_id": None, "max_similarity": 1.0, "method": "exact_match", "comparisons_made": 1}
                return {"is_redundant": False, "most_similar_factor_id": None, "max_similarity": 0.0, "method": "exact_match", "comparisons_made": len(expressions)}
            else:
                from quantaalpha.factors.library import FactorLibraryManager

                library = FactorLibraryManager(self.library_path)
                return library.check_redundancy(
                    new_factor_expression=expression,
                    correlation_threshold=0.85,
                    max_comparisons=50,
                )
        except Exception as e:
            logger.info(f"Redundancy check failed: {e}, proceeding with admission")
            return {"is_redundant": False}  # fail-open

    def get_next_scheduled_run(self) -> Optional[datetime]:
        """Get next scheduled run time."""
        return self._next_run

    def _update_next_run(self) -> None:
        """Update next run timestamp."""
        self._next_run = datetime.now() + timedelta(hours=self.interval_hours)

    def clear_execution_dataframe_cache(self) -> None:
        """Clear per-cycle cached execution data."""
        self._execution_dataframe_cache = None
