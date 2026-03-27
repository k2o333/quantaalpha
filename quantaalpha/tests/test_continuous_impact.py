"""
Unit tests for the continuous impact classifier.

Tests cover:
- Interface to bucket classification
- Bucket to factor candidate selection
- Fallback behavior for unknown interfaces/missing metadata
- Edge cases (empty inputs, None library manager, etc.)
"""

import json
from unittest.mock import MagicMock

import pytest


class TestInterfaceClassification:
    """Tests for classify_interfaces method."""

    def test_classify_price_volume_interfaces(self):
        """Test price/volume interface classification."""
        from quantaalpha.continuous.impact import ImpactClassifier

        classifier = ImpactClassifier()
        buckets = classifier.classify_interfaces(["daily", "daily_basic", "price", "volume"])

        assert "price_volume" in buckets
        assert len(buckets) == 1

    def test_classify_financial_interfaces(self):
        """Test financial interface classification."""
        from quantaalpha.continuous.impact import ImpactClassifier

        classifier = ImpactClassifier()
        buckets = classifier.classify_interfaces(
            ["financial", "income", "balance", "cashflow", "bank", "insurance"]
        )

        assert "financial" in buckets
        assert len(buckets) == 1

    def test_classify_moneyflow_interfaces(self):
        """Test moneyflow interface classification."""
        from quantaalpha.continuous.impact import ImpactClassifier

        classifier = ImpactClassifier()
        buckets = classifier.classify_interfaces(
            ["moneyflow", "margin", "shuangxiang", "north", "south"]
        )

        assert "moneyflow" in buckets
        assert len(buckets) == 1

    def test_classify_chip_interfaces(self):
        """Test chip interface classification."""
        from quantaalpha.continuous.impact import ImpactClassifier

        classifier = ImpactClassifier()
        buckets = classifier.classify_interfaces(
            ["chip", "float", "holder", "cyq_chip", "position"]
        )

        assert "chip" in buckets
        assert len(buckets) == 1

    def test_classify_unknown_interfaces(self):
        """Test unknown interface classification.

        When ALL interfaces are unknown and there are multiple,
        the classifier returns all buckets as a safety fallback
        to ensure some revalidation happens.
        """
        from quantaalpha.continuous.impact import ImpactClassifier

        classifier = ImpactClassifier()

        # Multiple unknown interfaces -> returns all buckets as safety fallback
        buckets = classifier.classify_interfaces(["unknown_interface", "foobar"])
        assert buckets == ["price_volume", "financial", "moneyflow", "chip", "other"]

        # Single unknown interface -> returns just "other"
        buckets_single = classifier.classify_interfaces(["unknown_interface"])
        assert buckets_single == ["other"]

    def test_classify_multiple_interfaces(self):
        """Test classifying multiple interfaces at once."""
        from quantaalpha.continuous.impact import ImpactClassifier

        classifier = ImpactClassifier()
        buckets = classifier.classify_interfaces(
            ["daily", "moneyflow", "financial", "unknown"]
        )

        assert "price_volume" in buckets
        assert "moneyflow" in buckets
        assert "financial" in buckets
        assert "other" in buckets
        assert len(buckets) == 4

    def test_classify_empty_list(self):
        """Test classifying empty interface list returns all buckets."""
        from quantaalpha.continuous.impact import ImpactClassifier

        classifier = ImpactClassifier()
        buckets = classifier.classify_interfaces([])

        assert buckets == ["price_volume", "financial", "moneyflow", "chip", "other"]

    def test_classify_cyq_prefix_interfaces(self):
        """Test cyq_* interfaces are classified as chip."""
        from quantaalpha.continuous.impact import ImpactClassifier

        classifier = ImpactClassifier()
        buckets = classifier.classify_interfaces(["cyq_chip", "cyq_position", "cyq_float"])

        assert "chip" in buckets
        assert len(buckets) == 1

    def test_classify_deduplication(self):
        """Test that duplicate bucket names are removed."""
        from quantaalpha.continuous.impact import ImpactClassifier

        classifier = ImpactClassifier()
        buckets = classifier.classify_interfaces(["daily", "price", "volume"])

        assert "price_volume" in buckets
        assert buckets.count("price_volume") == 1


class TestFallbackBehavior:
    """Tests for fallback behavior when metadata is sparse or unknown."""

    def test_fallback_on_unknown_interface(self):
        """Test fallback to active/stale/degraded when interface is unknown."""
        from quantaalpha.continuous.impact import ImpactClassifier

        classifier = ImpactClassifier()

        # Create mock library with factors
        mock_library = MagicMock()
        mock_library.data = {
            "factors": {
                "f1": {
                    "factor_id": "f1",
                    "factor_name": "Active Factor",
                    "factor_expression": "$close",
                    "tags": {"data_dependency": ["price_volume"]},
                    "evaluation": {"status": "active"},
                },
                "f2": {
                    "factor_id": "f2",
                    "factor_name": "Stale Factor",
                    "factor_expression": "$volume",
                    "tags": {"data_dependency": ["price_volume"]},
                    "evaluation": {"status": "stale"},
                },
                "f3": {
                    "factor_id": "f3",
                    "factor_name": "Degraded Factor",
                    "factor_expression": "$amount",
                    "tags": {"data_dependency": ["price_volume"]},
                    "evaluation": {"status": "degraded"},
                },
            }
        }

        # Unknown interface should trigger fallback
        candidates = classifier.select_factor_candidates(mock_library, ["other"], limit=10)

        assert len(candidates) == 3
        candidate_ids = [c["factor_id"] for c in candidates]
        assert "f1" in candidate_ids
        assert "f2" in candidate_ids
        assert "f3" in candidate_ids

    def test_fallback_on_empty_groups(self):
        """Test fallback when groups list is empty."""
        from quantaalpha.continuous.impact import ImpactClassifier

        classifier = ImpactClassifier()

        mock_library = MagicMock()
        mock_library.data = {
            "factors": {
                "f1": {
                    "factor_id": "f1",
                    "factor_name": "Active Factor",
                    "factor_expression": "$close",
                    "tags": {"data_dependency": ["price_volume"]},
                    "evaluation": {"status": "active"},
                },
            }
        }

        candidates = classifier.select_factor_candidates(mock_library, [], limit=10)

        assert len(candidates) == 1
        assert candidates[0]["factor_id"] == "f1"

    def test_fallback_on_none_library(self):
        """Test fallback returns empty list when library is None."""
        from quantaalpha.continuous.impact import ImpactClassifier

        classifier = ImpactClassifier()
        candidates = classifier.select_factor_candidates(None, ["price_volume"], limit=10)

        assert candidates == []

    def test_fallback_limit_enforcement(self):
        """Test that fallback limit is respected."""
        from quantaalpha.continuous.impact import ImpactClassifier

        classifier = ImpactClassifier(fallback_limit=2)

        mock_library = MagicMock()
        mock_library.data = {
            "factors": {
                "f1": {
                    "factor_id": "f1",
                    "factor_name": "Active Factor 1",
                    "factor_expression": "$close",
                    "tags": {"data_dependency": ["price_volume"]},
                    "evaluation": {"status": "active"},
                },
                "f2": {
                    "factor_id": "f2",
                    "factor_name": "Stale Factor",
                    "factor_expression": "$volume",
                    "tags": {"data_dependency": ["price_volume"]},
                    "evaluation": {"status": "stale"},
                },
                "f3": {
                    "factor_id": "f3",
                    "factor_name": "Degraded Factor",
                    "factor_expression": "$amount",
                    "tags": {"data_dependency": ["price_volume"]},
                    "evaluation": {"status": "degraded"},
                },
            }
        }

        # Request with unknown group and limit=2
        candidates = classifier.select_factor_candidates(mock_library, ["other"], limit=2)

        # Should respect the request limit (2), not fallback_limit (2)
        assert len(candidates) == 2

    def test_fallback_excludes_pending_and_deprecated(self):
        """Test that pending_validation and deprecated factors are excluded in fallback."""
        from quantaalpha.continuous.impact import ImpactClassifier

        classifier = ImpactClassifier()

        mock_library = MagicMock()
        mock_library.data = {
            "factors": {
                "f1": {
                    "factor_id": "f1",
                    "factor_name": "Active Factor",
                    "factor_expression": "$close",
                    "tags": {"data_dependency": ["price_volume"]},
                    "evaluation": {"status": "active"},
                },
                "f2": {
                    "factor_id": "f2",
                    "factor_name": "Pending Factor",
                    "factor_expression": "$volume",
                    "tags": {"data_dependency": ["price_volume"]},
                    "evaluation": {"status": "pending_validation"},
                },
                "f3": {
                    "factor_id": "f3",
                    "factor_name": "Deprecated Factor",
                    "factor_expression": "$amount",
                    "tags": {"data_dependency": ["price_volume"]},
                    "evaluation": {"status": "deprecated"},
                },
            }
        }

        candidates = classifier.select_factor_candidates(mock_library, ["other"], limit=10)

        assert len(candidates) == 1
        assert candidates[0]["factor_id"] == "f1"


class TestFactorCandidateSelection:
    """Tests for select_factor_candidates method with proper library data."""

    def test_select_by_price_volume_tag(self):
        """Test selecting factors by price_volume tag."""
        from quantaalpha.continuous.impact import ImpactClassifier

        classifier = ImpactClassifier()

        mock_library = MagicMock()
        mock_library.data = {
            "factors": {
                "pv1": {
                    "factor_id": "pv1",
                    "factor_name": "Price Volume Factor",
                    "factor_expression": "$close / $open - 1",
                    "tags": {"data_dependency": ["price_volume"]},
                    "evaluation": {"status": "active"},
                },
                "fin1": {
                    "factor_id": "fin1",
                    "factor_name": "Financial Factor",
                    "factor_expression": "$roe",
                    "tags": {"data_dependency": ["financial"]},
                    "evaluation": {"status": "active"},
                },
            }
        }

        candidates = classifier.select_factor_candidates(
            mock_library, ["price_volume"], limit=10
        )

        assert len(candidates) == 1
        assert candidates[0]["factor_id"] == "pv1"

    def test_select_by_financial_tag(self):
        """Test selecting factors by financial tag."""
        from quantaalpha.continuous.impact import ImpactClassifier

        classifier = ImpactClassifier()

        mock_library = MagicMock()
        mock_library.data = {
            "factors": {
                "pv1": {
                    "factor_id": "pv1",
                    "factor_name": "Price Volume Factor",
                    "factor_expression": "$close",
                    "tags": {"data_dependency": ["price_volume"]},
                    "evaluation": {"status": "active"},
                },
                "fin1": {
                    "factor_id": "fin1",
                    "factor_name": "Financial Factor",
                    "factor_expression": "$roe",
                    "tags": {"data_dependency": ["financial"]},
                    "evaluation": {"status": "active"},
                },
            }
        }

        candidates = classifier.select_factor_candidates(mock_library, ["financial"], limit=10)

        assert len(candidates) == 1
        assert candidates[0]["factor_id"] == "fin1"

    def test_select_by_expression_keywords(self):
        """Test selecting factors by expression keywords even without tags."""
        from quantaalpha.continuous.impact import ImpactClassifier

        classifier = ImpactClassifier()

        mock_library = MagicMock()
        mock_library.data = {
            "factors": {
                "mf1": {
                    "factor_id": "mf1",
                    "factor_name": "Money Flow Factor",
                    "factor_expression": "主力净流入",
                    "tags": {"data_dependency": []},  # No tags
                    "evaluation": {"status": "active"},
                },
                "ch1": {
                    "factor_id": "ch1",
                    "factor_name": "Chip Factor",
                    "factor_expression": "cyq_筹码分布",
                    "tags": {"data_dependency": []},  # No tags
                    "evaluation": {"status": "active"},
                },
            }
        }

        mf_candidates = classifier.select_factor_candidates(
            mock_library, ["moneyflow"], limit=10
        )
        ch_candidates = classifier.select_factor_candidates(mock_library, ["chip"], limit=10)

        assert len(mf_candidates) == 1
        assert mf_candidates[0]["factor_id"] == "mf1"

        assert len(ch_candidates) == 1
        assert ch_candidates[0]["factor_id"] == "ch1"

    def test_select_multiple_groups(self):
        """Test selecting factors from multiple groups."""
        from quantaalpha.continuous.impact import ImpactClassifier

        classifier = ImpactClassifier()

        mock_library = MagicMock()
        mock_library.data = {
            "factors": {
                "pv1": {
                    "factor_id": "pv1",
                    "factor_name": "Price Volume Factor",
                    "factor_expression": "$close",
                    "tags": {"data_dependency": ["price_volume"]},
                    "evaluation": {"status": "active"},
                },
                "fin1": {
                    "factor_id": "fin1",
                    "factor_name": "Financial Factor",
                    "factor_expression": "$roe",
                    "tags": {"data_dependency": ["financial"]},
                    "evaluation": {"status": "active"},
                },
            }
        }

        candidates = classifier.select_factor_candidates(
            mock_library, ["price_volume", "financial"], limit=10
        )

        assert len(candidates) == 2
        candidate_ids = [c["factor_id"] for c in candidates]
        assert "pv1" in candidate_ids
        assert "fin1" in candidate_ids

    def test_select_respects_limit(self):
        """Test that selection respects the limit parameter."""
        from quantaalpha.continuous.impact import ImpactClassifier

        classifier = ImpactClassifier()

        mock_library = MagicMock()
        mock_library.data = {
            "factors": {
                f"f{i}": {
                    "factor_id": f"f{i}",
                    "factor_name": f"Factor {i}",
                    "factor_expression": "$close",
                    "tags": {"data_dependency": ["price_volume"]},
                    "evaluation": {"status": "active"},
                }
                for i in range(10)
            }
        }

        candidates = classifier.select_factor_candidates(
            mock_library, ["price_volume"], limit=5
        )

        assert len(candidates) == 5


class TestNormalizedFactorDict:
    """Tests for the factor dict shape returned by select_factor_candidates."""

    def test_returned_dict_has_required_fields(self):
        """Test that returned factor dicts have all required fields."""
        from quantaalpha.continuous.impact import ImpactClassifier

        classifier = ImpactClassifier()

        mock_library = MagicMock()
        mock_library.data = {
            "factors": {
                "f1": {
                    "factor_id": "f1",
                    "factor_name": "Test Factor",
                    "factor_expression": "$close",
                    "factor_description": "A test factor",
                    "tags": {"data_dependency": ["price_volume"]},
                    "evaluation": {"status": "active"},
                    "metadata": {"created_at": "2024-01-01"},
                    "data_requirements": {"dimensions": ["price_volume"]},
                },
            }
        }

        candidates = classifier.select_factor_candidates(
            mock_library, ["price_volume"], limit=10
        )

        assert len(candidates) == 1
        cand = candidates[0]

        assert "factor_id" in cand
        assert "factor_name" in cand
        assert "factor_expression" in cand
        assert "tags" in cand
        assert "evaluation" in cand

        assert cand["factor_id"] == "f1"
        assert cand["factor_name"] == "Test Factor"
        assert cand["factor_expression"] == "$close"

    def test_missing_fields_default_to_empty(self):
        """Test that missing fields default to empty values in fallback path."""
        from quantaalpha.continuous.impact import ImpactClassifier

        classifier = ImpactClassifier()

        mock_library = MagicMock()
        mock_library.data = {
            "factors": {
                "f1": {
                    "factor_id": "f1",
                    # Missing factor_name, factor_expression, etc.
                    # But with active status so it appears in fallback
                    "tags": {},
                    "evaluation": {"status": "active"},
                },
            }
        }

        # Use "other" group to trigger fallback (since this factor has no tags)
        candidates = classifier.select_factor_candidates(
            mock_library, ["other"], limit=10
        )

        assert len(candidates) == 1
        cand = candidates[0]

        assert cand["factor_id"] == "f1"
        assert cand["factor_name"] == ""
        assert cand["factor_expression"] == ""
        assert cand["tags"] == {}
        # evaluation is preserved from the source entry
        assert cand["evaluation"] == {"status": "active"}


class TestGetValidBuckets:
    """Tests for get_valid_buckets method."""

    def test_returns_all_valid_buckets(self):
        """Test that get_valid_buckets returns all defined buckets."""
        from quantaalpha.continuous.impact import ImpactClassifier

        classifier = ImpactClassifier()
        buckets = classifier.get_valid_buckets()

        assert "price_volume" in buckets
        assert "financial" in buckets
        assert "moneyflow" in buckets
        assert "chip" in buckets
        assert "other" in buckets
        assert len(buckets) == 5


class TestDescribeBucket:
    """Tests for describe_bucket method."""

    def test_describes_known_bucket(self):
        """Test description for known buckets."""
        from quantaalpha.continuous.impact import ImpactClassifier

        classifier = ImpactClassifier()

        desc = classifier.describe_bucket("price_volume")
        assert "price" in desc.lower() or "volume" in desc.lower()

        desc = classifier.describe_bucket("financial")
        assert "financial" in desc.lower() or "roe" in desc.lower() or "roa" in desc.lower()

    def test_describes_unknown_bucket(self):
        """Test description for unknown bucket."""
        from quantaalpha.continuous.impact import ImpactClassifier

        classifier = ImpactClassifier()
        desc = classifier.describe_bucket("unknown_bucket")

        assert "unknown" in desc.lower()


class TestClassifierInitialization:
    """Tests for ImpactClassifier initialization."""

    def test_default_initialization(self):
        """Test default initialization values."""
        from quantaalpha.continuous.impact import ImpactClassifier

        classifier = ImpactClassifier()

        assert classifier.default_limit == 50
        assert classifier.fallback_limit == 100

    def test_custom_initialization(self):
        """Test custom initialization values."""
        from quantaalpha.continuous.impact import ImpactClassifier

        classifier = ImpactClassifier(default_limit=25, fallback_limit=75)

        assert classifier.default_limit == 25
        assert classifier.fallback_limit == 75


class TestClassifierIntegration:
    """Integration tests using a more realistic library scenario."""

    def test_real_library_integration(self, tmp_path):
        """Test classifier with a realistic library setup."""
        from quantaalpha.continuous.impact import ImpactClassifier
        from quantaalpha.factors.library import FactorLibraryManager

        # Create a temporary library file
        lib_path = tmp_path / "test_library.json"
        lib_path.write_text(
            json.dumps(
                {
                    "metadata": {
                        "version": "1.1",
                        "total_factors": 4,
                    },
                    "factors": {
                        "pv_factor": {
                            "factor_id": "pv_factor",
                            "factor_name": "Price Volume Momentum",
                            "factor_expression": "rank($close) / rank($volume)",
                            "tags": {"data_dependency": ["price_volume"]},
                            "evaluation": {"status": "active"},
                        },
                        "fin_factor": {
                            "factor_id": "fin_factor",
                            "factor_name": "ROE Factor",
                            "factor_expression": "$roe",
                            "tags": {"data_dependency": ["financial"]},
                            "evaluation": {"status": "stale"},
                        },
                        "moneyflow_factor": {
                            "factor_id": "moneyflow_factor",
                            "factor_name": "主力资金流",
                            "factor_expression": "主力净流入 / 流通市值",
                            "tags": {"data_dependency": []},
                            "evaluation": {"status": "active"},
                        },
                        "chip_factor": {
                            "factor_id": "chip_factor",
                            "factor_name": "Chip Distribution",
                            "factor_expression": "cyq_筹码集中度",
                            "tags": {"data_dependency": []},
                            "evaluation": {"status": "degraded"},
                        },
                    },
                }
            )
        )

        # Load the real library manager
        manager = FactorLibraryManager(str(lib_path))
        classifier = ImpactClassifier()

        # Test price_volume selection
        pv_candidates = classifier.select_factor_candidates(
            manager, ["price_volume"], limit=10
        )
        assert len(pv_candidates) == 1
        assert pv_candidates[0]["factor_id"] == "pv_factor"

        # Test financial selection
        fin_candidates = classifier.select_factor_candidates(manager, ["financial"], limit=10)
        assert len(fin_candidates) == 1
        assert fin_candidates[0]["factor_id"] == "fin_factor"

        # Test moneyflow selection by expression keyword
        mf_candidates = classifier.select_factor_candidates(
            manager, ["moneyflow"], limit=10
        )
        assert len(mf_candidates) == 1
        assert mf_candidates[0]["factor_id"] == "moneyflow_factor"

        # Test chip selection by expression keyword
        chip_candidates = classifier.select_factor_candidates(manager, ["chip"], limit=10)
        assert len(chip_candidates) == 1
        assert chip_candidates[0]["factor_id"] == "chip_factor"

    def test_interface_classification_real_scenario(self):
        """Test interface classification with real app4 interface names."""
        from quantaalpha.continuous.impact import ImpactClassifier

        classifier = ImpactClassifier()

        # Real app4 interface names
        interfaces = [
            "daily",  # price_volume
            "daily_basic",  # price_volume
            "moneyflow",  # moneyflow
            "financial",  # financial
            "cyq_chip",  # chip
            "bank_balance",  # financial
            "insurance_income",  # financial
            "unknown_table",  # other
        ]

        buckets = classifier.classify_interfaces(interfaces)

        assert "price_volume" in buckets
        assert "moneyflow" in buckets
        assert "financial" in buckets
        assert "chip" in buckets
        assert "other" in buckets

    def test_fallback_with_real_library(self, tmp_path):
        """Test fallback behavior with a real library containing no matching factors."""
        from quantaalpha.continuous.impact import ImpactClassifier
        from quantaalpha.factors.library import FactorLibraryManager

        # Create a library with only price_volume factors
        lib_path = tmp_path / "test_library.json"
        lib_path.write_text(
            json.dumps(
                {
                    "metadata": {"version": "1.1", "total_factors": 2},
                    "factors": {
                        "pv1": {
                            "factor_id": "pv1",
                            "factor_name": "Price Volume Factor",
                            "factor_expression": "$close",
                            "tags": {"data_dependency": ["price_volume"]},
                            "evaluation": {"status": "active"},
                        },
                        "pv2": {
                            "factor_id": "pv2",
                            "factor_name": "Another PV Factor",
                            "factor_expression": "$volume",
                            "tags": {"data_dependency": ["price_volume"]},
                            "evaluation": {"status": "stale"},
                        },
                    },
                }
            )
        )

        manager = FactorLibraryManager(str(lib_path))
        classifier = ImpactClassifier()

        # Request financial factors - none exist, should fallback to all
        candidates = classifier.select_factor_candidates(manager, ["financial"], limit=10)

        # Should return fallback candidates (active and stale price_volume factors)
        assert len(candidates) == 2
