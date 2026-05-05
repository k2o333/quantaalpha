"""Regime conditional IC computation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

import polars as pl

from quantaalpha.factor_ops.utils import RankICCalculator
from quantaalpha.factor_ops.utils._stats import is_finite, mean, sample_std


@dataclass(frozen=True)
class RegimeICResult:
    """按 regime 聚合的 IC 结果。"""

    horizon: int
    regime_ic: dict[str, dict[str, float | int]]
    best_regime: str
    worst_regime: str

    def to_ts_gru_features(self) -> dict[str, float | int]:
        """转换为 TS-GRU 先验特征字典。"""
        features: dict[str, float | int] = {}
        for regime, stats in self.regime_ic.items():
            prefix = f"regime_ic_{regime}"
            features[f"{prefix}_ic_mean"] = stats["ic_mean"]
            features[f"{prefix}_icir"] = stats["icir"]
            features[f"{prefix}_n_days"] = stats["n_days"]
        return features


class RegimeICComputer:
    """计算 regime 条件 IC/ICIR。"""

    def __init__(self, rank_ic_calculator: RankICCalculator | None = None) -> None:
        """初始化计算器。"""
        self.rank_ic_calculator = rank_ic_calculator or RankICCalculator()

    def compute(
        self,
        factor_values: pl.DataFrame,
        returns: pl.DataFrame,
        regime_labels: pl.DataFrame,
        *,
        horizon: int = 1,
        regime_column: str = "combined_regime",
    ) -> RegimeICResult:
        """从因子值、收益和 regime 标签计算条件 IC。"""
        daily_ic = self.rank_ic_calculator.compute_rank_ic(factor_values, returns, horizon=horizon)
        return self.summarize_daily_ic(
            daily_ic,
            regime_labels,
            horizon=horizon,
            regime_column=regime_column,
        )

    def summarize_daily_ic(
        self,
        daily_ic: pl.DataFrame,
        regime_labels: pl.DataFrame,
        *,
        horizon: int = 1,
        regime_column: str = "combined_regime",
    ) -> RegimeICResult:
        """从 daily IC 和 regime 标签聚合条件 IC。"""
        if regime_column not in regime_labels.columns:
            raise ValueError(f"regime_labels missing column: {regime_column}")
        joined = daily_ic.join(regime_labels.select(["date", regime_column]), on="date", how="inner")
        joined = joined.filter(pl.col(regime_column).is_not_null())
        regime_ic: dict[str, dict[str, float | int]] = {}
        for regime in sorted(joined[regime_column].unique().to_list()):
            values = [
                float(value)
                for value in joined.filter(pl.col(regime_column) == regime)["ic"].to_list()
                if is_finite(value)
            ]
            if not values:
                continue
            ic_std = sample_std(values)
            regime_ic[str(regime)] = {
                "ic_mean": _round_ic(mean(values)),
                "icir": mean(values) / ic_std * math.sqrt(252) if is_finite(ic_std) and ic_std != 0 else math.nan,
                "n_days": len(values),
            }
        return RegimeICResult(
            horizon=horizon,
            regime_ic=regime_ic,
            best_regime=_best_regime(regime_ic),
            worst_regime=_worst_regime(regime_ic),
        )


def _best_regime(regime_ic: dict[str, dict[str, Any]]) -> str:
    if not regime_ic:
        return ""
    return max(regime_ic.items(), key=lambda item: float(item[1]["ic_mean"]))[0]


def _worst_regime(regime_ic: dict[str, dict[str, Any]]) -> str:
    if not regime_ic:
        return ""
    return min(regime_ic.items(), key=lambda item: float(item[1]["ic_mean"]))[0]


def _round_ic(value: float) -> float:
    if not is_finite(value):
        return math.nan
    rounded = round(float(value), 10)
    return 0.0 if rounded == 0 else rounded
