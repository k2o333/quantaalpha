from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
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


def test_factor_template_noqlib_config_uses_mean_benchmark_mode() -> None:
    runner = object.__new__(QlibFactorRunner)
    runner.set_noqlib_config({"benchmark_mode": "mean"})

    config = runner._factor_template_to_noqlib_config(
        {
            "market": "csi300",
            "task": {
                "dataset": {"kwargs": {"handler": {"instruments": "csi300"}, "segments": {}}},
                "model": {"kwargs": {}},
            },
            "port_analysis_config": {
                "backtest": {"benchmark": "SH000300"},
                "strategy": {"kwargs": {"topk": 50, "n_drop": 5}},
            },
        },
        backend="vnpy",
    )

    assert config["backtest"]["backtest"]["benchmark"] == "mean"
    assert config["backtest_runtime"]["noqlib"]["benchmark_instruments"] == []


def test_factor_template_noqlib_config_slims_expanded_standard_frame_for_backtest() -> None:
    runner = object.__new__(QlibFactorRunner)
    runner.set_noqlib_config(
        {
            "standard_frame": {
                "daily_interface": "stk_factor_pro",
                "adjustment": "hfq",
                "admission_profile_path": "config/factor_mining_data_admission.yaml",
                "admission_profile": "expanded_app5_v1",
                "optional_fields": [{"feature_name": "$foo"}],
                "feature_view_fields": [{"feature_name": "$bar"}],
            }
        }
    )

    config = runner._factor_template_to_noqlib_config(
        {
            "market": "csi300",
            "task": {
                "dataset": {"kwargs": {"handler": {"instruments": "csi300"}, "segments": {}}},
                "model": {"kwargs": {}},
            },
            "port_analysis_config": {
                "backtest": {"benchmark": "SH000300"},
                "strategy": {"kwargs": {"topk": 50, "n_drop": 5}},
            },
        },
        backend="noqlib",
    )

    standard_frame = config["backtest_runtime"]["noqlib"]["standard_frame"]
    assert standard_frame == {"daily_interface": "stk_factor_pro", "adjustment": "hfq"}


def test_vnpy_runner_defers_pandas_market_until_portfolio(tmp_path: Path) -> None:
    events: list[str] = []
    template_root = tmp_path / "templates"
    template_dir = template_root / "factor_template"
    template_dir.mkdir(parents=True)
    (template_dir / "config.yaml").write_text(
        """
data_handler_config:
  start_time: 2024-01-01
  end_time: 2024-01-03
  data_loader:
    class: NestedDataLoader
    kwargs:
      config:
        label:
          - ["Ref($close, -2)/Ref($close, -1) - 1"]
          - ["LABEL0"]
      dataloader_l:
        - class: StaticDataLoader
          kwargs:
            config: combined_factors_df.parquet
task:
  dataset:
    kwargs:
      segments: {}
  model:
    kwargs: {}
port_analysis_config:
  backtest:
    start_time: 2024-01-01
    end_time: 2024-01-03
    benchmark: SH000300
  strategy:
    kwargs:
      topk: 1
      n_drop: 0
""",
        encoding="utf-8",
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    index = pd.MultiIndex.from_product(
        [[pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")], ["000001.SZ"]],
        names=["datetime", "instrument"],
    )
    pd.DataFrame({"factor": [0.1, 0.2]}, index=index).to_parquet(workspace / "combined_factors_df.parquet")

    market_pdf = pd.DataFrame(
        {
            "$open": [10.0, 10.1],
            "$high": [10.2, 10.3],
            "$low": [9.9, 10.0],
            "$close": [10.1, 10.2],
            "$volume": [100.0, 120.0],
            "$vwap": [10.05, 10.15],
            "$return": [0.0, 0.01],
        },
        index=index,
    )
    class FakeMarketFrame:
        def to_pandas(self):
            events.append("market_to_pandas")
            return market_pdf.reset_index()

    market_frame = FakeMarketFrame()

    class FakeProvider:
        def __init__(self, config):
            self.config = config

        def load_market_frame(self):
            events.append("load_market_frame")
            return market_frame

        def load_market_data(self):
            events.append("pandas_market")
            return market_pdf

    class FakeExpressionEngine:
        def __init__(self, frame):
            events.append("expression_engine")

        def compute_label(self, expression):
            events.append("label")
            return pd.DataFrame({"LABEL0": [0.01, 0.02]}, index=index)

    class FakeDatasetBuilder:
        def __init__(self, config):
            self.config = config

        def build(self, features, labels):
            events.append("dataset")
            assert "market_to_pandas" not in events
            combined = features.join(labels)
            return SimpleNamespace(raw_labels=labels["LABEL0"], combined=combined, label_column="LABEL0")

    class FakeModelRunner:
        def __init__(self, config):
            self.config = config

        def fit_predict(self, dataset):
            events.append("model")
            assert "market_to_pandas" not in events
            return pd.Series([0.1, 0.2], index=index, name="score")

    class FakeBacktester:
        def __init__(self, config, market):
            events.append("portfolio_init")
            assert "pandas_market" in events

        def run(self, prediction):
            events.append("portfolio")
            return {"annualized_return": 0.1}, pd.DataFrame(), pd.DataFrame()

    runner = object.__new__(QlibFactorRunner)
    runner._noqlib_config = {}
    exp = SimpleNamespace(experiment_workspace=SimpleNamespace(workspace_path=workspace))

    # Import the package before patching the source provider class; vnpy.__init__
    # imports backend.py, which copies NoQlibMarketDataProvider at import time.
    import quantaalpha.backtest.vnpy.backend  # noqa: F401

    with (
        patch("quantaalpha.factors.runner.DIRNAME", template_root),
        patch("quantaalpha.backtest.noqlib.data_provider.NoQlibMarketDataProvider", FakeProvider),
        patch("quantaalpha.backtest.vnpy.expression_engine.VnpyExpressionEngine", FakeExpressionEngine),
        patch("quantaalpha.backtest.noqlib.dataset.NoQlibDatasetBuilder", FakeDatasetBuilder),
        patch("quantaalpha.backtest.noqlib.model.NoQlibModelRunner", FakeModelRunner),
        patch("quantaalpha.backtest.noqlib.portfolio.NoQlibTopkDropoutBacktester", FakeBacktester),
    ):
        result = QlibFactorRunner._develop_noqlib(runner, exp, "config.yaml", backend="vnpy")

    assert float(result.loc["annualized_return", "value"]) == 0.1
    assert "market_to_pandas" not in events
    assert events.index("pandas_market") > events.index("model")
