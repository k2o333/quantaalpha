"""Tests for budget_seconds parameter in run_evolution_loop."""

import time
from unittest.mock import patch, MagicMock

import pytest


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
