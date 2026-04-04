"""Tests for factor tag classification system (S03)."""

import json
import tempfile
from pathlib import Path

import pytest

from quantaalpha.factors.library import (
    FactorLibraryManager,
    CATEGORY_TAGS,
    DATA_DEPENDENCY_TAGS,
    MARKET_ENVIRONMENT_TAGS,
    TIME_HORIZON_TAGS,
    TAG_DEFINITIONS,
    DEFAULT_TAGS,
)


class TestTagConstants:
    """Verify tag enumeration constants are properly defined."""

    def test_category_tags_defined(self):
        assert CATEGORY_TAGS == ["momentum", "reversal", "value", "quality", "liquidity"]

    def test_data_dependency_tags_defined(self):
        assert DATA_DEPENDENCY_TAGS == ["price_volume", "financial", "alternative"]

    def test_market_environment_tags_defined(self):
        assert MARKET_ENVIRONMENT_TAGS == ["bull", "bear", "sideways", "high_vol"]

    def test_time_horizon_tags_defined(self):
        assert TIME_HORIZON_TAGS == ["short_term", "intraday", "medium_term"]

    def test_tag_definitions_has_all_keys(self):
        assert set(TAG_DEFINITIONS.keys()) == {
            "category",
            "data_dependency",
            "market_environment",
            "time_horizon",
        }

    def test_default_tags_has_all_keys(self):
        assert set(DEFAULT_TAGS.keys()) == {
            "category",
            "data_dependency",
            "market_environment",
            "time_horizon",
        }

    def test_default_tags_all_empty_lists(self):
        for key, value in DEFAULT_TAGS.items():
            assert isinstance(value, list), f"{key} default should be a list"
            assert value == [], f"{key} default should be empty"


class TestNormalizeTags:
    """Verify _normalize_factor_entry handles tags correctly."""

    @pytest.fixture
    def temp_library(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lib_path = Path(tmpdir) / "factors.json"
            yield lib_path

    def test_new_entry_has_tags(self, temp_library):
        manager = FactorLibraryManager(str(temp_library))
        entry = manager._normalize_factor_entry({
            "factor_id": "test001",
            "factor_name": "test_factor",
            "factor_expression": "$close",
        })
        assert "tags" in entry
        assert set(entry["tags"].keys()) == {
            "category",
            "data_dependency",
            "market_environment",
            "time_horizon",
        }

    def test_new_entry_tags_are_empty_lists(self, temp_library):
        manager = FactorLibraryManager(str(temp_library))
        entry = manager._normalize_factor_entry({
            "factor_id": "test002",
            "factor_name": "test_factor",
        })
        for key in DEFAULT_TAGS:
            assert entry["tags"][key] == [], f"{key} should be empty list"

    def test_existing_entry_gets_tags(self, temp_library):
        manager = FactorLibraryManager(str(temp_library))
        # Simulate an old entry without tags field
        old_entry = {
            "factor_id": "old001",
            "factor_name": "old_factor",
            "factor_expression": "$close",
            "metadata": {},
        }
        normalized = manager._normalize_factor_entry(old_entry)
        assert "tags" in normalized
        for key in DEFAULT_TAGS:
            assert key in normalized["tags"]

    def test_preserves_existing_tags(self, temp_library):
        manager = FactorLibraryManager(str(temp_library))
        entry_with_tags = {
            "factor_id": "test003",
            "factor_name": "test_factor",
            "tags": {
                "category": ["momentum", "quality"],
                "data_dependency": ["price_volume"],
                "market_environment": ["bull"],
                "time_horizon": ["medium_term"],
            },
        }
        normalized = manager._normalize_factor_entry(entry_with_tags)
        assert normalized["tags"]["category"] == ["momentum", "quality"]
        assert normalized["tags"]["data_dependency"] == ["price_volume"]
        assert normalized["tags"]["market_environment"] == ["bull"]
        assert normalized["tags"]["time_horizon"] == ["medium_term"]

    def test_none_tags_becomes_default(self, temp_library):
        manager = FactorLibraryManager(str(temp_library))
        entry = {
            "factor_id": "test004",
            "factor_name": "test_factor",
            "tags": None,
        }
        normalized = manager._normalize_factor_entry(entry)
        assert normalized["tags"] == dict(DEFAULT_TAGS)

    def test_partial_tags_fills_missing(self, temp_library):
        manager = FactorLibraryManager(str(temp_library))
        entry = {
            "factor_id": "test005",
            "factor_name": "test_factor",
            "tags": {
                "category": ["value"],
            },
        }
        normalized = manager._normalize_factor_entry(entry)
        assert normalized["tags"]["category"] == ["value"]
        assert normalized["tags"]["data_dependency"] == []
        assert normalized["tags"]["market_environment"] == []
        assert normalized["tags"]["time_horizon"] == []

    def test_tags_json_serializable(self, temp_library):
        manager = FactorLibraryManager(str(temp_library))
        entry = manager._normalize_factor_entry({
            "factor_id": "test006",
            "factor_name": "test_factor",
            "tags": {
                "category": ["momentum"],
                "data_dependency": ["price_volume", "financial"],
                "market_environment": ["bull", "high_vol"],
                "time_horizon": ["short_term"],
            },
        })
        # Should not raise
        json_str = json.dumps(entry)
        parsed = json.loads(json_str)
        assert parsed["tags"] == entry["tags"]


class TestLibraryIntegration:
    """Integration tests: tags persist through library save/load."""

    @pytest.fixture
    def temp_library(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            lib_path = Path(tmpdir) / "factors.json"
            yield lib_path

    def test_upsert_factor_with_tags(self, temp_library):
        manager = FactorLibraryManager(str(temp_library))
        entry = {
            "factor_id": "upsert001",
            "factor_name": "upsert_test",
            "factor_expression": "$close",
            "tags": {
                "category": ["reversal"],
                "data_dependency": ["price_volume"],
                "market_environment": ["bear"],
                "time_horizon": ["short_term"],
            },
        }
        result = manager.upsert_factor(entry)
        assert result["tags"]["category"] == ["reversal"]
        # Reload from disk
        manager2 = FactorLibraryManager(str(temp_library))
        reloaded = manager2.get_factor("upsert001")
        assert reloaded is not None
        assert reloaded["tags"]["category"] == ["reversal"]
        assert reloaded["tags"]["market_environment"] == ["bear"]

    def test_library_load_migrates_old_factors(self, temp_library):
        # Write a legacy factor without tags directly to JSON
        with open(temp_library, "w") as f:
            json.dump(
                {
                    "metadata": {
                        "created_at": "2024-01-01T00:00:00",
                        "last_updated": "2024-01-01T00:00:00",
                        "total_factors": 1,
                        "version": "1.1",
                    },
                    "factors": {
                        "legacy001": {
                            "factor_id": "legacy001",
                            "factor_name": "legacy_factor",
                            "factor_expression": "$close",
                        }
                    },
                },
                f,
            )
        manager = FactorLibraryManager(str(temp_library))
        entry = manager.get_factor("legacy001")
        assert entry is not None
        assert "tags" in entry
        assert entry["tags"]["category"] == []
