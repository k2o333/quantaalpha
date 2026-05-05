"""七维度因子健康分计算器。"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

import polars as pl

from quantaalpha.factor_ops.utils._stats import is_finite, mean, sample_std
from quantaalpha.factor_ops.utils.ic_trend_calculator import ICTrendCalculator


@dataclass(frozen=True)
class HealthScoreResult:
    """因子健康分结果。"""

    factor_id: str
    health_score: float
    health_confidence: float
    health_breakdown: dict[str, float]


class HealthScorer:
    """计算 0-100 健康分、置信度和七维度明细。"""

    DEFAULT_WEIGHTS: dict[str, int] = {
        "prediction_power": 25,
        "stability": 20,
        "oos_ability": 15,
        "independence": 15,
        "tradability": 10,
        "recent_performance": 10,
        "signal_persistence": 5,
    }
    SINGLE_SIDE_FEE_RATE = 0.0015

    def __init__(self, weights: Mapping[str, int] | None = None) -> None:
        """初始化评分器。"""
        self.weights = dict(weights or self.DEFAULT_WEIGHTS)
        self._trend_calculator = ICTrendCalculator()

    def compute(self, factor_id: str, **inputs: Any) -> HealthScoreResult:
        """计算单个因子的健康分。"""
        dimension_scores = {
            "prediction_power": self._score_prediction_power(inputs.get("prediction_power")),
            "stability": self._score_stability(inputs.get("stability")),
            "oos_ability": self._score_oos_ability(inputs.get("oos_ability")),
            "independence": self._score_independence(inputs.get("independence")),
            "tradability": self._score_tradability(inputs.get("tradability")),
            "recent_performance": self._score_recent_performance(inputs.get("recent_performance"), factor_id),
            "signal_persistence": self._score_signal_persistence(inputs.get("signal_persistence")),
        }
        breakdown = {dimension: score or 0.0 for dimension, score in dimension_scores.items()}
        total_weight = sum(self.weights.values())
        score = sum(breakdown[dimension] * self.weights[dimension] for dimension in self.weights) / total_weight
        confidence = (
            sum(self.weights[dimension] for dimension, value in dimension_scores.items() if value is not None)
            / total_weight
        )
        return HealthScoreResult(
            factor_id=factor_id,
            health_score=score,
            health_confidence=confidence,
            health_breakdown=breakdown,
        )

    @staticmethod
    def map_sigmoid(value: float, *, k: float, x0: float) -> float:
        """按指定参数把数值映射到 0-100。"""
        if not is_finite(value):
            return 0.0
        exponent = -k * (float(value) - x0)
        if exponent > 700:
            return 0.0
        if exponent < -700:
            return 100.0
        return 100 / (1 + math.exp(exponent))

    def _score_prediction_power(self, data: Any) -> float | None:
        payload = _as_mapping(data)
        if payload is None:
            return None
        value = _first_number(payload, ("ic", "rank_ic"))
        if value is None:
            return None
        return self.map_sigmoid(abs(value), k=50, x0=0.03)

    def _score_stability(self, data: Any) -> float | None:
        payload = _as_mapping(data)
        if payload is None:
            return None
        icir = _first_number(payload, ("icir", "stability_icir"))
        if icir is not None:
            return self.map_sigmoid(icir, k=10, x0=0.5)
        score = _first_number(payload, ("stability_score", "period_pass_ratio"))
        if score is None:
            return None
        return _clamp_score(score * 100 if score <= 1 else score)

    def _score_oos_ability(self, data: Any) -> float | None:
        payload = _as_mapping(data)
        if payload is None:
            return None
        value = _first_number(payload, ("oos_ic", "oos_rank_ic"))
        if value is None:
            return None
        return self.map_sigmoid(abs(value), k=50, x0=0.02)

    def _score_independence(self, data: Any) -> float | None:
        payload = _as_mapping(data)
        if payload is None:
            return None
        corr = _first_number(payload, ("max_abs_corr", "correlation"))
        if corr is None:
            similarity = _first_number(payload, ("similarity_score",))
            if similarity is None:
                return None
            corr = similarity
        return self.map_sigmoid(abs(corr), k=-20, x0=0.85)

    def _score_tradability(self, data: Any) -> float | None:
        payload = _as_mapping(data)
        if payload is None:
            return None
        sharpe = _first_number(payload, ("sharpe_after_cost", "after_cost_sharpe"))
        if sharpe is None:
            sharpe = self._calculate_after_cost_sharpe(payload)
        if sharpe is None:
            return None
        return self.map_sigmoid(sharpe, k=5, x0=1.0)

    def _score_recent_performance(self, data: Any, factor_id: str) -> float | None:
        payload = _as_mapping(data)
        if payload is None:
            return None
        slope = _first_number(payload, ("trend_slope", "weighted_slope"))
        if slope is None and isinstance(payload.get("daily_ic"), pl.DataFrame):
            slope = self._daily_ic_weighted_slope(payload["daily_ic"], factor_id)
        if slope is None:
            values = _number_sequence(payload.get("daily_ic_series") or payload.get("ic_series"))
            if values:
                slope = self._trend_calculator.compute_trend_slope(pl.Series(values))["weighted_slope"]
        if slope is None or not is_finite(slope):
            return None
        return self.map_sigmoid(slope, k=10, x0=0)

    def _score_signal_persistence(self, data: Any) -> float | None:
        payload = _as_mapping(data)
        if payload is None:
            return None
        half_life = _first_number(payload, ("half_life", "half_life_days"))
        if half_life is None:
            return None
        return self.map_sigmoid(half_life, k=0.5, x0=10)

    def _daily_ic_weighted_slope(self, daily_ic: pl.DataFrame, factor_id: str) -> float:
        if daily_ic.is_empty() or "ic" not in daily_ic.columns:
            return math.nan
        table = daily_ic
        if "factor_id" in table.columns:
            table = table.filter(pl.col("factor_id") == factor_id)
        sort_columns = [column for column in ("date", "timestamp") if column in table.columns]
        if sort_columns:
            table = table.sort(sort_columns[0])
        return float(self._trend_calculator.compute_trend_slope(table["ic"])["weighted_slope"])

    def _calculate_after_cost_sharpe(self, payload: Mapping[str, Any]) -> float | None:
        returns = _number_sequence(payload.get("returns") or payload.get("raw_returns"))
        if not returns:
            return None
        turnover_values = _number_sequence(payload.get("turnover"))
        if not turnover_values:
            turnover_values = [float(payload["turnover"])] * len(returns) if is_finite(payload.get("turnover")) else [0.0] * len(returns)
        adjusted = [
            ret - 2 * self.SINGLE_SIDE_FEE_RATE * turnover
            for ret, turnover in zip(returns, turnover_values, strict=False)
        ]
        vol = sample_std(adjusted)
        if not is_finite(vol) or vol == 0:
            return None
        return mean(adjusted) / vol * math.sqrt(252)


def _as_mapping(data: Any) -> Mapping[str, Any] | None:
    return data if isinstance(data, Mapping) and data else None


def _first_number(payload: Mapping[str, Any], keys: Sequence[str]) -> float | None:
    for key in keys:
        value = payload.get(key)
        if is_finite(value):
            return float(value)
    return None


def _number_sequence(value: Any) -> list[float]:
    if isinstance(value, pl.Series):
        raw_values = value.to_list()
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        raw_values = value
    else:
        return []
    return [float(item) for item in raw_values if is_finite(item)]


def _clamp_score(value: float) -> float:
    return min(100.0, max(0.0, float(value)))
