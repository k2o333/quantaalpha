"""A/B/C/D tier classification policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from quantaalpha.factor_ops.utils._stats import is_finite, mean


@dataclass(frozen=True)
class TierResult:
    """分层策略结果。"""

    factor_id: str
    tier: str
    ops_status: str
    weight_cap: float
    ts_gru_group_softmax_cap: float
    reasons: list[str]


class TierClassifier:
    """基于健康分、OOS、相关性和衰减状态分类 A/B/C/D。"""

    def __init__(
        self,
        *,
        min_confidence: float = 0.60,
        core_health_threshold: float = 80.0,
        satellite_health_threshold: float = 60.0,
        watch_health_threshold: float = 40.0,
        max_core_corr: float = 0.85,
        oos_ic_threshold: float = 0.02,
        oos_icir_threshold: float = 0.30,
    ) -> None:
        """初始化分层阈值。"""
        self.min_confidence = min_confidence
        self.core_health_threshold = core_health_threshold
        self.satellite_health_threshold = satellite_health_threshold
        self.watch_health_threshold = watch_health_threshold
        self.max_core_corr = max_core_corr
        self.oos_ic_threshold = oos_ic_threshold
        self.oos_icir_threshold = oos_icir_threshold

    def classify(
        self,
        factor_id: str,
        *,
        health_score: float,
        health_confidence: float,
        **metrics: Any,
    ) -> TierResult:
        """输出分层和下游权重限制。"""
        hard_fail_reasons = self._hard_fail_reasons(health_score, metrics)
        if hard_fail_reasons:
            return self._result(factor_id, "D", "retired", 0.0, hard_fail_reasons)

        confidence_ok = health_confidence >= self.min_confidence
        if health_score >= self.core_health_threshold and confidence_ok:
            core_reasons = self._core_blocking_reasons(metrics)
            if not core_reasons:
                return self._result(factor_id, "A", "core", 1.0, ["core rules passed"])
            return self._result(factor_id, "B", "satellite", 0.5, core_reasons)

        if health_score >= self.satellite_health_threshold and confidence_ok:
            if metrics.get("marginal_contribution") or metrics.get("regime_effective") or health_score >= self.core_health_threshold:
                return self._result(factor_id, "B", "satellite", 0.5, ["satellite rules passed"])
            return self._result(factor_id, "C", "candidate", 0.0, ["missing marginal contribution evidence"])

        if health_score >= self.watch_health_threshold:
            reasons = ["candidate score band"]
            if not confidence_ok:
                reasons.append("confidence below threshold")
            return self._result(factor_id, "C", "watchlist", 0.0, reasons)

        return self._result(factor_id, "D", "retired", 0.0, ["health score below retired threshold"])

    def _hard_fail_reasons(self, health_score: float, metrics: dict[str, Any]) -> list[str]:
        reasons: list[str] = []
        if health_score < self.watch_health_threshold:
            reasons.append("health score below retired threshold")
        if metrics.get("pit_failed"):
            reasons.append("pit failed")
        if metrics.get("severe_data_issue"):
            reasons.append("severe data issue")
        if metrics.get("after_cost_effective") is False:
            reasons.append("after-cost ineffective")
        return reasons

    def _core_blocking_reasons(self, metrics: dict[str, Any]) -> list[str]:
        reasons: list[str] = []
        oos_ic = _number(metrics.get("oos_ic"))
        oos_icir = _number(metrics.get("oos_icir"))
        if oos_ic is None or oos_ic <= self.oos_ic_threshold or oos_icir is None or oos_icir <= self.oos_icir_threshold:
            reasons.append("oos failed")
        max_abs_corr = _number(metrics.get("max_abs_corr"))
        if max_abs_corr is not None and max_abs_corr >= self.max_core_corr:
            reasons.append("correlation too high")
        if self._recent_decay_detected(metrics.get("ic_history")):
            reasons.append("recent decay detected")
        return reasons

    @staticmethod
    def _recent_decay_detected(ic_history: Any) -> bool:
        if not isinstance(ic_history, list) or len(ic_history) < 120:
            return False
        baseline = mean(ic_history[-120:-60])
        recent_60 = mean(ic_history[-60:])
        recent_20 = mean(ic_history[-20:])
        if not is_finite(baseline) or baseline == 0 or not is_finite(recent_60) or not is_finite(recent_20):
            return False
        return (recent_60 / baseline) <= 0.8 or recent_20 <= 0

    @staticmethod
    def _result(factor_id: str, tier: str, status: str, cap: float, reasons: list[str]) -> TierResult:
        return TierResult(
            factor_id=factor_id,
            tier=tier,
            ops_status=status,
            weight_cap=cap,
            ts_gru_group_softmax_cap=cap,
            reasons=reasons,
        )


def _number(value: Any) -> float | None:
    return float(value) if is_finite(value) else None
