"""Training trigger condition evaluator."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from quantaalpha.factor_ops.eval.foundation_index import FoundationHealthIndexComputer


class TriggerConditionEvaluator:
    """统一评估训练触发条件。"""

    PRIORITIES = {
        "manual": 1,
        "fhi_drop": 2,
        "data_update": 3,
        "revalidation_decay": 4,
        "new_factor_threshold": 5,
        "schedule": 6,
    }

    def __init__(
        self,
        *,
        cooldown_minutes: int = 0,
        fhi_computer: FoundationHealthIndexComputer | None = None,
    ) -> None:
        """初始化 evaluator。"""
        self.cooldown_minutes = cooldown_minutes
        self.fhi_computer = fhi_computer or FoundationHealthIndexComputer()

    def evaluate(
        self,
        *,
        now: datetime | None = None,
        last_triggered_at: datetime | None = None,
        manual_requested: bool = False,
        fhi_history: list[float] | None = None,
        data_update: dict[str, Any] | None = None,
        revalidation_decay_count: int = 0,
        new_factor_count: int = 0,
        mining_new_factor_threshold: int = 5,
        scheduled: bool = False,
    ) -> dict[str, Any]:
        """返回最高优先级触发结果。"""
        now = now or datetime.now()
        if self._in_cooldown(now, last_triggered_at):
            return {"triggered": False, "reason": "cooldown", "priority": 99}

        candidates: list[str] = []
        if manual_requested:
            candidates.append("manual")
        if self.fhi_computer.detect_drop_trigger(fhi_history or [])["triggered"]:
            candidates.append("fhi_drop")
        if data_update and "training_evaluation" in data_update.get("workflows", []):
            candidates.append("data_update")
        if revalidation_decay_count > 0:
            candidates.append("revalidation_decay")
        if new_factor_count >= mining_new_factor_threshold:
            candidates.append("new_factor_threshold")
        if scheduled:
            candidates.append("schedule")
        if not candidates:
            return {"triggered": False, "reason": "", "priority": 99}
        reason = min(candidates, key=lambda item: self.PRIORITIES[item])
        return {"triggered": True, "reason": reason, "priority": self.PRIORITIES[reason]}

    def _in_cooldown(self, now: datetime, last_triggered_at: datetime | None) -> bool:
        if last_triggered_at is None or self.cooldown_minutes <= 0:
            return False
        elapsed_minutes = (now - last_triggered_at).total_seconds() / 60
        return elapsed_minutes < self.cooldown_minutes
