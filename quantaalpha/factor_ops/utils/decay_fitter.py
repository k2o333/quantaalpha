"""信号衰减半衰期拟合引擎。"""

from __future__ import annotations

import math
from typing import Literal


class DecayFitter:
    """半衰期拟合引擎。"""

    def fit_half_life(
        self,
        horizon_ic: dict[int, float],
        method: Literal["linear_interpolation", "exponential"] = "linear_interpolation",
    ) -> dict[str, float | int | str]:
        """拟合 Rank IC 衰减半衰期。"""
        if method != "linear_interpolation":
            raise ValueError("Only linear_interpolation decay fitting is supported")
        valid_items = sorted((int(horizon), abs(float(ic))) for horizon, ic in horizon_ic.items() if math.isfinite(ic))
        if not valid_items:
            return {"half_life_days": math.nan, "optimal_horizon": 0, "decay_speed": "unknown", "r_squared": math.nan}

        optimal_horizon, max_ic = max(valid_items, key=lambda item: item[1])
        threshold = max_ic * 0.5
        if valid_items[0][1] < threshold:
            half_life = 0.5
        else:
            half_life = 30.0
            for (left_h, left_ic), (right_h, right_ic) in zip(valid_items, valid_items[1:], strict=False):
                if left_ic >= threshold >= right_ic:
                    if left_ic == right_ic:
                        half_life = float(right_h)
                    else:
                        ratio = (threshold - left_ic) / (right_ic - left_ic)
                        half_life = left_h + ratio * (right_h - left_h)
                    break

        return {
            "half_life_days": half_life,
            "optimal_horizon": optimal_horizon,
            "decay_speed": self._speed(half_life),
            "r_squared": math.nan,
        }

    @staticmethod
    def _speed(half_life: float) -> str:
        if not math.isfinite(half_life):
            return "unknown"
        if half_life < 3:
            return "fast"
        if half_life <= 10:
            return "medium"
        return "slow"

