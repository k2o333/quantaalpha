"""Small CLI-facing summaries for factor_ops."""

from __future__ import annotations

import json
from typing import Any

import polars as pl

MODEL_ELIGIBLE_STATUSES = {"candidate", "core", "satellite", "degraded"}
LEGACY_EVALUATION_STATUS_TO_OPS_STATUS = {
    "pending_validation": "testing",
    "active": "candidate",
    "stale": "watchlist",
    "degraded": "degraded",
    "deprecated": "retired",
}


def build_status_summary(registry: pl.DataFrame) -> dict[str, Any]:
    """从 registry DataFrame 构建 factor-ops status 摘要。"""
    status_counts: dict[str, int] = {}
    tier_counts: dict[str, int] = {}
    eligible = 0
    for row in registry.to_dicts():
        ops = _ops(row.get("metadata_json"))
        status = _ops_status(ops, row.get("evaluation_status"))
        tier = str(ops.get("tier", ""))
        status_counts[status] = status_counts.get(status, 0) + 1
        if tier:
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
        if status in MODEL_ELIGIBLE_STATUSES:
            eligible += 1
    return {
        "total_factors": registry.height,
        "status_counts": status_counts,
        "tier_counts": tier_counts,
        "model_eligible_count": eligible,
    }


def _ops(metadata_json: Any) -> dict[str, Any]:
    metadata = json.loads(metadata_json or "{}") if isinstance(metadata_json, str) else metadata_json or {}
    return dict(metadata.get("ops", {}) or {})


def _ops_status(ops: dict[str, Any], evaluation_status: Any) -> str:
    status = ops.get("status")
    if status:
        return str(status)
    return LEGACY_EVALUATION_STATUS_TO_OPS_STATUS.get(str(evaluation_status or ""), "unknown")
