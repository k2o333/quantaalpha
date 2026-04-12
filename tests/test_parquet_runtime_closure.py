"""
Runtime closure tests for Parquet-native factor library paths.
"""

from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path


def _entry(
    *,
    factor_id: str = "factor_001",
    factor_name: str = "factor_001",
    factor_expression: str = "STD($close, 20)",
    expression_hash: str = "hash_001",
    evaluation_status: str = "active",
    sequence: int = 1,
) -> dict:
    now = datetime.now().isoformat()
    return {
        "factor_id": factor_id,
        "factor_name": factor_name,
        "factor_expression": factor_expression,
        "factor_expression_normalized": factor_expression,
        "expression_hash": expression_hash,
        "evaluation_status": evaluation_status,
        "created_at": now,
        "updated_at": now,
        "sequence": sequence,
        "op": "upsert",
        "tags_json": "{}",
        "metadata_json": "{}",
        "backtest_results_json": "{}",
    }


def test_parquet_revalidation_updates_status_via_facade_without_json(tmp_path, monkeypatch):
    """Parquet revalidation must update status through FactorStoreFacade, not FactorLibraryManager."""
    from quantaalpha.continuous.implementations import DefaultRevalidationScheduler
    from quantaalpha.factors.factor_store_facade import FactorStoreFacade
    import quantaalpha.factors.library as json_library

    store_dir = tmp_path / "parquet_store"
    facade = FactorStoreFacade(store_dir)
    facade.write_factor(
        _entry(
            factor_id="factor_reval",
            factor_name="factor_reval",
            expression_hash="hash_reval",
            evaluation_status="active",
            sequence=100,
        )
    )

    def fail_if_json_manager_used(*_args, **_kwargs):
        raise AssertionError("FactorLibraryManager must not be used for parquet revalidation")

    monkeypatch.setattr(json_library, "FactorLibraryManager", fail_if_json_manager_used)

    scheduler = DefaultRevalidationScheduler(
        library_backend="parquet",
        parquet_library_dir=str(store_dir),
        max_per_run=1,
        backtest_runner=lambda _factor_id, _factor_entry: False,
    )

    result = scheduler.run_revalidation()

    records = facade.read_effective_factor_records()
    assert result.errors == []
    assert result.status_changes["factor_reval"] == "degraded"
    assert records[0]["factor_id"] == "factor_reval"
    assert records[0]["evaluation_status"] == "degraded"
    assert not list(store_dir.rglob("*.json"))


def test_parquet_similarity_engine_uses_facade_records_not_json_library(tmp_path):
    """Parquet redundancy checks should use SimilarityEngine over facade records without reading JSON."""
    from quantaalpha.continuous.implementations import DefaultMiningScheduler
    from quantaalpha.factors.factor_store_facade import FactorStoreFacade
    from quantaalpha.factors.similarity_engine import SimilarityEngine

    store_dir = tmp_path / "parquet_store"
    facade = FactorStoreFacade(store_dir)
    facade.write_factor(
        _entry(
            factor_id="similar_factor",
            factor_name="similar_factor",
            factor_expression="STD($close, 20)",
            expression_hash="similar_hash",
            evaluation_status="active",
            sequence=200,
        )
    )

    engine = SimilarityEngine(
        {
            "enabled": True,
            "ensemble_mode": "weighted",
            "rejection_threshold": 0.1,
            "metrics": {
                "ast": {"enabled": False},
                "rag": {"enabled": False},
                "jaccard": {"enabled": True, "weight": 1.0},
            },
        }
    )
    scheduler = DefaultMiningScheduler(
        library_backend="parquet",
        parquet_library_dir=str(store_dir),
        library_path=str(tmp_path / "must_not_read.json"),
    )
    scheduler._similarity_engine = engine

    result = scheduler._check_redundancy(
        {
            "factor_id": "new_factor",
            "factor_name": "new_factor",
            "factor_expression": "STD($close, 20)",
        }
    )

    assert result["is_redundant"] is True
    assert result["method"] == "ensemble"
    assert result["most_similar_factor_id"] == "similar_factor"
    assert result["comparisons_made"] == 1


def test_parquet_similarity_engine_data_path_does_not_query_global_rag(tmp_path, monkeypatch):
    """Parquet library-data similarity must not call the legacy global RAG/fewshot library."""
    from quantaalpha.factors.factor_store_facade import FactorStoreFacade
    from quantaalpha.factors.similarity_engine import SimilarityEngine
    import quantaalpha.factors.fewshot as fewshot

    store_dir = tmp_path / "parquet_store"
    entry = _entry(
        factor_id="rag_guard_factor",
        factor_name="rag_guard_factor",
        factor_expression="MEAN($volume, 10)",
        expression_hash="rag_guard_hash",
        evaluation_status="active",
        sequence=300,
    )
    entry["metadata_json"] = json.dumps({"factor_description": "volume momentum"})
    facade = FactorStoreFacade(store_dir)
    facade.write_factor(entry)

    rag_calls = []

    def fail_if_global_rag_used(*_args, **_kwargs):
        rag_calls.append(True)
        raise AssertionError("global JSON/RAG factor library must not be queried")

    monkeypatch.setattr(fewshot, "query_active_factors_RAG", fail_if_global_rag_used)

    engine = SimilarityEngine(
        {
            "enabled": True,
            "ensemble_mode": "weighted",
            "rejection_threshold": 0.1,
            "metrics": {
                "ast": {"enabled": False},
                "rag": {"enabled": True, "weight": 1.0},
                "jaccard": {"enabled": True, "weight": 1.0},
            },
        }
    )

    result = engine.check_against_library_data(
        new_expression="MEAN($volume, 10)",
        library=facade.as_legacy_library(),
        max_comparisons=10,
    )

    assert result.comparisons_made == 1
    assert rag_calls == []
