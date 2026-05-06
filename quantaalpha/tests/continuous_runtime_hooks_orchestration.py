"""
Unit tests for continuous runtime hooks (the four critical seams).

Tests cover:
- _run_factor_backtest: backtest execution seam
- _validate_factor: factor validation seam
- _generate_factors: factor generation seam
- _retrieve_context: context retrieval seam

These tests verify that stubs are replaced with real integration behavior.
"""

import json
import logging
import sys
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import polars as pl
import pytest


def _ensure_repo_root_importable():
    repo_root = Path(__file__).resolve().parents[4]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))


_ensure_repo_root_importable()


class TestPhase4RuntimeEvolution:
    """Tests for Phase 4 runtime evolution adapter wiring.

    Tests cover:
    - _execute_orchestrated_action dispatches mutation and crossover (not unsupported)
    - _execute_mutation_action and _execute_crossover_action have real implementations
    - degraded mode blocks crossover before calling the adapter
    """

    def test_phase4_runtime_evolution_mutation_dispatches_to_helper(self, tmp_path):
        """Verify _execute_orchestrated_action dispatches 'mutation' to _execute_mutation_action."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultMiningScheduler(library_path=str(lib_path))

        # Mock the mutation action helper
        with patch.object(scheduler, "_execute_mutation_action") as mock_mutation:
            from quantaalpha.continuous.orchestration import ActionResult

            mock_mutation.return_value = ActionResult(
                action="mutation",
                status="success",
                generated_factors=1,
                validated_factors=1,
                added_factors=1,
            )

            result = scheduler._execute_orchestrated_action(
                action="mutation",
                params={"direction": "test"},
                node_id="mutation_node",
            )

            mock_mutation.assert_called_once()
            assert result.status != "unsupported"
            assert result.action == "mutation"

    def test_phase4_runtime_evolution_crossover_dispatches_to_helper(self, tmp_path):
        """Verify _execute_orchestrated_action dispatches 'crossover' to _execute_crossover_action."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultMiningScheduler(library_path=str(lib_path))

        # Mock the crossover action helper
        with patch.object(scheduler, "_execute_crossover_action") as mock_crossover:
            from quantaalpha.continuous.orchestration import ActionResult

            mock_crossover.return_value = ActionResult(
                action="crossover",
                status="success",
                generated_factors=1,
                validated_factors=1,
                added_factors=1,
            )

            result = scheduler._execute_orchestrated_action(
                action="crossover",
                params={"direction": "test"},
                node_id="crossover_node",
            )

            mock_crossover.assert_called_once()
            assert result.status != "unsupported"
            assert result.action == "crossover"

    def test_phase4_runtime_evolution_mutation_helper_calls_real_adapter(self, tmp_path):
        """Verify _execute_mutation_action calls the real adapter target path."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler
        from quantaalpha.continuous.orchestration import ActionResult

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultMiningScheduler(library_path=str(lib_path))
        scheduler._direction_planner_cfg = {"enabled": False}
        scheduler._evolution_cfg = {"max_rounds": 1}
        scheduler._state_cfg = {
            **scheduler._state_cfg,
            "log_root": str(tmp_path / "logs"),
            "budget_seconds": 17,
        }

        with patch(
            "quantaalpha.pipeline.factor_mining.run_evolution_action",
            return_value={"status": "success", "successful_tasks": 2, "factor_ids": ["m1", "m2"]},
        ) as mock_adapter:
            result = scheduler._execute_mutation_action(
                params={"direction": "mutation test"},
                node_id="mutation_node",
            )

        assert isinstance(result, ActionResult)
        assert result.status == "success"
        assert result.generated_factors == 2
        mock_adapter.assert_called_once_with(
            initial_direction="mutation test",
            evolution_cfg={
                **scheduler._evolution_cfg,
                "mutation_enabled": True,
                "crossover_enabled": False,
            },
            exec_cfg=scheduler._state_cfg,
            planning_cfg=scheduler._direction_planner_cfg,
            mutation_enabled=True,
            crossover_enabled=False,
            budget_seconds=17,
            log_root=str(tmp_path / "logs"),
        )

    def test_phase4_runtime_evolution_crossover_helper_calls_real_adapter(self, tmp_path):
        """Verify _execute_crossover_action calls the real adapter target path."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler
        from quantaalpha.continuous.orchestration import ActionResult

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultMiningScheduler(library_path=str(lib_path))
        scheduler._direction_planner_cfg = {"enabled": False}
        scheduler._evolution_cfg = {"max_rounds": 1}
        scheduler._state_cfg = {
            **scheduler._state_cfg,
            "log_root": str(tmp_path / "logs"),
            "budget_seconds": 19,
        }

        with patch(
            "quantaalpha.pipeline.factor_mining.run_evolution_action",
            return_value={"status": "success", "successful_tasks": 1, "factor_ids": ["c1"]},
        ) as mock_adapter:
            result = scheduler._execute_crossover_action(
                params={"direction": "crossover test"},
                node_id="crossover_node",
            )

        assert isinstance(result, ActionResult)
        assert result.status == "success"
        assert result.generated_factors == 1
        mock_adapter.assert_called_once_with(
            initial_direction="crossover test",
            evolution_cfg={
                **scheduler._evolution_cfg,
                "mutation_enabled": False,
                "crossover_enabled": True,
            },
            exec_cfg=scheduler._state_cfg,
            planning_cfg=scheduler._direction_planner_cfg,
            mutation_enabled=False,
            crossover_enabled=True,
            budget_seconds=19,
            log_root=str(tmp_path / "logs"),
        )

    def test_phase4_runtime_evolution_degraded_mode_blocks_crossover(self, tmp_path):
        """Verify degraded mode blocks crossover without calling the adapter."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        # Create scheduler with degraded mode enabled
        scheduler = DefaultMiningScheduler(
            library_path=str(lib_path),
            degraded_mode=True,
        )

        with patch("quantaalpha.pipeline.factor_mining.run_evolution_action") as mock_adapter:
            result = scheduler._execute_crossover_action(
                params={"direction": "test"},
                node_id="crossover_node",
            )

        # Result should indicate blocked/skipped/degraded
        assert result.status in ("blocked", "skipped", "degraded", "disabled")
        assert result.error is not None
        mock_adapter.assert_not_called()

    def test_phase4_runtime_evolution_failed_adapter_status_is_preserved(self, tmp_path):
        """Verify failed adapter result is not collapsed into degraded."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultMiningScheduler(library_path=str(lib_path))
        scheduler._direction_planner_cfg = {"enabled": False}
        scheduler._evolution_cfg = {"max_rounds": 1}

        with patch(
            "quantaalpha.pipeline.factor_mining.run_evolution_action",
            return_value={"status": "failed", "successful_tasks": 0, "failed_tasks": 3},
        ):
            result = scheduler._execute_mutation_action(
                params={"direction": "mutation test"},
                node_id="mutation_node",
            )

        assert result.status == "failed"


class TestPhase5OrchestrationTrace:
    """Tests for Phase 5: single-cycle orchestration trace observability."""

    def test_phase5_orchestration_trace_returns_trace_in_result(self, tmp_path):
        """Verify _run_orchestrated_cycle returns orchestration_trace in result."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultMiningScheduler(
            library_path=str(lib_path),
            orchestration_cfg={
                "enabled": True,
                "start_node": "original",
                "max_steps_per_cycle": 3,
                "nodes": [
                    {
                        "id": "original",
                        "kind": "action",
                        "action": "original",
                        "next": [],
                    }
                ],
                "conditions": [],
            },
        )

        with patch.object(scheduler, "_execute_orchestrated_action") as mock_action:
            from quantaalpha.continuous.orchestration import ActionResult

            mock_action.return_value = ActionResult(
                action="original",
                status="success",
                generated_factors=1,
                validated_factors=1,
                added_factors=1,
                metadata={"factor_ids": ["f1"]},
            )

            result = scheduler._run_orchestrated_cycle()

        assert "orchestration_trace" in result
        trace = result["orchestration_trace"]
        assert "cycle_id" in trace
        assert "start_node" in trace
        assert "stop_reason" in trace
        assert "steps" in trace
        assert trace["start_node"] == "original"

    def test_phase5_orchestration_trace_steps_have_required_fields(self, tmp_path):
        """Verify each step in orchestration_trace has required fields."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultMiningScheduler(
            library_path=str(lib_path),
            orchestration_cfg={
                "enabled": True,
                "start_node": "original",
                "max_steps_per_cycle": 3,
                "nodes": [
                    {
                        "id": "original",
                        "kind": "action",
                        "action": "original",
                        "next": [{"goto": "original"}],
                    }
                ],
                "conditions": [],
            },
        )

        step_count = [0]

        def mock_action(*args, **kwargs):
            from quantaalpha.continuous.orchestration import ActionResult

            step_count[0] += 1
            if step_count[0] >= 2:
                return ActionResult(
                    action="original",
                    status="error",
                    error="forced stop",
                )
            return ActionResult(
                action="original",
                status="success",
                generated_factors=0,
                validated_factors=0,
                added_factors=0,
            )

        with patch.object(scheduler, "_execute_orchestrated_action", side_effect=mock_action):
            result = scheduler._run_orchestrated_cycle()

        trace = result["orchestration_trace"]
        assert len(trace["steps"]) >= 1

        for step in trace["steps"]:
            assert "step_index" in step
            assert "current_node" in step
            assert "action" in step
            assert "action_status" in step
            assert "condition_results" in step
            assert "next_node" in step
            assert "error" in step

    def test_phase5_orchestration_trace_stop_reason_terminal_node(self, tmp_path):
        """Verify stop_reason is 'terminal_node' when reaching a terminal node."""
        from unittest.mock import patch
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultMiningScheduler(
            library_path=str(lib_path),
            orchestration_cfg={
                "enabled": True,
                "start_node": "original",
                "max_steps_per_cycle": 10,
                "nodes": [
                    {
                        "id": "original",
                        "kind": "action",
                        "action": "original",
                        "next": [{"goto": "end_node"}],
                    },
                    {
                        "id": "end_node",
                        "kind": "terminal",
                        "next": [],
                    },
                ],
                "conditions": [],
            },
        )

        with patch.object(scheduler, "_execute_orchestrated_action") as mock_action:
            from quantaalpha.continuous.orchestration import ActionResult

            mock_action.return_value = ActionResult(
                action="original",
                status="success",
            )

            result = scheduler._run_orchestrated_cycle()

        trace = result["orchestration_trace"]
        assert trace["stop_reason"] == "terminal_node"

    def test_phase5_orchestration_trace_stop_reason_max_steps_reached(self, tmp_path):
        """Verify stop_reason is 'max_steps_reached' when hitting step limit."""
        from unittest.mock import patch
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultMiningScheduler(
            library_path=str(lib_path),
            orchestration_cfg={
                "enabled": True,
                "start_node": "original",
                "max_steps_per_cycle": 2,
                "nodes": [
                    {
                        "id": "original",
                        "kind": "action",
                        "action": "original",
                        "next": [{"goto": "original"}],
                    }
                ],
                "conditions": [],
            },
        )

        with patch.object(scheduler, "_execute_orchestrated_action") as mock_action:
            from quantaalpha.continuous.orchestration import ActionResult

            mock_action.return_value = ActionResult(
                action="original",
                status="success",
            )

            result = scheduler._run_orchestrated_cycle()

        trace = result["orchestration_trace"]
        assert trace["stop_reason"] == "max_steps_reached"

    def test_phase5_orchestration_trace_stop_reason_no_valid_transition(self, tmp_path):
        """Verify stop_reason is 'no_valid_transition' when next_node is None."""
        from unittest.mock import patch
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultMiningScheduler(
            library_path=str(lib_path),
            orchestration_cfg={
                "enabled": True,
                "start_node": "original",
                "max_steps_per_cycle": 10,
                "nodes": [
                    {
                        "id": "original",
                        "kind": "action",
                        "action": "original",
                        "next": [],
                        "fallback_next": None,
                    }
                ],
                "conditions": [],
            },
        )

        with patch.object(scheduler, "_execute_orchestrated_action") as mock_action:
            from quantaalpha.continuous.orchestration import ActionResult

            mock_action.return_value = ActionResult(
                action="original",
                status="success",
            )

            result = scheduler._run_orchestrated_cycle()

        trace = result["orchestration_trace"]
        assert trace["stop_reason"] == "no_valid_transition"

    def test_phase5_orchestration_trace_stop_reason_stop_event(self, tmp_path):
        """Verify stop_reason is 'stop_event' when stop event is set."""
        from unittest.mock import patch
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultMiningScheduler(
            library_path=str(lib_path),
            orchestration_cfg={
                "enabled": True,
                "start_node": "original",
                "max_steps_per_cycle": 10,
                "nodes": [
                    {
                        "id": "original",
                        "kind": "action",
                        "action": "original",
                        "next": [{"goto": "original"}],
                    }
                ],
                "conditions": [],
            },
        )

        scheduler._stop_event.set()

        with patch.object(scheduler, "_execute_orchestrated_action") as mock_action:
            from quantaalpha.continuous.orchestration import ActionResult

            mock_action.return_value = ActionResult(
                action="original",
                status="success",
            )

            result = scheduler._run_orchestrated_cycle()

        trace = result["orchestration_trace"]
        assert trace["stop_reason"] == "stop_event"

    def test_phase5_orchestration_trace_condition_results_from_real_transition(self, tmp_path):
        """Verify condition_results comes from real transition evaluation."""
        from unittest.mock import patch
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultMiningScheduler(
            library_path=str(lib_path),
            orchestration_cfg={
                "enabled": True,
                "start_node": "decision_node",
                "max_steps_per_cycle": 5,
                "nodes": [
                    {
                        "id": "decision_node",
                        "kind": "action",
                        "action": "original",
                        "next": [
                            {"if": "high_pass_rate", "goto": "good_node"},
                            {"if": "low_pass_rate", "goto": "bad_node"},
                        ],
                        "fallback_next": "fallback_node",
                    },
                    {
                        "id": "good_node",
                        "kind": "terminal",
                        "next": [],
                    },
                    {
                        "id": "bad_node",
                        "kind": "terminal",
                        "next": [],
                    },
                    {
                        "id": "fallback_node",
                        "kind": "terminal",
                        "next": [],
                    },
                ],
                "conditions": [
                    {
                        "name": "high_pass_rate",
                        "type": "threshold",
                        "metric": "pass_rate",
                        "operator": "gte",
                        "value": 0.5,
                    },
                    {
                        "name": "low_pass_rate",
                        "type": "threshold",
                        "metric": "pass_rate",
                        "operator": "lt",
                        "value": 0.5,
                    },
                ],
            },
        )

        with patch.object(scheduler, "_execute_orchestrated_action") as mock_action:
            from quantaalpha.continuous.orchestration import ActionResult

            mock_action.return_value = ActionResult(
                action="original",
                status="success",
                added_factors=3,
                validated_factors=5,
            )

            result = scheduler._run_orchestrated_cycle()

        trace = result["orchestration_trace"]
        assert len(trace["steps"]) >= 1

        condition_step = None
        for step in trace["steps"]:
            if step["condition_results"]:
                condition_step = step
                break

        assert condition_step is not None, "Expected at least one step with condition_results"
        assert "high_pass_rate" in condition_step["condition_results"]
        assert condition_step["condition_results"]["high_pass_rate"] is True

    def test_phase5_orchestration_trace_cycle_id_is_real(self, tmp_path):
        """Verify cycle_id in trace is a real generated ID."""
        from unittest.mock import patch
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultMiningScheduler(
            library_path=str(lib_path),
            orchestration_cfg={
                "enabled": True,
                "start_node": "original",
                "max_steps_per_cycle": 3,
                "nodes": [
                    {
                        "id": "original",
                        "kind": "action",
                        "action": "original",
                        "next": [],
                    }
                ],
                "conditions": [],
            },
        )

        with patch.object(scheduler, "_execute_orchestrated_action") as mock_action:
            from quantaalpha.continuous.orchestration import ActionResult

            mock_action.return_value = ActionResult(
                action="original",
                status="success",
            )

            result = scheduler._run_orchestrated_cycle()

        trace = result["orchestration_trace"]
        assert trace["cycle_id"] is not None
        assert len(trace["cycle_id"]) > 0
        assert len(trace["cycle_id"]) == 8


class TestPhase6LLMAdvisorRuntime:
    """Phase 6: Tests for llm_advisor runtime wiring in _run_orchestrated_cycle."""

    def _make_scheduler_with_advisor(self, tmp_path, orchestrator_cfg):
        """Create a DefaultMiningScheduler with orchestration config."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultMiningScheduler(
            library_path=str(lib_path),
            orchestration_cfg=orchestrator_cfg,
        )
        return scheduler

    def test_phase6_llm_advisor_selects_valid_next_node(self, tmp_path):
        """Advisor returns a valid next_node from allowed_next; the loop uses it."""

        class FakeProvider:
            def advise(self, context):
                # Verify context is filtered (no factor code, no raw state)
                assert "factor_code" not in context
                assert "raw_state" not in context
                assert "allowed_next" in context
                return {"next_node": "crossover", "reason": "need more diversity"}

        orch_cfg = {
            "enabled": True,
            "start_node": "decider",
            "max_steps_per_cycle": 4,
            "nodes": [
                {
                    "id": "decider",
                    "kind": "decision",
                    "decision_mode": "llm_advisor",
                    "allowed_next": ["mutation", "crossover"],
                    "fallback_next": "mutation",
                    "next": [],
                },
                {
                    "id": "mutation",
                    "kind": "terminal",
                    "next": [],
                },
                {
                    "id": "crossover",
                    "kind": "terminal",
                    "next": [],
                },
            ],
            "conditions": [],
        }

        scheduler = self._make_scheduler_with_advisor(tmp_path, orch_cfg)
        scheduler._llm_advisor_provider = FakeProvider()

        # Do NOT mock _execute_orchestrated_action — let the real wiring run
        result = scheduler._run_orchestrated_cycle()

        # The trace should show advisor-selected next node
        trace = result["orchestration_trace"]
        assert len(trace["steps"]) >= 1
        step0 = trace["steps"][0]
        assert step0["next_node"] == "crossover"
        assert step0["action"] == "llm_advisor"

    def test_phase6_llm_advisor_invalid_next_node_falls_back(self, tmp_path):
        """Advisor returns a next_node NOT in allowed_next; loop uses fallback_next."""

        class FakeBadProvider:
            def advise(self, context):
                return {"next_node": "unknown_node", "reason": "bad choice"}

        orch_cfg = {
            "enabled": True,
            "start_node": "decider",
            "max_steps_per_cycle": 4,
            "nodes": [
                {
                    "id": "decider",
                    "kind": "decision",
                    "decision_mode": "llm_advisor",
                    "allowed_next": ["mutation", "crossover"],
                    "fallback_next": "mutation",
                    "next": [],
                },
                {
                    "id": "mutation",
                    "kind": "terminal",
                    "next": [],
                },
                {
                    "id": "crossover",
                    "kind": "terminal",
                    "next": [],
                },
            ],
            "conditions": [],
        }

        scheduler = self._make_scheduler_with_advisor(tmp_path, orch_cfg)
        scheduler._llm_advisor_provider = FakeBadProvider()

        result = scheduler._run_orchestrated_cycle()

        # The trace should show fallback to 'mutation'
        trace = result["orchestration_trace"]
        assert len(trace["steps"]) >= 1
        step0 = trace["steps"][0]
        assert step0["next_node"] == "mutation"

    def test_phase6_llm_advisor_provider_exception_falls_back(self, tmp_path):
        """Advisor provider raises exception; loop uses fallback_next without crashing."""

        class FailingProvider:
            def advise(self, context):
                raise RuntimeError("LLM service unavailable")

        orch_cfg = {
            "enabled": True,
            "start_node": "decider",
            "max_steps_per_cycle": 4,
            "nodes": [
                {
                    "id": "decider",
                    "kind": "decision",
                    "decision_mode": "llm_advisor",
                    "allowed_next": ["mutation", "crossover"],
                    "fallback_next": "mutation",
                    "next": [],
                },
                {
                    "id": "mutation",
                    "kind": "terminal",
                    "next": [],
                },
                {
                    "id": "crossover",
                    "kind": "terminal",
                    "next": [],
                },
            ],
            "conditions": [],
        }

        scheduler = self._make_scheduler_with_advisor(tmp_path, orch_cfg)
        scheduler._llm_advisor_provider = FailingProvider()

        # Should not raise — must fall back gracefully
        result = scheduler._run_orchestrated_cycle()

        trace = result["orchestration_trace"]
        assert len(trace["steps"]) >= 1
        step0 = trace["steps"][0]
        assert step0["next_node"] == "mutation"

    def test_phase6_llm_advisor_malformed_output_falls_back(self, tmp_path):
        """Advisor returns malformed JSON string; loop uses fallback_next."""

        class MalformedProvider:
            def advise(self, context):
                return "not valid json{{{ "

        orch_cfg = {
            "enabled": True,
            "start_node": "decider",
            "max_steps_per_cycle": 4,
            "nodes": [
                {
                    "id": "decider",
                    "kind": "decision",
                    "decision_mode": "llm_advisor",
                    "allowed_next": ["mutation", "crossover"],
                    "fallback_next": "mutation",
                    "next": [],
                },
                {
                    "id": "mutation",
                    "kind": "terminal",
                    "next": [],
                },
                {
                    "id": "crossover",
                    "kind": "terminal",
                    "next": [],
                },
            ],
            "conditions": [],
        }

        scheduler = self._make_scheduler_with_advisor(tmp_path, orch_cfg)
        scheduler._llm_advisor_provider = MalformedProvider()

        result = scheduler._run_orchestrated_cycle()

        trace = result["orchestration_trace"]
        assert len(trace["steps"]) >= 1
        step0 = trace["steps"][0]
        assert step0["next_node"] == "mutation"

    def test_phase6_llm_advisor_missing_next_node_falls_back(self, tmp_path):
        """Advisor returns dict without 'next_node' key; loop uses fallback_next."""

        class IncompleteProvider:
            def advise(self, context):
                return {"reason": "I don't know"}

        orch_cfg = {
            "enabled": True,
            "start_node": "decider",
            "max_steps_per_cycle": 4,
            "nodes": [
                {
                    "id": "decider",
                    "kind": "decision",
                    "decision_mode": "llm_advisor",
                    "allowed_next": ["mutation", "crossover"],
                    "fallback_next": "mutation",
                    "next": [],
                },
                {
                    "id": "mutation",
                    "kind": "terminal",
                    "next": [],
                },
                {
                    "id": "crossover",
                    "kind": "terminal",
                    "next": [],
                },
            ],
            "conditions": [],
        }

        scheduler = self._make_scheduler_with_advisor(tmp_path, orch_cfg)
        scheduler._llm_advisor_provider = IncompleteProvider()

        result = scheduler._run_orchestrated_cycle()

        trace = result["orchestration_trace"]
        assert len(trace["steps"]) >= 1
        step0 = trace["steps"][0]
        assert step0["next_node"] == "mutation"

    def test_phase6_llm_advisor_context_is_filtered(self, tmp_path):
        """Advisor context must not contain factor code or internal objects."""

        captured_context = {}

        class CapturingProvider:
            def advise(self, context):
                captured_context.update(context)
                return {"next_node": "mutation", "reason": "test"}

        orch_cfg = {
            "enabled": True,
            "start_node": "decider",
            "max_steps_per_cycle": 4,
            "nodes": [
                {
                    "id": "decider",
                    "kind": "decision",
                    "decision_mode": "llm_advisor",
                    "allowed_next": ["mutation", "crossover"],
                    "fallback_next": "mutation",
                    "next": [],
                },
                {
                    "id": "mutation",
                    "kind": "terminal",
                    "next": [],
                },
                {
                    "id": "crossover",
                    "kind": "terminal",
                    "next": [],
                },
            ],
            "conditions": [],
        }

        scheduler = self._make_scheduler_with_advisor(tmp_path, orch_cfg)
        scheduler._llm_advisor_provider = CapturingProvider()

        result = scheduler._run_orchestrated_cycle()

        # Verify context contains only allowed fields
        expected_keys = {
            "cycle_id",
            "current_node",
            "step_index",
            "generated_factors",
            "pass_rate",
            "active_parents",
            "diversity_score",
            "consecutive_failures",
            "allowed_next",
        }
        assert set(captured_context.keys()) == expected_keys
        assert "factor_code" not in captured_context
        assert "raw_state" not in captured_context
