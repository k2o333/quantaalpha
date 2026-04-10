import json

from quantaalpha.factors.fewshot import query_active_factors_ast
from quantaalpha.factors.similarity_engine import SimilarityEngine


def _write_library(tmp_path):
    library = {
        "metadata": {},
        "factors": {
            "f1": {
                "factor_id": "f1",
                "factor_name": "Price Diff",
                "factor_expression": "$close - $open",
                "factor_description": "price difference",
                "evaluation": {"status": "active"},
                "tags": {},
                "backtest_results": {"IC": 0.12, "Rank IC": 0.09},
            },
            "f2": {
                "factor_id": "f2",
                "factor_name": "Volume Mean",
                "factor_expression": "MEAN($volume, 10)",
                "factor_description": "volume average",
                "evaluation": {"status": "active"},
                "tags": {},
                "backtest_results": {"IC": 0.08, "Rank IC": 0.05},
            },
        },
    }
    path = tmp_path / "library.json"
    path.write_text(json.dumps(library))
    return path


def test_query_active_factors_ast_returns_matches_for_expression_query(tmp_path):
    library_path = _write_library(tmp_path)

    results = query_active_factors_ast(
        query="$close - $open",
        top_k=2,
        library_path=str(library_path),
    )

    assert results
    assert results[0]["factor_id"] == "f1"
    assert results[0]["score"] > 0


def test_query_active_factors_ast_skips_natural_language_query(tmp_path):
    library_path = _write_library(tmp_path)

    results = query_active_factors_ast(
        query="high IC factor with volume and momentum signals",
        top_k=2,
        library_path=str(library_path),
    )

    assert results == []


def test_similarity_engine_prefers_ast_for_expression_query(tmp_path):
    library_path = _write_library(tmp_path)
    engine = SimilarityEngine(
        {
            "enabled": True,
            "metrics": {
                "rag": {"enabled": False},
                "ast": {"enabled": True},
                "jaccard": {"enabled": True},
            },
        }
    )

    results = engine.query_similar_factors(
        query="$close - $open",
        library_path=str(library_path),
        top_k=2,
    )

    assert results
    assert results[0]["factor_id"] == "f1"
