from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pandas as pd
import polars as pl

from quantaalpha.factor_ops.performance_history import (
    PerformanceHistoryStore,
    build_summary_row,
)
from quantaalpha.pipeline.loop import append_combined_backtest_performance_history


def test_performance_history_appends_factor_history_and_latest_snapshot(tmp_path):
    store = PerformanceHistoryStore(tmp_path)

    first = build_summary_row(
        factor_id="factor-a",
        factor_name="AlphaA",
        factor_expression="DELTA(close, 5)",
        translated_expression="delta(close, 5)",
        source="mining_validation",
        validated_at=datetime(2026, 5, 1, 9, 30),
        execution_periods={
            "train": ("2020-01-01", "2022-12-31"),
            "valid": ("2023-01-01", "2023-12-31"),
            "test": ("2024-01-01", "2024-12-31"),
        },
        status="success",
        passed=True,
        ic_mean=0.031,
        ic_std=0.1,
        icir=0.31,
        positive_ratio=0.62,
        daily_ic_count=2,
        min_ic=0.02,
        min_rank_ic=0.01,
        computation_time_seconds=1.5,
    )
    second = build_summary_row(
        factor_id="factor-a",
        factor_name="AlphaA",
        factor_expression="DELTA(close, 5)",
        translated_expression="delta(close, 5)",
        source="revalidation",
        validated_at=datetime(2026, 6, 1, 9, 30),
        execution_periods={
            "train": ("2020-02-01", "2023-01-31"),
            "valid": ("2023-02-01", "2024-01-31"),
            "test": ("2024-02-01", "2025-01-31"),
        },
        status="failure",
        passed=False,
        ic_mean=0.004,
        ic_std=0.2,
        icir=0.02,
        positive_ratio=0.51,
        daily_ic_count=2,
        min_ic=0.02,
        min_rank_ic=0.01,
        computation_time_seconds=1.2,
        error_message="below threshold",
    )

    store.append_summary(first)
    store.append_summary(second)
    store.append_series(
        factor_id="factor-a",
        validation_id=second["validation_id"],
        metric_name="daily_ic",
        values=[0.01, -0.002],
        created_at=datetime(2026, 6, 1, 9, 31),
    )
    latest_path = store.refresh_latest_by_factor()

    history = store.load_factor_history("factor-a")
    assert history.select("source").to_series().to_list() == [
        "mining_validation",
        "revalidation",
    ]
    assert history.select("schema_version").to_series().to_list() == [1, 1]
    assert history.select("passed").to_series().to_list() == [True, False]

    latest = pl.read_parquet(latest_path)
    assert latest.select("factor_id").to_series().to_list() == ["factor-a"]
    assert latest.select("source").to_series().to_list() == ["revalidation"]

    series = pl.read_parquet(next((tmp_path / "series").glob("year=*/month=*/*.parquet")))
    assert series.select("metric_value").to_series().to_list() == [0.01, -0.002]
    assert series.select("metric_index").to_series().to_list() == [0, 1]


def test_combined_backtest_history_is_marked_as_combined_scope(tmp_path):
    store = PerformanceHistoryStore(tmp_path)
    experiment = SimpleNamespace(
        sub_tasks=[
            SimpleNamespace(
                factor_name="FactorA",
                factor_expression="TS_MEAN($close, 5)",
            ),
            SimpleNamespace(
                factor_name="FactorB",
                factor_expression="TS_STD($volume, 10)",
            ),
        ],
        result=pd.DataFrame(
            {"value": [0.021, 0.31, 0.019, 0.28, 0.18, 1.2, -0.08]},
            index=[
                "IC",
                "ICIR",
                "Rank IC",
                "Rank ICIR",
                "1day.excess_return_with_cost.annualized_return",
                "1day.excess_return_with_cost.information_ratio",
                "1day.excess_return_with_cost.max_drawdown",
            ],
        ),
    )

    written = append_combined_backtest_performance_history(
        experiment=experiment,
        store=store,
        performance_history_config={"update_latest_snapshot": True},
        execution_periods={"test": ("2025-01-01", "2025-12-31")},
        round_summary=SimpleNamespace(
            successful_factor_ids=[],
            failed_factor_ids=[],
            failed_reasons={},
        ),
        evolution_phase="original",
        trajectory_id="traj-1",
        round_number=0,
    )

    assert written == 2
    history = pl.concat(
        [pl.read_parquet(path) for path in (tmp_path / "summary").glob("year=*/month=*/*.parquet")],
        how="diagonal",
    )
    assert history.select("source").to_series().to_list() == [
        "mining_combined_backtest",
        "mining_combined_backtest",
    ]
    assert history.select("ic_mean").to_series().to_list() == [0.021, 0.021]
    assert history.select("rank_ic_mean").to_series().to_list() == [0.019, 0.019]
    assert history.select("annualized_return").to_series().to_list() == [0.18, 0.18]
    assert "combined_factor_backtest" in history.select("extra_json").to_series().to_list()[0]
    assert (tmp_path / "latest_by_factor.parquet").exists()


def test_latest_snapshot_handles_null_columns_from_failed_runs(tmp_path):
    store = PerformanceHistoryStore(tmp_path)
    failed = build_summary_row(
        factor_id="factor-a",
        factor_name="FactorA",
        factor_expression="TS_MEAN($close, 5)",
        translated_expression="TS_MEAN($close, 5)",
        source="revalidation",
        validated_at=datetime(2026, 5, 1, 9, 30),
        execution_periods={"test": ("2025-01-01", "2025-12-31")},
        status="failure",
        passed=False,
        error_message="No data available",
    )
    successful = build_summary_row(
        factor_id="factor-a",
        factor_name="FactorA",
        factor_expression="TS_MEAN($close, 5)",
        translated_expression="TS_MEAN($close, 5)",
        source="mining_combined_backtest",
        validated_at=datetime(2026, 5, 2, 9, 30),
        execution_periods={"test": ("2025-01-01", "2025-12-31")},
        status="success",
        passed=True,
        ic_mean=0.021,
        icir=0.31,
        annualized_return=0.18,
    )

    store.append_summary(failed)
    store.append_summary(successful)
    latest_path = store.refresh_latest_by_factor()

    latest = pl.read_parquet(latest_path)
    assert latest.select("source").to_series().to_list() == ["mining_combined_backtest"]
    assert latest.select("ic_mean").to_series().to_list() == [0.021]
