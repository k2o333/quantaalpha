from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import polars as pl

from quantaalpha.factors.runner import QlibFactorRunner


def test_noqlib_static_feature_loader_reads_parquet_with_polars(tmp_path: Path) -> None:
    runner = object.__new__(QlibFactorRunner)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    frame_path = workspace / "combined_factors_df.parquet"
    pl.DataFrame(
        {
            "datetime": ["2024-01-01", "2024-01-02"],
            "instrument": ["000001.SZ", "000001.SZ"],
            "factor": [0.1, 0.2],
        }
    ).write_parquet(frame_path)

    config = {
        "data_handler_config": {
            "data_loader": {
                "class": "StaticDataLoader",
                "kwargs": {"config": "combined_factors_df.parquet"},
            }
        }
    }

    with patch("pandas.read_parquet", side_effect=AssertionError("must use polars")):
        features = runner._load_noqlib_template_features(config=config, expression_engine=None, workspace_path=workspace)

    assert isinstance(features, pl.DataFrame)
    assert features.columns == ["datetime", "instrument", "factor"]
    assert features.get_column("factor").to_list() == [0.1, 0.2]


def test_noqlib_static_feature_loader_restores_feature_names_from_feature_prefix_parquet(tmp_path: Path) -> None:
    runner = object.__new__(QlibFactorRunner)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    pl.DataFrame(
        {
            "datetime": ["2024-01-01", "2024-01-02"],
            "instrument": ["000001.SZ", "000001.SZ"],
            "feature_alpha_one": [0.1, 0.2],
            "feature_alpha_two": [0.3, 0.4],
        }
    ).write_parquet(workspace / "combined_factors_df.parquet")

    config = {
        "data_handler_config": {
            "data_loader": {
                "class": "StaticDataLoader",
                "kwargs": {"config": "combined_factors_df.parquet"},
            }
        }
    }

    with patch("pandas.read_parquet", side_effect=AssertionError("must use polars")):
        features = runner._load_noqlib_template_features(config=config, expression_engine=None, workspace_path=workspace)

    assert isinstance(features, pl.DataFrame)
    assert features.columns == ["datetime", "instrument", "alpha_one", "alpha_two"]


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


def test_factor_template_to_noqlib_config_prefers_runtime_segments() -> None:
    runner = object.__new__(QlibFactorRunner)
    runner.set_noqlib_config(
        {
            "segments": {
                "train": ("2022-01-01", "2023-12-31"),
                "valid": ("2024-01-01", "2024-12-31"),
                "test": ("2025-01-01", "2025-12-31"),
            }
        }
    )
    qlib_cfg = {
        "data_handler_config": {
            "start_time": "2016-01-01",
            "end_time": "2025-12-31",
            "instruments": "csi300",
            "data_loader": {"kwargs": {"config": {}}},
        },
        "task": {
            "dataset": {
                "kwargs": {
                    "segments": {
                        "train": ["2016-01-01", "2019-12-31"],
                        "valid": ["2020-01-01", "2020-12-31"],
                        "test": ["2021-01-01", "2025-12-31"],
                    }
                }
            },
            "model": {"kwargs": {}},
        },
        "port_analysis_config": {"backtest": {}},
    }

    result = runner._factor_template_to_noqlib_config(qlib_cfg)

    assert result["dataset"]["segments"] == {
        "train": ("2022-01-01", "2023-12-31"),
        "valid": ("2024-01-01", "2024-12-31"),
        "test": ("2025-01-01", "2025-12-31"),
    }


def test_develop_runs_correlation_dedup_when_sota_factors_exist(tmp_path: Path) -> None:
    runner = object.__new__(QlibFactorRunner)
    (tmp_path / "ws").mkdir()

    sota_df = pl.DataFrame(
        {
            "datetime": ["2024-01-01", "2024-01-02"],
            "instrument": ["A", "A"],
            "old_factor": [1.0, 2.0],
        }
    ).with_columns(pl.col("datetime").str.strptime(pl.Datetime("ns")))
    new_df = pl.DataFrame(
        {
            "datetime": ["2024-01-01", "2024-01-02"],
            "instrument": ["A", "A"],
            "new_factor": [2.0, 3.0],
        }
    ).with_columns(pl.col("datetime").str.strptime(pl.Datetime("ns")))

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


def test_combined_quality_gate_prunes_highly_correlated_candidates() -> None:
    runner = object.__new__(QlibFactorRunner)
    index = pd.MultiIndex.from_product(
        [
            pd.date_range("2024-01-01", periods=4, freq="D"),
            ["A"],
        ],
        names=["datetime", "instrument"],
    )
    frame = pd.DataFrame(
        {
            "base": [1.0, 2.0, 3.0, 4.0],
            "duplicate": [2.0, 4.0, 6.0, 8.0],
            "orthogonal": [1.0, -1.0, 1.0, -1.0],
        },
        index=index,
    )

    result = runner._apply_combined_quality_gate(frame)

    assert list(result.columns) == ["base", "orthogonal"]


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
    pl.DataFrame(
        {
            "datetime": ["2024-01-01", "2024-01-02"],
            "instrument": ["000001.SZ", "000001.SZ"],
            "feature_factor": [0.1, 0.2],
        }
    ).write_parquet(workspace / "combined_factors_df.parquet")

    market_frame = pl.DataFrame(
        {
            "datetime": ["2024-01-01", "2024-01-02"],
            "instrument": ["000001.SZ", "000001.SZ"],
            "$open": [10.0, 10.1],
            "$high": [10.2, 10.3],
            "$low": [9.9, 10.0],
            "$close": [10.1, 10.2],
            "$volume": [100.0, 120.0],
            "$vwap": [10.05, 10.15],
            "$return": [0.0, 0.01],
        }
    ).with_columns(
        pl.col("datetime").str.strptime(pl.Datetime("ns")),
    )

    class FakeProvider:
        def __init__(self, config):
            self.config = config

        def load_market_frame(self):
            events.append("load_market_frame")
            return market_frame

            def load_market_data(self):
                events.append("pandas_market")
                raise AssertionError("noqlib/vnpy path must not request pandas market data")

    class FakeExpressionEngine:
        def __init__(self, frame):
            events.append("expression_engine")

        def compute_label(self, expression):
            events.append("label")
            return pl.DataFrame(
                {
                    "datetime": ["2024-01-01", "2024-01-02"],
                    "instrument": ["000001.SZ", "000001.SZ"],
                    "LABEL0": [0.01, 0.02],
                }
            ).with_columns(pl.col("datetime").str.strptime(pl.Datetime("ns")))

    class FakeDatasetBuilder:
        def __init__(self, config):
            self.config = config

        def build(self, features, labels):
            events.append("dataset")
            assert isinstance(features, pl.DataFrame)
            assert isinstance(labels, pl.DataFrame)
            combined = features.join(labels, on=["datetime", "instrument"])
            return SimpleNamespace(raw_labels=labels, combined=combined, label_column="LABEL0")

    class FakeModelRunner:
        def __init__(self, config):
            self.config = config

        def fit_predict(self, dataset):
            events.append("model")
            return pl.DataFrame(
                {
                    "datetime": ["2024-01-01", "2024-01-02"],
                    "instrument": ["000001.SZ", "000001.SZ"],
                    "score": [0.1, 0.2],
                }
            ).with_columns(pl.col("datetime").str.strptime(pl.Datetime("ns")))

    class FakeBacktester:
        def __init__(self, config, market):
            events.append("portfolio_init")
            assert isinstance(market, pl.DataFrame)
            assert "pandas_market" not in events

        def run(self, prediction):
            events.append("portfolio")
            assert isinstance(prediction, pl.DataFrame)
            return {"annualized_return": 0.1}, pl.DataFrame(), pl.DataFrame()

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

    assert result.filter(pl.col("metric") == "annualized_return").select("value").item() == 0.1
    assert "pandas_market" not in events
