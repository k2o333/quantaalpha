from __future__ import annotations

from .implementation_shared import *
from .implementation_shared import _translate_factor_expression


class MiningOrchestrationMixin:
    """Responsibility slice for DefaultMiningScheduler."""

    def _run_orchestrated_cycle(self, budget_seconds: Optional[int] = None) -> dict:
        """
        Run a single orchestrated mining cycle using SingleCycleOrchestrator.

        This is the Phase 3 runtime entry point for orchestration mode.
        Only supports 'original' action execution.

        Args:
            budget_seconds: Maximum seconds for this cycle (currently unused).

        Returns:
            Dict with factors_generated, factors_validated, factors_added, factor_ids, errors,
            and orchestration_trace (Phase 5).
        """
        from quantaalpha.continuous.orchestration import (
            SingleCycleOrchestrator,
            OrchestrationContext,
            validate_orchestration_config,
        )
        import uuid

        result = {
            "factors_generated": 0,
            "factors_validated": 0,
            "factors_added": 0,
            "factor_ids": [],
            "errors": [],
        }

        # Read orchestration config
        start_node = self._orchestration_cfg.get("start_node", "original")
        nodes = self._orchestration_cfg.get("nodes", [])
        conditions = self._orchestration_cfg.get("conditions", [])
        max_steps = self._orchestration_cfg.get("max_steps_per_cycle", 6)

        validate_orchestration_config(
            start_node=start_node,
            nodes=nodes,
            conditions=conditions,
            max_steps_per_cycle=max_steps,
        )

        # Initialize orchestrator
        orchestrator = SingleCycleOrchestrator(
            start_node=start_node,
            nodes=nodes,
            conditions=conditions,
            max_steps_per_cycle=max_steps,
        )

        # Initialize context
        context = OrchestrationContext(
            cycle_id=str(uuid.uuid4())[:8],
            current_node=start_node,
            step_index=0,
        )

        # Phase 5: Initialize orchestration trace
        orchestration_trace = {
            "cycle_id": context.cycle_id,
            "start_node": start_node,
            "stop_reason": None,
            "steps": [],
        }

        # Main orchestration loop
        while True:
            # Check stop conditions
            stop_reason, should_stop = orchestrator.should_stop_with_reason(context)

            if should_stop:
                orchestration_trace["stop_reason"] = stop_reason
                break

            # Check stop event
            if self._stop_event.is_set():
                orchestration_trace["stop_reason"] = "stop_event"
                break

            # Determine next action
            action_spec = orchestrator.next_action(context)

            # Execute the action
            # Phase 6: Pass allowed_next and fallback_next for decision nodes
            action_params = dict(action_spec.params)
            action_params["allowed_next"] = action_spec.allowed_next
            action_params["fallback_next"] = action_spec.fallback_next
            action_params["cycle_id"] = context.cycle_id
            action_params["step_index"] = context.step_index
            action_params["generated_factors"] = context.generated_factors
            action_params["pass_rate"] = context.pass_rate
            action_params["active_parents"] = context.active_parents
            action_params["diversity_score"] = context.diversity_score
            action_params["consecutive_failures"] = context.consecutive_failures

            action_result = self._execute_orchestrated_action(
                action=action_spec.action,
                params=action_params,
                node_id=action_spec.node_id,
            )

            # Update context with result
            context = orchestrator.apply_result(context, action_result)

            # Merge action result into return value
            result["factors_generated"] += action_result.generated_factors
            result["factors_validated"] += action_result.validated_factors
            result["factors_added"] += action_result.added_factors
            if action_result.metadata.get("factor_ids"):
                result["factor_ids"].extend(action_result.metadata["factor_ids"])
            if action_result.error:
                result["errors"].append(action_result.error)

            # Phase 5: Advance to next node with trace
            # Phase 6: For decision nodes, prefer advisor-selected next node
            if action_result.metadata.get("selected_next"):
                next_node = action_result.metadata["selected_next"]
                condition_results = {}
            else:
                next_node, condition_results = orchestrator.select_next_node_with_trace(context)

            # Build step trace
            # Phase 6: use action_result.action (real executed action) instead
            # of action_spec.action (which is None for decision nodes)
            step_trace = {
                "step_index": context.step_index,
                "current_node": context.current_node,
                "action": action_result.action,
                "action_status": action_result.status,
                "condition_results": condition_results,
                "next_node": next_node,
                "error": action_result.error,
            }
            orchestration_trace["steps"].append(step_trace)

            if next_node is None:
                # No valid next node
                orchestration_trace["stop_reason"] = "no_valid_transition"
                break

            context.current_node = next_node
            context.step_index += 1

            # Check budget / stop event (second check for safety)
            if self._stop_event.is_set():
                orchestration_trace["stop_reason"] = "stop_event"
                break

        # Phase 5: Attach trace to result
        result["orchestration_trace"] = orchestration_trace

        return result

    def _execute_orchestrated_action(
        self,
        action: Optional[str],
        params: dict,
        node_id: str,
    ) -> "ActionResult":
        """
        Dispatch and execute an orchestrated action.

        Phase 4 supports 'original', 'mutation', and 'crossover' actions.
        Phase 6 adds 'llm_advisor' for decision nodes.

        Args:
            action: Action type (e.g. 'original', 'mutation', 'crossover', 'llm_advisor').
            params: Action parameters from the node config.
            node_id: ID of the node being executed.

        Returns:
            ActionResult with execution result.
        """
        from quantaalpha.continuous.orchestration import ActionResult

        # Phase 6: For decision nodes with no action, dispatch by decision_mode
        if action is None:
            node = self._orchestration_cfg.get("nodes", [])
            node_def = next((n for n in node if n["id"] == node_id), None)
            if node_def and node_def.get("kind") == "decision":
                decision_mode = node_def.get("decision_mode")
                if decision_mode == "llm_advisor":
                    return self._execute_llm_advisor(params, node_id)

        if action == "original":
            return self._execute_original_action(params, node_id)
        elif action == "mutation":
            return self._execute_mutation_action(params, node_id)
        elif action == "crossover":
            return self._execute_crossover_action(params, node_id)
        elif action == "llm_advisor":
            return self._execute_llm_advisor(params, node_id)

        # Unsupported action
        logger.warning(f"Orchestration action '{action}' on node '{node_id}' is not supported")
        return ActionResult(
            action=action or "unknown",
            status="unsupported",
            error=f"Action '{action}' not supported",
        )

    def _execute_original_action(
        self,
        params: dict,
        node_id: str,
    ) -> "ActionResult":
        """
        Execute the 'original' action by reusing the existing AlphaAgentLoop path.

        Args:
            params: Action parameters (currently unused).
            node_id: ID of the node being executed.

        Returns:
            ActionResult with generated/validated/added factor counts.
        """
        from quantaalpha.continuous.orchestration import ActionResult

        try:
            # Reuse the existing original mining path by temporarily disabling
            # orchestration and calling _run_pipeline_mining's existing logic.
            # We directly invoke the AlphaAgentLoop path here.
            from pathlib import Path
            from quantaalpha.pipeline.settings import ALPHA_AGENT_FACTOR_PROP_SETTING
            from quantaalpha.pipeline.loop import AlphaAgentLoop

            steps = self._state_cfg.get("steps_per_mining", 5)
            direction = self._get_mining_direction()

            self._get_or_build_provider_pool()

            loop = AlphaAgentLoop(
                ALPHA_AGENT_FACTOR_PROP_SETTING,
                potential_direction=direction,
                stop_event=self._stop_event,
                use_local=True,
                quality_gate_config=self._quality_gate_config,
                step_model_routing=self._agent_loop_cfg.get("step_model_routing"),
                ensemble_config=self._ensemble_cfg if self._ensemble_cfg.get("enabled") else None,
                provider_pool_cfg=self._provider_pool_cfg,
                backtest_backend=self.backtest_backend,
                backtest_noqlib_config=self.backtest_noqlib_config,
                **self._build_alpha_agent_loop_storage_kwargs(),
            )
            loop.run(step_n=steps, stop_event=self._stop_event)

            factor_ids = self._extract_factors_from_loop(loop)

            return ActionResult(
                action="original",
                status="success" if factor_ids else "completed_no_factor",
                generated_factors=len(factor_ids),
                validated_factors=len(factor_ids),
                added_factors=len(factor_ids),
                metadata={
                    "factor_ids": factor_ids,
                    "node_id": node_id,
                },
            )

        except Exception as e:
            logger.error(f"Original action failed on node '{node_id}': {e}")
            return ActionResult(
                action="original",
                status="error",
                error=str(e),
            )

    def _execute_mutation_action(
        self,
        params: dict,
        node_id: str,
    ) -> "ActionResult":
        """
        Execute the 'mutation' action by calling the real evolution adapter.

        Args:
            params: Action parameters from the node config.
            node_id: ID of the node being executed.

        Returns:
            ActionResult with generated/validated/added factor counts.
        """
        from quantaalpha.continuous.orchestration import ActionResult

        try:
            # Import the real adapter entrypoint from factor_mining module
            from quantaalpha.pipeline.factor_mining import run_evolution_action

            direction = params.get("direction") or self._get_mining_direction()
            log_root = self._state_cfg.get("log_root")
            exec_cfg = {
                **self._state_cfg,
                "factor_store_kwargs": {
                    **self._build_alpha_agent_loop_storage_kwargs(),
                    "backtest_backend": self.backtest_backend,
                    "backtest_noqlib_config": self.backtest_noqlib_config,
                },
            }

            result = run_evolution_action(
                initial_direction=direction,
                evolution_cfg={
                    **self._evolution_cfg,
                    "mutation_enabled": True,
                    "crossover_enabled": False,
                },
                exec_cfg=exec_cfg,
                planning_cfg=self._direction_planner_cfg,
                mutation_enabled=True,
                crossover_enabled=False,
                budget_seconds=self._state_cfg.get("budget_seconds"),
                log_root=log_root,
            )

            factor_ids = result.get("factor_ids", [])
            result_status = result.get("status", "degraded")
            return ActionResult(
                action="mutation",
                status=result_status,
                generated_factors=result.get("successful_tasks", 0),
                validated_factors=result.get("successful_tasks", 0),
                added_factors=result.get("successful_tasks", 0),
                metadata={
                    "factor_ids": factor_ids,
                    "node_id": node_id,
                    "evolution_summary": result,
                },
            )

        except Exception as e:
            logger.error(f"Mutation action failed on node '{node_id}': {e}")
            return ActionResult(
                action="mutation",
                status="error",
                error=str(e),
            )

    def _execute_crossover_action(
        self,
        params: dict,
        node_id: str,
    ) -> "ActionResult":
        """
        Execute the 'crossover' action by calling the real evolution adapter.
        In degraded mode, crossover is blocked and returns a non-success result.

        Args:
            params: Action parameters from the node config.
            node_id: ID of the node being executed.

        Returns:
            ActionResult with generated/validated/added factor counts.
        """
        from quantaalpha.continuous.orchestration import ActionResult

        # Degraded mode blocks crossover
        if self._degraded_mode:
            logger.warning(f"Crossover blocked on node '{node_id}': degraded mode is active")
            return ActionResult(
                action="crossover",
                status="blocked",
                error="Crossover is disabled in degraded mode",
            )

        try:
            # Import the real adapter entrypoint from factor_mining module
            from quantaalpha.pipeline.factor_mining import run_evolution_action

            direction = params.get("direction") or self._get_mining_direction()
            log_root = self._state_cfg.get("log_root")
            exec_cfg = {
                **self._state_cfg,
                "factor_store_kwargs": {
                    **self._build_alpha_agent_loop_storage_kwargs(),
                    "backtest_backend": self.backtest_backend,
                    "backtest_noqlib_config": self.backtest_noqlib_config,
                },
            }

            result = run_evolution_action(
                initial_direction=direction,
                evolution_cfg={
                    **self._evolution_cfg,
                    "mutation_enabled": False,
                    "crossover_enabled": True,
                },
                exec_cfg=exec_cfg,
                planning_cfg=self._direction_planner_cfg,
                mutation_enabled=False,
                crossover_enabled=True,
                budget_seconds=self._state_cfg.get("budget_seconds"),
                log_root=log_root,
            )

            factor_ids = result.get("factor_ids", [])
            result_status = result.get("status", "degraded")
            return ActionResult(
                action="crossover",
                status=result_status,
                generated_factors=result.get("successful_tasks", 0),
                validated_factors=result.get("successful_tasks", 0),
                added_factors=result.get("successful_tasks", 0),
                metadata={
                    "factor_ids": factor_ids,
                    "node_id": node_id,
                    "evolution_summary": result,
                },
            )

        except Exception as e:
            logger.error(f"Crossover action failed on node '{node_id}': {e}")
            return ActionResult(
                action="crossover",
                status="error",
                error=str(e),
            )

    def _execute_llm_advisor(
        self,
        params: dict,
        node_id: str,
    ) -> "ActionResult":
        """
        Execute the llm_advisor decision node.

        Phase 6: Filters context to allowed fields only, calls a provider,
        validates the output against allowed_next, and falls back to fallback_next
        on any failure.

        Args:
            params: Node parameters including allowed_next, fallback_next,
                    and optional provider override.
            node_id: ID of the decision node being executed.

        Returns:
            ActionResult with selected_next in metadata (or fallback_used=True).
        """
        from quantaalpha.continuous.orchestration import ActionResult

        allowed_next = params.get("allowed_next", [])
        fallback_next = params.get("fallback_next")

        # Build the filtered advisor context (spec: strict filtering)
        advisor_context = {
            "cycle_id": params.get("cycle_id", ""),
            "current_node": node_id,
            "step_index": params.get("step_index", 0),
            "generated_factors": params.get("generated_factors", 0),
            "pass_rate": params.get("pass_rate", 0.0),
            "active_parents": params.get("active_parents", 0),
            "diversity_score": params.get("diversity_score", 0.0),
            "consecutive_failures": params.get("consecutive_failures", 0),
            "allowed_next": list(allowed_next),
        }

        # Try to get advisor recommendation
        try:
            provider = params.get("llm_provider")
            if provider is None:
                provider = getattr(self, "_llm_advisor_provider", None)

            if provider is None:
                raise RuntimeError("No llm_advisor provider configured")

            raw_output = provider.advise(advisor_context)
        except Exception as exc:
            logger.warning(f"llm_advisor on node '{node_id}': provider failed: {exc}, falling back to '{fallback_next}'")
            return ActionResult(
                action="llm_advisor",
                status="error",
                metadata={
                    "selected_next": fallback_next,
                    "fallback_used": True,
                    "error": str(exc),
                    "advisor_context": advisor_context,
                },
                error=str(exc),
            )

        # Validate the advisor output
        selected_next = self._validate_advisor_output(raw_output, allowed_next, fallback_next, node_id)

        if selected_next == fallback_next:
            status = "fallback"
            fallback_used = True
        else:
            status = "success"
            fallback_used = False

        reason = ""
        if isinstance(raw_output, dict):
            reason = raw_output.get("reason", "")

        return ActionResult(
            action="llm_advisor",
            status=status,
            metadata={
                "selected_next": selected_next,
                "fallback_used": fallback_used,
                "advisor_reason": reason,
                "advisor_context": advisor_context,
            },
        )

    def _validate_advisor_output(
        self,
        raw_output: Any,
        allowed_next: list[str],
        fallback_next: str | None,
        node_id: str,
    ) -> str:
        """
        Validate advisor output and return the selected next node.

        Falls back to fallback_next on any validation failure.
        """
        try:
            if raw_output is None:
                logger.warning(f"llm_advisor on node '{node_id}': provider returned None, falling back to '{fallback_next}'")
                return fallback_next

            # Handle string output (just a node name)
            if isinstance(raw_output, str):
                try:
                    import json

                    parsed = json.loads(raw_output)
                except (json.JSONDecodeError, ValueError):
                    # Treat as raw node name
                    if raw_output in allowed_next:
                        return raw_output
                    logger.warning(f"llm_advisor on node '{node_id}': string output '{raw_output}' not in allowed_next, falling back to '{fallback_next}'")
                    return fallback_next
                raw_output = parsed

            # Handle dict output
            if isinstance(raw_output, dict):
                next_node = raw_output.get("next_node")
                if next_node is None:
                    logger.warning(f"llm_advisor on node '{node_id}': missing 'next_node' in output, falling back to '{fallback_next}'")
                    return fallback_next

                if next_node not in allowed_next:
                    logger.warning(f"llm_advisor on node '{node_id}': next_node '{next_node}' not in allowed_next {allowed_next}, falling back to '{fallback_next}'")
                    return fallback_next

                return next_node

            # Unexpected type
            logger.warning(f"llm_advisor on node '{node_id}': unexpected output type {type(raw_output)}, falling back to '{fallback_next}'")
            return fallback_next

        except Exception as exc:
            logger.error(f"llm_advisor on node '{node_id}': validation error: {exc}, falling back to '{fallback_next}'")
            return fallback_next
