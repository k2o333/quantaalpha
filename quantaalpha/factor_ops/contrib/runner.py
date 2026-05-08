"""Executable model contribution workflow."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import polars as pl

from quantaalpha.factor_ops.contrib.downgrade_rules import DowngradeRuleEngine, DowngradeSuggestion
from quantaalpha.factor_ops.contrib.model_contrib import ContributionReport, ModelContributionEvaluator
from quantaalpha.factor_ops.registry.updater import RegistryUpdateResult, RegistryUpdater

MetricRunner = Callable[[tuple[str, ...]], dict[str, Any]]


@dataclass(frozen=True)
class ContributionWorkflowResult:
    """模型贡献自动化工作流结果。"""

    report: ContributionReport
    suggestions: list[DowngradeSuggestion]
    registry_updates: list[RegistryUpdateResult]
    metrics: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """转换为可序列化 dict。"""
        return {
            "report": self.report.to_dict(),
            "suggestions": [
                {
                    "factor_id": suggestion.factor_id,
                    "new_status": suggestion.new_status,
                    "reason": suggestion.reason,
                    "metrics_snapshot": suggestion.metrics_snapshot,
                }
                for suggestion in self.suggestions
            ],
            "registry_updates": [
                {
                    "factor_id": update.factor_id,
                    "success": update.success,
                    "old_status": update.old_status,
                    "new_status": update.new_status,
                    "lifecycle_log_id": update.lifecycle_log_id,
                    "error": update.error,
                }
                for update in self.registry_updates
            ],
            "metrics": self.metrics,
        }


class ModelContributionWorkflowRunner:
    """执行 Baseline / Candidate-added / Drop-one 并生成降级回写。"""

    def __init__(
        self,
        registry: pl.DataFrame,
        *,
        metric_runner: MetricRunner,
        rule_engine: DowngradeRuleEngine | None = None,
        registry_updater: RegistryUpdater | None = None,
    ) -> None:
        """初始化 runner。"""
        self.registry = registry
        self.metric_runner = metric_runner
        self.rule_engine = rule_engine or DowngradeRuleEngine()
        self.registry_updater = registry_updater

    def run(
        self,
        *,
        shap_rank_pct: dict[str, float] | None = None,
        timestamp: str = "2026-05-08T00:00:00",
        apply_registry_updates: bool = False,
    ) -> ContributionWorkflowResult:
        """执行贡献评价工作流。"""
        core_features = _features_by_status(self.registry, {"core"})
        if not core_features:
            raise ValueError("core pool is empty")
        candidate_pool = _features_by_status(self.registry, {"satellite", "candidate"})
        baseline = self.metric_runner(tuple(core_features))
        candidate_added: dict[str, dict[str, Any]] = {}
        drop_one: dict[str, dict[str, Any]] = {}
        for candidate in candidate_pool:
            candidate_added[candidate] = self.metric_runner(tuple([*core_features, candidate]))
        full_pool = tuple([*core_features, *candidate_pool])
        for factor_id in full_pool:
            remaining = tuple(item for item in full_pool if item != factor_id)
            drop_one[factor_id] = self.metric_runner(remaining)
        metrics = {
            "baseline": baseline,
            "candidate_added": candidate_added,
            "drop_one": drop_one,
            "shap_rank_pct": shap_rank_pct or {},
        }
        report = _with_runner_drop_one_semantics(
            ModelContributionEvaluator(self.registry).generate_report(metrics),
            candidate_added,
            drop_one,
        )
        suggestions = self.rule_engine.evaluate(report)
        updates: list[RegistryUpdateResult] = []
        if apply_registry_updates:
            if self.registry_updater is None:
                raise ValueError("registry_updater is required when apply_registry_updates=True")
            updates = [
                self.registry_updater.update_ops(
                    suggestion.factor_id,
                    ops_update={
                        "status": suggestion.new_status,
                        "contribution": suggestion.metrics_snapshot,
                    },
                    reason=suggestion.reason,
                    timestamp=timestamp,
                    operator="model_contribution",
                )
                for suggestion in suggestions
            ]
        return ContributionWorkflowResult(
            report=report,
            suggestions=suggestions,
            registry_updates=updates,
            metrics=metrics,
        )


def _features_by_status(registry: pl.DataFrame, statuses: set[str]) -> list[str]:
    if "ops_status" not in registry.columns:
        return []
    return [
        str(row["factor_id"])
        for row in registry.filter(pl.col("ops_status").is_in(sorted(statuses))).sort("factor_id").to_dicts()
    ]


def _with_runner_drop_one_semantics(
    report: ContributionReport,
    candidate_added_metrics: dict[str, dict[str, Any]],
    drop_one_metrics: dict[str, dict[str, Any]],
) -> ContributionReport:
    drop_one = dict(report.drop_one)
    for row in report.candidate_added:
        factor_id = str(row["factor_id"])
        full_ic = float(candidate_added_metrics.get(factor_id, {}).get("rank_ic", candidate_added_metrics.get(factor_id, {}).get("ic", row.get("rank_ic", 0.0))))
        removed_ic = float(drop_one_metrics.get(factor_id, {}).get("rank_ic", drop_one_metrics.get(factor_id, {}).get("ic", full_ic)))
        drop_one[factor_id] = {
            "rank_ic": removed_ic,
            "ic_change": _round(full_ic - removed_ic),
        }
    return ContributionReport(
        baseline=report.baseline,
        candidate_added=report.candidate_added,
        drop_one=drop_one,
        shap_rank_pct=report.shap_rank_pct,
        candidate_pool=report.candidate_pool,
        source_types=report.source_types,
    )


def _round(value: float) -> float:
    rounded = round(float(value), 10)
    return 0.0 if rounded == 0 else rounded
