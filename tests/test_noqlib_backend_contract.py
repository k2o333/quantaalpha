from __future__ import annotations

import builtins
import json
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
PKG_ROOT = ROOT / "quantaalpha"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_resolve_backend_prefers_explicit_over_env(monkeypatch):
    from quantaalpha.backtest.facade import resolve_backend

    monkeypatch.setenv("QUANTAALPHA_BACKTEST_BACKEND", "noqlib")
    assert resolve_backend({"backtest_runtime": {"backend": "qlib"}}, "dual_parity") == "dual_parity"


def test_noqlib_facade_construction_does_not_import_qlib(tmp_path, monkeypatch):
    from quantaalpha.backtest.facade import BacktestFacade

    cfg_path = tmp_path / "backtest.yaml"
    cfg_path.write_text(
        json.dumps({"backtest_runtime": {"backend": "noqlib"}}),
        encoding="utf-8",
    )
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "qlib" or name.startswith("qlib."):
            raise AssertionError(f"noqlib facade imported qlib: {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    facade = BacktestFacade(str(cfg_path), backend="noqlib")
    assert facade.backend == "noqlib"


def test_signal_metrics_returns_expected_keys():
    from quantaalpha.backtest.noqlib.signal_analysis import signal_metrics

    index = pd.MultiIndex.from_product(
        [[pd.Timestamp("2020-01-01"), pd.Timestamp("2020-01-02")], ["A", "B", "C"]],
        names=["datetime", "instrument"],
    )
    pred = pd.Series([1, 2, 3, 3, 2, 1], index=index)
    label = pd.Series([1, 2, 3, 1, 2, 3], index=index)
    metrics = signal_metrics(pred, label)
    assert set(metrics) == {"IC", "ICIR", "Rank IC", "Rank ICIR"}
    assert metrics["IC"] == 0.0
    assert metrics["Rank IC"] == 0.0


def test_noqlib_risk_metrics_handles_empty_series():
    from quantaalpha.backtest.noqlib.risk import risk_metrics

    metrics = risk_metrics(pd.Series(dtype=float))
    assert metrics == {
        "annualized_return": 0.0,
        "information_ratio": 0.0,
        "max_drawdown": 0.0,
        "calmar_ratio": 0.0,
    }


def test_noqlib_backend_runs_tiny_csv_without_qlib(tmp_path, monkeypatch):
    from quantaalpha.backtest.facade import BacktestFacade

    rows = []
    dates = pd.date_range("2020-01-01", periods=80, freq="D")
    for day_index, dt in enumerate(dates):
        for stock_index, instrument in enumerate(["A", "B", "C", "D", "E"]):
            close = 10 + day_index * 0.1 + stock_index * 0.2
            rows.append(
                {
                    "trade_date": dt.strftime("%Y%m%d"),
                    "ts_code": instrument,
                    "open": close * 0.99,
                    "high": close * 1.01,
                    "low": close * 0.98,
                    "close": close,
                    "vol": 1000 + stock_index,
                    "amount": close * (1000 + stock_index),
                    "pct_chg": 0.1 + stock_index * 0.01,
                }
            )
    market_path = tmp_path / "market.csv"
    pd.DataFrame(rows).to_csv(market_path, index=False)
    factors_path = tmp_path / "factors.json"
    factors_path.write_text(
        json.dumps({"factors": {"f1": {"factor_name": "CloseFactor", "factor_expression": "$close"}}}),
        encoding="utf-8",
    )
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(
        yaml.safe_dump(
            {
                "backtest_runtime": {"backend": "noqlib", "noqlib": {"market_data_path": str(market_path)}},
                "factor_source": {"type": "custom", "custom": {"json_files": [str(factors_path)]}},
                "data": {"start_time": "2020-01-01", "end_time": "2020-03-20", "market": "all"},
                "dataset": {
                    "label": "Ref($close, -2) / Ref($close, -1) - 1",
                    "segments": {
                        "train": ["2020-01-01", "2020-02-10"],
                        "valid": ["2020-02-11", "2020-02-20"],
                        "test": ["2020-02-21", "2020-03-20"],
                    },
                },
                "model": {"type": "lgb", "params": {"learning_rate": 0.05, "num_leaves": 7, "num_boost_round": 5, "verbose": -1}},
                "backtest": {
                    "strategy": {"kwargs": {"topk": 3, "n_drop": 1}},
                    "backtest": {
                        "start_time": "2020-02-21",
                        "end_time": "2020-03-15",
                        "benchmark": "mean",
                        "exchange_kwargs": {"open_cost": 0.0, "close_cost": 0.0},
                    },
                },
                "experiment": {
                    "name": "tmp",
                    "recorder": "tmp",
                    "output_dir": str(tmp_path / "out"),
                    "output_metrics_file": "metrics.json",
                },
            }
        ),
        encoding="utf-8",
    )
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "qlib" or name.startswith("qlib."):
            raise AssertionError(f"noqlib backend imported qlib: {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    result = BacktestFacade(str(cfg_path), backend="noqlib").run()
    assert {"IC", "Rank IC", "annualized_return", "information_ratio"} <= set(result)
    assert (tmp_path / "out" / "metrics.json").exists()


def test_noqlib_backend_runs_alpha158_20_synthetic_csv(tmp_path):
    from quantaalpha.backtest.facade import BacktestFacade

    rows = []
    dates = pd.date_range("2020-01-01", periods=90, freq="D")
    instruments = [f"S{i:03d}" for i in range(8)]
    for day_index, dt in enumerate(dates):
        for stock_index, instrument in enumerate(instruments):
            close = 20 + day_index * 0.07 + stock_index * 0.13
            rows.append(
                {
                    "trade_date": dt.strftime("%Y%m%d"),
                    "ts_code": instrument,
                    "open": close * (0.99 + stock_index * 0.0001),
                    "high": close * 1.02,
                    "low": close * 0.98,
                    "close": close,
                    "vol": 1000 + stock_index * 10 + day_index,
                    "amount": close * (1000 + stock_index * 10 + day_index),
                    "pct_chg": 0.2 + stock_index * 0.02,
                }
            )
    market_path = tmp_path / "market.csv"
    pd.DataFrame(rows).to_csv(market_path, index=False)
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(
        yaml.safe_dump(
            {
                "backtest_runtime": {"backend": "noqlib", "noqlib": {"market_data_path": str(market_path)}},
                "factor_source": {"type": "alpha158_20"},
                "data": {"start_time": "2020-01-01", "end_time": "2020-03-30", "market": "all"},
                "dataset": {
                    "label": "Ref($close, -2) / Ref($close, -1) - 1",
                    "segments": {
                        "train": ["2020-01-01", "2020-02-14"],
                        "valid": ["2020-02-15", "2020-02-29"],
                        "test": ["2020-03-01", "2020-03-30"],
                    },
                },
                "model": {"type": "lgb", "params": {"learning_rate": 0.05, "num_leaves": 7, "num_boost_round": 5, "verbose": -1}},
                "backtest": {
                    "strategy": {"kwargs": {"topk": 4, "n_drop": 1}},
                    "backtest": {
                        "start_time": "2020-03-01",
                        "end_time": "2020-03-25",
                        "benchmark": "mean",
                        "exchange_kwargs": {"open_cost": 0.0, "close_cost": 0.0},
                    },
                },
                "experiment": {
                    "name": "alpha158_20",
                    "recorder": "tmp",
                    "output_dir": str(tmp_path / "out"),
                    "output_metrics_file": "metrics.json",
                },
            }
        ),
        encoding="utf-8",
    )
    result = BacktestFacade(str(cfg_path), backend="noqlib").run()
    assert {"IC", "Rank IC", "annualized_return", "information_ratio"} <= set(result)
    assert (tmp_path / "out" / "metrics.json").exists()


def test_alpha158_20_native_expression_engine_does_not_use_fallback(tmp_path, monkeypatch):
    from quantaalpha.backtest.factor_loader import FactorLoader
    from quantaalpha.backtest.noqlib.expression_engine import NoQlibExpressionEngine

    rows = []
    dates = pd.date_range("2020-01-01", periods=70, freq="D")
    for day_index, dt in enumerate(dates):
        for stock_index, instrument in enumerate(["A", "B", "C", "D"]):
            close = 10 + day_index * 0.2 + stock_index
            rows.append(
                {
                    "datetime": dt,
                    "instrument": instrument,
                    "$open": close * 0.99,
                    "$high": close * 1.02,
                    "$low": close * 0.98,
                    "$close": close,
                    "$volume": 1000 + day_index + stock_index,
                    "$vwap": close,
                    "$return": 0.001 * (stock_index + 1),
                }
            )
    market = pd.DataFrame(rows).set_index(["datetime", "instrument"])
    factors, _ = FactorLoader({"factor_source": {"type": "alpha158_20"}}).load_factors()

    def fail_fallback(*args, **kwargs):
        raise AssertionError("alpha158_20 should be covered by native evaluator")

    monkeypatch.setattr(NoQlibExpressionEngine, "_custom_calculator", fail_fallback)
    features = NoQlibExpressionEngine(market).compute(
        [{"factor_id": name, "factor_name": name, "factor_expression": expr} for name, expr in factors.items()]
    )
    assert set(features.columns) == set(factors)
    assert len(features) == len(market)


def test_dual_parity_report_writer(tmp_path):
    from quantaalpha.backtest.noqlib.dual_parity import DualParityBacktestBackend

    backend = DualParityBacktestBackend(
        "unused.yaml",
        {"experiment": {"output_dir": str(tmp_path)}, "backtest_runtime": {"parity": {"output_winner": "qlib"}}},
    )
    backend._write_report({"IC": 0.1, "Rank IC": 0.2}, {"IC": 0.1, "Rank IC": 0.19})
    report_path = tmp_path / "dual_parity_report.json"
    assert report_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["Rank IC"]["abs_diff"] == 0.010000000000000009
