from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import polars as pl
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_standard_frame_required_columns_are_frozen() -> None:
    from quantaalpha.backtest.contracts import (
        STANDARD_FRAME_REQUIRED_COLUMNS,
        validate_standard_frame_columns,
    )

    assert STANDARD_FRAME_REQUIRED_COLUMNS == (
        "datetime",
        "instrument",
        "$open",
        "$high",
        "$low",
        "$close",
        "$volume",
        "$vwap",
        "$return",
    )
    validate_standard_frame_columns(STANDARD_FRAME_REQUIRED_COLUMNS)
    with pytest.raises(ValueError, match=r"\$return"):
        validate_standard_frame_columns(STANDARD_FRAME_REQUIRED_COLUMNS[:-1])


def test_all_current_app5_clean_active_interfaces_are_classified() -> None:
    from quantaalpha.backtest.contracts import APP5_INTERFACE_CLASSES, inventory_clean_active_interfaces

    admissions = inventory_clean_active_interfaces(Path(__file__).resolve().parents[3] / "data")
    assert admissions
    names = {item.interface for item in admissions}
    assert {"daily", "daily_basic", "trade_cal", "income_vip", "stock_basic"} <= names
    assert len(names) == len(admissions)
    for item in admissions:
        assert item.primary_class in APP5_INTERFACE_CLASSES
        assert item.reason


def test_optional_standard_frame_fields_require_join_and_asof_policy() -> None:
    from quantaalpha.backtest.contracts import OptionalStandardFrameField, validate_optional_standard_frame_field

    field = OptionalStandardFrameField(
        source_interface="daily_basic",
        source_field="turnover_rate",
        feature_name="$daily_basic_turnover_rate",
        dtype="float32",
        join_key=("datetime", "instrument"),
        time_policy="same_trade_date_no_lookahead",
        missing_policy="nan",
        allowed_usage=("factor_mining",),
    )
    validate_optional_standard_frame_field(field)
    with pytest.raises(ValueError, match="time/asof"):
        validate_optional_standard_frame_field(
            OptionalStandardFrameField(
                source_interface="daily_basic",
                source_field="turnover_rate",
                feature_name="$daily_basic_turnover_rate",
                dtype="float32",
                join_key=("datetime", "instrument"),
                time_policy="",
                missing_policy="nan",
                allowed_usage=("factor_mining",),
            )
        )


def test_metric_namespace_keeps_signal_long_short_and_long_only_separate() -> None:
    from quantaalpha.backtest.contracts import QlibReturnProvenance, build_metric_namespaces

    namespaces = build_metric_namespaces(
        signal_metrics={
            "IC": 0.01,
            "ICIR": 0.2,
            "Rank IC": 0.03,
            "Rank ICIR": 0.4,
            "long_short_return_annualized": 0.99,
        },
        portfolio_metrics={"annualized_return": 0.12, "information_ratio": 0.5},
        daily_report_columns=("return", "bench", "cost", "turnover", "cash", "equity"),
        qlib_return_provenance=QlibReturnProvenance(
            recorder_object="recorder-id",
            dataframe_path='portfolio_metric_dict["1day"][0]',
            column_name="excess_return",
            transformation='report["return"] - report["bench"] - report["cost"]',
            risk_analyzer_input="risk_analysis(excess_return_with_cost)",
            daily_series_name="excess_vs_benchmark.daily_excess_return",
        ),
    )
    assert set(namespaces) == {
        "signal_ic",
        "diagnostic_long_short",
        "long_only_portfolio",
        "excess_vs_benchmark",
        "portfolio_diagnostics",
    }
    assert "long_short_return_annualized" in namespaces["diagnostic_long_short"]
    assert "long_short_return_annualized" not in namespaces["excess_vs_benchmark"]
    assert namespaces["excess_vs_benchmark"]["annualized_return"] == 0.12
    assert namespaces["excess_vs_benchmark"]["qlib_return_provenance"]["column_name"] == "excess_return"


def test_metric_namespace_keeps_missing_price_diagnostics_separate() -> None:
    from quantaalpha.backtest.contracts import build_metric_namespaces

    namespaces = build_metric_namespaces(
        portfolio_metrics={
            "annualized_return": 0.12,
            "missing_close_valuation_count": 2,
            "missing_open_buy_skip_count": 3,
            "missing_open_sell_skip_count": 4,
            "missing_price_example_count": 5,
        },
    )

    assert namespaces["portfolio_diagnostics"] == {
        "missing_close_valuation_count": 2,
        "missing_open_buy_skip_count": 3,
        "missing_open_sell_skip_count": 4,
        "missing_price_example_count": 5,
    }
    assert "missing_close_valuation_count" not in namespaces["excess_vs_benchmark"]


def test_long_only_daily_report_contract_is_deterministic_for_same_prediction() -> None:
    from quantaalpha.backtest.noqlib.portfolio import NoQlibTopkDropoutBacktester

    dates = pd.date_range("2020-01-01", periods=5, freq="D")
    instruments = ["A", "B", "C"]
    index = pd.MultiIndex.from_product([dates, instruments], names=["datetime", "instrument"])
    market = pd.DataFrame(
        {
            "$open": [10.0, 20.0, 30.0] * len(dates),
            "$high": [11.0, 21.0, 31.0] * len(dates),
            "$low": [9.0, 19.0, 29.0] * len(dates),
            "$close": [10.5, 20.5, 30.5] * len(dates),
            "$volume": [100.0, 100.0, 100.0] * len(dates),
            "$vwap": [10.2, 20.2, 30.2] * len(dates),
            "$return": [0.01, 0.02, 0.03] * len(dates),
        },
        index=index,
    )
    prediction = pd.Series(range(len(index)), index=index, dtype=float)
    config = {
        "backtest": {
            "strategy": {"kwargs": {"topk": 2, "n_drop": 1}},
            "backtest": {
                "start_time": "2020-01-02",
                "end_time": "2020-01-05",
                "account": 1000000,
                "benchmark": "mean",
                "exchange_kwargs": {"open_cost": 0.0, "close_cost": 0.0, "min_cost": 0.0},
            },
        }
    }

    _left_metrics, left_report, left_positions = NoQlibTopkDropoutBacktester(config, market).run(prediction)
    _right_metrics, right_report, right_positions = NoQlibTopkDropoutBacktester(config, market).run(prediction)

    assert {"return", "bench", "cost", "turnover", "cash", "equity"} <= set(left_report.columns)
    pd.testing.assert_frame_equal(left_report, right_report)
    pd.testing.assert_frame_equal(left_positions, right_positions)


def test_app5_standard_frame_builder_materializes_manifest(tmp_path: Path) -> None:
    from quantaalpha.backtest.contracts import OptionalStandardFrameField
    from quantaalpha.backtest.standard_frame import App5StandardFrameBuilder, StandardFrameRequest

    storage_root = tmp_path / "data"
    daily_frame = pl.DataFrame(
        {
            "ts_code": ["000001.SZ", "000001.SZ"],
            "trade_date": ["20240102", "20240103"],
            "open": [10.0, 11.0],
            "high": [10.5, 11.5],
            "low": [9.5, 10.5],
            "close": [10.2, 11.2],
            "vol": [1000.0, 1100.0],
            "amount": [1020.0, 1232.0],
            "pct_chg": [1.0, 9.8039],
        }
    )
    daily_basic_frame = pl.DataFrame(
        {
            "ts_code": ["000001.SZ", "000001.SZ"],
            "trade_date": ["20240102", "20240103"],
            "turnover_rate": [1.2, 1.3],
        }
    )

    class FakeAdapter:
        def read(self, interface_name, **kwargs):
            del kwargs
            return {"daily": daily_frame, "daily_basic": daily_basic_frame}[interface_name]

    result = App5StandardFrameBuilder(adapter=FakeAdapter(), storage_root=storage_root).build(
        StandardFrameRequest(
            start_date="2024-01-02",
            end_date="2024-01-03",
            storage_root=str(storage_root),
            materialized_cache_root=str(tmp_path / "cache"),
            optional_fields=(
                OptionalStandardFrameField(
                    source_interface="daily_basic",
                    source_field="turnover_rate",
                    feature_name="$daily_basic_turnover_rate",
                    dtype="float64",
                    join_key=("datetime", "instrument"),
                    time_policy="same_trade_date_no_lookahead",
                    missing_policy="required",
                    allowed_usage=("factor_mining", "backtest_standard_frame"),
                ),
            ),
        )
    )

    assert {"datetime", "instrument", "$open", "$return", "$daily_basic_turnover_rate"} <= set(result.frame.columns)
    assert result.manifest["standard_frame"]["row_count"] == 2
    assert result.parquet_path and Path(result.parquet_path).exists()
    assert result.manifest_path and Path(result.manifest_path).exists()


def test_app5_standard_frame_qfq_adjustment_uses_explicit_adjusted_prices(tmp_path: Path) -> None:
    from quantaalpha.backtest.standard_frame import App5StandardFrameBuilder, StandardFrameRequest

    daily_frame = pl.DataFrame(
        {
            "ts_code": ["000001.SZ", "000001.SZ"],
            "trade_date": ["20240102", "20240103"],
            "open_qfq": [8.0, 8.8],
            "high_qfq": [8.4, 9.1],
            "low_qfq": [7.9, 8.7],
            "close_qfq": [8.2, 9.0],
            "vol": [1000.0, 1100.0],
            "amount": [1020.0, 1232.0],
            "pct_chg": [1.0, 9.7561],
        }
    )

    class FakeAdapter:
        def read(self, interface_name, **kwargs):
            del interface_name, kwargs
            return daily_frame

    result = App5StandardFrameBuilder(adapter=FakeAdapter(), storage_root=tmp_path).build(
        StandardFrameRequest(
            start_date="2024-01-02",
            end_date="2024-01-03",
            daily_interface="stk_factor_pro",
            adjustment="qfq",
        )
    )

    assert result.manifest["standard_frame"]["adjustment"] == "qfq"
    assert result.frame.get_column("$open").to_list() == [8.0, 8.8]
    assert result.frame.get_column("$close").to_list() == [8.2, 9.0]
    assert result.frame.get_column("$vwap").to_list() == [8.2, 9.0]


def test_app5_standard_frame_qfq_adjustment_fails_without_adjusted_columns(tmp_path: Path) -> None:
    from quantaalpha.backtest.standard_frame import App5StandardFrameBuilder, StandardFrameRequest

    class FakeAdapter:
        def read(self, interface_name, **kwargs):
            del interface_name, kwargs
            return pl.DataFrame(
                {
                    "ts_code": ["000001.SZ"],
                    "trade_date": ["20240102"],
                    "open": [10.0],
                    "high": [10.5],
                    "low": [9.5],
                    "close": [10.2],
                    "vol": [1000.0],
                    "amount": [1020.0],
                    "pct_chg": [1.0],
                }
            )

    with pytest.raises(ValueError, match="adjustment=qfq requires columns"):
        App5StandardFrameBuilder(adapter=FakeAdapter(), storage_root=tmp_path).build(
            StandardFrameRequest(daily_interface="daily", adjustment="qfq")
        )


def test_app5_standard_frame_rejects_optional_field_without_asof_policy(tmp_path: Path) -> None:
    from quantaalpha.backtest.standard_frame import request_from_mapping

    with pytest.raises(KeyError):
        request_from_mapping(
            {
                "optional_fields": [
                    {
                        "source_interface": "daily_basic",
                        "source_field": "turnover_rate",
                        "feature_name": "$daily_basic_turnover_rate",
                        "allowed_usage": ["factor_mining"],
                    }
                ]
            }
        )


def test_qlib_return_provenance_extraction_and_required_payload() -> None:
    from quantaalpha.backtest.qlib_provenance import (
        extract_excess_return_series,
        qlib_excess_return_provenance,
        require_qlib_return_provenance,
    )

    report = pd.DataFrame({"return": [0.02, 0.01], "bench": [0.01, 0.0], "cost": [0.001, 0.002]})
    series = extract_excess_return_series(report)
    assert series.tolist() == pytest.approx([0.009, 0.008])
    provenance = qlib_excess_return_provenance(recorder_object="recorder").to_dict()
    payload = require_qlib_return_provenance(
        {"metric_namespaces": {"excess_vs_benchmark": {"qlib_return_provenance": provenance}}}
    )
    assert payload["risk_analyzer_input"] == "qlib.contrib.evaluate.risk_analysis(excess_return_with_cost)"


def test_long_only_parity_blocks_annualized_return_until_daily_series_proven() -> None:
    from quantaalpha.backtest.long_only_parity import (
        assert_annualized_return_comparable,
        compare_long_only_daily_reports,
    )

    left = pd.DataFrame(
        {"return": [0.01, 0.02], "bench": [0.0, 0.01], "cost": [0.001, 0.001]},
        index=pd.date_range("2020-01-01", periods=2),
    )
    right = left.copy()
    report = compare_long_only_daily_reports(left, right)
    assert report.passed is True
    with pytest.raises(ValueError, match="source_series_proven_identical"):
        assert_annualized_return_comparable(report, {"source_series_proven_identical": False})
    assert_annualized_return_comparable(report, {"source_series_proven_identical": True})


def test_neg_function_normalizes_to_unary_minus_for_generated_expressions() -> None:
    from quantaalpha.backtest.expression import canonicalize_expression
    from quantaalpha.factors.expression_syntax import normalize_expression_syntax, normalize_neg_function

    expr = "NEG(TS_CORR($return, DELAY($return, 1), 5)) * RANK(TS_STD($volume, 20))"
    assert normalize_neg_function(expr) == "-(TS_CORR($return, DELAY($return, 1), 5)) * RANK(TS_STD($volume, 20))"
    assert canonicalize_expression(expr).canonical.startswith("-(TS_CORR")

    autocorr_expr = "RANK(ABS(TS_AUTOCORRELATION($return, 5)) * TS_STD($return, 20))"
    assert "TS_AUTOCORRELATION" not in normalize_expression_syntax(autocorr_expr)
    assert "TS_CORR($return, DELAY($return, 1), 5)" in canonicalize_expression(autocorr_expr).canonical
