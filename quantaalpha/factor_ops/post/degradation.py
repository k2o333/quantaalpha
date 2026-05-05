"""Training POST degradation adapter."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from quantaalpha.factor_ops.monitor.input_adapter import DegradationLifecycleBridge


@dataclass(frozen=True)
class DegradationPostResult:
    """训练后衰减处理结果。"""

    factor_ids: list[str]
    lifecycle_log_ids: list[str]
    suggested_ops_updates: list[dict[str, Any]]


class DegradationPostProcessor:
    """把降解检测建议写入审计日志，并转换为 ops 更新建议。"""

    def __init__(self, lifecycle_storage_root: str | Path) -> None:
        """初始化处理器。"""
        self.bridge = DegradationLifecycleBridge(lifecycle_storage_root)

    def process(
        self,
        suggestions: Iterable[Any],
        *,
        timestamp: str,
    ) -> DegradationPostResult:
        """处理降解建议。"""
        actionable = [
            suggestion
            for suggestion in suggestions
            if getattr(suggestion, "recommended_status", "") in {"watch", "degraded"}
        ]
        log_ids = self.bridge.write_suggestions(actionable, timestamp=timestamp, created_at=timestamp)
        return DegradationPostResult(
            factor_ids=[str(getattr(suggestion, "factor_id")) for suggestion in actionable],
            lifecycle_log_ids=log_ids,
            suggested_ops_updates=[self._ops_update(suggestion) for suggestion in actionable],
        )

    @staticmethod
    def _ops_update(suggestion: Any) -> dict[str, Any]:
        return {
            "factor_id": str(getattr(suggestion, "factor_id")),
            "ops_update": {
                "status": getattr(suggestion, "recommended_status"),
                "recent_performance": {
                    "trend_slope": getattr(suggestion, "trend_slope", None),
                    "rolling_ic_mean": getattr(suggestion, "rolling_ic_mean", None),
                    "consecutive_low_count": getattr(suggestion, "consecutive_low_count", 0),
                },
            },
            "reason": getattr(suggestion, "reason", ""),
        }
