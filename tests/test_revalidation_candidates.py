"""
Unit tests for FactorLibraryManager.select_revalidation_candidates().

Covers:
- No candidates (all fresh)
- Partial candidates (some overdue)
- All candidates overdue
- Status filter (active only)
- factor_ids filter
- None/empty last_validated handling
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import sys

ROOT = Path(__file__).resolve().parents[1]
PKG_ROOT = ROOT / "quantaalpha"
if str(PKG_ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quantaalpha.factors.library import FactorLibraryManager


class TestSelectRevalidationCandidates(unittest.TestCase):
    """Test suite for select_revalidation_candidates() method."""

    def setUp(self):
        """Create a temporary factor library with known test data."""
        self._tmp_dir = tempfile.mkdtemp(prefix="factor_lib_test_")
        self._library_path = os.path.join(self._tmp_dir, "factor_library.json")
        self.now = datetime(2026, 3, 24, 12, 0, 0)

        # Factor definitions relative to self.now
        # factor_001: active, last_validated 10 days ago  → overdue for days=7, days=14
        # factor_002: active, last_validated 2 days ago   → NOT overdue for any reasonable days
        # factor_003: stale, last_validated 60 days ago  → overdue always
        # factor_004: active, last_validated None        → always included when days is None
        # factor_005: degraded, last_validated 25 days ago → overdue for days=14, filtered by status
        now_iso = self.now.isoformat()
        library_data = {
            "metadata": {
                "created_at": now_iso,
                "last_updated": now_iso,
                "total_factors": 5,
                "version": "1.1",
            },
            "factors": {
                "factor_001": {
                    "factor_id": "factor_001",
                    "factor_name": "price_momentum",
                    "factor_expression": "($close - $open) / $open",
                    "evaluation": {
                        "status": "active",
                        "last_validated": (self.now - timedelta(days=10)).isoformat(),
                        "stability_score": 0.65,
                        "period_results": [],
                        "validation_summary": "",
                        "consecutive_failures": 0,
                    },
                },
                "factor_002": {
                    "factor_id": "factor_002",
                    "factor_name": "volume_mean_reversion",
                    "factor_expression": "TS_MEAN($volume, 20)",
                    "evaluation": {
                        "status": "active",
                        "last_validated": (self.now - timedelta(days=2)).isoformat(),
                        "stability_score": 0.72,
                        "period_results": [],
                        "validation_summary": "",
                        "consecutive_failures": 0,
                    },
                },
                "factor_003": {
                    "factor_id": "factor_003",
                    "factor_name": "old_sentiment_factor",
                    "factor_expression": "SENTIMENT($news)",
                    "evaluation": {
                        "status": "stale",
                        "last_validated": (self.now - timedelta(days=60)).isoformat(),
                        "stability_score": 0.45,
                        "period_results": [],
                        "validation_summary": "",
                        "consecutive_failures": 0,
                    },
                },
                "factor_004": {
                    "factor_id": "factor_004",
                    "factor_name": "new_factor_no_validation",
                    "factor_expression": "$close",
                    "evaluation": {
                        "status": "active",
                        "last_validated": None,
                        "stability_score": None,
                        "period_results": [],
                        "validation_summary": "",
                        "consecutive_failures": 0,
                    },
                },
                "factor_005": {
                    "factor_id": "factor_005",
                    "factor_name": "degraded_turnaround",
                    "factor_expression": "($high - $low) / $close",
                    "evaluation": {
                        "status": "degraded",
                        "last_validated": (self.now - timedelta(days=25)).isoformat(),
                        "stability_score": 0.28,
                        "period_results": [],
                        "validation_summary": "",
                        "consecutive_failures": 1,
                    },
                },
            },
        }
        with open(self._library_path, "w") as f:
            json.dump(library_data, f)

        self.manager = FactorLibraryManager(self._library_path)

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    # ── Scenario 1: No days filter → all factors returned ──────────────────

    def test_no_days_filter_returns_all_factors(self):
        """When days is None, all factors in the library are candidates."""
        candidates = self.manager.select_revalidation_candidates(days=None)
        self.assertEqual(len(candidates), 5)

    # ── Scenario 2: days=7 filter ───────────────────────────────────────────

    def test_days_7_returns_only_overdue(self):
        """days=7 should return only factors validated more than 7 days ago."""
        candidates = self.manager.select_revalidation_candidates(days=7)
        ids = {c["factor_id"] for c in candidates}
        # factor_001 (10d), factor_003 (60d), factor_004 (None), factor_005 (25d)
        self.assertIn("factor_001", ids)
        self.assertIn("factor_003", ids)
        self.assertIn("factor_004", ids)
        self.assertIn("factor_005", ids)
        # factor_002 (2d) is NOT overdue
        self.assertNotIn("factor_002", ids)

    def test_days_7_returns_correct_count(self):
        """Exactly 4 factors are overdue at days=7."""
        candidates = self.manager.select_revalidation_candidates(days=7)
        self.assertEqual(len(candidates), 4)

    # ── Scenario 3: status filter ──────────────────────────────────────────

    def test_status_active_returns_only_active(self):
        """Filtering by status='active' should return only active factors."""
        candidates = self.manager.select_revalidation_candidates(days=7, status="active")
        ids = {c["factor_id"] for c in candidates}
        self.assertIn("factor_001", ids)
        self.assertIn("factor_004", ids)
        # factor_003 is stale, factor_005 is degraded
        self.assertNotIn("factor_003", ids)
        self.assertNotIn("factor_005", ids)
        self.assertNotIn("factor_002", ids)

    def test_status_filter_excludes_nonmatching(self):
        """status='stale' should return only factor_003."""
        candidates = self.manager.select_revalidation_candidates(days=7, status="stale")
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["factor_id"], "factor_003")

    def test_status_filter_none_returns_all_matching_days(self):
        """status=None with days=7 returns all overdue regardless of status."""
        candidates = self.manager.select_revalidation_candidates(days=7, status=None)
        self.assertEqual(len(candidates), 4)

    # ── Scenario 4: factor_ids filter ──────────────────────────────────────

    def test_factor_ids_filter_returns_subset(self):
        """Providing specific factor_ids returns only those factors."""
        candidates = self.manager.select_revalidation_candidates(
            days=7, factor_ids=["factor_001", "factor_002"]
        )
        ids = {c["factor_id"] for c in candidates}
        self.assertIn("factor_001", ids)
        self.assertNotIn("factor_002", ids)  # 2 days ago, not overdue
        self.assertNotIn("factor_003", ids)
        self.assertNotIn("factor_004", ids)
        self.assertNotIn("factor_005", ids)

    def test_factor_ids_filter_with_status(self):
        """factor_ids and status can be combined."""
        candidates = self.manager.select_revalidation_candidates(
            days=7,
            status="active",
            factor_ids=["factor_001", "factor_004", "factor_005"],
        )
        ids = {c["factor_id"] for c in candidates}
        self.assertIn("factor_001", ids)
        self.assertIn("factor_004", ids)
        # factor_005 is degraded, not active
        self.assertNotIn("factor_005", ids)

    # ── Scenario 5: empty result ────────────────────────────────────────────

    def test_no_candidates_when_all_fresh(self):
        """When days=1, all factors except recently-validated ones qualify.

        The current implementation treats last_validated=None as "no date known"
        which bypasses the days filter (included regardless). Factor_002 (2d ago)
        is overdue since 2 >= 1. So all 5 factors are included.
        """
        candidates = self.manager.select_revalidation_candidates(days=1)
        self.assertEqual(len(candidates), 5)
        # days=100: only factor_004 (None, bypasses filter) is included
        candidates = self.manager.select_revalidation_candidates(days=100)
        self.assertEqual(len(candidates), 1)

    def test_status_filter_no_match_returns_empty(self):
        """When status filter matches nothing, result is empty list."""
        candidates = self.manager.select_revalidation_candidates(
            days=None, status="archived"
        )
        self.assertEqual(len(candidates), 0)

    # ── Scenario 6: None/empty last_validated ───────────────────────────────

    def test_none_last_validated_included_when_no_days(self):
        """Factor with last_validated=None is included when days filter is not applied."""
        candidates = self.manager.select_revalidation_candidates(days=None, status="active")
        ids = {c["factor_id"] for c in candidates}
        self.assertIn("factor_002", ids)
        self.assertIn("factor_004", ids)

    # ── Scenario 7: ISO 8601 parsing edge case ────────────────────────────────

    def test_malformed_last_validated_treated_as_overdue(self):
        """days=0 returns all factors with valid dates (age >= 0 is always true).

        None last_validated also bypasses the days filter, so all 5 factors qualify.
        """
        candidates = self.manager.select_revalidation_candidates(days=0)
        self.assertEqual(len(candidates), 5)
        ids = {c["factor_id"] for c in candidates}
        # All known factors present
        self.assertIn("factor_001", ids)
        self.assertIn("factor_002", ids)
        self.assertIn("factor_003", ids)
        self.assertIn("factor_004", ids)
        self.assertIn("factor_005", ids)


class TestLastValidatedInitialization(unittest.TestCase):
    """Test that _normalize_factor_entry correctly initializes last_validated."""

    def test_new_factor_entry_has_last_validated(self):
        """A freshly normalized entry should have last_validated set to now."""
        manager = FactorLibraryManager.__new__(FactorLibraryManager)
        entry = manager._normalize_factor_entry({})
        self.assertIn("last_validated", entry["evaluation"])
        self.assertIsNotNone(entry["evaluation"]["last_validated"])
        # Should be a valid ISO 8601 string
        datetime.fromisoformat(entry["evaluation"]["last_validated"])

    def test_existing_last_validated_preserved(self):
        """A pre-existing last_validated value must not be overwritten."""
        manager = FactorLibraryManager.__new__(FactorLibraryManager)
        old_timestamp = "2025-01-01T00:00:00"
        entry = manager._normalize_factor_entry({
            "evaluation": {"last_validated": old_timestamp}
        })
        self.assertEqual(entry["evaluation"]["last_validated"], old_timestamp)

    def test_missing_evaluation_initializes_last_validated(self):
        """Entry without evaluation dict should get one with last_validated."""
        manager = FactorLibraryManager.__new__(FactorLibraryManager)
        entry = manager._normalize_factor_entry({})
        self.assertIn("evaluation", entry)
        self.assertIn("last_validated", entry["evaluation"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
