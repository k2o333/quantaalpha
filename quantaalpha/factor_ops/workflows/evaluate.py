"""Evaluate 工作流。"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import polars as pl

from quantaalpha.factor_ops.eval import (
    DecayProfileComputer,
    FoundationHealthIndexComputer,
    HealthScorer,
    RedundancyClusterer,
    RegimeICComputer,
    TierClassifier,
)
from quantaalpha.factor_ops.lifecycle import StatusMachine
from quantaalpha.factor_ops.utils import RankICCalculator
from quantaalpha.factor_ops.workflows.io import (
    factor_column_frame,
    load_factor_values,
    load_registry_frame,
    load_returns,
    normalize_factor_values,
)


class EvaluateWorkflowRunner:
    """执行健康分、分层、状态建议与消费侧摘要。"""

    def run(
        self,
        factor_id: str,
        *,
        factor_values: str | Path,
        returns: str | Path,
        registry_path: str | Path | None = None,
        no_write: bool = False,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """评估单因子并返回状态建议，不直接写 registry。"""
        raw_values = load_factor_values(factor_values)
        values = normalize_factor_values(raw_values, factor_id)
        returns_df = load_returns(returns)
        daily_ic = RankICCalculator().compute_rank_ic(values, returns_df, horizon=1)
        ic_values = [float(value) for value in daily_ic["ic"].to_list() if isinstance(value, (int, float))]
        mean_ic = sum(ic_values) / len(ic_values) if ic_values else 0.0
        decay = DecayProfileComputer().compute(values, returns_df, horizons=[1])
        regime = RegimeICComputer().summarize_daily_ic(
            daily_ic,
            pl.DataFrame({"date": daily_ic["date"].to_list(), "combined_regime": ["default"] * daily_ic.height}),
        )
        cluster = RedundancyClusterer().compute_candidate_cluster(
            factor_id,
            factor_column_frame(raw_values, factor_id),
            None,
        )
        health = HealthScorer().compute(
            factor_id,
            prediction_power={"ic": mean_ic},
            stability={"icir": 1.0 if len(ic_values) >= 1 else math.nan},
            oos_ability={"oos_ic": mean_ic},
            independence=cluster.to_health_independence_input(),
            tradability={"sharpe_after_cost": 1.0},
            recent_performance={"daily_ic_series": ic_values},
            signal_persistence=decay.to_health_input(),
        )
        tier = TierClassifier().classify(
            factor_id,
            health_score=health.health_score,
            health_confidence=health.health_confidence,
            marginal_contribution=True,
            oos_ic=mean_ic,
            oos_icir=1.0,
            max_abs_corr=cluster.max_abs_corr,
        )
        current_status = _current_status(registry_path, factor_id)
        transition = StatusMachine().transition(
            factor_id,
            current_status=current_status,
            event="gate_passed" if current_status == "testing" else "tier_update",
            gate_result="pass",
            tier=tier.tier,
            health_score=health.health_score,
            health_confidence=health.health_confidence,
        )
        fhi: dict[str, Any] = {}
        if registry_path is not None:
            fhi = _compute_fhi(registry_path, factor_id, health.health_score, health.health_confidence)
        return {
            "success": True,
            "factor_id": factor_id,
            "health_score": health.health_score,
            "health_confidence": health.health_confidence,
            "health_breakdown": health.health_breakdown,
            "decay_profile": {
                "half_life_days": decay.half_life_days,
                "optimal_horizon": decay.optimal_horizon,
                "decay_speed": decay.decay_speed,
                "horizon_ic": decay.horizon_ic,
                "ts_gru_allowed": decay.ts_gru_allowed,
            },
            "regime_ic": regime.regime_ic,
            "cluster": {
                "cluster_id": cluster.cluster_id,
                "nearest_factor_id": cluster.nearest_factor_id,
                "max_abs_corr": cluster.max_abs_corr,
                "redundancy_action": cluster.redundancy_action,
            },
            "foundation_health_index": fhi,
            "tier": tier.tier,
            "ops_status": tier.ops_status,
            "suggested_status": transition.suggested_status if transition.transition_valid else tier.ops_status,
            "suggestion_reason": transition.reason or "; ".join(tier.reasons),
            "written": False if dry_run or no_write else False,
        }


def _current_status(registry_path: str | Path | None, factor_id: str) -> str:
    if registry_path is None:
        return "testing"
    for row in load_registry_frame(registry_path).to_dicts():
        if str(row.get("factor_id")) == factor_id:
            metadata = row.get("metadata_json") or {}
            if isinstance(metadata, str):
                import json

                metadata = json.loads(metadata or "{}")
            return str((metadata.get("ops") or {}).get("status") or "testing")
    return "testing"


def _compute_fhi(registry_path: str | Path, factor_id: str, score: float, confidence: float) -> dict[str, Any]:
    records = []
    for row in load_registry_frame(registry_path).to_dicts():
        records.append(
            {
                "factor_id": str(row.get("factor_id")),
                "data_source_type": "mined",
                "health_score": score if str(row.get("factor_id")) == factor_id else 50.0,
                "health_confidence": confidence,
            }
        )
    result = FoundationHealthIndexComputer().compute(pl.DataFrame(records)) if records else None
    if result is None:
        return {}
    return {
        "foundation_health_index": result.foundation_health_index,
        "foundation_factor_count": result.foundation_factor_count,
    }
