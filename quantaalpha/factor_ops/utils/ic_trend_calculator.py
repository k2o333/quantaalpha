"""IC 趋势公共计算引擎。"""

from __future__ import annotations

import math

import polars as pl

from quantaalpha.factor_ops.utils._stats import linear_slope, mean


class ICTrendCalculator:
    """IC 序列趋势分析引擎。"""

    def compute_trend_slope(
        self,
        ic_series: pl.Series,
        windows: list[int] | None = None,
        weights: list[float] | None = None,
    ) -> dict[str, float | str]:
        """计算多窗口加权趋势斜率。"""
        windows = windows or [20, 60, 120]
        weights = weights or [0.5, 0.3, 0.2]
        values = [float(value) for value in ic_series.to_list() if isinstance(value, (int, float))]
        slopes: dict[str, float | str] = {}
        weighted_terms: list[tuple[float, float]] = []
        for window, weight in zip(windows, weights, strict=True):
            slope = linear_slope(values[-window:]) if len(values) >= window else math.nan
            slopes[f"slope_{window}d"] = slope
            if math.isfinite(slope):
                weighted_terms.append((slope, weight))
        total_weight = sum(weight for _, weight in weighted_terms)
        weighted_slope = (
            sum(slope * weight for slope, weight in weighted_terms) / total_weight if total_weight else math.nan
        )
        slopes["weighted_slope"] = weighted_slope
        slopes["trend_direction"] = self._direction(weighted_slope)
        return slopes

    def detect_significant_decline(
        self,
        ic_series: pl.Series,
        decline_threshold: float = 0.20,
        min_window: int = 60,
    ) -> bool:
        """检测最近窗口 IC 均值是否相对之前窗口显著下降。"""
        values = [float(value) for value in ic_series.to_list() if isinstance(value, (int, float))]
        if len(values) < min_window * 2:
            if len(values) < min_window:
                return False
            baseline = mean(values[:-min_window]) if values[:-min_window] else values[0]
            recent = mean(values[-min_window:])
        else:
            baseline = mean(values[-min_window * 2 : -min_window])
            recent = mean(values[-min_window:])
        if not math.isfinite(baseline) or baseline == 0 or not math.isfinite(recent):
            return False
        return (baseline - recent) / abs(baseline) >= decline_threshold

    @staticmethod
    def _direction(slope: float) -> str:
        if not math.isfinite(slope) or abs(slope) < 1e-12:
            return "flat"
        return "up" if slope > 0 else "down"

