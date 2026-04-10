import json
from unittest.mock import patch

from quantaalpha.continuous.implementations import DefaultMiningScheduler


def _make_library(tmp_path):
    lib_path = tmp_path / "lib.json"
    lib_path.write_text(json.dumps({"metadata": {}, "factors": {}}))
    return lib_path


def _make_scheduler(tmp_path, similarity_engine_cfg):
    return DefaultMiningScheduler(
        library_path=str(_make_library(tmp_path)),
        similarity_engine_cfg=similarity_engine_cfg,
    )


def test_retrieve_context_skips_rag_when_disabled(tmp_path):
    scheduler = _make_scheduler(
        tmp_path,
        {
            "enabled": True,
            "metrics": {
                "rag": {"enabled": False},
                "ast": {"enabled": True},
                "jaccard": {"enabled": True},
            },
        },
    )

    with patch(
        "quantaalpha.factors.similarity_engine.SimilarityEngine.query_similar_factors",
        return_value=[],
    ), patch(
        "quantaalpha.factors.fewshot.query_active_factors_RAG",
        return_value=[],
    ) as mock_rag, patch(
        "quantaalpha.factors.fewshot.query_active_factors_jaccard",
        return_value=[],
    ) as mock_jaccard:
        scheduler._retrieve_context()

    mock_rag.assert_not_called()
    mock_jaccard.assert_called_once()


def test_retrieve_context_uses_rag_when_enabled(tmp_path):
    scheduler = _make_scheduler(
        tmp_path,
        {
            "enabled": True,
            "metrics": {
                "rag": {"enabled": True},
                "ast": {"enabled": True},
                "jaccard": {"enabled": True},
            },
        },
    )

    with patch(
        "quantaalpha.factors.similarity_engine.SimilarityEngine.query_similar_factors",
        return_value=[],
    ), patch(
        "quantaalpha.factors.fewshot.query_active_factors_RAG",
        return_value=[],
    ) as mock_rag, patch(
        "quantaalpha.factors.fewshot.query_active_factors_jaccard",
        return_value=[],
    ) as mock_jaccard:
        scheduler._retrieve_context()

    mock_rag.assert_called_once()
    mock_jaccard.assert_not_called()
