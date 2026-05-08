"""Portfolio optimization input mapping contracts."""

from __future__ import annotations

import math

import polars as pl


class PortfolioWeightMapper:
    """把 factor_ops health/tier 和 TS-GRU 动态权重映射到组合输入。"""

    def map_factor_weights(
        self,
        *,
        health_scores: dict[str, float],
        dynamic_weights: dict[str, float],
        tier_caps: dict[str, float] | None = None,
        regime_scale: float = 1.0,
    ) -> dict[str, float]:
        """health softmax × dynamic weights，再应用 tier cap 并归一。"""
        if regime_scale < 0:
            raise ValueError("regime_scale must be non-negative")
        tier_caps = tier_caps or {}
        priorities = _softmax(health_scores)
        raw = {
            factor_id: priorities.get(factor_id, 0.0) * float(dynamic_weights.get(factor_id, 0.0)) * regime_scale
            for factor_id in health_scores
        }
        capped = {factor_id: min(value, tier_caps.get(factor_id, 1.0)) for factor_id, value in raw.items()}
        total = sum(capped.values())
        if total == 0:
            return {factor_id: 0.0 for factor_id in capped}
        return {factor_id: value / total for factor_id, value in capped.items()}

    def build_stock_weights(
        self,
        factor_values: pl.DataFrame,
        *,
        factor_weights: dict[str, float],
        max_abs_weight: float = 0.05,
    ) -> pl.DataFrame:
        """把因子权重和因子值映射为市场中性股票权重。"""
        scores: list[float] = []
        for row in factor_values.to_dicts():
            scores.append(sum(float(row.get(factor_id, 0.0)) * weight for factor_id, weight in factor_weights.items()))
        mean_score = sum(scores) / len(scores) if scores else 0.0
        centered = [score - mean_score for score in scores]
        max_abs_score = max((abs(score) for score in centered), default=0.0)
        if max_abs_score == 0:
            weights = [0.0] * len(centered)
        else:
            weights = [score / max_abs_score * max_abs_weight for score in centered]
        # Remove residual rounding drift to preserve market neutrality.
        if weights:
            drift = sum(weights) / len(weights)
            weights = [weight - drift for weight in weights]
        return pl.DataFrame({"stock_id": factor_values["stock_id"].to_list(), "weight": weights})

    def regime_scale_from_probability(
        self,
        *,
        high_vol_probability: float = 0.0,
        crisis_probability: float = 0.0,
        min_scale: float = 0.25,
    ) -> float:
        """用 high-vol/crisis probability 生成组合风险预算缩放。"""
        for field_name, value in {
            "high_vol_probability": high_vol_probability,
            "crisis_probability": crisis_probability,
            "min_scale": min_scale,
        }.items():
            if value < 0:
                raise ValueError(f"{field_name} must be non-negative")
        risk_probability = min(1.0, max(high_vol_probability, crisis_probability))
        return max(min_scale, 1.0 - risk_probability)


def _softmax(values: dict[str, float]) -> dict[str, float]:
    if not values:
        return {}
    scaled = {key: float(value) / 10 for key, value in values.items()}
    max_value = max(scaled.values())
    exp_values = {key: math.exp(value - max_value) for key, value in scaled.items()}
    total = sum(exp_values.values())
    return {key: value / total for key, value in exp_values.items()}
