"""9-state factor ops lifecycle status machine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class TransitionResult:
    """状态转换建议结果。"""

    factor_id: str
    old_status: str
    suggested_status: str
    transition_valid: bool
    reason: str
    legacy_status: str
    model_eligible: bool
    applied: bool = False
    error: str = ""


class StatusMachine:
    """运营状态机，第一版只产出 suggested_status。"""

    LEGACY_STATUS_MAP: dict[str, str] = {
        "draft": "pending_validation",
        "testing": "pending_validation",
        "candidate": "active",
        "watchlist": "stale",
        "core": "active",
        "satellite": "active",
        "degraded": "degraded",
        "retired": "deprecated",
        "blacklist": "",
    }
    MODEL_ELIGIBLE = {
        "candidate": True,
        "core": True,
        "satellite": True,
        "degraded": True,
    }

    def transition(
        self,
        factor_id: str,
        *,
        current_status: str,
        event: str,
        **context: Any,
    ) -> TransitionResult:
        """根据事件和上下文生成状态转换建议。"""
        if event == "gate_failed" and context.get("gate_result") == "blacklist":
            return self._valid(factor_id, current_status, "blacklist", context.get("reason", "hard gate failed"))

        if current_status == "draft" and event == "calculation_completed":
            return self._valid(factor_id, current_status, "testing", "calculation completed")

        if current_status == "testing" and event == "gate_passed":
            if context.get("gate_result") == "pass" and _number(context.get("health_score"), 0) >= 40:
                return self._valid(factor_id, current_status, "candidate", "gate passed and health >= 40")

        if current_status == "candidate" and event == "tier_update":
            return self._candidate_tier_transition(factor_id, current_status, context)

        if current_status in {"core", "satellite"} and event == "health_score_update":
            return self._active_health_transition(factor_id, current_status, context)

        if current_status == "satellite" and event == "tier_update" and context.get("tier") == "A":
            return self._valid(factor_id, current_status, "core", "health recovered to core tier")

        if current_status == "degraded":
            if event == "revalidation_failed" and int(context.get("consecutive_failures", 0)) >= 3:
                return self._valid(factor_id, current_status, "retired", "consecutive failures >= 3")
            if event == "revalidation_passed":
                return self._valid(factor_id, current_status, "satellite", "revalidation recovered")

        if current_status in {"candidate", "watchlist"} and event == "timeout_check":
            return self._timeout_transition(factor_id, current_status, context)

        if current_status == "retired" and event == "manual_revalidation_passed":
            return self._valid(factor_id, current_status, "watchlist", "manual revalidation passed")

        if current_status == "retired" and event == "confirm_blacklist":
            return self._valid(factor_id, current_status, "blacklist", "confirmed permanent failure")

        return self._invalid(factor_id, current_status)

    def _candidate_tier_transition(
        self,
        factor_id: str,
        current_status: str,
        context: dict[str, Any],
    ) -> TransitionResult:
        tier = context.get("tier")
        health_score = _number(context.get("health_score"), 0)
        confidence = _number(context.get("health_confidence"), 1)
        if tier == "A" or health_score >= 80:
            return self._valid(factor_id, current_status, "core", "candidate promoted to core")
        if tier == "B" or 60 <= health_score < 80:
            return self._valid(factor_id, current_status, "satellite", "candidate promoted to satellite")
        if tier == "C" or health_score < 60 or confidence < 0.5:
            return self._valid(factor_id, current_status, "watchlist", "candidate moved to watchlist")
        return self._invalid(factor_id, current_status)

    def _active_health_transition(
        self,
        factor_id: str,
        current_status: str,
        context: dict[str, Any],
    ) -> TransitionResult:
        health = _number(context.get("health_score"), 0)
        previous = _number(context.get("previous_health_score"), health)
        if previous - health >= 20:
            return self._valid(factor_id, current_status, "degraded", "health score dropped >= 20")
        if 40 < health < 60:
            return self._valid(factor_id, current_status, "watchlist", "health score in watchlist band")
        if current_status == "core" and 60 <= health < 80:
            return self._valid(factor_id, current_status, "satellite", "core downgraded to satellite")
        return self._invalid(factor_id, current_status)

    def _timeout_transition(
        self,
        factor_id: str,
        current_status: str,
        context: dict[str, Any],
    ) -> TransitionResult:
        entered_at = _parse_datetime(context.get("status_entered_at"))
        if entered_at is None:
            return self._invalid(factor_id, current_status)
        age_days = (datetime.now() - entered_at).days
        health_score = _number(context.get("health_score"), 0)
        if current_status == "candidate" and age_days >= 90 and health_score < 60:
            return self._valid(factor_id, current_status, "retired", "candidate no improvement for 90 days")
        if current_status == "watchlist" and age_days >= 60:
            return self._valid(factor_id, current_status, "retired", "watchlist timeout for 60 days")
        return self._invalid(factor_id, current_status)

    def _valid(self, factor_id: str, old_status: str, new_status: str, reason: str) -> TransitionResult:
        return TransitionResult(
            factor_id=factor_id,
            old_status=old_status,
            suggested_status=new_status,
            transition_valid=True,
            reason=reason,
            legacy_status=self.LEGACY_STATUS_MAP[new_status],
            model_eligible=self.MODEL_ELIGIBLE.get(new_status, False),
        )

    def _invalid(self, factor_id: str, old_status: str) -> TransitionResult:
        return TransitionResult(
            factor_id=factor_id,
            old_status=old_status,
            suggested_status=old_status,
            transition_valid=False,
            reason="",
            legacy_status=self.LEGACY_STATUS_MAP.get(old_status, ""),
            model_eligible=self.MODEL_ELIGIBLE.get(old_status, False),
            error="no transition rule matched",
        )


def _number(value: Any, default: float) -> float:
    return float(value) if isinstance(value, (int, float)) else default


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
