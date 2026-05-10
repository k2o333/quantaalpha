from __future__ import annotations

import builtins
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
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


def test_noqlib_risk_metrics_matches_qlib_risk_analysis():
    qlib_evaluate = pytest.importorskip("qlib.contrib.evaluate")
    from quantaalpha.backtest.noqlib.risk import risk_metrics

    returns = pd.Series([0.01, -0.02, 0.003, 0.0, 0.015, -0.005], index=pd.date_range("2020-01-01", periods=6))
    oracle = qlib_evaluate.risk_analysis(returns)["risk"]
    metrics = risk_metrics(returns)
    assert metrics["annualized_return"] == pytest.approx(float(oracle["annualized_return"]))
    assert metrics["information_ratio"] == pytest.approx(float(oracle["information_ratio"]))
    assert metrics["max_drawdown"] == pytest.approx(float(oracle["max_drawdown"]))
    assert metrics["calmar_ratio"] == pytest.approx(
        float(oracle["annualized_return"]) / abs(float(oracle["max_drawdown"]))
    )


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


def test_alpha158_20_matches_real_qlib_oracle_when_data_available(tmp_path):
    provider_uri = os.environ.get("QLIB_DATA_DIR") or os.environ.get("QLIB_PROVIDER_URI")
    if not provider_uri or not Path(provider_uri).exists():
        pytest.skip("QLIB_DATA_DIR/QLIB_PROVIDER_URI not available")
    pytest.importorskip("qlib")

    from quantaalpha.backtest.factor_loader import FactorLoader
    from quantaalpha.backtest.noqlib.export_qlib_oracle import export_oracle
    from quantaalpha.backtest.noqlib.expression_engine import NoQlibExpressionEngine

    instruments = ["000001.SZ", "000002.SZ", "000008.SZ", "000009.SZ", "000012.SZ"]
    export_oracle(
        provider_uri=provider_uri,
        output_dir=str(tmp_path),
        instruments=instruments,
        start_time="2020-01-01",
        end_time="2020-03-31",
        market_start_time="2019-09-01",
        factor_source="alpha158_20",
    )
    market = pd.read_parquet(tmp_path / "oracle_market.parquet").set_index(["datetime", "instrument"]).sort_index()
    oracle = pd.read_parquet(tmp_path / "oracle_features.parquet").set_index(["datetime", "instrument"]).sort_index()
    factors, _ = FactorLoader({"factor_source": {"type": "alpha158_20"}}).load_factors()
    calculated = NoQlibExpressionEngine(market).compute(
        [{"factor_id": name, "factor_name": name, "factor_expression": expr} for name, expr in factors.items()]
    )
    calculated = calculated.sort_index().loc[oracle.index, oracle.columns]
    for column in oracle.columns:
        np.testing.assert_allclose(
            calculated[column].to_numpy(),
            oracle[column].to_numpy(),
            rtol=1e-6,
            atol=1e-5,
            equal_nan=True,
            err_msg=column,
        )


def test_alpha158_matches_real_qlib_oracle_when_data_available(tmp_path):
    provider_uri = os.environ.get("QLIB_DATA_DIR") or os.environ.get("QLIB_PROVIDER_URI")
    if not provider_uri or not Path(provider_uri).exists():
        pytest.skip("QLIB_DATA_DIR/QLIB_PROVIDER_URI not available")
    pytest.importorskip("qlib")

    from quantaalpha.backtest.factor_loader import FactorLoader
    from quantaalpha.backtest.noqlib.export_qlib_oracle import export_oracle
    from quantaalpha.backtest.noqlib.expression_engine import NoQlibExpressionEngine

    instruments = ["000001.SZ", "000002.SZ", "000008.SZ", "000009.SZ", "000012.SZ"]
    export_oracle(
        provider_uri=provider_uri,
        output_dir=str(tmp_path),
        instruments=instruments,
        start_time="2020-01-01",
        end_time="2020-03-31",
        market_start_time="2019-01-01",
        factor_source="alpha158",
    )
    market = pd.read_parquet(tmp_path / "oracle_market.parquet").set_index(["datetime", "instrument"]).sort_index()
    oracle = pd.read_parquet(tmp_path / "oracle_features.parquet").set_index(["datetime", "instrument"]).sort_index()
    factors, _ = FactorLoader({"factor_source": {"type": "alpha158"}}).load_factors()
    calculated = NoQlibExpressionEngine(market).compute(
        [{"factor_id": name, "factor_name": name, "factor_expression": expr} for name, expr in factors.items()]
    )
    calculated = calculated.sort_index().loc[oracle.index, oracle.columns]
    for column in oracle.columns:
        np.testing.assert_allclose(
            calculated[column].to_numpy(),
            oracle[column].to_numpy(),
            rtol=1e-6,
            atol=1e-5,
            equal_nan=True,
            err_msg=column,
        )


def test_alpha360_matches_real_qlib_oracle_when_data_available(tmp_path):
    provider_uri = os.environ.get("QLIB_DATA_DIR") or os.environ.get("QLIB_PROVIDER_URI")
    if not provider_uri or not Path(provider_uri).exists():
        pytest.skip("QLIB_DATA_DIR/QLIB_PROVIDER_URI not available")
    pytest.importorskip("qlib")

    from quantaalpha.backtest.factor_loader import FactorLoader
    from quantaalpha.backtest.noqlib.export_qlib_oracle import export_oracle
    from quantaalpha.backtest.noqlib.expression_engine import NoQlibExpressionEngine

    instruments = ["000001.SZ", "000002.SZ", "000008.SZ", "000009.SZ", "000012.SZ"]
    export_oracle(
        provider_uri=provider_uri,
        output_dir=str(tmp_path),
        instruments=instruments,
        start_time="2020-01-01",
        end_time="2020-03-31",
        market_start_time="2019-01-01",
        factor_source="alpha360",
    )
    market = pd.read_parquet(tmp_path / "oracle_market.parquet").set_index(["datetime", "instrument"]).sort_index()
    oracle = pd.read_parquet(tmp_path / "oracle_features.parquet").set_index(["datetime", "instrument"]).sort_index()
    factors, _ = FactorLoader({"factor_source": {"type": "alpha360"}}).load_factors()
    calculated = NoQlibExpressionEngine(market).compute(
        [{"factor_id": name, "factor_name": name, "factor_expression": expr} for name, expr in factors.items()]
    )
    calculated = calculated.sort_index().loc[oracle.index, oracle.columns]
    for column in oracle.columns:
        np.testing.assert_allclose(
            calculated[column].to_numpy(),
            oracle[column].to_numpy(),
            rtol=1e-6,
            atol=1e-5,
            equal_nan=True,
            err_msg=column,
        )


def test_noqlib_data_provider_accepts_qlib_style_market_parquet(tmp_path):
    from quantaalpha.backtest.noqlib.data_provider import NoQlibMarketDataProvider

    market_path = tmp_path / "market.parquet"
    pd.DataFrame(
        {
            "datetime": [pd.Timestamp("2020-01-01"), pd.Timestamp("2020-01-02")],
            "instrument": ["A", "A"],
            "$open": [10.0, 11.0],
            "$high": [10.5, 11.5],
            "$low": [9.5, 10.5],
            "$close": [10.2, 11.2],
            "$volume": [1000.0, 1001.0],
            "$vwap": [10.1, 11.1],
        }
    ).to_parquet(market_path, index=False)
    provider = NoQlibMarketDataProvider({"backtest_runtime": {"noqlib": {"market_data_path": str(market_path)}}})
    market = provider.load_market_data()
    assert list(market.columns) == ["$open", "$high", "$low", "$close", "$volume", "$vwap", "$return"]
    assert market.index.names == ["datetime", "instrument"]
    assert market.loc[(pd.Timestamp("2020-01-02"), "A"), "$return"] == pytest.approx(11.2 / 10.2 - 1.0)


def test_noqlib_topk_dropout_matches_qlib_selection_sequence():
    from quantaalpha.backtest.noqlib.portfolio import _next_topk_dropout_holdings

    instruments = ["000001.SZ", "000002.SZ", "000008.SZ", "000009.SZ", "000012.SZ"]
    holdings: list[str] = []
    expected = [
        ["000009.SZ", "000008.SZ", "000002.SZ"],
        ["000008.SZ", "000002.SZ", "000001.SZ"],
        ["000002.SZ", "000001.SZ", "000012.SZ"],
    ]
    # These are the previous-step predictions used by qlib for 2020-01-06/07/08
    # in the real-data smoke check.
    signal_offsets = [1, 2, 3]
    for offset, expected_holdings in zip(signal_offsets, expected):
        pred = pd.Series(
            [float((index + offset) % len(instruments)) for index, _instrument in enumerate(instruments)],
            index=instruments,
        )
        holdings = _next_topk_dropout_holdings(holdings=holdings, pred_score=pred, topk=3, n_drop=1)
        assert holdings == expected_holdings


def test_noqlib_portfolio_requires_configured_benchmark_data():
    from quantaalpha.backtest.noqlib.portfolio import NoQlibTopkDropoutBacktester

    index = pd.MultiIndex.from_product(
        [[pd.Timestamp("2020-01-01"), pd.Timestamp("2020-01-02")], ["A", "B"]],
        names=["datetime", "instrument"],
    )
    market = pd.DataFrame(
        {
            "$open": [10.0, 20.0, 11.0, 21.0],
            "$high": [10.0, 20.0, 11.0, 21.0],
            "$low": [10.0, 20.0, 11.0, 21.0],
            "$close": [10.0, 20.0, 11.0, 21.0],
            "$volume": [100.0, 100.0, 100.0, 100.0],
            "$vwap": [10.0, 20.0, 11.0, 21.0],
            "$return": [0.0, 0.0, 0.1, 0.05],
        },
        index=index,
    )
    prediction = pd.Series([1.0, 2.0, 1.0, 2.0], index=index)
    config = {
        "backtest": {
            "strategy": {"kwargs": {"topk": 1, "n_drop": 1}},
            "backtest": {
                "start_time": "2020-01-02",
                "end_time": "2020-01-02",
                "benchmark": "SH000300",
                "exchange_kwargs": {"open_cost": 0.0, "close_cost": 0.0, "min_cost": 0.0},
            },
        }
    }
    with pytest.raises(KeyError, match="benchmark SH000300"):
        NoQlibTopkDropoutBacktester(config, market).run(prediction)


def test_noqlib_portfolio_return_matches_real_qlib_fixed_prediction_when_data_available(tmp_path):
    provider_uri = os.environ.get("QLIB_DATA_DIR") or os.environ.get("QLIB_PROVIDER_URI")
    if not provider_uri or not Path(provider_uri).exists():
        pytest.skip("QLIB_DATA_DIR/QLIB_PROVIDER_URI not available")
    pytest.importorskip("qlib")

    import qlib
    from qlib.backtest import backtest as qlib_backtest
    from qlib.data import D

    from quantaalpha.backtest.noqlib.export_qlib_oracle import export_oracle
    from quantaalpha.backtest.noqlib.portfolio import NoQlibTopkDropoutBacktester

    instruments = ["000001.SZ", "000002.SZ", "000008.SZ", "000009.SZ", "000012.SZ"]
    qlib.init(provider_uri=provider_uri, region="cn")
    dates = pd.to_datetime(D.calendar(start_time="2020-01-01", end_time="2020-01-15", freq="day"))
    prediction = _rotating_prediction(dates, instruments)
    portfolio_metric_dict, _indicator_dict = qlib_backtest(
        executor={
            "class": "SimulatorExecutor",
            "module_path": "qlib.backtest.executor",
            "kwargs": {
                "time_per_step": "day",
                "generate_portfolio_metrics": True,
                "verbose": False,
                "indicator_config": {"show_indicator": False},
            },
        },
        strategy={
            "class": "TopkDropoutStrategy",
            "module_path": "qlib.contrib.strategy.signal_strategy",
            "kwargs": {"signal": prediction, "topk": 3, "n_drop": 1},
        },
        start_time="2020-01-06",
        end_time="2020-01-15",
        account=100000000,
        benchmark="SH000300",
        exchange_kwargs={
            "codes": instruments,
            "freq": "day",
            "limit_threshold": 0.095,
            "deal_price": "open",
            "open_cost": 0.0005,
            "close_cost": 0.0015,
            "min_cost": 5.0,
        },
    )
    qlib_report, _qlib_positions = portfolio_metric_dict["1day"]
    export_oracle(
        provider_uri=provider_uri,
        output_dir=str(tmp_path),
        instruments=[*instruments, "SH000300"],
        start_time="2020-01-01",
        end_time="2020-01-15",
        market_start_time="2019-12-01",
        factor_source="alpha158_20",
    )
    market = pd.read_parquet(tmp_path / "oracle_market.parquet").set_index(["datetime", "instrument"]).sort_index()
    market["$return"] = market.groupby(level="instrument")["$close"].pct_change().fillna(0.0)
    config = {
        "backtest": {
            "strategy": {"kwargs": {"topk": 3, "n_drop": 1}},
            "backtest": {
                "start_time": "2020-01-06",
                "end_time": "2020-01-15",
                "account": 100000000,
                "benchmark": "SH000300",
                "exchange_kwargs": {"open_cost": 0.0005, "close_cost": 0.0015, "min_cost": 5.0},
            },
        }
    }
    _metrics, noqlib_report, _positions = NoQlibTopkDropoutBacktester(config, market).run(prediction)
    pd.testing.assert_series_equal(
        noqlib_report["return"],
        qlib_report["return"],
        check_names=False,
        rtol=1e-6,
        atol=1e-8,
    )
    pd.testing.assert_series_equal(
        noqlib_report["bench"],
        qlib_report["bench"],
        check_names=False,
        check_dtype=False,
        rtol=1e-6,
        atol=1e-8,
    )
    pd.testing.assert_series_equal(
        noqlib_report["cost"],
        qlib_report["cost"],
        check_names=False,
        check_dtype=False,
        rtol=1e-6,
        atol=1e-8,
    )


def _rotating_prediction(dates: pd.DatetimeIndex, instruments: list[str]) -> pd.Series:
    index = []
    values = []
    for day_index, dt in enumerate(dates):
        for stock_index, instrument in enumerate(instruments):
            index.append((dt, instrument))
            values.append(float((stock_index + day_index) % len(instruments)))
    return pd.Series(values, index=pd.MultiIndex.from_tuples(index, names=["datetime", "instrument"]))


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
