from __future__ import annotations

import json
from dataclasses import dataclass

from quantaalpha.factor_ops.lifecycle.log_writer import LifecycleLogReader
from quantaalpha.factor_ops.post.degradation import DegradationPostProcessor, DegradationPostResult


@dataclass(frozen=True)
class _Suggestion:
    factor_id: str = "factor_001"
    factor_name: str = "value"
    current_status: str = "satellite"
    recommended_status: str = "degraded"
    reason: str = "health score dropped"
    rolling_ic_mean: float = 0.002
    trend_slope: float = -0.003
    consecutive_low_count: int = 9


def test_degradation_post_processor_writes_lifecycle_and_health_recent_input(tmp_path) -> None:
    """Degradation POST 将建议写 lifecycle_log，并产出近期状态输入。"""
    result = DegradationPostProcessor(tmp_path).process(
        [_Suggestion()],
        timestamp="2026-05-05T13:00:00",
    )

    assert isinstance(result, DegradationPostResult)
    assert result.factor_ids == ["factor_001"]
    assert result.suggested_ops_updates == [
        {
            "factor_id": "factor_001",
            "ops_update": {
                "status": "degraded",
                "recent_performance": {
                    "trend_slope": -0.003,
                    "rolling_ic_mean": 0.002,
                    "consecutive_low_count": 9,
                },
            },
            "reason": "health score dropped",
        }
    ]
    row = LifecycleLogReader(tmp_path).query(factor_id="factor_001").row(0, named=True)
    assert row["old_status"] == "satellite"
    assert row["new_status"] == "degraded"
    assert json.loads(row["metrics_snapshot"])["trend_slope"] == -0.003


def test_degradation_post_processor_ignores_active_suggestions(tmp_path) -> None:
    """recommended_status=active 不写 lifecycle，不生成 ops update。"""
    suggestion = _Suggestion(recommended_status="active")
    result = DegradationPostProcessor(tmp_path).process([suggestion], timestamp="2026-05-05T13:00:00")

    assert result.factor_ids == []
    assert result.lifecycle_log_ids == []
    assert result.suggested_ops_updates == []
