from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import types

if "quantaalpha.factors.experiment" not in sys.modules:
    experiment_stub = types.ModuleType("quantaalpha.factors.experiment")
    experiment_stub.QlibFactorExperiment = object
    sys.modules["quantaalpha.factors.experiment"] = experiment_stub

from quantaalpha.factors.runner import QlibFactorRunner


def test_develop_logs_backtest_boundaries(tmp_path: Path) -> None:
    runner = object.__new__(QlibFactorRunner)

    workspace = SimpleNamespace(
        workspace_path=tmp_path / "ws",
        before_execute=lambda: None,
        execute=lambda **kwargs: ("result-frame", "executor-log"),
    )
    exp = SimpleNamespace(
        based_experiments=[],
        sub_workspace_list=[object(), object(), None],
        experiment_workspace=workspace,
        result=None,
    )

    fake_logger = SimpleNamespace(info=MagicMock(), warning=MagicMock())

    with patch("quantaalpha.factors.runner.logger", fake_logger):
        result = QlibFactorRunner.develop.__wrapped__(runner, exp, use_local=True)

    messages = [call.args[0] for call in fake_logger.info.call_args_list]

    assert any("Execute factor backtest" in message for message in messages)
    assert any("Backtest workspace ready" in message for message in messages)
    assert any("Backtest execution finished" in message for message in messages)
    assert result.result == "result-frame"


def test_develop_runs_correlation_dedup_when_sota_factors_exist(tmp_path: Path) -> None:
    runner = object.__new__(QlibFactorRunner)
    (tmp_path / "ws").mkdir()

    sota_df = __import__("pandas").DataFrame(
        {"old_factor": [1.0, 2.0]},
        index=__import__("pandas").MultiIndex.from_tuples(
            [("2024-01-01", "A"), ("2024-01-02", "A")],
            names=["datetime", "instrument"],
        ),
    )
    new_df = __import__("pandas").DataFrame(
        {"new_factor": [2.0, 3.0]},
        index=sota_df.index,
    )

    workspace = SimpleNamespace(
        workspace_path=tmp_path / "ws",
        before_execute=lambda: None,
        execute=lambda **kwargs: ("result-frame", "executor-log"),
    )
    exp = SimpleNamespace(
        based_experiments=[SimpleNamespace(result="ok"), SimpleNamespace(result="ok")],
        sub_workspace_list=[],
        experiment_workspace=workspace,
        result=None,
    )

    calls = {"dedup": 0}

    def fake_process_factor_data(arg):
        if isinstance(arg, list):
            return sota_df
        return new_df

    def fake_dedup(sota, new):
        calls["dedup"] += 1
        return new

    runner.process_factor_data = fake_process_factor_data
    runner.deduplicate_new_factors = fake_dedup
    runner._apply_combined_quality_gate = lambda df: df

    result = QlibFactorRunner.develop.__wrapped__(runner, exp, use_local=True)

    assert calls["dedup"] == 1
    assert result.result == "result-frame"
