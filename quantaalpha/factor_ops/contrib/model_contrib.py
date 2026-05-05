"""Model contribution report construction."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import polars as pl


@dataclass(frozen=True)
class ContributionReport:
    """模型贡献评价报告。"""

    baseline: dict[str, Any]
    candidate_added: list[dict[str, Any]]
    drop_one: dict[str, dict[str, Any]]
    shap_rank_pct: dict[str, float]
    candidate_pool: list[str]
    source_types: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        """转换为可序列化 dict。"""
        return {
            "baseline": self.baseline,
            "candidate_added": self.candidate_added,
            "drop_one": self.drop_one,
            "shap_rank_pct": self.shap_rank_pct,
            "candidate_pool": self.candidate_pool,
            "source_types": self.source_types,
        }


class ModelContributionEvaluator:
    """从 registry 与训练/回测指标生成贡献报告。"""

    def __init__(self, registry: pl.DataFrame) -> None:
        """初始化 evaluator。"""
        self.registry = registry

    def generate_report(self, metrics: dict[str, Any]) -> ContributionReport:
        """生成 Baseline / Candidate-added / Drop-one 贡献报告。"""
        core_features = self._features_by_status({"core"})
        if not core_features:
            raise ValueError("core pool is empty")
        candidate_pool = self._features_by_status({"satellite", "candidate"})
        baseline = dict(metrics.get("baseline", {}))
        baseline["features"] = core_features
        baseline_ic = float(baseline.get("rank_ic", baseline.get("ic", 0.0)))

        candidate_added = []
        for factor_id, result in dict(metrics.get("candidate_added", {})).items():
            new_ic = float(result.get("rank_ic", result.get("ic", baseline_ic)))
            candidate_added.append(
                {
                    "factor_id": factor_id,
                    "rank_ic": new_ic,
                    "ic_improvement": _round(new_ic - baseline_ic),
                    "icir": result.get("icir"),
                }
            )

        drop_one = {}
        for factor_id, result in dict(metrics.get("drop_one", {})).items():
            new_ic = float(result.get("rank_ic", result.get("ic", baseline_ic)))
            drop_one[factor_id] = {
                "rank_ic": new_ic,
                "ic_change": _round(baseline_ic - new_ic),
            }

        return ContributionReport(
            baseline=baseline,
            candidate_added=candidate_added,
            drop_one=drop_one,
            shap_rank_pct={str(key): float(value) for key, value in dict(metrics.get("shap_rank_pct", {})).items()},
            candidate_pool=candidate_pool,
            source_types=self._source_types(),
        )

    def _features_by_status(self, statuses: set[str]) -> list[str]:
        if "ops_status" not in self.registry.columns:
            return []
        return [
            str(row["factor_id"])
            for row in self.registry.filter(pl.col("ops_status").is_in(sorted(statuses))).to_dicts()
        ]

    def _source_types(self) -> dict[str, str]:
        if "data_source_type" not in self.registry.columns:
            return {}
        return {str(row["factor_id"]): str(row.get("data_source_type", "")) for row in self.registry.to_dicts()}


def _round(value: float) -> float:
    rounded = round(float(value), 10)
    return 0.0 if rounded == 0 else rounded
