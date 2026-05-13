from __future__ import annotations

import os
import sys
from pathlib import Path
import logging.config

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[3]
PKG_ROOT = ROOT / "third_party" / "quantaalpha"
if str(PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(PKG_ROOT))


def _provider_uri() -> Path | None:
    configured = os.environ.get("QLIB_DATA_DIR") or os.environ.get("QLIB_PROVIDER_URI")
    candidates = []
    if configured:
        candidates.append(Path(configured))
    candidates.append(ROOT / "third_party" / "data" / "qlib_data_csi300_bin")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def test_vnpy_polars_factor_and_portfolio_match_qlib_real_data(tmp_path: Path) -> None:
    provider_uri = _provider_uri()
    if provider_uri is None:
        pytest.skip("qlib provider data not available")
    pytest.importorskip("qlib")

    import qlib
    from qlib.backtest import backtest as qlib_backtest
    from qlib.contrib.evaluate import risk_analysis
    from qlib.data import D

    from quantaalpha.backtest.long_only_parity import (
        DAILY_REPORT_COLUMNS,
        assert_annualized_return_comparable,
        compare_long_only_daily_reports,
        compare_long_only_positions,
        normalize_qlib_daily_report,
        qlib_positions_to_frame,
    )
    from quantaalpha.backtest.noqlib.export_qlib_oracle import export_oracle
    from quantaalpha.backtest.noqlib.portfolio import NoQlibTopkDropoutBacktester
    from quantaalpha.backtest.qlib_provenance import extract_excess_return_series, qlib_excess_return_provenance
    from quantaalpha.backtest.vnpy.expression_engine import VnpyExpressionEngine

    instruments = ["000001.SZ", "000002.SZ", "000008.SZ", "000009.SZ", "000012.SZ"]
    benchmark = "SH000300"
    factor_expression = "Mean($close, 2)"
    logging.config.BaseConfigurator.importer = __import__
    qlib.init(provider_uri=str(provider_uri), region="cn")

    export_oracle(
        provider_uri=str(provider_uri),
        output_dir=str(tmp_path),
        instruments=[*instruments, benchmark],
        start_time="2020-01-01",
        end_time="2020-01-15",
        market_start_time="2019-12-01",
        factor_source="alpha158_20",
    )
    market = pd.read_parquet(tmp_path / "oracle_market.parquet").set_index(["datetime", "instrument"]).sort_index()
    market["$return"] = market.groupby(level="instrument")["$close"].pct_change().fillna(0.0)

    qlib_factor = D.features(
        instruments,
        [factor_expression],
        start_time="2020-01-01",
        end_time="2020-01-15",
        freq="day",
    )
    qlib_factor.columns = ["signal"]
    qlib_prediction = qlib_factor["signal"].swaplevel().sort_index()

    vnpy_features = VnpyExpressionEngine(market).compute(
        [{"factor_id": "signal", "factor_name": "signal", "factor_expression": factor_expression}]
    )
    vnpy_prediction = vnpy_features.loc[qlib_prediction.index, "signal"].sort_index()
    np.testing.assert_allclose(
        vnpy_prediction.to_numpy(),
        qlib_prediction.to_numpy(),
        rtol=1e-6,
        atol=1e-5,
        equal_nan=True,
    )

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
            "kwargs": {"signal": qlib_prediction, "topk": 3, "n_drop": 1},
        },
        start_time="2020-01-06",
        end_time="2020-01-15",
        account=100000000,
        benchmark=benchmark,
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
    config = {
        "backtest": {
            "strategy": {"kwargs": {"topk": 3, "n_drop": 1}},
            "backtest": {
                "start_time": "2020-01-06",
                "end_time": "2020-01-15",
                "account": 100000000,
                "benchmark": benchmark,
                "exchange_kwargs": {"open_cost": 0.0005, "close_cost": 0.0015, "min_cost": 5.0},
            },
        }
    }
    vnpy_metrics, vnpy_report, vnpy_positions = NoQlibTopkDropoutBacktester(config, market).run(vnpy_prediction)
    pd.testing.assert_series_equal(
        vnpy_report["return"],
        qlib_report["return"],
        check_names=False,
        rtol=1e-6,
        atol=1e-8,
    )

    qlib_daily = normalize_qlib_daily_report(qlib_report)
    daily_parity = compare_long_only_daily_reports(
        qlib_daily,
        vnpy_report,
        columns=DAILY_REPORT_COLUMNS,
        rtol=1e-6,
        atol=1e-6,
    )
    assert daily_parity.passed, daily_parity.to_dict()

    positions_parity = compare_long_only_positions(
        qlib_positions_to_frame(_qlib_positions),
        vnpy_positions,
        rtol=1e-6,
        atol=1e-4,
    )
    assert positions_parity.passed, positions_parity.to_dict()

    provenance = qlib_excess_return_provenance(
        recorder_object="direct qlib.backtest fixture",
        source_series_proven_identical=daily_parity.passed and positions_parity.passed,
    ).to_dict()
    assert_annualized_return_comparable(daily_parity, provenance)
    qlib_excess = extract_excess_return_series(qlib_report)
    qlib_annualized = float(risk_analysis(qlib_excess)["risk"]["annualized_return"])
    assert vnpy_metrics["annualized_return"] == pytest.approx(qlib_annualized, rel=1e-10, abs=1e-10)
    pd.testing.assert_series_equal(
        vnpy_report["bench"],
        qlib_report["bench"],
        check_names=False,
        check_dtype=False,
        rtol=1e-6,
        atol=1e-8,
    )
    pd.testing.assert_series_equal(
        vnpy_report["cost"],
        qlib_report["cost"],
        check_names=False,
        check_dtype=False,
        rtol=1e-6,
        atol=1e-8,
    )
