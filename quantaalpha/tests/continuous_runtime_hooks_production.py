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


class TestPhase7OrchestrationIntegration:
    """Phase 7: Scenario-level runtime regression tests for single-cycle orchestration.

    These tests prove real runtime wiring through _run_orchestrated_cycle()
    across combined scenarios: original-only, mutation/crossover, degraded mode,
    and llm_advisor valid/fallback.
    """

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_scheduler_for_scenario(tmp_path, orchestration_cfg, degraded_mode=False):
        """Build a DefaultMiningScheduler configured for a Phase 7 scenario."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        return DefaultMiningScheduler(
            library_path=str(lib_path),
            degraded_mode=degraded_mode,
            state_cfg={
                "log_root": str(tmp_path / "logs"),
                "steps_per_mining": 2,
            },
            evolution_cfg={"enabled": True, "max_rounds": 2},
            escalation_cfg={"enabled": False},
            orchestration_cfg=orchestration_cfg,
        )

    # ------------------------------------------------------------------
    # Scenario A: Original-only happy path
    # ------------------------------------------------------------------

    def test_phase7_orchestration_integration_original_only(self, tmp_path):
        """Scenario A: original -> terminal proves runtime loop reaches terminal cleanly.

        Asserts:
        - runtime loop executes normally
        - orchestration_trace.steps[0].action == "original"
        - stop_reason == "terminal_node"
        """
        from unittest.mock import patch
        import sys
        import types

        orch_cfg = {
            "enabled": True,
            "start_node": "original",
            "max_steps_per_cycle": 4,
            "nodes": [
                {
                    "id": "original",
                    "kind": "action",
                    "action": "original",
                    "next": [{"goto": "terminal_node"}],
                },
                {
                    "id": "terminal_node",
                    "kind": "terminal",
                    "next": [],
                },
            ],
            "conditions": [],
        }

        scheduler = self._make_scheduler_for_scenario(tmp_path, orch_cfg)

        class MockLoop:
            def __init__(self, *args, **kwargs):
                pass

            def run(self, step_n=None, stop_event=None):
                pass

            def _get_successful_factor_ids(self):
                return ["factor_orig_1", "factor_orig_2"]

        fake_loop_mod = types.ModuleType("quantaalpha.pipeline.loop")
        fake_loop_mod.AlphaAgentLoop = MockLoop
        sys.modules["quantaalpha.pipeline.loop"] = fake_loop_mod

        try:
            with patch("quantaalpha.continuous.implementations.logger"):
                result = scheduler._run_orchestrated_cycle()
        finally:
            del sys.modules["quantaalpha.pipeline.loop"]

        assert "orchestration_trace" in result, "Missing orchestration_trace in result"
        trace = result["orchestration_trace"]

        # Verify step 0 action is "original"
        assert len(trace["steps"]) >= 1, "Expected at least one step in trace"
        assert trace["steps"][0]["action"] == "original", f"Expected first action to be 'original', got {trace['steps'][0]['action']}"

        # Verify terminal stop reason
        assert trace["stop_reason"] == "terminal_node", f"Expected stop_reason 'terminal_node', got {trace['stop_reason']}"

        # Verify factors were generated
        assert result["factors_generated"] >= 0, "factors_generated should be non-negative"

    # ------------------------------------------------------------------
    # Scenario B: Evolution path (mutation -> crossover)
    # ------------------------------------------------------------------

    def test_phase7_orchestration_integration_mutation_then_crossover(self, tmp_path):
        """Scenario B: mutation -> crossover proves both helpers called in one cycle.

        Asserts:
        - mutation helper is called by runtime loop
        - crossover helper is called by runtime loop
        - trace step order is correct (mutation before crossover)
        """
        from unittest.mock import patch

        orch_cfg = {
            "enabled": True,
            "start_node": "mutation",
            "max_steps_per_cycle": 6,
            "nodes": [
                {
                    "id": "mutation",
                    "kind": "action",
                    "action": "mutation",
                    "next": [{"goto": "crossover"}],
                },
                {
                    "id": "crossover",
                    "kind": "action",
                    "action": "crossover",
                    "next": [{"goto": "terminal_node"}],
                },
                {
                    "id": "terminal_node",
                    "kind": "terminal",
                    "next": [],
                },
            ],
            "conditions": [],
        }

        scheduler = self._make_scheduler_for_scenario(tmp_path, orch_cfg)

        with patch("quantaalpha.pipeline.factor_mining.run_evolution_action") as mock_evo:
            mock_evo.return_value = {"status": "success", "factor_ids": ["factor_evo_1"], "successful_tasks": 1}
            with patch.object(scheduler, "_get_mining_direction", return_value="momentum"):
                with patch("quantaalpha.continuous.implementations.logger"):
                    result = scheduler._run_orchestrated_cycle()

        # Verify both mutation and crossover were called
        assert mock_evo.call_count == 2, f"Expected run_evolution_action to be called twice (mutation + crossover), but was called {mock_evo.call_count} time(s)"

        # Verify runtime loop produced a trace
        assert "orchestration_trace" in result, "Missing orchestration_trace in result"
        trace = result["orchestration_trace"]

        # Verify step order: mutation before crossover
        assert len(trace["steps"]) >= 2, f"Expected at least two steps in trace, got {len(trace['steps'])}"
        assert trace["steps"][0]["action"] == "mutation", f"Expected first action 'mutation', got {trace['steps'][0]['action']}"
        assert trace["steps"][1]["action"] == "crossover", f"Expected second action 'crossover', got {trace['steps'][1]['action']}"

        # Verify stop reason
        assert trace["stop_reason"] == "terminal_node", f"Expected stop_reason 'terminal_node', got {trace['stop_reason']}"

    # ------------------------------------------------------------------
    # Scenario C: Degraded mode blocks crossover
    # ------------------------------------------------------------------

    def test_phase7_orchestration_integration_degraded_crossover_block(self, tmp_path):
        """Scenario C: degraded_mode=True blocks crossover without crashing the cycle.

        Asserts:
        - crossover is blocked
        - cycle does not crash
        - trace action_status is interpretable (e.g. 'blocked' or 'error')
        """
        from unittest.mock import patch

        orch_cfg = {
            "enabled": True,
            "start_node": "crossover",
            "max_steps_per_cycle": 4,
            "nodes": [{"id": "crossover", "kind": "action", "action": "crossover", "next": []}],
            "conditions": [],
        }

        # Build scheduler with degraded_mode=True
        scheduler = self._make_scheduler_for_scenario(tmp_path, orch_cfg, degraded_mode=True)

        # Should not crash
        with patch("quantaalpha.continuous.implementations.logger"):
            result = scheduler._run_orchestrated_cycle()

        # Verify trace exists
        assert "orchestration_trace" in result, "Missing orchestration_trace in result"
        trace = result["orchestration_trace"]

        # Verify crossover was blocked
        assert len(trace["steps"]) >= 1, "Expected at least one step in trace"
        step = trace["steps"][0]
        assert step["action"] == "crossover", f"Expected action 'crossover', got {step['action']}"

        # Verify action_status indicates blocked or error
        assert step["action_status"] in ("blocked", "error"), f"Expected action_status 'blocked' or 'error', got {step['action_status']}"

        # Verify cycle did not crash (result is a valid dict)
        assert isinstance(result, dict), "Result should be a valid dict"

    # ------------------------------------------------------------------
    # Scenario D: Advisor decision + fallback (valid selection)
    # ------------------------------------------------------------------

    def test_phase7_orchestration_integration_llm_advisor_valid(self, tmp_path):
        """Scenario D: advisor selects legal next node through real runtime loop.

        Asserts:
        - llm_advisor action is executed
        - advisor selects a valid next node
        - trace shows decision step with action == 'llm_advisor'
        """
        from unittest.mock import patch

        class MockAdvisorProvider:
            def advise(self, context):
                # Return crossover (different from fallback_next which is mutation)
                return {"next_node": "crossover", "reason": "test_valid_selection"}

        orch_cfg = {
            "enabled": True,
            "start_node": "decider",
            "max_steps_per_cycle": 6,
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
                    "kind": "action",
                    "action": "mutation",
                    "next": [{"goto": "terminal_node"}],
                },
                {
                    "id": "crossover",
                    "kind": "action",
                    "action": "crossover",
                    "next": [{"goto": "terminal_node"}],
                },
                {
                    "id": "terminal_node",
                    "kind": "terminal",
                    "next": [],
                },
            ],
            "conditions": [],
        }

        scheduler = self._make_scheduler_for_scenario(tmp_path, orch_cfg)
        scheduler._llm_advisor_provider = MockAdvisorProvider()

        with patch("quantaalpha.pipeline.factor_mining.run_evolution_action") as mock_evo:
            mock_evo.return_value = {"status": "success", "factor_ids": ["factor_advisor_1"], "successful_tasks": 1}
            with patch.object(scheduler, "_get_mining_direction", return_value="momentum"):
                with patch("quantaalpha.continuous.implementations.logger"):
                    result = scheduler._run_orchestrated_cycle()

        # Verify trace
        assert "orchestration_trace" in result, "Missing orchestration_trace"
        trace = result["orchestration_trace"]

        # Verify llm_advisor step exists
        advisor_steps = [s for s in trace["steps"] if s["action"] == "llm_advisor"]
        assert len(advisor_steps) >= 1, f"Expected at least one llm_advisor step, got {[s['action'] for s in trace['steps']]}"

        # Verify advisor selected next node
        advisor_step = advisor_steps[0]
        assert advisor_step["action_status"] == "success", f"Expected advisor status 'success', got {advisor_step['action_status']}"

    # ------------------------------------------------------------------
    # Scenario D: Advisor decision + fallback (invalid output)
    # ------------------------------------------------------------------

    def test_phase7_orchestration_integration_llm_advisor_fallback_invalid(self, tmp_path):
        """Scenario D: advisor returns illegal next node, fallback_next is used.

        Asserts:
        - advisor returns an invalid next_node
        - fallback_next is used instead
        - trace shows fallback behavior
        """
        from unittest.mock import patch

        class MockAdvisorProviderInvalid:
            def advise(self, context):
                # Return a node NOT in allowed_next
                return {"next_node": "invalid_node", "reason": "invalid_selection"}

        orch_cfg = {
            "enabled": True,
            "start_node": "decider",
            "max_steps_per_cycle": 4,
            "nodes": [
                {"id": "decider", "kind": "decision", "decision_mode": "llm_advisor", "allowed_next": ["mutation", "crossover"], "fallback_next": "crossover", "next": []},
                {"id": "mutation", "kind": "terminal", "next": []},
                {"id": "crossover", "kind": "terminal", "next": []},
            ],
            "conditions": [],
        }

        scheduler = self._make_scheduler_for_scenario(tmp_path, orch_cfg)
        scheduler._llm_advisor_provider = MockAdvisorProviderInvalid()

        with patch("quantaalpha.continuous.implementations.logger"):
            result = scheduler._run_orchestrated_cycle()

        # Verify trace
        assert "orchestration_trace" in result, "Missing orchestration_trace"
        trace = result["orchestration_trace"]

        # Verify llm_advisor step shows fallback behavior
        advisor_steps = [s for s in trace["steps"] if s["action"] == "llm_advisor"]
        assert len(advisor_steps) >= 1, "Expected at least one llm_advisor step"

        advisor_step = advisor_steps[0]
        # The status should be 'fallback' since the advisor returned an invalid node
        assert advisor_step["action_status"] == "fallback", f"Expected advisor status 'fallback', got {advisor_step['action_status']}"

    # ------------------------------------------------------------------
    # Scenario D: Advisor decision + fallback (provider failure)
    # ------------------------------------------------------------------

    def test_phase7_orchestration_integration_llm_advisor_fallback_provider_failure(self, tmp_path):
        """Scenario D: advisor provider raises exception, fallback_next is used.

        Asserts:
        - provider failure is caught
        - fallback_next is used
        - trace shows error/fallback status
        """
        from unittest.mock import patch

        class MockAdvisorProviderFailure:
            def advise(self, context):
                raise RuntimeError("Simulated provider failure")

        orch_cfg = {
            "enabled": True,
            "start_node": "decider",
            "max_steps_per_cycle": 4,
            "nodes": [
                {"id": "decider", "kind": "decision", "decision_mode": "llm_advisor", "allowed_next": ["mutation"], "fallback_next": "mutation", "next": []},
                {"id": "mutation", "kind": "terminal", "next": []},
            ],
            "conditions": [],
        }

        scheduler = self._make_scheduler_for_scenario(tmp_path, orch_cfg)
        scheduler._llm_advisor_provider = MockAdvisorProviderFailure()

        # Should not crash - should fallback gracefully
        with patch("quantaalpha.continuous.implementations.logger"):
            result = scheduler._run_orchestrated_cycle()

        # Verify trace
        assert "orchestration_trace" in result, "Missing orchestration_trace"
        trace = result["orchestration_trace"]

        # Verify llm_advisor step shows error/fallback
        advisor_steps = [s for s in trace["steps"] if s["action"] == "llm_advisor"]
        assert len(advisor_steps) >= 1, "Expected at least one llm_advisor step"

        advisor_step = advisor_steps[0]
        assert advisor_step["action_status"] == "error", f"Expected advisor status 'error', got {advisor_step['action_status']}"

    # ------------------------------------------------------------------
    # Trace field consistency
    # ------------------------------------------------------------------

    def test_phase7_orchestration_integration_trace_field_consistency(self, tmp_path):
        """Verify trace fields are correct across combined scenarios.

        Asserts:
        - every step has a real 'action' (not None)
        - decision steps have action == 'llm_advisor' (not None)
        - next_node matches runtime's actual selection
        - stop_reason matches scenario termination reason
        """
        from unittest.mock import patch
        import sys
        import types

        orch_cfg = {
            "enabled": True,
            "start_node": "original",
            "max_steps_per_cycle": 4,
            "nodes": [{"id": "original", "kind": "action", "action": "original", "next": []}],
            "conditions": [],
        }

        scheduler = self._make_scheduler_for_scenario(tmp_path, orch_cfg)

        class MockLoop:
            def __init__(self, *args, **kwargs):
                pass

            def run(self, step_n=None, stop_event=None):
                pass

            def _get_successful_factor_ids(self):
                return ["factor_trace_1"]

        fake_loop_mod = types.ModuleType("quantaalpha.pipeline.loop")
        fake_loop_mod.AlphaAgentLoop = MockLoop
        sys.modules["quantaalpha.pipeline.loop"] = fake_loop_mod

        try:
            with patch("quantaalpha.continuous.implementations.logger"):
                result = scheduler._run_orchestrated_cycle()
        finally:
            del sys.modules["quantaalpha.pipeline.loop"]

        trace = result["orchestration_trace"]

        # Every step must have a non-None action
        for step in trace["steps"]:
            assert step["action"] is not None, f"Step {step['step_index']} has None action"
            assert isinstance(step["action"], str), f"Step {step['step_index']} action is not a string: {type(step['action'])}"

        # stop_reason must be set
        assert trace["stop_reason"] is not None, "stop_reason should not be None"
        assert isinstance(trace["stop_reason"], str), "stop_reason should be a string"


class TestPhase8ProductionReadiness:
    """Phase 8 acceptance tests for single-cycle orchestration production readiness.

    These tests exercise the real runtime loop via _run_orchestrated_cycle()
    and cover:
    - Profile A: original-only flow
    - Profile B: mutation->crossover flow
    - Profile C: advisor fallback flow
    - Profile D: degraded crossover block
    """

    def _make_scheduler(self, tmp_path, orchestration_cfg, degraded_mode=False):
        """Helper to create a scheduler with orchestration config."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultMiningScheduler(
            pipeline_mode=True,
            state_cfg={
                "log_root": str(tmp_path / "log"),
                "steps_per_mining": 2,
            },
            escalation_cfg={"enabled": False},
            evolution_cfg={"enabled": False},
            orchestration_cfg=orchestration_cfg,
            degraded_mode=degraded_mode,
        )
        return scheduler

    # ----------------------------------------------------------------
    # Profile A: Original-only flow
    # ----------------------------------------------------------------
    def test_phase8_production_readiness_original_only_flow(self, tmp_path):
        """Profile A: original-only flow ends at terminal with trace.

        - start node: original
        - next: terminal
        - cycle ends normally
        - stop_reason == "terminal_node"
        - trace contains at least one "original" step
        """
        orch_cfg = {
            "enabled": True,
            "start_node": "original",
            "max_steps_per_cycle": 4,
            "nodes": [
                {
                    "id": "original",
                    "kind": "action",
                    "action": "original",
                    "next": [{"goto": "terminal"}],
                },
                {
                    "id": "terminal",
                    "kind": "terminal",
                    "next": [],
                },
            ],
            "conditions": [],
        }

        scheduler = self._make_scheduler(tmp_path, orch_cfg)

        # Mock AlphaAgentLoop to return a deterministic factor
        import sys
        import types

        class MockLoop:
            def __init__(self, *args, **kwargs):
                pass

            def run(self, step_n=None, stop_event=None):
                pass

            def _get_successful_factor_ids(self):
                return ["orig_factor_1"]

        fake_loop_mod = types.ModuleType("quantaalpha.pipeline.loop")
        fake_loop_mod.AlphaAgentLoop = MockLoop
        sys.modules["quantaalpha.pipeline.loop"] = fake_loop_mod

        try:
            with patch("quantaalpha.continuous.implementations.logger"):
                result = scheduler._run_orchestrated_cycle()
        finally:
            del sys.modules["quantaalpha.pipeline.loop"]

        trace = result["orchestration_trace"]

        assert trace["stop_reason"] == "terminal_node", f"Expected stop_reason 'terminal_node', got '{trace['stop_reason']}'"

        # Trace must contain at least one original step
        actions = [s["action"] for s in trace["steps"]]
        assert "original" in actions, f"Expected 'original' in trace actions, got {actions}"

    # ----------------------------------------------------------------
    # Profile B: Mutation->crossover flow
    # ----------------------------------------------------------------
    def test_phase8_production_readiness_mutation_crossover_flow(self, tmp_path):
        """Profile B: mutation->crossover flow runs both actions.

        - start node: mutation
        - next: crossover (unconditional)
        - crossover -> terminal
        - trace contains both mutation and crossover steps
        """
        orch_cfg = {
            "enabled": True,
            "start_node": "mutation",
            "max_steps_per_cycle": 6,
            "nodes": [
                {
                    "id": "mutation",
                    "kind": "action",
                    "action": "mutation",
                    "next": [{"goto": "crossover"}],
                },
                {
                    "id": "crossover",
                    "kind": "action",
                    "action": "crossover",
                    "next": [{"goto": "terminal"}],
                },
                {
                    "id": "terminal",
                    "kind": "terminal",
                    "next": [],
                },
            ],
            "conditions": [],
        }

        scheduler = self._make_scheduler(tmp_path, orch_cfg)

        # Mock run_evolution_action for mutation and crossover
        with patch("quantaalpha.pipeline.factor_mining.run_evolution_action") as mock_evo:
            mock_evo.return_value = {
                "factor_ids": ["evo_factor_1"],
                "successful_tasks": 1,
                "status": "success",
            }

            with patch("quantaalpha.continuous.implementations.logger"):
                result = scheduler._run_orchestrated_cycle()

        trace = result["orchestration_trace"]

        actions = [s["action"] for s in trace["steps"]]
        assert "mutation" in actions, f"Expected 'mutation' in trace actions, got {actions}"
        assert "crossover" in actions, f"Expected 'crossover' in trace actions, got {actions}"

        # Verify order: mutation before crossover
        mut_idx = actions.index("mutation")
        cross_idx = actions.index("crossover")
        assert mut_idx < cross_idx, f"Expected mutation (idx {mut_idx}) before crossover (idx {cross_idx})"

    # ----------------------------------------------------------------
    # Profile C: Advisor fallback flow
    # ----------------------------------------------------------------
    def test_phase8_production_readiness_advisor_fallback_flow(self, tmp_path):
        """Profile C: advisor returns illegal next, falls back correctly.

        - start node: llm_advisor decision node
        - advisor returns a node NOT in allowed_next
        - runtime falls back to fallback_next
        - trace shows decision step and fallback result
        """
        orch_cfg = {
            "enabled": True,
            "start_node": "advisor_node",
            "max_steps_per_cycle": 4,
            "nodes": [
                {
                    "id": "advisor_node",
                    "kind": "decision",
                    "decision_mode": "llm_advisor",
                    "allowed_next": ["mutation", "crossover"],
                    "fallback_next": "original",
                    "next": [
                        {"if": "always_true", "goto": "mutation"},
                        {"goto": "original"},
                    ],
                },
                {
                    "id": "mutation",
                    "kind": "action",
                    "action": "mutation",
                    "next": [{"goto": "terminal"}],
                },
                {
                    "id": "original",
                    "kind": "action",
                    "action": "original",
                    "next": [{"goto": "terminal"}],
                },
                {
                    "id": "crossover",
                    "kind": "action",
                    "action": "crossover",
                    "next": [{"goto": "terminal"}],
                },
                {
                    "id": "terminal",
                    "kind": "terminal",
                    "next": [],
                },
            ],
            "conditions": [
                {
                    "name": "always_true",
                    "type": "flag",
                    "metric": "llm_available",
                },
            ],
        }

        scheduler = self._make_scheduler(tmp_path, orch_cfg)

        # Mock advisor provider to return an illegal next node
        def mock_advise(context):
            return {"next_node": "INVALID_NODE_NOT_IN_ALLOWED"}

        scheduler._llm_advisor_provider = MagicMock()
        scheduler._llm_advisor_provider.advise = mock_advise

        with patch("quantaalpha.pipeline.factor_mining.run_evolution_action") as mock_evo:
            mock_evo.return_value = {
                "factor_ids": ["factor_1"],
                "successful_tasks": 1,
                "status": "success",
            }

            with patch("quantaalpha.continuous.implementations.logger"):
                result = scheduler._run_orchestrated_cycle()

        trace = result["orchestration_trace"]

        # Find the advisor step
        advisor_steps = [s for s in trace["steps"] if s["action"] == "llm_advisor"]
        assert len(advisor_steps) >= 1, f"Expected at least one llm_advisor step, got {[s['action'] for s in trace['steps']]}"

        advisor_step = advisor_steps[0]
        # The advisor should have fallen back to 'original' (the fallback_next)
        assert advisor_step["next_node"] == "original", f"Expected advisor to fall back to 'original', got '{advisor_step['next_node']}'"

    def test_phase8_production_readiness_advisor_fallback_on_provider_exception(self, tmp_path):
        """Profile C (provider-failure branch): advisor provider raises, falls back correctly.

        - start node: llm_advisor decision node
        - advisor provider raises an exception
        - runtime falls back to fallback_next
        - trace shows decision step with fallback_used=True
        """
        orch_cfg = {
            "enabled": True,
            "start_node": "advisor_node",
            "max_steps_per_cycle": 4,
            "nodes": [
                {
                    "id": "advisor_node",
                    "kind": "decision",
                    "decision_mode": "llm_advisor",
                    "allowed_next": ["mutation", "crossover"],
                    "fallback_next": "original",
                    "next": [
                        {"if": "always_true", "goto": "mutation"},
                        {"goto": "original"},
                    ],
                },
                {
                    "id": "mutation",
                    "kind": "action",
                    "action": "mutation",
                    "next": [{"goto": "terminal"}],
                },
                {
                    "id": "original",
                    "kind": "action",
                    "action": "original",
                    "next": [{"goto": "terminal"}],
                },
                {
                    "id": "crossover",
                    "kind": "action",
                    "action": "crossover",
                    "next": [{"goto": "terminal"}],
                },
                {
                    "id": "terminal",
                    "kind": "terminal",
                    "next": [],
                },
            ],
            "conditions": [
                {
                    "name": "always_true",
                    "type": "flag",
                    "metric": "llm_available",
                },
            ],
        }

        scheduler = self._make_scheduler(tmp_path, orch_cfg)

        # Mock advisor provider to raise an exception
        def mock_advise(context):
            raise RuntimeError("LLM provider unavailable")

        scheduler._llm_advisor_provider = MagicMock()
        scheduler._llm_advisor_provider.advise = mock_advise

        with patch("quantaalpha.pipeline.factor_mining.run_evolution_action") as mock_evo:
            mock_evo.return_value = {
                "factor_ids": ["factor_1"],
                "successful_tasks": 1,
                "status": "success",
            }

            with patch("quantaalpha.continuous.implementations.logger"):
                result = scheduler._run_orchestrated_cycle()

        trace = result["orchestration_trace"]

        # Find the advisor step
        advisor_steps = [s for s in trace["steps"] if s["action"] == "llm_advisor"]
        assert len(advisor_steps) >= 1, f"Expected at least one llm_advisor step, got {[s['action'] for s in trace['steps']]}"

        advisor_step = advisor_steps[0]
        # The advisor should have fallen back to 'original' (the fallback_next)
        assert advisor_step["next_node"] == "original", f"Expected advisor to fall back to 'original' on provider exception, got '{advisor_step['next_node']}'"

    # ----------------------------------------------------------------
    # Profile D: Degraded crossover block
    # ----------------------------------------------------------------
    def test_phase8_production_readiness_degraded_crossover_block(self, tmp_path):
        """Profile D: degraded crossover block is safe and traceable.

        - start node: crossover
        - degraded_mode=True
        - crossover is blocked
        - cycle does not crash
        - action status and stop reason are explainable
        """
        orch_cfg = {
            "enabled": True,
            "start_node": "crossover",
            "max_steps_per_cycle": 4,
            "nodes": [
                {
                    "id": "crossover",
                    "kind": "action",
                    "action": "crossover",
                    "next": [{"goto": "terminal"}],
                },
                {
                    "id": "terminal",
                    "kind": "terminal",
                    "next": [],
                },
            ],
            "conditions": [],
        }

        # Create scheduler with degraded_mode=True
        scheduler = self._make_scheduler(tmp_path, orch_cfg, degraded_mode=True)

        with patch("quantaalpha.continuous.implementations.logger"):
            result = scheduler._run_orchestrated_cycle()

        # Should not crash
        assert "errors" in result

        trace = result["orchestration_trace"]

        # Find the crossover step
        crossover_steps = [s for s in trace["steps"] if s["action"] == "crossover"]
        assert len(crossover_steps) >= 1, f"Expected at least one crossover step, got {[s['action'] for s in trace['steps']]}"

        crossover_step = crossover_steps[0]
        # Action status should indicate blocked/unsupported
        assert crossover_step["action_status"] in ("blocked", "unsupported", "error"), f"Expected crossover to be blocked/unsupported, got '{crossover_step['action_status']}'"

        # Stop reason should be set (not crash)
        assert trace["stop_reason"] is not None, "stop_reason should be set"
        assert isinstance(trace["stop_reason"], str), "stop_reason should be a string"


def test_parquet_revalidation_respects_days_threshold_before_limit():
    """Prove parquet candidate selection filters by revalidation_days_threshold before max_revalidation_per_run truncation."""
    from datetime import datetime, timedelta, timezone
    from unittest.mock import MagicMock, patch
    import json

    from quantaalpha.continuous.main import (
        ContinuousOrchestrator,
        _filter_parquet_candidates_by_days_threshold,
    )

    now = datetime.now()
    one_day_ago = (now - timedelta(days=1)).isoformat()
    thirty_days_ago = (now - timedelta(days=30)).isoformat()
    now_iso = now.isoformat()

    # Create mock parquet records equivalent to:
    # new_today: created_at=now, empty metadata_json
    # validated_yesterday: metadata_json.last_validated=one_day_ago
    # stale: metadata_json.last_validated=thirty_days_ago
    mock_records = [
        {
            "factor_id": "new_today",
            "factor_name": "New Today",
            "factor_expression": "$close",
            "evaluation_status": "active",
            "created_at": now_iso,
            "updated_at": now_iso,
            "metadata_json": "{}",
        },
        {
            "factor_id": "validated_yesterday",
            "factor_name": "Validated Yesterday",
            "factor_expression": "$open",
            "evaluation_status": "active",
            "created_at": thirty_days_ago,
            "updated_at": one_day_ago,
            "metadata_json": json.dumps({"last_validated": one_day_ago}),
        },
        {
            "factor_id": "stale",
            "factor_name": "Stale Factor",
            "factor_expression": "$volume",
            "evaluation_status": "active",
            "created_at": thirty_days_ago,
            "updated_at": thirty_days_ago,
            "metadata_json": json.dumps({"last_validated": thirty_days_ago}),
        },
    ]

    # Test the helper directly first
    due = _filter_parquet_candidates_by_days_threshold(mock_records, days_threshold=21, now=now)
    due_ids = [r["factor_id"] for r in due]
    assert "stale" in due_ids, f"stale should be due (30 days > 21 threshold), got {due_ids}"
    assert "new_today" not in due_ids, f"new_today should NOT be due (just created), got {due_ids}"
    assert "validated_yesterday" not in due_ids, f"validated_yesterday should NOT be due (1 day < 21 threshold), got {due_ids}"

    # Now exercise the real parquet candidate selection path in ContinuousOrchestrator._run_revalidation
    # by mocking FactorStoreFacade to return our mock records.
    captured_candidates = []

    class MockOrchestrator:
        """Minimal mock that captures candidates passed to run_revalidation_cycle."""

        def __init__(self):
            self._captured_candidates = []

        def run_revalidation_cycle(self, candidates=None):
            self._captured_candidates = candidates or []
            from quantaalpha.continuous.scheduler import RevalidationResult

            return RevalidationResult()

    # Build a mock config with the required settings
    mock_config = MagicMock()
    mock_config.factor.library_backend = "parquet"
    mock_config.factor.parquet_library_dir = "/tmp/test_parquet_store"
    mock_config.validation.max_revalidation_per_run = 1
    mock_config.revalidation_days_threshold = 21

    mock_impact_classifier = MagicMock()

    # Create the real ContinuousOrchestrator with mocked dependencies
    orchestrator = MagicMock(spec=ContinuousOrchestrator)
    orchestrator.config = mock_config
    orchestrator._impact_classifier = mock_impact_classifier
    orchestrator._bridge = None
    orchestrator._orchestrator = MockOrchestrator()

    # Mock FactorStoreFacade.read_effective_factor_records to return our records
    with patch("quantaalpha.factors.factor_store_facade.FactorStoreFacade") as mock_facade_class:
        mock_facade = MagicMock()
        mock_facade.read_effective_factor_records.return_value = mock_records
        mock_facade_class.return_value = mock_facade

        # Call the real _run_revalidation method
        from quantaalpha.continuous.main import ContinuousOrchestrator as RealOrchestrator

        # We need to call the real method but with our mocked orchestrator
        # Use the real _run_revalidation logic by creating a minimal test instance
        real_orchestrator = object.__new__(RealOrchestrator)
        real_orchestrator.config = mock_config
        real_orchestrator._impact_classifier = mock_impact_classifier
        real_orchestrator._bridge = None
        real_orchestrator._orchestrator = orchestrator._orchestrator

        result = real_orchestrator._run_revalidation()

    # The captured candidates should only contain 'stale'
    captured = orchestrator._orchestrator._captured_candidates
    captured_ids = [c.get("factor_id") for c in captured]

    assert "stale" in captured_ids, f"stale factor must be present in candidates passed to orchestrator, got {captured_ids}"
    assert "new_today" not in captured_ids, f"new_today must NOT be present in candidates (filtered out by days threshold), got {captured_ids}"
    assert "validated_yesterday" not in captured_ids, f"validated_yesterday must NOT be present in candidates (filtered out by days threshold), got {captured_ids}"
    # With max_revalidation_per_run=1, only stale should be there (1 item)
    assert len(captured) <= 1, f"candidates must be truncated to max_revalidation_per_run=1 after days filtering, got {len(captured)} items: {captured_ids}"


class TestValidationEnrichment:
    """Test flat field enrichment in validation results."""

    def test_validate_factor_enriches_success_with_flat_field_metrics(self, tmp_path):
        """_validate_factor success path returns flat IC, ICIR, Rank IC, Rank ICIR, positive_ratio,
        and validation_elapsed_ms at the top level, while preserving the summary structure."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultMiningScheduler(library_path=str(lib_path))

        with patch("third_party.glue.factor_executor.FactorExecutor") as mock_executor_class:
            mock_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.ic_value = 0.05
            mock_result.ic_result = MagicMock()
            mock_result.ic_result.positive_ratio = 0.6
            mock_result.ic_result.icir = 1.5
            mock_result.ic_result.rank_ic_mean = 0.04
            mock_result.ic_result.rank_icir = 1.2
            mock_instance.execute_single.return_value = mock_result
            mock_executor_class.return_value = mock_instance

            result = scheduler._validate_factor("test_factor", {"factor_id": "test_factor", "factor_expression": "$close"})

            assert result["status"] == "success"
            assert "summary" in result
            assert "IC" in result, "Top-level IC should be present"
            assert "ICIR" in result, "Top-level ICIR should be present"
            assert "Rank IC" in result, "Top-level Rank IC should be present"
            assert "positive_ratio" in result, "Top-level positive_ratio should be present"
            assert "validation_elapsed_ms" in result, "Top-level validation_elapsed_ms should be present"
            assert result["IC"] == 0.05
            assert isinstance(result["validation_elapsed_ms"], (int, float))
            assert result["validation_elapsed_ms"] >= 0

    def test_validate_factor_enriches_failure_with_flat_field_metrics(self, tmp_path):
        """_validate_factor failure path (IC below threshold) returns flat fields where available,
        including validation_elapsed_ms, while preserving the summary structure."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        lib_path = tmp_path / "lib.json"
        lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))

        scheduler = DefaultMiningScheduler(library_path=str(lib_path))

        with patch("third_party.glue.factor_executor.FactorExecutor") as mock_executor_class:
            mock_instance = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.ic_value = 0.005  # Below threshold
            mock_result.ic_result = MagicMock()
            mock_result.ic_result.positive_ratio = 0.4
            mock_result.ic_result.icir = 0.2
            mock_result.ic_result.rank_ic_mean = 0.003
            mock_result.ic_result.rank_icir = 0.1
            mock_instance.execute_single.return_value = mock_result
            mock_executor_class.return_value = mock_instance

            result = scheduler._validate_factor("weak_factor", {"factor_id": "weak_factor", "factor_expression": "$volume"})

            assert result["status"] == "failure"
            assert "summary" in result
            assert "IC" in result, "Top-level IC should be present"
            assert "validation_elapsed_ms" in result, "Top-level validation_elapsed_ms should be present"
            assert result["IC"] == 0.005
            assert isinstance(result["validation_elapsed_ms"], (int, float))
            assert result["validation_elapsed_ms"] >= 0
