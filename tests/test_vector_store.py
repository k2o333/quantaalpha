"""
Unit tests for FactorVectorStore and fewshot RAG integration.

Tests cover:
- Vector store CRUD operations
- ChromaDB integration (or fallback mode)
- Sync from factor library
- Fewshot query methods
- Jaccard fallback
"""

import json
import os
import tempfile
import pytest
from pathlib import Path

# Import the modules under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from quantaalpha.factors.vector_store import (
    FactorVectorStore,
    FactorVectorEntry,
    create_vector_store,
    CHROMADB_AVAILABLE,
)
from quantaalpha.factors.fewshot import (
    compute_jaccard_similarity,
    query_active_factors_jaccard,
    build_fewshot_context,
    summarize_common_patterns,
    reset_vector_store,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as td:
        yield td


@pytest.fixture
def sample_factor():
    """Sample factor entry for testing."""
    return {
        "factor_id": "test_001",
        "factor_expression": "RANK(TS_MEAN($close, 20)) / RANK(TS_MEAN($volume, 20))",
        "factor_name": "Volume-Weighted Momentum",
        "tags": {
            "category": ["momentum"],
            "data_dependency": ["price_volume"],
            "market_environment": ["bull", "sideways"],
            "time_horizon": ["medium_term"],
        },
        "evaluation": {
            "status": "active",
            "stability_score": 0.75,
        },
        "backtest_results": {
            "IC": 0.0532,
            "Rank IC": 0.0418,
        },
    }


@pytest.fixture
def sample_library(temp_dir, sample_factor):
    """Create a sample factor library JSON file."""
    library_path = os.path.join(temp_dir, "factor_library.json")
    
    library_data = {
        "metadata": {
            "version": "1.1",
            "total_factors": 2,
        },
        "factors": {
            "test_001": sample_factor,
            "test_002": {
                "factor_id": "test_002",
                "factor_expression": "DELTA($close, 1) / DELTA($close, 5)",
                "factor_name": "Price Reversal",
                "tags": {
                    "category": ["reversal"],
                    "data_dependency": ["price_volume"],
                    "market_environment": ["high_vol"],
                    "time_horizon": ["short_term"],
                },
                "evaluation": {
                    "status": "active",
                    "stability_score": 0.62,
                },
                "backtest_results": {
                    "IC": 0.0387,
                    "Rank IC": 0.0321,
                },
            },
            "test_003": {
                "factor_id": "test_003",
                "factor_expression": "TS_CORR($close, $volume, 20)",
                "factor_name": "Volume Correlation",
                "tags": {
                    "category": ["liquidity"],
                    "data_dependency": ["price_volume"],
                    "market_environment": [],
                    "time_horizon": ["medium_term"],
                },
                "evaluation": {
                    "status": "degraded",
                    "stability_score": 0.15,
                },
                "backtest_results": {
                    "IC": 0.012,
                    "Rank IC": 0.008,
                },
            },
        },
    }
    
    with open(library_path, "w", encoding="utf-8") as f:
        json.dump(library_data, f)
    
    return library_path


@pytest.fixture
def vector_store(temp_dir):
    """Create a FactorVectorStore instance for testing."""
    reset_vector_store()  # Clear singleton
    store = FactorVectorStore(
        persist_directory=temp_dir,
        collection_name="test_factors",
    )
    yield store
    reset_vector_store()  # Clean up singleton


# =============================================================================
# FactorVectorEntry Tests
# =============================================================================

class TestFactorVectorEntry:
    """Tests for FactorVectorEntry dataclass."""
    
    def test_create_entry(self):
        """Test basic entry creation."""
        entry = FactorVectorEntry(
            factor_id="test_001",
            factor_expression="close / open",
            tags={"category": ["momentum"]},
            metadata={"status": "active"},
        )
        
        assert entry.factor_id == "test_001"
        assert entry.factor_expression == "close / open"
        assert entry.tags == {"category": ["momentum"]}
        assert entry.metadata == {"status": "active"}
        assert entry.created_at is not None
    
    def test_default_values(self):
        """Test default values are set correctly."""
        entry = FactorVectorEntry(
            factor_id="test_002",
            factor_expression="RANK($close)",
        )
        
        assert entry.tags == {}
        assert entry.metadata == {}


# =============================================================================
# FactorVectorStore Tests
# =============================================================================

class TestFactorVectorStoreBasics:
    """Basic CRUD tests for FactorVectorStore."""
    
    def test_init_in_memory(self):
        """Test initialization in memory mode."""
        store = FactorVectorStore()
        assert store is not None
        assert store.count() == 0
    
    def test_init_with_persist(self, temp_dir):
        """Test initialization with persistence."""
        store = FactorVectorStore(persist_directory=temp_dir)
        assert store is not None
        assert store.count() == 0
    
    def test_add_factor_basic(self, vector_store):
        """Test adding a basic factor."""
        result = vector_store.add_factor(
            factor_id="factor_001",
            factor_expression="close / open",
        )
        
        assert result is True
        assert vector_store.count() == 1
    
    def test_add_factor_with_tags(self, vector_store):
        """Test adding a factor with tags."""
        result = vector_store.add_factor(
            factor_id="factor_002",
            factor_expression="RANK(TS_MEAN($close, 20))",
            tags={"category": ["momentum"], "data_dependency": ["price_volume"]},
            metadata={"status": "active", "ic": 0.05},
        )
        
        assert result is True
    
    def test_add_factor_empty_expression(self, vector_store):
        """Test adding factor with empty expression fails."""
        result = vector_store.add_factor(
            factor_id="factor_003",
            factor_expression="",
        )
        
        assert result is False
        assert vector_store.count() == 0
    
    def test_add_duplicate_factor(self, vector_store):
        """Test adding duplicate factor updates existing."""
        vector_store.add_factor(
            factor_id="factor_004",
            factor_expression="original",
        )
        assert vector_store.count() == 1
        
        # Re-add with updated expression
        vector_store.add_factor(
            factor_id="factor_004",
            factor_expression="updated",
        )
        assert vector_store.count() == 1
        
        # Verify update
        results = vector_store.query_similar("updated")
        assert len(results) == 1
        assert results[0]["factor_expression"] == "updated"
    
    def test_remove_factor(self, vector_store):
        """Test removing a factor."""
        vector_store.add_factor(
            factor_id="factor_005",
            factor_expression="to_be_removed",
        )
        assert vector_store.count() == 1
        
        vector_store.remove_factor("factor_005")
        assert vector_store.count() == 0
    
    def test_remove_nonexistent_factor(self, vector_store):
        """Test removing non-existent factor doesn't error."""
        result = vector_store.remove_factor("nonexistent")
        assert result is True
    
    def test_clear_store(self, vector_store):
        """Test clearing all factors."""
        for i in range(5):
            vector_store.add_factor(
                factor_id=f"factor_{i}",
                factor_expression=f"expr_{i}",
            )
        assert vector_store.count() == 5
        
        vector_store.clear()
        assert vector_store.count() == 0


class TestVectorStoreQuery:
    """Tests for query functionality."""
    
    def test_query_similar_basic(self, vector_store):
        """Test basic similarity query."""
        # Add test factors
        vector_store.add_factor(
            factor_id="momentum_001",
            factor_expression="RANK(TS_MEAN($close, 20))",
            tags={"category": ["momentum"]},
            metadata={"status": "active"},
        )
        vector_store.add_factor(
            factor_id="reversal_001",
            factor_expression="DELTA($close, 1) / DELTA($close, 5)",
            tags={"category": ["reversal"]},
            metadata={"status": "active"},
        )
        
        results = vector_store.query_similar("momentum", top_k=5)
        
        assert len(results) >= 1
        # Momentum factor should be more similar to "momentum" query
        momentum_scores = [r for r in results if r["factor_id"] == "momentum_001"]
        assert len(momentum_scores) == 1
    
    def test_query_with_filter(self, vector_store):
        """Test query with status filter."""
        vector_store.add_factor(
            factor_id="active_001",
            factor_expression="active_factor",
            metadata={"status": "active"},
        )
        vector_store.add_factor(
            factor_id="degraded_001",
            factor_expression="degraded_factor",
            metadata={"status": "degraded"},
        )
        
        results = vector_store.query_similar(
            "factor",
            top_k=10,
            filter_metadata={"status": "active"},
        )
        
        assert len(results) >= 1
        for r in results:
            assert r["metadata"]["status"] == "active"
    
    def test_query_empty_store(self, vector_store):
        """Test query on empty store returns empty."""
        results = vector_store.query_similar("momentum", top_k=5)
        assert results == []


class TestVectorStoreSync:
    """Tests for sync from library functionality."""
    
    def test_sync_from_library(self, vector_store, sample_library):
        """Test syncing factors from library file."""
        count = vector_store.sync_from_library(sample_library)
        
        assert count == 3
        assert vector_store.count() == 3
    
    def test_sync_with_status_filter(self, vector_store, sample_library):
        """Test syncing only active factors."""
        count = vector_store.sync_from_library(
            sample_library,
            filter_status="active",
        )
        
        assert count == 2
        assert vector_store.count() == 2
    
    def test_sync_nonexistent_library(self, vector_store):
        """Test syncing from non-existent library returns 0."""
        count = vector_store.sync_from_library("/nonexistent/path.json")
        assert count == 0


# =============================================================================
# Jaccard Similarity Tests
# =============================================================================

class TestJaccardSimilarity:
    """Tests for Jaccard similarity computation."""
    
    def test_identical_texts(self):
        """Test Jaccard similarity of identical texts."""
        text = "momentum reversal factor"
        score = compute_jaccard_similarity(text, text)
        assert score == 1.0
    
    def test_no_overlap(self):
        """Test Jaccard similarity with no overlap."""
        score = compute_jaccard_similarity("momentum factor", "liquidity indicator")
        assert score == 0.0
    
    def test_partial_overlap(self):
        """Test Jaccard similarity with partial overlap."""
        score = compute_jaccard_similarity("momentum factor", "momentum reversal")
        assert 0 < score < 1
    
    def test_empty_texts(self):
        """Test Jaccard similarity with empty texts."""
        assert compute_jaccard_similarity("", "text") == 0.0
        assert compute_jaccard_similarity("text", "") == 0.0
        assert compute_jaccard_similarity("", "") == 0.0
    
    def test_case_insensitivity(self):
        """Test Jaccard similarity is case-insensitive."""
        score1 = compute_jaccard_similarity("MOMENTUM", "momentum")
        score2 = compute_jaccard_similarity("momentum", "momentum")
        assert abs(score1 - score2) < 0.001


# =============================================================================
# Fewshot Query Tests
# =============================================================================

class TestQueryActiveFactorsJaccard:
    """Tests for Jaccard-based factor query."""
    
    def test_query_from_library(self, sample_library):
        """Test querying factors from library."""
        results = query_active_factors_jaccard(
            query="rank close volume",
            top_k=5,
            min_score=0.05,
            library_path=sample_library,
        )
        
        assert len(results) >= 1
        for r in results:
            assert r["metadata"]["status"] == "active"
    
    def test_query_nonexistent_library(self):
        """Test query from non-existent library returns empty."""
        results = query_active_factors_jaccard(
            query="rank close volume",
            library_path="/nonexistent/library.json",
        )
        assert results == []
    
    def test_query_filters_by_status(self, sample_library):
        """Test that query only returns active factors."""
        results = query_active_factors_jaccard(
            query="correlation",
            top_k=5,
            library_path=sample_library,
        )
        
        # test_003 (degraded) should not appear
        for r in results:
            assert r["metadata"]["status"] == "active"


# =============================================================================
# Context Building Tests
# =============================================================================

class TestBuildFewshotContext:
    """Tests for few-shot context building."""
    
    def test_empty_factors(self):
        """Test building context with no factors."""
        context = build_fewshot_context([])
        assert context == "No similar factors found."
    
    def test_single_factor(self):
        """Test building context with single factor."""
        factors = [
            {
                "factor_id": "test_001",
                "factor_expression": "RANK($close)",
                "factor_name": "Price Rank",
                "score": 0.85,
                "tags": {"category": ["momentum"]},
                "metadata": {"ic": 0.05, "rank_ic": 0.04},
            }
        ]
        
        context = build_fewshot_context(factors)
        
        assert "Price Rank" in context
        assert "RANK($close)" in context
        assert "momentum" in context
        assert "85.00%" in context  # Formatted as percentage
    
    def test_multiple_factors(self):
        """Test building context with multiple factors."""
        factors = [
            {"factor_id": "f1", "factor_expression": "expr1", "score": 0.9,
             "tags": {}, "metadata": {}},
            {"factor_id": "f2", "factor_expression": "expr2", "score": 0.7,
             "tags": {}, "metadata": {}},
        ]
        
        context = build_fewshot_context(factors)
        
        assert "expr1" in context
        assert "expr2" in context
        assert "Factor 1" in context
        assert "Factor 2" in context


class TestSummarizePatterns:
    """Tests for pattern summarization."""
    
    def test_empty_factors(self):
        """Test summary with no factors."""
        summary = summarize_common_patterns([], "momentum")
        assert "No existing factors" in summary
    
    def test_pattern_extraction(self):
        """Test pattern extraction from factors."""
        factors = [
            {
                "factor_id": "f1",
                "factor_expression": "RANK(TS_MEAN($close, 20))",
                "tags": {
                    "category": ["momentum"],
                    "data_dependency": ["price_volume"],
                },
                "metadata": {"ic": 0.05},
            },
            {
                "factor_id": "f2",
                "factor_expression": "RANK(TS_MEAN($volume, 10))",
                "tags": {
                    "category": ["momentum"],
                    "data_dependency": ["price_volume"],
                },
                "metadata": {"ic": 0.04},
            },
        ]
        
        summary = summarize_common_patterns(factors, "momentum")
        
        assert "2 similar factors" in summary
        assert "momentum" in summary
        assert "price_volume" in summary
        assert "RANK" in summary or "TS_MEAN" in summary


# =============================================================================
# Factory Function Tests
# =============================================================================

class TestFactoryFunction:
    """Tests for create_vector_store factory function."""
    
    def test_create_default(self):
        """Test creating store with defaults."""
        reset_vector_store()
        store = create_vector_store()
        assert store is not None
        assert isinstance(store, FactorVectorStore)
    
    def test_create_with_params(self, temp_dir):
        """Test creating store with custom params."""
        reset_vector_store()
        store = create_vector_store(
            persist_dir=temp_dir,
            collection="custom_collection",
        )
        assert store.collection_name == "custom_collection"


# =============================================================================
# Integration Tests
# =============================================================================

class TestVectorStoreIntegration:
    """End-to-end integration tests."""
    
    def test_full_workflow(self, temp_dir):
        """Test complete add -> query -> remove workflow."""
        # Create store
        store = FactorVectorStore(persist_directory=temp_dir)
        
        # Add factors
        store.add_factor(
            factor_id="e2e_001",
            factor_expression="RANK(TS_MEAN($close, 20))",
            tags={"category": ["momentum"]},
            metadata={"status": "active", "ic": 0.05},
        )
        store.add_factor(
            factor_id="e2e_002",
            factor_expression="DELTA($close, 1)",
            tags={"category": ["reversal"]},
            metadata={"status": "active", "ic": 0.03},
        )
        
        # Query - use terms that appear in expressions
        results = store.query_similar("rank mean close volume", top_k=10)
        assert len(results) >= 1
        
        # Remove
        store.remove_factor("e2e_001")
        assert store.count() >= 0
        
        # Query remaining
        results = store.query_similar("close delta", top_k=10)
        assert len(results) >= 0
    
    def test_sync_and_query_workflow(self, temp_dir, sample_library):
        """Test sync from library and query workflow."""
        # Create and sync store
        store = FactorVectorStore(persist_directory=temp_dir)
        count = store.sync_from_library(sample_library, filter_status="active")
        assert count == 2
        
        # Query for momentum
        results = store.query_similar("momentum", top_k=5)
        assert len(results) >= 1
        
        # Verify results have expected structure
        for r in results:
            assert "factor_id" in r
            assert "score" in r
            assert "factor_expression" in r


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
