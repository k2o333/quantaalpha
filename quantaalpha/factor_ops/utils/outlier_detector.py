"""极端值检测公共引擎。"""

from __future__ import annotations

import math

import polars as pl

from quantaalpha.factor_ops.utils._stats import mean, population_std


class OutlierDetector:
    """极端值检测和截尾处理引擎。"""

    def mad_winsorize(self, series: pl.Series, n_mad: float = 5.0) -> pl.Series:
        """按 median ± n_mad * MAD 做 winsorize。"""
        values = [value for value in series.to_list() if isinstance(value, (int, float)) and math.isfinite(value)]
        if not values:
            return series
        median = self._median(values)
        mad = self._median([abs(value - median) for value in values])
        lower = median - n_mad * mad
        upper = median + n_mad * mad
        clipped = [
            min(max(float(value), lower), upper) if isinstance(value, (int, float)) and math.isfinite(value) else value
            for value in series.to_list()
        ]
        return pl.Series(series.name, clipped)

    def percentile_clip(self, series: pl.Series, lower: float = 0.01, upper: float = 0.99) -> pl.Series:
        """按分位数截尾。"""
        values = sorted(
            float(value) for value in series.to_list() if isinstance(value, (int, float)) and math.isfinite(value)
        )
        if not values:
            return series
        lower_value = self._quantile(values, lower)
        upper_value = self._quantile(values, upper)
        clipped = [
            min(max(float(value), lower_value), upper_value)
            if isinstance(value, (int, float)) and math.isfinite(value)
            else value
            for value in series.to_list()
        ]
        return pl.Series(series.name, clipped)

    def detect_single_day_jump(self, series: pl.Series, zscore_threshold: float = 5.0) -> bool:
        """检测最后一个值相对历史是否发生单日跳变。"""
        values = [float(value) for value in series.to_list() if isinstance(value, (int, float)) and math.isfinite(value)]
        if len(values) < 3:
            return False
        history = values[:-1]
        std = population_std(history)
        if not math.isfinite(std) or std == 0:
            return False
        zscore = abs(values[-1] - mean(history)) / std
        return zscore > zscore_threshold

    @staticmethod
    def _median(values: list[float]) -> float:
        sorted_values = sorted(values)
        mid = len(sorted_values) // 2
        if len(sorted_values) % 2:
            return sorted_values[mid]
        return (sorted_values[mid - 1] + sorted_values[mid]) / 2

    @staticmethod
    def _quantile(values: list[float], quantile: float) -> float:
        position = (len(values) - 1) * quantile
        left = int(position)
        right = min(left + 1, len(values) - 1)
        weight = position - left
        return values[left] * (1 - weight) + values[right] * weight
