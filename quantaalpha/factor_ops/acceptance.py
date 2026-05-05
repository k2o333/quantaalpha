"""Minimal end-to-end acceptance runner for factor_ops contracts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl

from quantaalpha.factor_ops.consumer import TSGRUFactorInputBuilder
from quantaalpha.factor_ops.eval import HealthScorer, TierClassifier
from quantaalpha.factor_ops.gate.data_quality import DataQualityGate, DataQualityGateConfig
from quantaalpha.factor_ops.registry import RegistryUpdater


class FactorOpsAcceptanceRunner:
    """运行 Gate → Health → Tier → Registry → Consumer 最小闭环。"""

    def __init__(self, storage_root: str | Path) -> None:
        """初始化 runner。"""
        self.storage_root = Path(storage_root)

    def run_minimal_loop(
        self,
        *,
        factor_id: str,
        factor_values: pl.DataFrame,
        returns: pl.DataFrame,
    ) -> dict[str, Any]:
        """执行最小闭环并返回证据。"""
        gate_result = DataQualityGate(
            DataQualityGateConfig(min_cross_section_count=2, min_cross_section_pass_ratio=1.0)
        ).run(
            factor_id,
            factor_values.rename({factor_id: "factor_value"}),
            created_at="2026-05-05T16:00:00",
        )
        health = HealthScorer().compute(
            factor_id,
            prediction_power={"ic": 0.05, "rank_ic": 0.04},
            stability={"icir": 0.8},
            oos_ability={"oos_ic": 0.04},
            independence={"max_abs_corr": 0.3},
            tradability={"sharpe_after_cost": 1.2},
            recent_performance={"trend_slope": 0.1},
            signal_persistence={"half_life_days": 20},
        )
        tier = TierClassifier().classify(
            factor_id,
            health_score=health.health_score,
            health_confidence=health.health_confidence,
            marginal_contribution=True,
        )
        store = _MemoryStore(factor_id)
        registry_result = RegistryUpdater(store, lifecycle_storage_root=self.storage_root).update_ops(
            factor_id,
            ops_update={
                "status": tier.ops_status,
                "tier": tier.tier,
                "health_score": health.health_score,
                "legacy_status": "active",
            },
            expected_version=0,
            reason="acceptance minimal loop",
            timestamp="2026-05-05T16:00:00",
        )
        registry = pl.DataFrame(
            {
                "factor_id": [factor_id],
                "ops_status": [tier.ops_status],
                "tier": [tier.tier],
                "health_score": [health.health_score],
                "cluster_id": ["cluster_acceptance"],
            }
        )
        consumer_payload = TSGRUFactorInputBuilder().build(registry)
        return {
            "gate_result": gate_result.gate_result,
            "health_score": health.health_score,
            "tier": tier.tier,
            "registry_update_success": registry_result.success,
            "consumer_payload": consumer_payload,
            "returns_rows": returns.height,
        }


class _MemoryStore:
    def __init__(self, factor_id: str) -> None:
        self.factor_id = factor_id
        self.writes: list[dict[str, Any]] = []

    def read_effective_factor_records(self) -> list[dict[str, Any]]:
        return [
            {
                "factor_id": self.factor_id,
                "factor_name": self.factor_id,
                "factor_expression": "acceptance",
                "factor_expression_normalized": "acceptance",
                "expression_hash": "acceptance",
                "evaluation_status": "pending_validation",
                "created_at": "2026-05-05T16:00:00",
                "updated_at": "2026-05-05T16:00:00",
                "sequence": 0,
                "op": "upsert",
                "tags_json": "{}",
                "metadata_json": json.dumps({"ops": {"status": "candidate", "tier": "C", "version": 0}}),
                "backtest_results_json": "{}",
            }
        ]

    def write_factor(self, event: dict[str, Any]) -> None:
        self.writes.append(event)
