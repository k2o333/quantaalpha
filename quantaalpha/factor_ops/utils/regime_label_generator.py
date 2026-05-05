"""市场状态标签生成引擎。"""

from __future__ import annotations

import polars as pl


class RegimeLabelGenerator:
    """基于趋势和波动率生成市场状态标签。"""

    def generate_labels(
        self,
        market_returns: pl.DataFrame,
        trend_window: int = 20,
        vol_window: int = 20,
        trend_threshold: float = 0.02,
        vol_percentiles: tuple[float, float] = (0.30, 0.70),
    ) -> pl.DataFrame:
        """生成 regime 标签。"""
        df = market_returns.sort("date")
        returns = [float(value) for value in df["market_return"].to_list()]
        rolling_mean = self._rolling_mean(returns, trend_window)
        rolling_std = self._rolling_std(returns, vol_window)
        low_threshold = self._quantile([value for value in rolling_std if value is not None], vol_percentiles[0])
        high_threshold = self._quantile([value for value in rolling_std if value is not None], vol_percentiles[1])

        records: list[dict[str, str | None]] = []
        for date_value, trend_value, vol_value in zip(df["date"].to_list(), rolling_mean, rolling_std, strict=True):
            trend_regime = self._trend_regime(trend_value, trend_threshold)
            vol_regime = self._vol_regime(vol_value, low_threshold, high_threshold)
            records.append(
                {
                    "date": date_value,
                    "trend_regime": trend_regime,
                    "vol_regime": vol_regime,
                    "combined_regime": self._combined(trend_regime, vol_regime),
                }
            )
        return pl.DataFrame(
            records,
            schema={
                "date": pl.String,
                "trend_regime": pl.String,
                "vol_regime": pl.String,
                "combined_regime": pl.String,
            },
        )

    @staticmethod
    def _trend_regime(value: float | None, threshold: float) -> str | None:
        if value is None:
            return None
        if value > threshold:
            return "bull"
        if value < -threshold:
            return "bear"
        return "sideways"

    @staticmethod
    def _vol_regime(value: float | None, low_threshold: float | None, high_threshold: float | None) -> str | None:
        if value is None or low_threshold is None or high_threshold is None:
            return None
        if value > high_threshold:
            return "high_vol"
        if value < low_threshold:
            return "low_vol"
        return "normal_vol"

    @staticmethod
    def _combined(trend_regime: str | None, vol_regime: str | None) -> str | None:
        if trend_regime is None or vol_regime is None:
            return None
        if trend_regime == "sideways":
            return "sideways_normal" if vol_regime == "normal_vol" else f"sideways_{vol_regime}"
        return f"{trend_regime}_{vol_regime}"

    @staticmethod
    def _rolling_mean(values: list[float], window: int) -> list[float | None]:
        output: list[float | None] = []
        for idx in range(len(values)):
            if idx + 1 < window:
                output.append(None)
            else:
                window_values = values[idx + 1 - window : idx + 1]
                output.append(sum(window_values) / len(window_values))
        return output

    @staticmethod
    def _rolling_std(values: list[float], window: int) -> list[float | None]:
        output: list[float | None] = []
        for idx in range(len(values)):
            if idx + 1 < window:
                output.append(None)
            else:
                window_values = values[idx + 1 - window : idx + 1]
                avg = sum(window_values) / len(window_values)
                output.append((sum((value - avg) ** 2 for value in window_values) / len(window_values)) ** 0.5)
        return output

    @staticmethod
    def _quantile(values: list[float], quantile: float) -> float | None:
        if not values:
            return None
        sorted_values = sorted(values)
        position = (len(sorted_values) - 1) * quantile
        left = int(position)
        right = min(left + 1, len(sorted_values) - 1)
        weight = position - left
        return sorted_values[left] * (1 - weight) + sorted_values[right] * weight

