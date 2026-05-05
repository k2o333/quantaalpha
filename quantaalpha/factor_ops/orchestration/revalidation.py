"""Revalidation planning helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from quantaalpha.factor_ops.lifecycle.status_machine import StatusMachine


@dataclass(frozen=True)
class RevalidationResult:
    """复验状态映射结果。"""

    factor_id: str
    suggested_status: str
    transition_valid: bool
    health_recompute_required: bool
    lifecycle_log_required: bool


class RevalidationPlanner:
    """按 9-state 运营状态选择复验对象，并映射复验结果。"""

    DEFAULT_ELIGIBLE_STATUSES = {"core", "satellite", "degraded", "candidate"}

    def __init__(self, status_machine: StatusMachine | None = None) -> None:
        """初始化 planner。"""
        self.status_machine = status_machine or StatusMachine()

    def select_candidates(
        self,
        records: list[dict[str, Any]],
        *,
        eligible_statuses: set[str] | None = None,
    ) -> list[str]:
        """返回需要复验的 factor_id 列表。"""
        eligible = eligible_statuses or self.DEFAULT_ELIGIBLE_STATUSES
        selected: list[str] = []
        for record in records:
            status = _ops(record).get("status")
            if status in eligible:
                selected.append(str(record.get("factor_id")))
        return selected

    def map_result(
        self,
        *,
        factor_id: str,
        current_status: str,
        passed: bool,
        consecutive_failures: int = 0,
    ) -> RevalidationResult:
        """把复验结果映射为状态建议。"""
        event = "revalidation_passed" if passed else "revalidation_failed"
        transition = self.status_machine.transition(
            factor_id,
            current_status=current_status,
            event=event,
            consecutive_failures=consecutive_failures,
        )
        if not transition.transition_valid and not passed and current_status in {"core", "satellite"}:
            transition = self.status_machine.transition(
                factor_id,
                current_status=current_status,
                event="health_score_update",
                health_score=0,
                previous_health_score=25,
            )
        return RevalidationResult(
            factor_id=factor_id,
            suggested_status=transition.suggested_status,
            transition_valid=transition.transition_valid,
            health_recompute_required=True,
            lifecycle_log_required=transition.transition_valid,
        )


def _ops(record: dict[str, Any]) -> dict[str, Any]:
    metadata = record.get("metadata_json", {})
    if isinstance(metadata, str):
        metadata = json.loads(metadata or "{}")
    return dict(metadata.get("ops", {}) or {})
