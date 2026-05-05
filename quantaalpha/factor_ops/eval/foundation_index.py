"""Foundation Health Index computation."""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from quantaalpha.factor_ops.utils._stats import is_finite


@dataclass(frozen=True)
class FoundationHealthIndexResult:
    """基石健康度结果。"""

    foundation_health_index: float
    foundation_factor_count: int
    included_factor_ids: list[str]
    excluded_factor_ids: list[str]

    def to_metadata_ops(self) -> dict[str, float | int]:
        """转换为 metadata_json.ops 字段。"""
        return {
            "foundation_health_index": self.foundation_health_index,
            "foundation_factor_count": self.foundation_factor_count,
        }


class FoundationHealthIndexComputer:
    """计算剥离 DL/衍生因子的基石健康度。"""

    FOUNDATION_SOURCE_TYPES = {"mined", "manual", "formula"}
    EXCLUDED_SOURCE_TYPES = {"dl-feature", "composite", "derived"}

    def compute(self, registry: pl.DataFrame) -> FoundationHealthIndexResult:
        """从 registry/eval snapshot DataFrame 计算 FHI。"""
        required = {"factor_id", "data_source_type", "health_score", "health_confidence"}
        missing = required - set(registry.columns)
        if missing:
            raise ValueError(f"registry missing columns: {sorted(missing)}")

        with_source = registry.with_columns(pl.col("data_source_type").str.to_lowercase().alias("_source_type"))
        included = with_source.filter(pl.col("_source_type").is_in(sorted(self.FOUNDATION_SOURCE_TYPES)))
        excluded = with_source.filter(~pl.col("_source_type").is_in(sorted(self.FOUNDATION_SOURCE_TYPES)))

        weighted_terms: list[tuple[float, float]] = []
        for row in included.to_dicts():
            score = row["health_score"]
            confidence = row["health_confidence"]
            if is_finite(score) and is_finite(confidence) and float(confidence) > 0:
                weighted_terms.append((float(score), float(confidence)))
        total_weight = sum(weight for _, weight in weighted_terms)
        fhi = sum(score * weight for score, weight in weighted_terms) / total_weight if total_weight else 0.0
        return FoundationHealthIndexResult(
            foundation_health_index=_round_score(fhi),
            foundation_factor_count=included.height,
            included_factor_ids=sorted(str(value) for value in included["factor_id"].to_list()),
            excluded_factor_ids=sorted(str(value) for value in excluded["factor_id"].to_list()),
        )

    def detect_drop_trigger(
        self,
        fhi_history: list[float],
        *,
        absolute_drop_threshold: float = 10.0,
        five_day_cumulative_drop_threshold: float = 15.0,
    ) -> dict[str, float | str | bool]:
        """检测 FHI 下降触发条件。"""
        values = [float(value) for value in fhi_history if is_finite(value)]
        if len(values) < 2:
            return {"triggered": False, "reason": "", "drop": 0.0}

        absolute_drop = values[-2] - values[-1]
        if absolute_drop >= absolute_drop_threshold:
            return {"triggered": True, "reason": "absolute_drop", "drop": _round_score(absolute_drop)}

        if len(values) >= 6:
            cumulative_drop = values[-6] - values[-1]
            if cumulative_drop >= five_day_cumulative_drop_threshold:
                return {
                    "triggered": True,
                    "reason": "five_day_cumulative_drop",
                    "drop": _round_score(cumulative_drop),
                }
        return {"triggered": False, "reason": "", "drop": 0.0}


def _round_score(value: float) -> float:
    rounded = round(float(value), 10)
    return 0.0 if rounded == 0 else rounded
