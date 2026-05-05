"""TS-GRU consumer input contract builders."""

from __future__ import annotations

from typing import Any

import polars as pl


class TSGRUFactorInputBuilder:
    """构建 TS-GRU Level 3 消费 factor_ops 的输入。"""

    MODEL_ELIGIBLE_STATUSES = {"candidate", "core", "satellite", "degraded"}

    def build(
        self,
        registry: pl.DataFrame,
        *,
        regime_features: dict[str, dict[str, float]] | None = None,
    ) -> dict[str, Any]:
        """输出因子列表、特征字典和 cluster cap。"""
        regime_features = regime_features or {}
        selected = registry.filter(pl.col("ops_status").is_in(sorted(self.MODEL_ELIGIBLE_STATUSES))).sort("factor_id")
        factor_ids = [str(value) for value in selected["factor_id"].to_list()]
        features = {}
        group_caps: dict[str, float] = {}
        for row in selected.to_dicts():
            factor_id = str(row["factor_id"])
            tier = str(row.get("tier", ""))
            features[factor_id] = {
                "health_score_norm": float(row.get("health_score", 0.0)) / 100,
                "tier_core": 1 if tier == "A" else 0,
                "tier_satellite": 1 if tier == "B" else 0,
                "tier_candidate": 1 if tier == "C" else 0,
                "tier_watchlist": 1 if tier == "D" else 0,
                **regime_features.get(factor_id, {}),
            }
            cluster_id = str(row.get("cluster_id", ""))
            if cluster_id:
                group_caps[cluster_id] = 1.0
        return {"factor_ids": factor_ids, "features": features, "group_softmax_caps": group_caps}

    def build_h_t_registry_payload(
        self,
        *,
        factor_id: str,
        factor_expression: str,
        created_at: str,
    ) -> dict[str, Any]:
        """构建 h_T 注册 payload，标记为 DL-Feature。"""
        return {
            "factor_id": factor_id,
            "factor_name": factor_id,
            "factor_expression": factor_expression,
            "created_at": created_at,
            "metadata_json": {
                "data_source_type": "DL-Feature",
                "derived_from": [],
                "ops": {"status": "testing", "tier": "", "version": 0},
            },
        }
