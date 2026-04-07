"""Tests for pipeline_mode integration in DefaultMiningScheduler."""

import pytest


class TestMiningSchedulerPipelineMode:
    """Tests for pipeline_mode parameter and behavior."""

    def test_mining_scheduler_pipeline_mode_init(self):
        """DefaultMiningScheduler accepts pipeline_mode parameter."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler(
            pipeline_mode=True,
            quality_gate_config={"min_ic": 0.02},
        )
        assert scheduler._pipeline_mode is True
        assert scheduler._quality_gate_config == {"min_ic": 0.02}

    def test_mining_scheduler_legacy_mode_unchanged(self):
        """DefaultMiningScheduler with pipeline_mode=False uses legacy path."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler(pipeline_mode=False)
        assert scheduler._pipeline_mode is False
        # Should have legacy methods
        assert hasattr(scheduler, "_generate_via_llm")
        assert hasattr(scheduler, "_generate_via_mutation")

    def test_mining_scheduler_pipeline_mode_defaults(self):
        """DefaultMiningScheduler defaults pipeline_mode to False."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler()
        assert scheduler._pipeline_mode is False

    def test_mining_scheduler_accepts_evolution_cfg(self):
        """DefaultMiningScheduler accepts evolution_cfg parameter."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler(
            pipeline_mode=True,
            evolution_cfg={"enabled": True, "max_rounds": 2},
        )
        assert scheduler._evolution_cfg == {"enabled": True, "max_rounds": 2}

    def test_mining_scheduler_accepts_state_cfg(self):
        """DefaultMiningScheduler accepts state_cfg parameter."""
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler(
            pipeline_mode=True,
            state_cfg={"steps_per_mining": 3, "max_pool_size": 200},
        )
        assert scheduler._state_cfg == {"steps_per_mining": 3, "max_pool_size": 200}

    def test_pipeline_mode_run_mining_executes_pipeline_path(self):
        """pipeline_mode=True calls _run_pipeline_mining, not legacy path."""
        from unittest.mock import patch
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler(
            pipeline_mode=True,
            state_cfg={"steps_per_mining": 3, "max_pool_size": 100},
        )

        with patch.object(
            scheduler,
            "_run_pipeline_mining",
            return_value={
                "factors_generated": 2,
                "factors_validated": 2,
                "factors_added": 2,
                "factor_ids": ["factor_a", "factor_b"],
                "errors": [],
            },
        ) as mock_pipeline:
            result = scheduler.run_mining()

            mock_pipeline.assert_called_once()
            assert result.factors_generated == 2
            assert result.factors_added == 2
            assert result.factor_ids == ["factor_a", "factor_b"]

    def test_legacy_mode_run_mining_uses_generate_factors(self):
        """pipeline_mode=False calls _generate_factors, not pipeline path."""
        from unittest.mock import patch
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler(pipeline_mode=False)

        with patch.object(scheduler, "_retrieve_context", return_value="context"):
            with patch.object(scheduler, "_generate_factors", return_value=[]) as mock_generate:
                result = scheduler.run_mining()

                mock_generate.assert_called_once_with("context")
                assert result.factors_generated == 0


class TestMaxLoopsPerCycle:
    """Tests for Bug 5: max_loops_per_cycle should run multiple AlphaAgentLoop iterations."""

    def test_max_loops_per_cycle_runs_multiple_loops(self):
        """_run_pipeline_mining runs AlphaAgentLoop max_loops_per_cycle times when no factors found.

        Bug 5: Previously only ran a single AlphaAgentLoop regardless of max_loops_per_cycle config.
        """
        from unittest.mock import patch, MagicMock
        import sys
        import types

        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler(
            pipeline_mode=True,
            state_cfg={
                "log_root": "/tmp/test_max_loops",
                "steps_per_mining": 2,
                "max_loops_per_cycle": 3,
            },
            escalation_cfg={"enabled": False},
            evolution_cfg={"enabled": False},
        )

        loop_run_count = []

        class MockLoop:
            def __init__(self, *args, **kwargs):
                pass

            def run(self, step_n=None, stop_event=None):
                loop_run_count.append(1)

        fake_loop_mod = types.ModuleType("quantaalpha.pipeline.loop")
        fake_loop_mod.AlphaAgentLoop = MockLoop
        sys.modules["quantaalpha.pipeline.loop"] = fake_loop_mod

        try:
            with (
                patch.object(scheduler, "_get_mining_direction", return_value=None),
                patch.object(scheduler, "_state_manager", None),
                patch.object(scheduler, "_extract_factors_from_loop", return_value=[]),
                patch.object(scheduler, "_persist_state"),
            ):
                scheduler._run_pipeline_mining()
        finally:
            del sys.modules["quantaalpha.pipeline.loop"]

        assert len(loop_run_count) == 3, f"Expected AlphaAgentLoop to run 3 times (max_loops_per_cycle=3), but it ran {len(loop_run_count)} time(s). max_loops_per_cycle config is not being used."

    def test_max_loops_per_cycle_stops_early_on_success(self):
        """_run_pipeline_mining stops looping when factors are found."""
        from unittest.mock import patch, MagicMock
        import sys
        import types

        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler(
            pipeline_mode=True,
            state_cfg={
                "log_root": "/tmp/test_max_loops_early_stop",
                "steps_per_mining": 2,
                "max_loops_per_cycle": 3,
            },
            escalation_cfg={"enabled": False},
            evolution_cfg={"enabled": False},
        )

        loop_run_count = []
        call_num = [0]

        class MockLoop:
            def __init__(self, *args, **kwargs):
                pass

            def run(self, step_n=None, stop_event=None):
                loop_run_count.append(1)
                call_num[0] += 1

        fake_loop_mod = types.ModuleType("quantaalpha.pipeline.loop")
        fake_loop_mod.AlphaAgentLoop = MockLoop
        sys.modules["quantaalpha.pipeline.loop"] = fake_loop_mod

        try:
            # First call returns factors (success), so loop should stop after 1 iteration
            def mock_extract(loop):
                if call_num[0] == 1:
                    return ["factor_1"]
                return []

            with (
                patch.object(scheduler, "_get_mining_direction", return_value=None),
                patch.object(scheduler, "_state_manager", None),
                patch.object(scheduler, "_extract_factors_from_loop", side_effect=mock_extract),
                patch.object(scheduler, "_persist_state"),
            ):
                scheduler._run_pipeline_mining()
        finally:
            del sys.modules["quantaalpha.pipeline.loop"]

        assert len(loop_run_count) == 1, f"Expected loop to stop after 1 iteration (factors found), but it ran {len(loop_run_count)} time(s)."


class TestExtractFactorsFromLoop:
    """Tests for _extract_factors_from_loop method name matching."""

    def test_extract_factors_from_loop_uses_underscore_method(self):
        """_extract_factors_from_loop must call _get_successful_factor_ids (underscore-prefixed).

        Bug: implementations.py calls loop.get_successful_factor_ids() but the actual
        method on AlphaAgentLoop is _get_successful_factor_ids().
        """
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler()

        class MockLoop:
            def _get_successful_factor_ids(self):
                return ["factor_a", "factor_b"]

        mock_loop = MockLoop()
        factor_ids = scheduler._extract_factors_from_loop(mock_loop)

        assert factor_ids == ["factor_a", "factor_b"], f"Expected ['factor_a', 'factor_b'], got {factor_ids}. _extract_factors_from_loop should call _get_successful_factor_ids()"


class TestOrchestrationRuntimeEntry:
    """Tests for Phase 3: orchestration runtime entry in _run_pipeline_mining()."""

    def test_orchestration_disabled_uses_existing_pipeline_path(self):
        """orchestration.enabled=false still uses existing _run_pipeline_mining path."""
        from unittest.mock import patch, MagicMock
        import sys
        import types

        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler(
            pipeline_mode=True,
            state_cfg={
                "log_root": "/tmp/test_orch_disabled",
                "steps_per_mining": 2,
            },
            escalation_cfg={"enabled": False},
            evolution_cfg={"enabled": False},
            orchestration_cfg={"enabled": False},
        )

        loop_run_count = []

        class MockLoop:
            def __init__(self, *args, **kwargs):
                pass

            def run(self, step_n=None, stop_event=None):
                loop_run_count.append(1)

        fake_loop_mod = types.ModuleType("quantaalpha.pipeline.loop")
        fake_loop_mod.AlphaAgentLoop = MockLoop
        sys.modules["quantaalpha.pipeline.loop"] = fake_loop_mod

        try:
            with (
                patch.object(scheduler, "_get_mining_direction", return_value=None),
                patch.object(scheduler, "_state_manager", None),
                patch.object(scheduler, "_extract_factors_from_loop", return_value=[]),
                patch.object(scheduler, "_persist_state"),
                patch("quantaalpha.continuous.implementations.logger"),  # mock logger.set_storages_path
            ):
                result = scheduler._run_pipeline_mining()

            # Should NOT call _run_orchestrated_cycle since orchestration is disabled
            assert result["factors_generated"] == 0
        finally:
            del sys.modules["quantaalpha.pipeline.loop"]

    def test_orchestration_enabled_calls_run_orchestrated_cycle(self):
        """orchestration.enabled=true calls _run_orchestrated_cycle instead of existing path."""
        from unittest.mock import patch, MagicMock

        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler(
            pipeline_mode=True,
            state_cfg={
                "log_root": "/tmp/test_orch_enabled",
                "steps_per_mining": 2,
            },
            escalation_cfg={"enabled": False},
            evolution_cfg={"enabled": False},
            orchestration_cfg={
                "enabled": True,
                "mode": "conditional_flow",
                "max_steps_per_cycle": 3,
                "start_node": "original",
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

        # _run_orchestrated_cycle should exist and be callable
        assert hasattr(scheduler, "_run_orchestrated_cycle"), (
            "DefaultMiningScheduler should have _run_orchestrated_cycle method when orchestration is enabled"
        )

        # Mock _run_orchestrated_cycle to verify it gets called
        with patch.object(
            scheduler,
            "_run_orchestrated_cycle",
            return_value={
                "factors_generated": 1,
                "factors_validated": 1,
                "factors_added": 1,
                "factor_ids": ["orch_factor_1"],
                "errors": [],
            },
        ) as mock_orch_cycle:
            result = scheduler._run_pipeline_mining()

            mock_orch_cycle.assert_called_once()
            assert result["factors_generated"] == 1
            assert result["factor_ids"] == ["orch_factor_1"]

    def test_orchestration_enabled_still_initializes_runtime_basics_and_persists(self):
        """orchestration.enabled=true still initializes state/workspace basics and persists state."""
        from unittest.mock import patch

        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        scheduler = DefaultMiningScheduler(
            pipeline_mode=True,
            state_cfg={
                "log_root": "/tmp/test_orch_runtime_basics",
                "steps_per_mining": 2,
            },
            escalation_cfg={"enabled": False},
            evolution_cfg={"enabled": False},
            orchestration_cfg={
                "enabled": True,
                "mode": "conditional_flow",
                "max_steps_per_cycle": 3,
                "start_node": "original",
                "nodes": [
                    {"id": "original", "kind": "action", "action": "original", "next": []}
                ],
                "conditions": [],
            },
        )

        with (
            patch.object(scheduler, "_init_state_manager") as mock_init_state_manager,
            patch.object(scheduler, "_run_orchestrated_cycle", return_value={
                "factors_generated": 0,
                "factors_validated": 0,
                "factors_added": 0,
                "factor_ids": [],
                "errors": [],
            }) as mock_orch_cycle,
            patch.object(scheduler, "_persist_state") as mock_persist_state,
            patch("quantaalpha.continuous.implementations.logger") as mock_logger,
        ):
            result = scheduler._run_pipeline_mining()

        mock_init_state_manager.assert_called_once()
        mock_orch_cycle.assert_called_once()
        mock_persist_state.assert_called_once()
        mock_logger.set_storages_path.assert_called_once()
        assert result["errors"] == []
