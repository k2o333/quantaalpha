"""Factor value redundancy clustering utilities."""

from __future__ import annotations

from dataclasses import dataclass

import polars as pl

from quantaalpha.factor_ops.utils import CorrelationEngine


@dataclass(frozen=True)
class RedundancyClusterResult:
    """候选因子冗余聚类结果。"""

    factor_id: str
    cluster_id: str
    nearest_factor_id: str
    max_abs_corr: float
    redundancy_action: str

    def to_health_independence_input(self) -> dict[str, float]:
        """转换为 HealthScorer independence 输入。"""
        return {"max_abs_corr": self.max_abs_corr}


class RedundancyClusterer:
    """候选因子 vs core/satellite pool 的低资源冗余聚类器。"""

    def __init__(
        self,
        correlation_threshold: float = 0.70,
        window_days: int = 120,
        correlation_engine: CorrelationEngine | None = None,
    ) -> None:
        """初始化聚类器。"""
        self.correlation_threshold = correlation_threshold
        self.window_days = window_days
        self.correlation_engine = correlation_engine or CorrelationEngine()

    def compute_candidate_cluster(
        self,
        factor_id: str,
        candidate_df: pl.DataFrame,
        pool_df: pl.DataFrame | None,
        *,
        pool_cluster_map: dict[str, str] | None = None,
    ) -> RedundancyClusterResult:
        """计算候选因子与 pool 的最近相关簇。"""
        pool_cluster_map = pool_cluster_map or {}
        if pool_df is None or pool_df.is_empty():
            return self._new_cluster(factor_id, "", 0.0)

        pairwise = self.correlation_engine.compute_pairwise_corr(
            candidate_df,
            pool_df,
            window_days=self.window_days,
        )
        if pairwise.is_empty():
            return self._new_cluster(factor_id, "", 0.0)

        summary = (
            pairwise.with_columns(pl.col("correlation").abs().alias("abs_corr"))
            .group_by("pool_factor")
            .agg(
                pl.col("abs_corr").mean().alias("max_abs_corr"),
                pl.col("correlation").mean().alias("mean_corr"),
            )
            .sort(["max_abs_corr", "mean_corr", "pool_factor"], descending=[True, True, False])
        )
        nearest = str(summary["pool_factor"][0])
        max_abs_corr = _round_corr(float(summary["max_abs_corr"][0]))
        if max_abs_corr >= self.correlation_threshold:
            return RedundancyClusterResult(
                factor_id=factor_id,
                cluster_id=pool_cluster_map.get(nearest, f"cluster_{nearest}"),
                nearest_factor_id=nearest,
                max_abs_corr=max_abs_corr,
                redundancy_action="join_existing_cluster",
            )
        return self._new_cluster(factor_id, nearest, max_abs_corr)

    @staticmethod
    def _new_cluster(factor_id: str, nearest: str, max_abs_corr: float) -> RedundancyClusterResult:
        return RedundancyClusterResult(
            factor_id=factor_id,
            cluster_id=f"cluster_{factor_id}",
            nearest_factor_id=nearest,
            max_abs_corr=max_abs_corr,
            redundancy_action="new_cluster",
        )


class ClusterQuotaManager:
    """按 cluster/category 配额输出超额因子。"""

    DEFAULT_CLUSTER_QUOTAS: dict[str, int] = {
        "value": 2,
        "quality": 2,
        "momentum": 2,
        "volatility": 2,
        "liquidity": 2,
        "default": 2,
    }

    def __init__(self, quotas: dict[str, int] | None = None) -> None:
        """初始化配额管理器。"""
        self.quotas = dict(quotas or self.DEFAULT_CLUSTER_QUOTAS)

    def check_quota_compliance(
        self,
        assignments: pl.DataFrame,
        health_scores: dict[str, float],
    ) -> dict[str, list[str]]:
        """返回每个 cluster 内按健康分排序后的超额因子列表。"""
        required = {"factor_id", "cluster_id"}
        missing = required - set(assignments.columns)
        if missing:
            raise ValueError(f"assignments missing columns: {sorted(missing)}")
        output: dict[str, list[str]] = {}
        for cluster_id in sorted(assignments["cluster_id"].unique().to_list()):
            cluster_df = assignments.filter(pl.col("cluster_id") == cluster_id)
            quota = self._quota_for_cluster(cluster_df)
            ranked = sorted(
                cluster_df.to_dicts(),
                key=lambda row: (-health_scores.get(str(row["factor_id"]), 0.0), str(row["factor_id"])),
            )
            output[str(cluster_id)] = [str(row["factor_id"]) for row in ranked[quota:]]
        return output

    def _quota_for_cluster(self, cluster_df: pl.DataFrame) -> int:
        if "category" in cluster_df.columns and cluster_df.height:
            category = str(cluster_df["category"][0])
        else:
            category = "default"
        return self.quotas.get(category, self.quotas.get("default", 2))


def _round_corr(value: float) -> float:
    rounded = round(value, 10)
    return 0.0 if rounded == 0 else rounded
