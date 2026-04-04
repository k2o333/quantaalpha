"""
Tests for FactorLibraryManager redundancy check functionality.
Task D2: 因子相关性去冗余
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from quantaalpha.factors.library import FactorLibraryManager


class TestExpressionSimilarity:
    """Test suite for _expression_similarity method."""

    @pytest.fixture
    def tmp_path(self):
        """Create a temporary library path."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "library.json"
            p.write_text(
                json.dumps(
                    {
                        "metadata": {
                            "created_at": datetime.now().isoformat(),
                            "last_updated": datetime.now().isoformat(),
                            "total_factors": 0,
                            "version": "1.1",
                        },
                        "factors": {},
                    }
                ),
                encoding="utf-8",
            )
            yield str(p)

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a FactorLibraryManager instance."""
        return FactorLibraryManager(tmp_path)

    def test_identical_expressions(self, manager):
        """Identical expressions should have similarity 1.0."""
        sim = manager._expression_similarity("ts_mean($close,20)", "ts_mean($close,20)")
        assert sim == 1.0

    def test_empty_expressions(self, manager):
        """Empty expressions should return 0.0."""
        assert manager._expression_similarity("", "") == 0.0
        assert manager._expression_similarity("ts_mean($close,20)", "") == 0.0
        assert manager._expression_similarity("", "ts_mean($close,20)") == 0.0

    def test_skeleton_same_params_different(self, manager):
        """Only numeric parameters different (same skeleton) should be >= 0.90."""
        sim = manager._expression_similarity(
            "ts_mean($close,20)", "ts_mean($close,60)"
        )
        assert sim >= 0.90, f"Expected >= 0.90 for skeleton match, got {sim}"

    def test_skeleton_same_complex(self, manager):
        """Complex expressions with only params different should be >= 0.90."""
        sim = manager._expression_similarity(
            "ts_corr($volume, ts_mean($close, 5), 20)",
            "ts_corr($volume, ts_mean($close, 10), 60)",
        )
        assert sim >= 0.90, f"Expected >= 0.90 for skeleton match, got {sim}"

    def test_different_expressions_low_similarity(self, manager):
        """Completely different expressions should have low similarity."""
        sim = manager._expression_similarity(
            "ts_mean($close,20)",
            "ts_std($volume,30)",
        )
        # Should be low but not zero since both have ts_ prefix and $ variables
        assert sim < 0.85

    def test_normalize_expression(self, manager):
        """_normalize_expression_for_comparison should normalize expressions."""
        normalized = manager._normalize_expression_for_comparison(
            "  TS_MEAN(  $close , 20 )  "
        )
        assert normalized == "ts_mean($close,20)"
        assert " " not in normalized
        assert normalized.islower() or normalized == normalized


class TestRedundancyCheck:
    """Test suite for check_redundancy method."""

    @pytest.fixture
    def tmp_path(self):
        """Create a temporary library path."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "library.json"
            p.write_text(
                json.dumps(
                    {
                        "metadata": {
                            "created_at": datetime.now().isoformat(),
                            "last_updated": datetime.now().isoformat(),
                            "total_factors": 0,
                            "version": "1.1",
                        },
                        "factors": {},
                    }
                ),
                encoding="utf-8",
            )
            yield str(p)

    @pytest.fixture
    def manager(self, tmp_path):
        """Create a FactorLibraryManager instance."""
        return FactorLibraryManager(tmp_path)

    def test_identical_expression_is_redundant(self, manager):
        """
        RED test: 完全相同的表达式应判定为冗余 (is_redundant=True).
        """
        # Add existing factor with status="active"
        manager.upsert_factor({
            "factor_id": "f1",
            "factor_expression": "ts_mean($close, 20)",
            "evaluation": {"status": "active"},
        })

        result = manager.check_redundancy("ts_mean($close, 20)")
        assert result["is_redundant"] is True, f"Expected is_redundant=True, got {result}"
        assert result["max_similarity"] >= 0.99, f"Expected similarity >= 0.99, got {result['max_similarity']}"

    def test_window_variant_is_redundant(self, manager):
        """
        RED test: 仅窗口参数不同应判定为高相似 (similarity >= 0.85).
        """
        manager.upsert_factor({
            "factor_id": "f1",
            "factor_expression": "ts_mean($close, 20)",
            "evaluation": {"status": "active"},
        })

        result = manager.check_redundancy("ts_mean($close, 60)")
        assert result["max_similarity"] >= 0.85, (
            f"Expected similarity >= 0.85 for window variant, got {result['max_similarity']}"
        )
        assert result["is_redundant"] is True, (
            f"Expected is_redundant=True for similarity >= 0.85, got {result}"
        )

    def test_different_expression_not_redundant(self, manager):
        """
        RED test: 完全不同的表达式不应判定为冗余 (is_redundant=False).
        """
        manager.upsert_factor({
            "factor_id": "f1",
            "factor_expression": "ts_mean($close, 20)",
        })

        result = manager.check_redundancy(
            "ts_corr($volume, ts_mean($close, 5), 20) / ts_std($close, 10)"
        )
        assert result["is_redundant"] is False, (
            f"Expected is_redundant=False for different expression, got {result}"
        )
        assert result["max_similarity"] < 0.85, (
            f"Expected similarity < 0.85 for different expression, got {result['max_similarity']}"
        )

    def test_empty_library_not_redundant(self, manager):
        """
        RED test: 空因子库不应判定为冗余.
        """
        result = manager.check_redundancy("ts_mean($close, 20)")
        assert result["is_redundant"] is False, (
            f"Expected is_redundant=False for empty library, got {result}"
        )
        assert result["max_similarity"] == 0.0, (
            f"Expected max_similarity=0.0 for empty library, got {result['max_similarity']}"
        )

    def test_failopen_on_exception(self, manager):
        """
        RED test: 冗余检查异常时应 fail-open (不阻止入库).
        """
        # Mock select_revalidation_candidates to raise
        with patch.object(
            manager, "select_revalidation_candidates", side_effect=RuntimeError("DB error")
        ):
            result = manager.check_redundancy("ts_mean($close, 20)")
            # fail-open: is_redundant should be False
            assert result["is_redundant"] is False, (
                f"Expected fail-open (is_redundant=False) on exception, got {result}"
            )


class TestRedundancyCheckIntegration:
    """Integration tests for redundancy check with DefaultMiningScheduler."""

    @pytest.fixture
    def tmp_library_path(self):
        """Create a temporary library file."""
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "library.json"
            p.write_text(
                json.dumps(
                    {
                        "metadata": {
                            "created_at": datetime.now().isoformat(),
                            "last_updated": datetime.now().isoformat(),
                            "total_factors": 0,
                            "version": "1.1",
                        },
                        "factors": {},
                    }
                ),
                encoding="utf-8",
            )
            yield str(p)

    def test_redundancy_check_failopen(self, tmp_library_path):
        """
        RED test: _check_redundancy 在异常时应 fail-open (返回 is_redundant=False).
        """
        from quantaalpha.continuous.implementations import DefaultMiningScheduler

        # Create a minimal scheduler with required params
        scheduler = DefaultMiningScheduler(
            data_bridge=None,
            library_path=tmp_library_path,
            max_per_run=10,
            interval_hours=24,
        )

        # Mock library.check_redundancy to raise an exception to test fail-open
        with patch(
            "quantaalpha.factors.library.FactorLibraryManager.check_redundancy",
            side_effect=RuntimeError("Simulated library error"),
        ):
            result = scheduler._check_redundancy({"factor_expression": "ts_mean($close,20)"})
            assert result["is_redundant"] is False, (
                f"Expected fail-open (is_redundant=False) on exception, got {result}"
            )