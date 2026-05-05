"""Data update routing for factor_ops workflows."""

from __future__ import annotations

from typing import Any


class DataMonitorRouter:
    """将数据更新事件映射为 factor_ops 工作流触发。"""

    PRICE_DATASETS = {"daily_price", "price", "quotes"}
    FUNDAMENTAL_DATASETS = {"fundamental", "financial", "finance"}

    def route_update(self, event: dict[str, Any]) -> dict[str, Any]:
        """输出去重键和待触发工作流。"""
        dataset = str(event.get("dataset", ""))
        change_type = str(event.get("change_type", "update"))
        workflows = ["revalidation", "health_recompute"]
        if event.get("major_update") or dataset in self.PRICE_DATASETS | self.FUNDAMENTAL_DATASETS:
            workflows.append("fhi_recompute")
        if dataset in self.PRICE_DATASETS:
            workflows.append("training_evaluation")
        return {
            "trigger_type": "data_update",
            "workflows": _dedupe(workflows),
            "dedupe_key": f"{dataset}:{change_type}",
            "event": dict(event),
        }


def _dedupe(values: list[str]) -> list[str]:
    output: list[str] = []
    for value in values:
        if value not in output:
            output.append(value)
    return output
