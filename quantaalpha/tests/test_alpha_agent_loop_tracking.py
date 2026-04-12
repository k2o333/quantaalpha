"""Tests for AlphaAgentLoop fail-fast invariants in factor construction and tracking."""
import pytest
import sys
from unittest.mock import MagicMock, patch, PropertyMock

from quantaalpha.core.exception import FactorEmptyError


def _ensure_stop_event_in_module():
    """Ensure STOP_EVENT exists in the loop module for tests that bypass __init__."""
    import quantaalpha.pipeline.loop as loop_module
    if not hasattr(loop_module, 'STOP_EVENT'):
        loop_module.STOP_EVENT = None


class TestFactorConstructRejectsEmptyExperiment:
    """factor_construct must raise FactorEmptyError when constructor returns no sub_tasks."""

    def test_factor_construct_rejects_empty_experiment(self):
        """When factor_constructor.convert returns an experiment with no sub_tasks,
        factor_construct must raise FactorEmptyError, not silently continue."""
        from quantaalpha.pipeline.loop import AlphaAgentLoop
        _ensure_stop_event_in_module()

        # Create a minimal mock loop that bypasses __init__
        loop = object.__new__(AlphaAgentLoop)
        loop.factor_constructor = MagicMock()
        loop._failure_tracker = MagicMock()
        loop._failure_tracker._round_in_progress = False
        loop.trace = MagicMock()
        loop._step_model_routing = {}  # Required by _with_step_model

        # Mock factor_constructor to return an experiment with empty sub_tasks
        mock_experiment = MagicMock()
        mock_experiment.sub_tasks = []
        loop.factor_constructor.convert.return_value = mock_experiment

        prev_out = {"factor_propose": MagicMock()}

        with pytest.raises(FactorEmptyError, match="[Nn]o.*factor|[Ee]mpty|[Nn]o.*sub_task|[Nn]o.*task"):
            AlphaAgentLoop.factor_construct(loop, prev_out)


class TestTrackCoderResultRejectsFactorIdMismatch:
    """_track_coder_result must raise FactorEmptyError when tracking lists have mismatched lengths."""

    def test_track_coder_result_rejects_factor_id_mismatch(self):
        """When sub_tasks and sub_workspace_list lengths differ from _current_round_factors,
        _track_coder_result must raise FactorEmptyError, not leak IndexError."""
        from quantaalpha.pipeline.loop import AlphaAgentLoop

        # Create a minimal mock loop
        loop = object.__new__(AlphaAgentLoop)
        loop._current_round_factors = ["factor_a", "factor_b"]  # 2 factors
        loop._failure_tracker = MagicMock()

        # Experiment has 3 tasks/workspaces but only 2 factor_ids -> mismatch
        mock_experiment = MagicMock()
        mock_task = MagicMock()
        mock_task.factor_name = "test_factor"
        mock_task.factor_expression = "expr"
        mock_experiment.sub_tasks = [mock_task, mock_task, mock_task]  # 3 tasks
        mock_experiment.sub_workspace_list = [MagicMock(), MagicMock(), MagicMock()]  # 3 workspaces

        # Call the real _track_coder_result method
        with pytest.raises(FactorEmptyError, match="[Mm]ismatch|[Ll]ength|[Cc]ount|[Tt]racking"):
            AlphaAgentLoop._track_coder_result(loop, mock_experiment)


class TestTrackCoderResultRejectsWorkspaceMismatch:
    """_track_coder_result must raise FactorEmptyError when workspace count mismatches tasks."""

    def test_track_coder_result_rejects_workspace_count_mismatch(self):
        """When sub_workspace_list length doesn't match sub_tasks length,
        _track_coder_result must raise FactorEmptyError, not partial tracking."""
        from quantaalpha.pipeline.loop import AlphaAgentLoop

        loop = object.__new__(AlphaAgentLoop)
        loop._current_round_factors = ["factor_x"]  # 1 factor
        loop._failure_tracker = MagicMock()

        mock_experiment = MagicMock()
        mock_task = MagicMock()
        mock_task.factor_name = "test_factor"
        mock_task.factor_expression = "expr"
        mock_experiment.sub_tasks = [mock_task]  # 1 task
        mock_experiment.sub_workspace_list = [MagicMock(), MagicMock()]  # 2 workspaces -> mismatch

        with pytest.raises(FactorEmptyError, match="[Mm]ismatch|[Ll]ength|[Cc]ount|[Ww]orkspace"):
            AlphaAgentLoop._track_coder_result(loop, mock_experiment)


class TestFactorCalculateRejectsNoneCoderOutput:
    """factor_calculate must raise FactorEmptyError when coder returns None."""

    def test_factor_calculate_rejects_none_coder_output(self):
        """When coder.develop returns None, factor_calculate must raise FactorEmptyError."""
        from quantaalpha.pipeline.loop import AlphaAgentLoop
        _ensure_stop_event_in_module()

        loop = object.__new__(AlphaAgentLoop)
        loop.coder = MagicMock()
        loop.coder.develop.return_value = None

        prev_out = {"factor_construct": MagicMock()}

        with pytest.raises(FactorEmptyError, match="[Cc]oder|[Nn]one|[Ee]mpty|[Nn]o.*factor"):
            AlphaAgentLoop.factor_calculate(loop, prev_out)

    def test_factor_calculate_rejects_empty_coder_output(self):
        """When coder.develop returns experiment with no sub_tasks, factor_calculate must raise FactorEmptyError."""
        from quantaalpha.pipeline.loop import AlphaAgentLoop
        _ensure_stop_event_in_module()

        loop = object.__new__(AlphaAgentLoop)
        mock_experiment = MagicMock()
        mock_experiment.sub_tasks = []
        mock_experiment.sub_workspace_list = []
        loop.coder = MagicMock()
        loop.coder.develop.return_value = mock_experiment

        prev_out = {"factor_construct": MagicMock()}

        with pytest.raises(FactorEmptyError, match="[Cc]oder|[Ee]mpty|[Nn]o.*factor|[Nn]o.*sub_task"):
            AlphaAgentLoop.factor_calculate(loop, prev_out)
