from __future__ import annotations

import json
from dataclasses import dataclass

import polars as pl
from quantaalpha.factor_ops.lifecycle.log_writer import LifecycleLogReader
from quantaalpha.factor_ops.monitor.input_adapter import (
    DegradationLifecycleBridge,
    FactorMonitorInputAdapter,
)


def test_monitor_input_adapter_exports_daily_ic_contract_for_health_score() -> None:
    """Monitor 输出标准化为 HealthScorer 可消费的 daily IC 契约。"""
    raw = pl.DataFrame(
        {
            "trade_date": ["2026-05-02", "2026-05-01", "2026-05-01"],
            "factor_name": ["value", "value", "quality"],
            "ic_mean": [0.03, 0.02, -0.01],
            "rank_ic_mean": [0.04, 0.01, -0.02],
            "coverage": [0.98, 0.97, 0.96],
        }
    )

    daily_ic = FactorMonitorInputAdapter().export_daily_ic(
        raw,
        factor_column="factor_name",
        date_column="trade_date",
        ic_column="ic_mean",
        rank_ic_column="rank_ic_mean",
    )

    assert daily_ic.columns == ["date", "factor_id", "ic", "rank_ic", "coverage"]
    assert daily_ic.to_dicts() == [
        {"date": "2026-05-01", "factor_id": "quality", "ic": -0.01, "rank_ic": -0.02, "coverage": 0.96},
        {"date": "2026-05-01", "factor_id": "value", "ic": 0.02, "rank_ic": 0.01, "coverage": 0.97},
        {"date": "2026-05-02", "factor_id": "value", "ic": 0.03, "rank_ic": 0.04, "coverage": 0.98},
    ]


def test_monitor_input_adapter_reads_daily_ic_parquet_with_filters(tmp_path) -> None:
    """Monitor daily IC 可从 Parquet 读取并按 factor/date 过滤。"""
    source = tmp_path / "monitor_daily_ic.parquet"
    pl.DataFrame(
        {
            "date": ["2026-05-01", "2026-05-02", "2026-05-03"],
            "factor_id": ["value", "value", "quality"],
            "ic": [0.02, 0.03, -0.01],
            "rank_ic": [0.01, 0.04, -0.02],
        }
    ).write_parquet(source)

    daily_ic = FactorMonitorInputAdapter().read_daily_ic(
        source,
        factor_id="value",
        start="2026-05-02",
        end="2026-05-31",
    )

    assert daily_ic.to_dicts() == [
        {"date": "2026-05-02", "factor_id": "value", "ic": 0.03, "rank_ic": 0.04}
    ]


@dataclass(frozen=True)
class _DegradationSuggestion:
    factor_id: str = "factor_001"
    factor_name: str = "value"
    current_status: str = "active"
    recommended_status: str = "watch"
    reason: str = "Rolling IC mean below threshold"
    rolling_ic_mean: float = 0.003
    trend_slope: float = -0.002
    consecutive_low_count: int = 8


def test_degradation_lifecycle_bridge_writes_audited_suggestion(tmp_path) -> None:
    """降解建议先写 lifecycle_log，保留检测指标快照。"""
    bridge = DegradationLifecycleBridge(tmp_path)

    log_ids = bridge.write_suggestions(
        [_DegradationSuggestion()],
        timestamp="2026-05-05T11:00:00",
        created_at="2026-05-05T11:00:01",
    )

    assert len(log_ids) == 1
    row = LifecycleLogReader(tmp_path).query(factor_id="factor_001").row(0, named=True)
    assert row["old_status"] == "active"
    assert row["new_status"] == "watch"
    assert row["operator"] == "degradation_detector"
    assert row["reason"] == "Rolling IC mean below threshold"
    assert json.loads(row["metrics_snapshot"]) == {
        "consecutive_low_count": 8,
        "factor_name": "value",
        "rolling_ic_mean": 0.003,
        "trend_slope": -0.002,
    }
