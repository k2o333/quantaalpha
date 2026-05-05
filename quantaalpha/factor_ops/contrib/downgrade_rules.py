"""Downgrade suggestion rules from model contribution reports."""

from __future__ import annotations

from dataclasses import dataclass

from quantaalpha.factor_ops.contrib.model_contrib import ContributionReport


@dataclass(frozen=True)
class DowngradeSuggestion:
    """基于贡献报告的降级建议。"""

    factor_id: str
    new_status: str
    reason: str
    metrics_snapshot: dict[str, float | str]


class DowngradeRuleEngine:
    """贡献评价降级规则引擎。"""

    def __init__(
        self,
        *,
        shap_tail_threshold: float = 0.80,
        drop_one_threshold: float = 0.002,
        ts_gru_shap_pass_threshold: float = 0.50,
        ts_gru_drop_one_pass_threshold: float = 0.003,
    ) -> None:
        """初始化阈值。"""
        self.shap_tail_threshold = shap_tail_threshold
        self.drop_one_threshold = drop_one_threshold
        self.ts_gru_shap_pass_threshold = ts_gru_shap_pass_threshold
        self.ts_gru_drop_one_pass_threshold = ts_gru_drop_one_pass_threshold

    def evaluate(self, report: ContributionReport) -> list[DowngradeSuggestion]:
        """输出降级建议列表。"""
        suggestions: list[DowngradeSuggestion] = []
        for row in report.candidate_added:
            factor_id = str(row["factor_id"])
            shap_rank_pct = report.shap_rank_pct.get(factor_id, 0.0)
            drop_one_ic = float(report.drop_one.get(factor_id, {}).get("ic_change", 0.0))
            source_type = report.source_types.get(factor_id, "")
            if _is_ts_gru(source_type):
                if shap_rank_pct > self.ts_gru_shap_pass_threshold and drop_one_ic < self.ts_gru_drop_one_pass_threshold:
                    suggestions.append(
                        self._suggest(
                            factor_id,
                            "ts-gru contribution failed",
                            shap_rank_pct,
                            drop_one_ic,
                            source_type,
                        )
                    )
                continue
            if shap_rank_pct > self.shap_tail_threshold and drop_one_ic < self.drop_one_threshold:
                suggestions.append(
                    self._suggest(
                        factor_id,
                        "low shap rank and drop-one IC below threshold",
                        shap_rank_pct,
                        drop_one_ic,
                        source_type,
                    )
                )
        return suggestions

    @staticmethod
    def _suggest(
        factor_id: str,
        reason: str,
        shap_rank_pct: float,
        drop_one_ic: float,
        source_type: str,
    ) -> DowngradeSuggestion:
        return DowngradeSuggestion(
            factor_id=factor_id,
            new_status="watchlist",
            reason=reason,
            metrics_snapshot={
                "shap_rank_pct": shap_rank_pct,
                "drop_one_ic_change": drop_one_ic,
                "data_source_type": source_type,
            },
        )


def _is_ts_gru(source_type: str) -> bool:
    return source_type.lower() in {"dl-feature", "dl_feature", "ts-gru", "ts_gru"}
