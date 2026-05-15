from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
REPO_ROOT = Path(__file__).resolve().parents[3]


def _market() -> pd.DataFrame:
    rows = []
    for dt in pd.date_range("2020-01-01", periods=4, freq="D"):
        for offset, instrument in enumerate(["A", "B"]):
            close = float(dt.day + offset)
            rows.append(
                {
                    "datetime": dt,
                    "instrument": instrument,
                    "$open": close,
                    "$high": close,
                    "$low": close,
                    "$close": close,
                    "$volume": 100.0,
                    "$vwap": close,
                    "$return": 0.0,
                }
            )
    return pd.DataFrame(rows).set_index(["datetime", "instrument"])


def test_canonicalize_prefers_uppercase_quantaalpha_dsl() -> None:
    from quantaalpha.backtest.expression import canonicalize_expression

    assert canonicalize_expression("Mean($close, 20)").canonical == "TS_MEAN($close, 20)"
    normalized = canonicalize_expression("ts_mean(close, 20)")
    assert normalized.canonical == "TS_MEAN($close, 20)"
    assert normalized.warnings


def test_shared_polars_kernel_evaluates_canonical_and_aliases() -> None:
    from quantaalpha.backtest.expression import SharedPolarsExpressionKernel

    kernel = SharedPolarsExpressionKernel(_market())
    result = kernel.compute(
        [
            {"factor_id": "mean2", "factor_name": "mean2", "factor_expression": "TS_MEAN($close, 2)"},
            {"factor_id": "ret1", "factor_name": "ret1", "factor_expression": "$close / Ref($close, 1) - 1"},
            {"factor_id": "rank2", "factor_name": "rank2", "factor_expression": "ts_rank(close, 2)"},
        ]
    )
    idx = (pd.Timestamp("2020-01-02"), "A")
    assert result.loc[idx, "mean2"] == pytest.approx(1.5)
    assert result.loc[idx, "ret1"] == pytest.approx(1.0)
    assert result.loc[idx, "rank2"] == pytest.approx(1.0)


def test_shared_polars_kernel_evaluates_alpha158_operator_subset() -> None:
    from quantaalpha.backtest.expression import SharedPolarsExpressionKernel

    kernel = SharedPolarsExpressionKernel(_market())
    result = kernel.compute(
        [
            {"factor_id": "q", "factor_name": "q", "factor_expression": "Quantile($close, 2, 0.5)"},
            {"factor_id": "imax", "factor_name": "imax", "factor_expression": "IdxMax($high, 2)"},
            {"factor_id": "imin", "factor_name": "imin", "factor_expression": "IdxMin($low, 2)"},
            {"factor_id": "corr", "factor_name": "corr", "factor_expression": "Corr($close, Log($volume + 1), 2)"},
            {"factor_id": "slope", "factor_name": "slope", "factor_expression": "Slope($close, 2)"},
            {"factor_id": "rsquare", "factor_name": "rsquare", "factor_expression": "Rsquare($close, 2)"},
            {"factor_id": "resi", "factor_name": "resi", "factor_expression": "Resi($close, 2)"},
            {"factor_id": "greater", "factor_name": "greater", "factor_expression": "Greater($close - DELAY($close, 1), 0)"},
            {"factor_id": "cntp", "factor_name": "cntp", "factor_expression": "TS_MEAN($close > DELAY($close, 1), 2)"},
            {"factor_id": "z", "factor_name": "z", "factor_expression": "TS_ZSCORE($close, 2)"},
            {"factor_id": "rank_cs", "factor_name": "rank_cs", "factor_expression": "RANK($close)"},
            {"factor_id": "median_cs", "factor_name": "median_cs", "factor_expression": "MEDIAN($close)"},
            {"factor_id": "max_elem", "factor_name": "max_elem", "factor_expression": "MAX(0, $close - 2)"},
            {"factor_id": "var2", "factor_name": "var2", "factor_expression": "TS_VAR($close, 2)"},
            {"factor_id": "pct", "factor_name": "pct", "factor_expression": "TS_PCTCHANGE($close, 1)"},
            {"factor_id": "inv", "factor_name": "inv", "factor_expression": "INV($close)"},
            {"factor_id": "sign", "factor_name": "sign", "factor_expression": "SIGN($close - 2)"},
            {"factor_id": "ternary", "factor_name": "ternary", "factor_expression": "($return >= 0) && ($close >= $open) ? 1 : -1"},
            {"factor_id": "filter", "factor_name": "filter", "factor_expression": "FILTER($close, $volume > 0)"},
            {"factor_id": "bb", "factor_name": "bb", "factor_expression": "BB_UPPER($close, 2)"},
            {"factor_id": "macd", "factor_name": "macd", "factor_expression": "MACD($close, 2, 3)"},
            {
                "factor_id": "sumif_and",
                "factor_name": "sumif_and",
                "factor_expression": "SUMIF($return, 2, ($volume > 0) && (ABS($return) < 1))",
            },
            {
                "factor_id": "nested_ternary",
                "factor_name": "nested_ternary",
                "factor_expression": "($close > MEDIAN($close)) ? (($volume > 0) ? 1 : -1) : 0",
            },
            {
                "factor_id": "regbeta_seq",
                "factor_name": "regbeta_seq",
                "factor_expression": "REGBETA(LOG(TS_VAR(DELTA(LOG($close), 1), 2)), LOG(SEQUENCE(2)), 2)",
            },
                {
                    "factor_id": "regbeta_scalar",
                    "factor_name": "regbeta_scalar",
                    "factor_expression": "REGBETA($close, LOG(5), 1)",
                },
        ]
    )
    idx = (pd.Timestamp("2020-01-02"), "A")
    assert result.loc[idx, "q"] == pytest.approx(1.5)
    assert result.loc[idx, "imax"] == pytest.approx(2.0)
    assert result.loc[idx, "imin"] == pytest.approx(1.0)
    assert result.loc[idx, "slope"] == pytest.approx(1.0)
    assert result.loc[idx, "rsquare"] == pytest.approx(1.0)
    assert result.loc[idx, "resi"] == pytest.approx(0.0)
    assert result.loc[idx, "greater"] == pytest.approx(1.0)
    assert result.loc[idx, "cntp"] == pytest.approx(0.5)
    assert result.loc[idx, "z"] == pytest.approx(0.707106, rel=1e-5)
    assert result.loc[idx, "rank_cs"] == pytest.approx(0.5)
    assert result.loc[idx, "median_cs"] == pytest.approx(2.5)
    assert result.loc[idx, "max_elem"] == pytest.approx(0.0)
    assert result.loc[idx, "var2"] == pytest.approx(0.5)
    assert result.loc[idx, "pct"] == pytest.approx(1.0)
    assert result.loc[idx, "inv"] == pytest.approx(0.5)
    assert result.loc[idx, "sign"] == pytest.approx(0.0)
    assert result.loc[idx, "ternary"] == pytest.approx(1.0)
    assert result.loc[idx, "filter"] == pytest.approx(2.0)
    assert result.loc[idx, "bb"] == pytest.approx(2.207106, rel=1e-5)
    assert pd.notna(result.loc[idx, "macd"])
    assert result.loc[idx, "sumif_and"] == pytest.approx(0.0)
    assert result.loc[idx, "nested_ternary"] == pytest.approx(0.0)
    x = np.log(5)
    assert result.loc[idx, "regbeta_scalar"] == pytest.approx(2.0 * x / (x**2 + 1.0))


def test_shared_polars_kernel_count_counts_true_conditions_only() -> None:
    from quantaalpha.backtest.expression import SharedPolarsExpressionKernel

    market = _market()
    result = SharedPolarsExpressionKernel(market).compute_expression("COUNT($close > 2, 2)", "count_true")

    assert pd.isna(result.loc[(pd.Timestamp("2020-01-01"), "A"), "count_true"])
    assert result.loc[(pd.Timestamp("2020-01-02"), "A"), "count_true"] == pytest.approx(0.0)
    assert result.loc[(pd.Timestamp("2020-01-02"), "B"), "count_true"] == pytest.approx(1.0)
    assert result.loc[(pd.Timestamp("2020-01-03"), "A"), "count_true"] == pytest.approx(1.0)
    assert result.loc[(pd.Timestamp("2020-01-03"), "B"), "count_true"] == pytest.approx(2.0)


def test_shared_polars_kernel_rejects_uncovered_operator() -> None:
    from quantaalpha.backtest.expression import SharedPolarsExpressionKernel, UnsupportedExpressionError

    with pytest.raises(UnsupportedExpressionError):
        SharedPolarsExpressionKernel(_market()).compute_expression("SECTOR_RETURN($close)", "sector")


@pytest.mark.parametrize("factor_source,market_start", [("alpha158_20", "2019-09-01"), ("alpha158", "2019-01-01"), ("alpha360", "2019-01-01")])
def test_shared_polars_kernel_matches_real_qlib_oracle_for_builtin_sets(
    tmp_path: Path,
    factor_source: str,
    market_start: str,
) -> None:
    provider_uri = _provider_uri()
    if provider_uri is None:
        pytest.skip("qlib provider data not available")
    pytest.importorskip("qlib")

    from quantaalpha.backtest.factor_loader import FactorLoader
    from quantaalpha.backtest.noqlib.export_qlib_oracle import export_oracle
    from quantaalpha.backtest.expression import SharedPolarsExpressionKernel

    instruments = ["000001.SZ", "000002.SZ", "000008.SZ", "000009.SZ", "000012.SZ"]
    export_oracle(
        provider_uri=str(provider_uri),
        output_dir=str(tmp_path),
        instruments=instruments,
        start_time="2020-01-01",
        end_time="2020-03-31",
        market_start_time=market_start,
        factor_source=factor_source,
    )
    market = pd.read_parquet(tmp_path / "oracle_market.parquet").set_index(["datetime", "instrument"]).sort_index()
    oracle = pd.read_parquet(tmp_path / "oracle_features.parquet").set_index(["datetime", "instrument"]).sort_index()
    factors, _custom = FactorLoader({"factor_source": {"type": factor_source}}).load_factors()
    calculated = SharedPolarsExpressionKernel(market).compute(
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
            err_msg=f"{factor_source}:{column}",
        )


def _provider_uri() -> Path | None:
    candidates = [REPO_ROOT / "third_party" / "data" / "qlib_data_csi300_bin"]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None
