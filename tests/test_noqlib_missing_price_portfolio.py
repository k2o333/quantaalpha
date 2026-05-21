from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl
import pytest


def _base_config(*, risk_degree: float = 1.0) -> dict:
    return {
        "backtest": {
            "strategy": {"kwargs": {"topk": 1, "n_drop": 1, "risk_degree": risk_degree}},
            "backtest": {
                "start_time": "2021-01-01",
                "end_time": "2021-01-03",
                "account": 1000,
                "benchmark": "mean",
                "exchange_kwargs": {"open_cost": 0.0, "close_cost": 0.0, "min_cost": 0.0},
            },
        }
    }


def _market(rows: list[dict]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    frame["datetime"] = pd.to_datetime(frame["datetime"])
    return frame.set_index(["datetime", "instrument"]).sort_index()


def _prediction(prefer_b_on_day2: bool = False) -> pd.Series:
    index = pd.MultiIndex.from_tuples(
        [
            (pd.Timestamp("2021-01-01"), "A"),
            (pd.Timestamp("2021-01-01"), "B"),
            (pd.Timestamp("2021-01-02"), "A"),
            (pd.Timestamp("2021-01-02"), "B"),
        ],
        names=["datetime", "instrument"],
    )
    values = [10.0, 1.0, 1.0, 10.0] if prefer_b_on_day2 else [10.0, 1.0, 10.0, 1.0]
    return pd.Series(values, index=index)


def test_missing_close_does_not_produce_silent_zero_drawdown() -> None:
    from quantaalpha.backtest.noqlib.portfolio import NoQlibTopkDropoutBacktester

    market = _market(
        [
            {"datetime": "2021-01-01", "instrument": "A", "$open": 10.0, "$close": 10.0, "$return": 0.0},
            {"datetime": "2021-01-01", "instrument": "B", "$open": 20.0, "$close": 20.0, "$return": 0.0},
            {"datetime": "2021-01-02", "instrument": "A", "$open": 10.0, "$close": 10.0, "$return": 0.0},
            {"datetime": "2021-01-02", "instrument": "B", "$open": 20.0, "$close": 20.0, "$return": 0.0},
            {"datetime": "2021-01-03", "instrument": "B", "$open": 20.0, "$close": 20.0, "$return": 0.0},
        ]
    )

    metrics, report, _positions = NoQlibTopkDropoutBacktester(_base_config(), market).run(_prediction())

    assert np.isfinite(report[["return", "cash", "equity"]].to_numpy(dtype=float)).all()
    assert metrics["missing_close_valuation_count"] == 1
    assert metrics["missing_price_example_count"] == 1
    assert metrics["max_drawdown"] <= 0.0


def test_missing_sell_open_skips_trade_and_records_diagnostic() -> None:
    from quantaalpha.backtest.noqlib.portfolio import NoQlibTopkDropoutBacktester

    market = _market(
        [
            {"datetime": "2021-01-01", "instrument": "A", "$open": 10.0, "$close": 10.0, "$return": 0.0},
            {"datetime": "2021-01-01", "instrument": "B", "$open": 20.0, "$close": 20.0, "$return": 0.0},
            {"datetime": "2021-01-02", "instrument": "A", "$open": 10.0, "$close": 10.0, "$return": 0.0},
            {"datetime": "2021-01-02", "instrument": "B", "$open": 20.0, "$close": 20.0, "$return": 0.0},
            {"datetime": "2021-01-03", "instrument": "A", "$open": float("nan"), "$close": 10.0, "$return": 0.0},
            {"datetime": "2021-01-03", "instrument": "B", "$open": 20.0, "$close": 20.0, "$return": 0.0},
        ]
    )

    metrics, report, positions = NoQlibTopkDropoutBacktester(_base_config(risk_degree=0.5), market).run(_prediction(prefer_b_on_day2=True))

    assert np.isfinite(report[["return", "cash", "equity"]].to_numpy(dtype=float)).all()
    assert metrics["missing_open_sell_skip_count"] == 1
    assert positions.loc[positions["date"].eq(pd.Timestamp("2021-01-03")), "instrument"].to_list() == ["A"]


def test_save_results_preserves_missing_price_counters(tmp_path: Path) -> None:
    from quantaalpha.backtest.noqlib.result_writer import save_results

    metrics = {
        "annualized_return": 0.1,
        "information_ratio": 1.0,
        "max_drawdown": -0.2,
        "calmar_ratio": 0.5,
        "missing_close_valuation_count": 2,
        "missing_open_buy_skip_count": 3,
        "missing_open_sell_skip_count": 4,
        "missing_price_example_count": 5,
    }
    output_path = save_results(
        config={"experiment": {"output_dir": str(tmp_path), "output_metrics_file": "metrics.json"}},
        metrics=metrics,
        exp_name="missing_price",
        factor_source="custom",
        num_factors=1,
        elapsed=0.1,
        output_name=None,
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    saved_metrics = payload["metrics"]
    assert saved_metrics["missing_close_valuation_count"] == 2
    assert saved_metrics["missing_open_buy_skip_count"] == 3
    assert saved_metrics["missing_open_sell_skip_count"] == 4
    assert saved_metrics["missing_price_example_count"] == 5


def test_save_results_writes_parquet_artifacts_with_explicit_date_columns(tmp_path: Path) -> None:
    from quantaalpha.backtest.noqlib.result_writer import save_results

    daily_report = pd.DataFrame(
        {
            "return": [0.01, -0.02],
            "bench": [0.001, 0.002],
            "cost": [0.0001, 0.0002],
            "turnover": [0.5, 0.4],
            "cash": [100.0, 98.0],
            "equity": [101.0, 99.0],
        },
        index=pd.Index(pd.to_datetime(["2021-01-01", "2021-01-02"]), name="datetime"),
    )
    positions = pd.DataFrame(
        {
            "date": pd.to_datetime(["2021-01-01", "2021-01-02"]),
            "instrument": ["A", "B"],
            "weight": [0.6, 0.4],
        }
    )

    save_results(
        config={"experiment": {"output_dir": str(tmp_path), "output_metrics_file": "metrics.json"}},
        metrics={"annualized_return": 0.1},
        exp_name="parquet_artifacts",
        factor_source="custom",
        num_factors=1,
        elapsed=0.1,
        output_name="demo",
        daily_report=daily_report,
        positions=positions,
    )

    daily_path = tmp_path / "demo_long_only_daily_report.parquet"
    excess_path = tmp_path / "demo_cumulative_excess.parquet"
    positions_path = tmp_path / "demo_long_only_positions.parquet"

    assert daily_path.exists()
    assert excess_path.exists()
    assert positions_path.exists()
    assert not (tmp_path / "demo_long_only_daily_report.csv").exists()
    assert not (tmp_path / "demo_cumulative_excess.csv").exists()
    assert not (tmp_path / "demo_long_only_positions.csv").exists()

    daily = pl.read_parquet(daily_path)
    assert daily.columns[:4] == ["date", "return", "bench", "cost"]
    assert daily.height == 2

    excess = pl.read_parquet(excess_path)
    assert excess.columns == ["date", "daily_excess_return", "cumulative_excess_return"]
    assert excess["daily_excess_return"].to_list() == pytest.approx([0.0089, -0.0222])
    assert excess["cumulative_excess_return"].to_list() == pytest.approx([0.0089, -0.0133])

    saved_positions = pl.read_parquet(positions_path)
    assert saved_positions.columns == ["date", "instrument", "weight"]


@pytest.mark.real_data
def test_app5_stk_factor_pro_has_known_600519_gap() -> None:
    import polars as pl

    root = Path("/home/quan/testdata/aspipe_v4/data")
    daily_manifest = root / "daily" / "manifest" / "current.json"
    pro_manifest = root / "stk_factor_pro" / "manifest" / "current.json"
    if not daily_manifest.exists() or not pro_manifest.exists():
        pytest.skip("App5 daily/stk_factor_pro manifests are not available")

    def dates_for(interface: str) -> set[str]:
        manifest = json.loads((root / interface / "manifest" / "current.json").read_text(encoding="utf-8"))
        files = [str(root / interface / item) for item in manifest.get("active_files", [])]
        if not files:
            pytest.skip(f"{interface} manifest has no active files")
        frame = (
            pl.scan_parquet(files, missing_columns="insert")
            .filter(
                (pl.col("ts_code").cast(pl.Utf8) == "600519.SH")
                & (pl.col("trade_date").cast(pl.Utf8) >= "20210101")
                & (pl.col("trade_date").cast(pl.Utf8) <= "20210110")
            )
            .select(pl.col("trade_date").cast(pl.Utf8))
            .collect()
        )
        return set(frame.get_column("trade_date").to_list())

    assert {"20210104", "20210105", "20210106", "20210107", "20210108"} <= dates_for("daily")
    assert dates_for("stk_factor_pro") == {"20210104", "20210105", "20210108"}
