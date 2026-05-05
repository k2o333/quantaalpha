from __future__ import annotations

import polars as pl
import pytest
from quantaalpha.factor_ops.eval.redundancy_cluster import (
    ClusterQuotaManager,
    RedundancyClusterer,
    RedundancyClusterResult,
)


def test_redundancy_clusterer_finds_nearest_pool_factor_and_action() -> None:
    """候选因子 vs pool 低资源策略输出最近因子、相关性和 cluster_id。"""
    candidate = pl.DataFrame(
        {
            "date": ["2026-05-01"] * 4 + ["2026-05-02"] * 4,
            "stock_id": ["A", "B", "C", "D"] * 2,
            "candidate": [1.0, 2.0, 3.0, 4.0, 1.0, 2.0, 3.0, 4.0],
        }
    )
    pool = pl.DataFrame(
        {
            "date": ["2026-05-01"] * 4 + ["2026-05-02"] * 4,
            "stock_id": ["A", "B", "C", "D"] * 2,
            "core_value": [1.0, 2.0, 3.0, 4.0, 1.0, 2.0, 3.0, 4.0],
            "core_momentum": [4.0, 3.0, 2.0, 1.0, 4.0, 3.0, 2.0, 1.0],
        }
    )

    result = RedundancyClusterer(correlation_threshold=0.85).compute_candidate_cluster(
        "candidate",
        candidate,
        pool,
        pool_cluster_map={"core_value": "cluster_value", "core_momentum": "cluster_momentum"},
    )

    assert isinstance(result, RedundancyClusterResult)
    assert result.nearest_factor_id == "core_value"
    assert result.max_abs_corr == pytest.approx(1.0)
    assert result.cluster_id == "cluster_value"
    assert result.redundancy_action == "join_existing_cluster"
    assert result.to_health_independence_input() == {"max_abs_corr": 1.0}


def test_redundancy_clusterer_assigns_new_cluster_when_no_pool_match() -> None:
    """无高相关 pool 因子时创建稳定的新 cluster id。"""
    candidate = pl.DataFrame(
        {
            "date": ["2026-05-01"] * 4,
            "stock_id": ["A", "B", "C", "D"],
            "candidate": [1.0, 1.0, 2.0, 2.0],
        }
    )
    pool = pl.DataFrame(
        {
            "date": ["2026-05-01"] * 4,
            "stock_id": ["A", "B", "C", "D"],
            "core": [1.0, 2.0, 1.0, 2.0],
        }
    )

    result = RedundancyClusterer(correlation_threshold=0.85).compute_candidate_cluster("candidate", candidate, pool)

    assert result.max_abs_corr == pytest.approx(0.0)
    assert result.nearest_factor_id == "core"
    assert result.cluster_id == "cluster_candidate"
    assert result.redundancy_action == "new_cluster"


def test_cluster_quota_manager_flags_excess_by_health_score() -> None:
    """簇配额按 health_score 保留最高分，其余进入降级候选。"""
    assignments = pl.DataFrame(
        {
            "factor_id": ["f1", "f2", "f3", "f4"],
            "cluster_id": ["cluster_a", "cluster_a", "cluster_a", "cluster_b"],
            "category": ["value", "value", "value", "quality"],
        }
    )
    health_scores = {"f1": 70.0, "f2": 90.0, "f3": 80.0, "f4": 60.0}

    result = ClusterQuotaManager(quotas={"value": 2, "quality": 1}).check_quota_compliance(
        assignments,
        health_scores,
    )

    assert result["cluster_a"] == ["f1"]
    assert result["cluster_b"] == []
