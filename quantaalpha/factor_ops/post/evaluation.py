"""Training POST evaluation adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from quantaalpha.factor_ops.eval.health_scorer import HealthScorer
from quantaalpha.factor_ops.utils._stats import is_finite


@dataclass(frozen=True)
class EvaluationPostResult:
    """训练后评价接入结果。"""

    factor_id: str
    health_inputs: dict[str, dict[str, float]]
    health_score: float
    health_confidence: float
    eval_snapshot: dict[str, Any]
    manifest_stage_output: dict[str, Any]


class EvaluationPostProcessor:
    """把训练后评价指标转为 factor_ops eval/health 契约。"""

    def __init__(self, health_scorer: HealthScorer | None = None) -> None:
        """初始化处理器。"""
        self.health_scorer = health_scorer or HealthScorer()

    def process(
        self,
        *,
        factor_id: str,
        evaluation_metrics: dict[str, Any],
        stage_output_path: str = "",
    ) -> EvaluationPostResult:
        """规范化评价指标并计算健康分。"""
        health_inputs = self._health_inputs(evaluation_metrics)
        health_result = self.health_scorer.compute(factor_id, **health_inputs)
        snapshot = {
            "factor_id": factor_id,
            "health_score": health_result.health_score,
            "health_confidence": health_result.health_confidence,
            "health_breakdown": health_result.health_breakdown,
            "health_inputs": health_inputs,
            "raw_metrics": dict(evaluation_metrics),
        }
        manifest = {
            "evaluation_result_path": stage_output_path,
            "health_score": health_result.health_score,
        }
        return EvaluationPostResult(
            factor_id=factor_id,
            health_inputs=health_inputs,
            health_score=health_result.health_score,
            health_confidence=health_result.health_confidence,
            eval_snapshot=snapshot,
            manifest_stage_output=manifest,
        )

    def _health_inputs(self, metrics: dict[str, Any]) -> dict[str, dict[str, float]]:
        prediction = _compact(
            {
                "ic": _metric(metrics, "IC", "ic"),
                "rank_ic": _metric(metrics, "Rank IC", "RankIC", "rank_ic"),
            }
        )
        stability = _compact({"icir": _metric(metrics, "ICIR", "icir")})
        oos = _compact(
            {
                "oos_ic": _metric(metrics, "OOS IC", "oos_ic"),
                "oos_icir": _metric(metrics, "OOS ICIR", "oos_icir"),
            }
        )
        tradability = _compact(
            {
                "turnover": _metric(metrics, "turnover_rate", "turnover"),
                "sharpe_after_cost": _metric(metrics, "sharpe_after_cost", "after_cost_sharpe"),
            }
        )
        output: dict[str, dict[str, float]] = {}
        if prediction:
            output["prediction_power"] = prediction
        if stability:
            output["stability"] = stability
        if oos:
            output["oos_ability"] = oos
        if tradability:
            output["tradability"] = tradability
        return output


def _metric(metrics: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = metrics.get(key)
        if is_finite(value):
            return float(value)
    return None


def _compact(values: dict[str, float | None]) -> dict[str, float]:
    return {key: value for key, value in values.items() if value is not None}
