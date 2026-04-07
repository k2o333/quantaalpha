"""Tests for budget_seconds parameter in run_evolution_loop."""

import time
from unittest.mock import patch, MagicMock

import pytest


class TestPhase4RuntimeEvolution:
    """Tests for Phase 4 runtime evolution adapter: run_evolution_action."""

    def test_phase4_runtime_evolution_mutation_adapter_calls_run_evolution_loop(self):
        """run_evolution_action delegates to run_evolution_loop with mutation flags."""
        from quantaalpha.pipeline.factor_mining import run_evolution_action

        with patch(
            "quantaalpha.pipeline.factor_mining.run_evolution_loop",
            return_value={"status": "success", "successful_tasks": 1},
        ) as mock_loop:
            result = run_evolution_action(
                initial_direction="mutation direction",
                evolution_cfg={"max_rounds": 3, "mutation_enabled": False, "crossover_enabled": True},
                exec_cfg={"steps_per_loop": 5, "use_local": True},
                planning_cfg={"enabled": False},
                mutation_enabled=True,
                crossover_enabled=False,
                budget_seconds=11,
                log_root="/tmp/phase4-mutation",
            )

        assert result["status"] == "success"
        mock_loop.assert_called_once_with(
            initial_direction="mutation direction",
            evolution_cfg={
                "max_rounds": 3,
                "mutation_enabled": True,
                "crossover_enabled": False,
            },
            exec_cfg={"steps_per_loop": 5, "use_local": True},
            planning_cfg={"enabled": False},
            stop_event=None,
            quality_gate_cfg=None,
            budget_seconds=11,
            log_root="/tmp/phase4-mutation",
        )

    def test_phase4_runtime_evolution_crossover_adapter_sets_flags(self):
        """run_evolution_action delegates to run_evolution_loop with crossover flags."""
        from quantaalpha.pipeline.factor_mining import run_evolution_action

        with patch(
            "quantaalpha.pipeline.factor_mining.run_evolution_loop",
            return_value={"status": "degraded", "successful_tasks": 0},
        ) as mock_loop:
            result = run_evolution_action(
                initial_direction="crossover direction",
                evolution_cfg={"max_rounds": 5, "mutation_enabled": True, "crossover_enabled": False},
                exec_cfg={"steps_per_loop": 7, "use_local": False},
                planning_cfg={"enabled": True},
                mutation_enabled=False,
                crossover_enabled=True,
                budget_seconds=13,
                log_root="/tmp/phase4-crossover",
            )

        assert result["status"] == "degraded"
        mock_loop.assert_called_once_with(
            initial_direction="crossover direction",
            evolution_cfg={
                "max_rounds": 5,
                "mutation_enabled": False,
                "crossover_enabled": True,
            },
            exec_cfg={"steps_per_loop": 7, "use_local": False},
            planning_cfg={"enabled": True},
            stop_event=None,
            quality_gate_cfg=None,
            budget_seconds=13,
            log_root="/tmp/phase4-crossover",
        )


class TestEvolutionBudget:
    """Tests for evolution budget enforcement."""

    def test_run_evolution_loop_budget_seconds(self):
        """run_evolution_loop respects budget_seconds and stops early."""
        from quantaalpha.pipeline.factor_mining import run_evolution_loop

        # Mock EvolutionController to simulate incomplete evolution
        with patch("quantaalpha.pipeline.factor_mining.EvolutionController") as MockController:
            mock_controller = MagicMock()
            mock_controller.is_complete.return_value = False
            mock_controller.get_next_task.return_value = None
            MockController.return_value = mock_controller

            # With very short budget, should exit quickly
            start = time.time()
            result = run_evolution_loop(
                initial_direction="test",
                evolution_cfg={
                    "max_rounds": 100,
                    "mutation_enabled": False,
                    "crossover_enabled": False,
                    "parallel_enabled": False,
                },
                exec_cfg={"steps_per_loop": 5, "use_local": True},
                planning_cfg={"enabled": False},
                stop_event=None,
                budget_seconds=1,  # 1 second budget
            )
            elapsed = time.time() - start

            # Should have exited within reasonable time (not waited for 100 rounds)
            assert elapsed < 5, f"Should exit quickly with 1s budget, took {elapsed:.1f}s"

    def test_run_evolution_loop_no_budget(self):
        """run_evolution_loop works without budget_seconds (backward compat)."""
        from quantaalpha.pipeline.factor_mining import run_evolution_loop

        with patch("quantaalpha.pipeline.factor_mining.EvolutionController") as MockController:
            mock_controller = MagicMock()
            mock_controller.is_complete.return_value = True  # Immediately complete
            MockController.return_value = mock_controller

            # Should work without budget_seconds
            result = run_evolution_loop(
                initial_direction="test",
                evolution_cfg={"max_rounds": 1, "mutation_enabled": False, "crossover_enabled": False},
                exec_cfg={"steps_per_loop": 5, "use_local": True},
                planning_cfg={"enabled": False},
                stop_event=None,
            )
            # Should complete normally
            assert result is not None
