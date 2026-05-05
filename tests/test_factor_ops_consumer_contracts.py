from __future__ import annotations

import polars as pl
import pytest
from quantaalpha.factor_ops.consumer import PortfolioWeightMapper, TSGRUFactorInputBuilder


def test_ts_gru_factor_input_builder_filters_and_encodes_factor_ops_inputs() -> None:
    registry = pl.DataFrame(
        {
            "factor_id": ["core_a", "sat_b", "watch_c"],
            "ops_status": ["core", "satellite", "watchlist"],
            "tier": ["A", "B", "C"],
            "health_score": [90.0, 70.0, 45.0],
            "cluster_id": ["cluster_1", "cluster_1", "cluster_2"],
        }
    )
    regime_features = {
        "core_a": {"regime_ic_bull_ic_mean": 0.04},
        "sat_b": {"regime_ic_bull_ic_mean": 0.02},
    }

    result = TSGRUFactorInputBuilder().build(registry, regime_features=regime_features)

    assert result["factor_ids"] == ["core_a", "sat_b"]
    assert result["features"]["core_a"]["health_score_norm"] == 0.9
    assert result["features"]["core_a"]["tier_core"] == 1
    assert result["features"]["sat_b"]["tier_satellite"] == 1
    assert result["group_softmax_caps"] == {"cluster_1": 1.0}


def test_ts_gru_factor_input_builder_creates_dl_feature_registry_payload() -> None:
    payload = TSGRUFactorInputBuilder().build_h_t_registry_payload(
        factor_id="h_t_20260505",
        factor_expression="ts_gru_level3_weighted_signal",
        created_at="2026-05-05T15:00:00",
    )

    metadata = payload["metadata_json"]
    assert payload["factor_id"] == "h_t_20260505"
    assert metadata["data_source_type"] == "DL-Feature"
    assert metadata["ops"]["status"] == "testing"
    assert metadata["derived_from"] == []


def test_portfolio_weight_mapper_combines_health_and_dynamic_weights() -> None:
    mapper = PortfolioWeightMapper()
    result = mapper.map_factor_weights(
        health_scores={"core_a": 90.0, "sat_b": 70.0},
        dynamic_weights={"core_a": 0.6, "sat_b": 0.4},
        tier_caps={"core_a": 1.0, "sat_b": 0.5},
    )

    assert sum(result.values()) == pytest.approx(1.0)
    assert result["core_a"] > result["sat_b"]
    assert result["sat_b"] <= 0.5


def test_portfolio_weight_mapper_builds_market_neutral_stock_weights() -> None:
    factor_values = pl.DataFrame(
        {
            "stock_id": ["A", "B", "C", "D"],
            "core_a": [1.0, 0.5, -0.5, -1.0],
            "sat_b": [0.5, 1.0, -1.0, -0.5],
        }
    )

    weights = PortfolioWeightMapper().build_stock_weights(
        factor_values,
        factor_weights={"core_a": 0.7, "sat_b": 0.3},
        max_abs_weight=0.05,
    )

    assert set(weights.columns) == {"stock_id", "weight"}
    assert weights["weight"].abs().max() <= 0.05
    assert weights["weight"].sum() == pytest.approx(0.0)
