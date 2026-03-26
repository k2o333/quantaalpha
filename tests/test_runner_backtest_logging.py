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
