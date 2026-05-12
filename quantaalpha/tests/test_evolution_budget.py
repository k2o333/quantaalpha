"""Tests for budget_seconds parameter in run_evolution_loop."""

import time
import inspect
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

    def test_bounded_llm_task_failure_classifier(self):
        """Known bounded LLM exhaustions are skip-worthy task failures."""
        from quantaalpha.pipeline.factor_mining import _is_bounded_llm_task_failure

        assert _is_bounded_llm_task_failure(RuntimeError("Failed to create call_structured after 1 retries."))
        assert _is_bounded_llm_task_failure(
            RuntimeError("Multi-hypothesis construct failed after 2 attempts: category=empty_factors")
        )
        assert _is_bounded_llm_task_failure(
            RuntimeError(
                "Factor proposal failed after 2 retries: expression acceptability failure for bad_factor"
            )
        )
        assert _is_bounded_llm_task_failure(RuntimeError("Feedback generation failed: timeout"))
        assert not _is_bounded_llm_task_failure(ValueError("unexpected data corruption"))

    def test_run_evolution_loop_uses_warning_for_bounded_llm_failures(self):
        """Evolution loop does not emit traceback-level logs for bounded LLM failures."""
        from quantaalpha.pipeline.factor_mining import run_evolution_loop

        source = inspect.getsource(run_evolution_loop)
        assert "_is_bounded_llm_task_failure" in source
        assert "Task skipped after bounded LLM failure" in source

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

    def test_evolution_task_passes_factor_store_kwargs_to_loop(self, tmp_path):
        """Evolution task AlphaAgentLoop receives parquet store and compact kwargs."""
        from quantaalpha.pipeline.evolution import RoundPhase
        from quantaalpha.pipeline.factor_mining import _run_evolution_task

        loop = MagicMock()
        loop._get_trajectory_data.return_value = {}

        with patch("quantaalpha.pipeline.loop.AlphaAgentLoop", return_value=loop) as MockLoop:
            _run_evolution_task(
                task={
                    "phase": RoundPhase.ORIGINAL,
                    "direction_id": 0,
                    "round_idx": 0,
                    "parent_trajectories": [],
                },
                directions=["test direction"],
                step_n=1,
                use_local=True,
                user_direction="test direction",
                log_root=str(tmp_path),
                stop_event=None,
                quality_gate_cfg={},
                factor_store_kwargs={
                    "parquet_store_path": str(tmp_path / "parquet_store"),
                    "parquet_compact_config": {"delta_file_threshold": 3},
                },
            )

        kwargs = MockLoop.call_args.kwargs
        assert kwargs["parquet_store_path"] == str(tmp_path / "parquet_store")
        assert kwargs["parquet_compact_config"] == {"delta_file_threshold": 3}
