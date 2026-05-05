"""Decay Profile evaluation wrapper."""

from __future__ import annotations

import math
from dataclasses import dataclass

import polars as pl

from quantaalpha.factor_ops.utils import DecayFitter, RankICCalculator
from quantaalpha.factor_ops.utils._stats import is_finite


@dataclass(frozen=True)
class DecayProfileResult:
    """因子衰减画像结果。"""

    half_life_days: float
    optimal_horizon: int
    decay_speed: str
    horizon_ic: dict[int, float]
    ts_gru_allowed: bool

    def to_health_input(self) -> dict[str, float | str]:
        """转换为 HealthScorer signal_persistence 输入。"""
        return {
            "half_life": self.half_life_days,
            "decay_speed": self.decay_speed,
        }


class DecayProfileComputer:
    """计算多 horizon Rank IC 衰减画像。"""

    def __init__(
        self,
        rank_ic_calculator: RankICCalculator | None = None,
        decay_fitter: DecayFitter | None = None,
    ) -> None:
        """初始化计算器。"""
        self.rank_ic_calculator = rank_ic_calculator or RankICCalculator()
        self.decay_fitter = decay_fitter or DecayFitter()

    def compute(
        self,
        factor_values: pl.DataFrame,
        returns: pl.DataFrame,
        *,
        horizons: list[int] | None = None,
    ) -> DecayProfileResult:
        """从因子值和多 horizon 收益计算 Decay Profile。"""
        horizons = horizons or [1, 2, 5, 10, 20]
        multi_ic = self.rank_ic_calculator.compute_multi_horizon_ic(
            factor_values,
            returns,
            horizons=horizons,
        )
        horizon_ic = {
            int(row["horizon"]): _round_ic(row["ic"])
            for row in multi_ic.group_by("horizon").agg(pl.col("ic").mean()).iter_rows(named=True)
            if is_finite(row["ic"])
        }
        return self.summarize_horizon_ic(horizon_ic)

    def summarize_horizon_ic(self, horizon_ic: dict[int, float]) -> DecayProfileResult:
        """从已计算的 horizon IC 摘要半衰期。"""
        fit = self.decay_fitter.fit_half_life(horizon_ic)
        half_life = float(fit["half_life_days"])
        return DecayProfileResult(
            half_life_days=half_life,
            optimal_horizon=int(fit["optimal_horizon"]),
            decay_speed=str(fit["decay_speed"]),
            horizon_ic={int(horizon): _round_ic(ic) for horizon, ic in sorted(horizon_ic.items())},
            ts_gru_allowed=math.isfinite(half_life) and half_life >= 1,
        )


def _round_ic(value: float) -> float:
    if not is_finite(value):
        return math.nan
    rounded = round(float(value), 10)
    return 0.0 if rounded == 0 else rounded
