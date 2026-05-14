from __future__ import annotations

from .implementation_shared import *
from .implementation_shared import _translate_factor_expression


class MiningPipelineMixin:
    """Responsibility slice for DefaultMiningScheduler."""

    def _check_app5_freshness_before_mining(self) -> dict | None:
        cfg = getattr(self, "_app5_freshness_cfg", {}) or {}
        if not cfg.get("enabled", False):
            return None
        try:
            from app5.observability.freshness import check_freshness, load_continuous_profile

            profile = load_continuous_profile(cfg.get("profile_path", "config/continuous_profile.yaml"))
            report = check_freshness(
                data_root=cfg.get("data_root", "data/app5"),
                profile=profile,
                threshold_hours=cfg.get("threshold_hours"),
            )
            return report.to_dict()
        except Exception as exc:
            logger.warning(f"app5 freshness check failed before mining: {exc}")
            return {"status": "failed", "error": str(exc)}

    def _run_pipeline_mining(self, budget_seconds: Optional[int] = None) -> dict:
        """
        Run mining via AlphaAgentLoop or EvolutionController, or orchestration runtime.

        Args:
            budget_seconds: Maximum seconds for this mining run.

        Returns:
            Dict with factors_generated, factors_validated, factors_added, factor_ids, errors.
        """
        result = {
            "factors_generated": 0,
            "factors_validated": 0,
            "factors_added": 0,
            "factor_ids": [],
            "errors": [],
        }

        from pathlib import Path

        freshness = self._check_app5_freshness_before_mining()
        if freshness is not None and freshness.get("status") != "passed":
            result["status"] = "skipped_stale_app5"
            result["freshness"] = freshness
            result["errors"].append("app5 freshness gate failed")
            logger.warning("Skipping pipeline mining because app5 freshness gate failed")
            return result

        # Phase 3: orchestration runtime branch
        if self._orchestration_cfg.get("enabled", False):
            logger.info("Phase 3: entering orchestration runtime (original-only)")
            # Keep basic runtime setup aligned with the existing pipeline path.
            from quantaalpha.continuous.escalation import EscalationState
            from quantaalpha.continuous.scheduler import EscalationConfig

            escalation_config = EscalationConfig.from_dict(self._escalation_cfg)
            if self._escalation_state is None:
                self._escalation_state = EscalationState(escalation_config)

            if self._state_manager is None:
                self._init_state_manager()

            workspace_root = Path(self._state_cfg.get("log_root", "log/continuous/mining"))
            if not workspace_root.is_absolute():
                workspace_root = workspace_root.resolve()
            workspace_root.mkdir(parents=True, exist_ok=True)
            logger.set_storages_path(workspace_root)

            orchestrated_result = self._run_orchestrated_cycle(budget_seconds=budget_seconds)
            self._persist_state()
            return orchestrated_result

        from quantaalpha.pipeline.settings import ALPHA_AGENT_FACTOR_PROP_SETTING
        from quantaalpha.pipeline.loop import AlphaAgentLoop

        # Apply degraded mode overrides
        effective_evolution_cfg = dict(self._evolution_cfg)
        if self._degraded_mode:
            effective_evolution_cfg["crossover_enabled"] = False
            logger.info("Degraded mode: crossover disabled, using mutation-only")

        # Initialize escalation state (persist across cycles)
        from quantaalpha.continuous.escalation import EscalationState
        from quantaalpha.continuous.scheduler import EscalationConfig

        escalation_config = EscalationConfig.from_dict(self._escalation_cfg)
        if self._escalation_state is None:
            self._escalation_state = EscalationState(escalation_config)
        escalation_state = self._escalation_state

        # Initialize state manager if not done
        if self._state_manager is None:
            self._init_state_manager()

        # Set up workspace
        workspace_root = Path(self._state_cfg.get("log_root", "log/continuous/mining"))
        # 确保使用绝对路径
        if not workspace_root.is_absolute():
            workspace_root = workspace_root.resolve()
        workspace_root.mkdir(parents=True, exist_ok=True)
        logger.set_storages_path(workspace_root)

        # Get mining direction
        direction = self._get_mining_direction()

        evolution_enabled = self._evolution_cfg.get("enabled", False)

        if evolution_enabled:
            # Run evolution loop
            try:
                from quantaalpha.pipeline.factor_mining import run_evolution_loop

                ev_cfg = {
                    "max_rounds": effective_evolution_cfg.get("max_rounds", 3),
                    "mutation_enabled": effective_evolution_cfg.get("mutation_enabled", True),
                    "crossover_enabled": effective_evolution_cfg.get("crossover_enabled", False),
                    "crossover_size": effective_evolution_cfg.get("crossover_size", 2),
                    "crossover_n": effective_evolution_cfg.get("crossover_n", 2),
                    "parallel_enabled": effective_evolution_cfg.get("parallel_enabled", False),
                    "fresh_start": effective_evolution_cfg.get("fresh_start", False),
                }

                run_evolution_loop(
                    initial_direction=direction,
                    evolution_cfg=ev_cfg,
                    exec_cfg={
                        "steps_per_loop": self._state_cfg.get("steps_per_mining", 5),
                        "use_local": True,
                        "max_tasks_per_run": self._orchestration_cfg.get("max_steps_per_cycle", 6),
                        "factor_store_kwargs": {
                            **self._build_alpha_agent_loop_storage_kwargs(),
                            "step_model_routing": self._agent_loop_cfg.get("step_model_routing"),
                            "ensemble_config": self._ensemble_cfg if self._ensemble_cfg.get("enabled") else None,
                            "provider_pool_cfg": self._provider_pool_cfg,
                            "backtest_backend": self.backtest_backend,
                            "backtest_noqlib_config": self.backtest_noqlib_config,
                        },
                    },
                    planning_cfg={"enabled": False},
                    stop_event=self._stop_event,
                    quality_gate_cfg=self._quality_gate_config,
                    budget_seconds=budget_seconds,
                    log_root=str(workspace_root),  # ★ 显式传入绝对路径
                )

                factor_ids = self._extract_factors_from_evolution()
                result["factor_ids"] = factor_ids
                result["factors_generated"] = len(factor_ids)
                result["factors_validated"] = len(factor_ids)
                result["factors_added"] = len(factor_ids)

            except Exception as e:
                logger.error(f"Evolution mining failed: {e}")
                result["errors"].append(f"evolution: {str(e)}")
        else:
            # Run AlphaAgentLoop with max_loops_per_cycle
            max_loops = self._state_cfg.get("max_loops_per_cycle", 1)
            for loop_idx in range(max_loops):
                try:
                    steps = self._state_cfg.get("steps_per_mining", 5)

                    # Resolve escalation-aware routing (returns originals if tier==1)
                    effective_step_model_routing = self._resolve_escalated_routing(
                        escalation_state,
                        self._agent_loop_cfg.get("step_model_routing") or {},
                    )

                    # Build direction with optional failure-trajectory injection
                    effective_direction = self._build_escalated_direction(
                        direction,
                        escalation_state,
                    )

                    self._get_or_build_provider_pool()

                    loop = AlphaAgentLoop(
                        ALPHA_AGENT_FACTOR_PROP_SETTING,
                        potential_direction=effective_direction,
                        stop_event=self._stop_event,
                        use_local=True,
                        quality_gate_config=self._quality_gate_config,
                        step_model_routing=effective_step_model_routing,
                        ensemble_config=self._ensemble_cfg if self._ensemble_cfg.get("enabled") else None,
                        provider_pool_cfg=self._provider_pool_cfg,
                        backtest_backend=self.backtest_backend,
                        backtest_noqlib_config=self.backtest_noqlib_config,
                        **self._build_alpha_agent_loop_storage_kwargs(),
                    )
                    loop.run(step_n=steps, stop_event=self._stop_event)

                    factor_ids = self._extract_factors_from_loop(loop)
                    result["factor_ids"] = factor_ids
                    result["factors_generated"] = len(factor_ids)
                    result["factors_validated"] = len(factor_ids)
                    result["factors_added"] = len(factor_ids)

                    # Record success/failure for escalation
                    if factor_ids:
                        escalation_state.record_success()
                        break  # Success — stop looping
                    else:
                        escalation_state.record_failure(
                            {
                                "error": "No factors generated",
                                "step": "AlphaAgentLoop",
                                "error_type": "capability",
                            }
                        )
                        if escalation_state.should_escalate(escalation_config):
                            escalation_state.escalate(escalation_config)
                            logger.info(f"[escalation] Tier escalated to {escalation_state.current_tier}; next loop will use higher-tier provider")

                except Exception as e:
                    import traceback

                    traceback.print_exc()
                    logger.error(f"Pipeline mining failed (loop {loop_idx + 1}/{max_loops}): {e}")
                    result["errors"].append(f"pipeline: {str(e)}")
                    escalation_state.record_failure(
                        {
                            "error": str(e),
                            "step": "AlphaAgentLoop",
                            "error_type": "api",  # Structured flag: exceptions are availability issues
                        }
                    )
                    if escalation_state.should_escalate(escalation_config):
                        escalation_state.escalate(escalation_config)
                        logger.info(f"[escalation] Tier escalated to {escalation_state.current_tier} (api error); next loop will try fallback provider")

        # Save state after mining
        self._persist_state()

        return result

    def _init_state_manager(self) -> None:
        """Initialize the ContinuousStateManager."""
        from quantaalpha.continuous.state import ContinuousStateManager

        self._state_manager = ContinuousStateManager(
            pool_save_path=self._state_cfg.get("pool_save_path", "log/continuous/trajectory_pool.json"),
            max_pool_size=self._state_cfg.get("max_pool_size", 500),
        )

    def _get_mining_direction(self) -> Optional[str]:
        """Get mining direction from planner or trajectory history."""
        # Use direction planner if enabled
        if self._direction_planner_cfg.get("enabled") and self._state_manager is not None:
            from quantaalpha.continuous.planner import ContinuousDirectionPlanner

            failure_tracker = self._state_manager.get_failure_tracker()
            pool = self._state_manager.load_pool()

            # Cache planner instance to preserve _used_categories across calls
            if self._direction_planner is None:
                self._direction_planner = ContinuousDirectionPlanner(
                    failure_tracker=failure_tracker,
                    trajectory_pool=pool,
                    diversity_window=self._direction_planner_cfg.get("diversity_window", 3),
                    last_failed_within_hours=self._direction_planner_cfg.get("last_failed_within_hours", 48),
                )
            else:
                # Update data references while preserving _used_categories
                self._direction_planner._failure_tracker = failure_tracker
                self._direction_planner._trajectory_pool = pool
            planner = self._direction_planner

            force_different = self._degraded_mode
            result = planner.plan_next_direction(force_different_category=force_different)
            planner.record_used_category(result.category)
            logger.info(f"Direction planner selected: {result.direction} (category={result.category}, source={result.source})")
            return result.direction

        # Fallback to existing logic
        if self._state_manager is not None:
            pool = self._state_manager.load_pool()
            trajectories = pool.get_all()
            if trajectories:
                best = max(
                    trajectories,
                    key=lambda t: t.get_primary_metric() or 0.0,
                )
                if best.hypothesis:
                    return best.hypothesis[:200]
        return None

    def _extract_factors_from_loop(self, loop) -> list:
        """Extract successful factor IDs from an AlphaAgentLoop instance."""
        try:
            return loop._get_successful_factor_ids()
        except Exception as e:
            logger.warning(f"Failed to extract factor IDs from loop: {e}")
            return []

    def _extract_factors_from_evolution(self) -> list:
        """Extract successful factor IDs from the evolution controller's pool."""
        if self._state_manager is None:
            return []

        try:
            import hashlib

            pool = self._state_manager.load_pool()
            active_ids = []
            for traj in pool.get_all():
                eval_info = traj.extra_info.get("evaluation", {})
                if eval_info.get("status") == "active":
                    for factor in traj.factors:
                        factor_name = factor.get("factor_name", "")
                        factor_expr = factor.get("factor_expression", "")
                        if factor_name and factor_expr:
                            fid = hashlib.md5(f"{factor_name}_{factor_expr}".encode()).hexdigest()[:16]
                            active_ids.append(fid)
            return active_ids
        except Exception as e:
            logger.warning(f"Failed to extract factor IDs from evolution: {e}")
            return []

    def _persist_state(self) -> None:
        """Save state and purge if needed."""
        if self._state_manager is None:
            return

        try:
            self._state_manager.save_pool()
            self._state_manager.purge_pool()
        except Exception as e:
            logger.error(f"Failed to persist state: {e}")

    def _add_factor_to_library(self, factor_entry: dict) -> None:
        """
        Add validated factor to library.

        Args:
            factor_entry: Factor entry dict to add.
        """
        try:
            factor_id = factor_entry.get("factor_id", "")

            if getattr(self, "library_backend", "json") == "parquet":
                # Parquet backend: write through FactorStoreFacade
                from quantaalpha.factors.factor_store_facade import FactorStoreFacade

                facade = FactorStoreFacade(store_path=self.parquet_library_dir)

                now_iso = datetime.now().isoformat()
                expression = factor_entry.get("factor_expression", "")
                import hashlib

                expression_hash = hashlib.sha256(expression.encode()).hexdigest()[:16]
                base_sequence = int(datetime.now(timezone.utc).timestamp() * 1_000_000)

                entry = {
                    "factor_id": factor_id,
                    "factor_name": factor_entry.get("factor_name", factor_id),
                    "factor_expression": expression,
                    "factor_expression_normalized": expression,
                    "expression_hash": expression_hash,
                    "evaluation_status": "active",
                    "created_at": now_iso,
                    "updated_at": now_iso,
                    "sequence": base_sequence,
                    "op": "upsert",
                    "tags_json": "[]",
                    "metadata_json": "{}",
                    "backtest_results_json": "{}",
                }
                facade.write_factor(entry)
                logger.info(f"Factor {factor_id} added to Parquet library")
            else:
                # JSON fallback
                from quantaalpha.factors.library import FactorLibraryManager

                library = FactorLibraryManager(self.library_path)
                validation_result = {
                    "status": "success",
                    "summary": {
                        "stability_score": 0.6,
                        "validation_summary": f"Factor {factor_id} activated after mining",
                    },
                }
                library.apply_validation_result(factor_entry, validation_result)
                logger.info(f"Factor {factor_id} added to library")

        except ImportError:
            logger.error("Factor library module not available")
        except Exception as e:
            logger.error(f"Error adding factor {factor_entry.get('factor_id', '')} to library: {e}")
