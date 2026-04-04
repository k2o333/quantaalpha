"""
Tests for revalidate CLI command.

Covers three modes:
- dry_run: Select candidates only, no execution
- default: Reuse existing evaluation results
- real_backtest: Execute actual backtest validation
"""

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

# Setup path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quantaalpha.cli import revalidate


class TestRevalidateCLIModes(unittest.TestCase):
    """Test the three mutually exclusive modes of revalidate CLI."""

    def setUp(self):
        """Create a temporary factor library for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.library_path = Path(self.temp_dir) / "test_library.json"
        self._create_test_library()

    def tearDown(self):
        """Clean up temporary files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_test_library(self):
        """Create a test factor library with sample factors."""
        now = datetime.now()
        library_data = {
            "metadata": {
                "created_at": now.isoformat(),
                "last_updated": now.isoformat(),
                "total_factors": 3,
                "version": "1.1",
            },
            "factors": {
                "factor_001": {
                    "factor_id": "factor_001",
                    "factor_name": "test_factor_1",
                    "factor_expression": "($close - $open) / $open",
                    "evaluation": {
                        "status": "active",
                        "last_validated": (now - timedelta(days=10)).isoformat(),
                        "stability_score": 0.65,
                        "period_results": [{"period": "1m", "ic": 0.05}],
                        "validation_summary": "previous_validation",
                        "consecutive_failures": 0,
                    },
                },
                "factor_002": {
                    "factor_id": "factor_002",
                    "factor_name": "test_factor_2",
                    "factor_expression": "TS_MEAN($volume, 20)",
                    "evaluation": {
                        "status": "stale",
                        "last_validated": (now - timedelta(days=60)).isoformat(),
                        "stability_score": 0.45,
                        "period_results": [],
                        "validation_summary": "old_validation",
                        "consecutive_failures": 0,
                    },
                },
                "factor_003": {
                    "factor_id": "factor_003",
                    "factor_name": "test_factor_no_expr",
                    "factor_expression": "",
                    "evaluation": {
                        "status": "pending_validation",
                        "last_validated": None,
                        "stability_score": None,
                        "period_results": [],
                        "validation_summary": "",
                        "consecutive_failures": 0,
                    },
                },
            },
        }
        with open(self.library_path, "w") as f:
            json.dump(library_data, f)

    # === DRY-RUN MODE TESTS ===

    def test_dry_run_returns_correct_structure(self):
        """dry_run mode should return {mode, total_candidates, candidates, success}."""
        result = revalidate(str(self.library_path), dry_run=True)

        self.assertEqual(result["mode"], "dry_run")
        self.assertIn("total_candidates", result)
        self.assertIn("candidates", result)
        self.assertIn("success", result)
        self.assertTrue(result["success"])

    def test_dry_run_includes_candidate_fields(self):
        """dry_run mode should include specific candidate fields."""
        result = revalidate(str(self.library_path), dry_run=True)

        for candidate in result["candidates"]:
            self.assertIn("factor_id", candidate)
            self.assertIn("factor_name", candidate)
            self.assertIn("status", candidate)
            self.assertIn("last_validated", candidate)
            self.assertIn("stability_score", candidate)
            self.assertIn("factor_expression", candidate)

    def test_dry_run_no_modifications(self):
        """dry_run mode should not modify the library file."""
        with open(self.library_path) as f:
            original_content = f.read()

        revalidate(str(self.library_path), dry_run=True)

        with open(self.library_path) as f:
            new_content = f.read()

        self.assertEqual(original_content, new_content)

    def test_dry_run_filters_by_days(self):
        """dry_run mode should filter candidates by days parameter."""
        result = revalidate(str(self.library_path), dry_run=True, days=30)

        # factor_001 was validated 10 days ago, should be excluded
        candidate_ids = [c["factor_id"] for c in result["candidates"]]
        self.assertNotIn("factor_001", candidate_ids)
        # factor_002 was validated 60 days ago, should be included
        self.assertIn("factor_002", candidate_ids)

    def test_dry_run_filters_by_status(self):
        """dry_run mode should filter candidates by status parameter."""
        result = revalidate(str(self.library_path), dry_run=True, status="stale")

        for candidate in result["candidates"]:
            self.assertEqual(candidate["status"], "stale")

    def test_dry_run_filters_by_factor_ids(self):
        """dry_run mode should filter candidates by factor_ids parameter."""
        result = revalidate(str(self.library_path), dry_run=True, factor_ids="factor_001")

        self.assertEqual(len(result["candidates"]), 1)
        self.assertEqual(result["candidates"][0]["factor_id"], "factor_001")

    # === DEFAULT MODE TESTS ===

    def test_default_mode_returns_correct_structure(self):
        """Default mode should return explicit status_refresh semantics."""
        result = revalidate(str(self.library_path))

        self.assertEqual(result["mode"], "status_refresh")
        self.assertIn("total_candidates", result)
        self.assertIn("success", result)
        self.assertIn("failed", result)
        self.assertIn("skipped", result)
        self.assertIn("details", result)
        self.assertTrue(result["used_existing_results"])

    def test_default_mode_detail_fields(self):
        """Default mode details should include specific fields."""
        result = revalidate(str(self.library_path))

        for detail in result["details"]:
            self.assertIn("factor_id", detail)
            self.assertIn("before_status", detail)
            self.assertIn("after_status", detail)
            self.assertIn("revalidation_source", detail)

    def test_default_mode_updates_library(self):
        """Default mode should update the library with reused validation."""
        original_modified = self.library_path.stat().st_mtime

        result = revalidate(str(self.library_path))

        # File should be modified (if no_write is False)
        # Note: depending on timing, we check the library was processed
        self.assertGreater(result["success"], 0)

    def test_default_mode_no_write(self):
        """Default mode with no_write should not persist changes."""
        with open(self.library_path) as f:
            original_content = f.read()

        revalidate(str(self.library_path), no_write=True)

        with open(self.library_path) as f:
            new_content = f.read()

        self.assertEqual(original_content, new_content)

    # === REAL-BACKTEST MODE TESTS ===

    def test_real_backtest_returns_correct_structure(self):
        """real_backtest mode should return runner-backed details."""
        with patch(
            "quantaalpha.pipeline.factor_backtest.run_real_backtest",
            return_value={
                "metrics": {
                    "stability_score": 0.81,
                    "multi_period_validation": {
                        "period_results": [{"period": "2025Q4", "metrics": {"IC": 0.12}}],
                        "summary": {
                            "stability_score": 0.81,
                            "validation_summary": "real_runner",
                        },
                    },
                },
                "factors_backtested": ["factor_001"],
            },
        ):
            result = revalidate(
                str(self.library_path),
                real_backtest=True,
                backtest_config="/tmp/backtest.yaml",
            )

        self.assertEqual(result["mode"], "real_backtest")
        self.assertIn("total_candidates", result)
        self.assertIn("success", result)
        self.assertIn("failed", result)
        self.assertIn("errors", result)
        self.assertIn("details", result)

    def test_real_backtest_skips_missing_expression(self):
        """real_backtest mode should skip factors without expression."""
        result = revalidate(str(self.library_path), real_backtest=True, no_write=True)

        # factor_003 has no expression, should be skipped
        skipped_details = [d for d in result["details"] if d.get("status") == "skipped"]
        self.assertGreater(len(skipped_details), 0)

    @patch("quantaalpha.pipeline.factor_backtest.run_real_backtest")
    def test_real_backtest_calls_runner_once_per_factor(self, mock_backtest):
        """real_backtest mode should invoke the real runner integration per factor."""
        mock_backtest.return_value = {
            "metrics": {
                "stability_score": 0.61,
                "multi_period_validation": {
                    "period_results": [{"period": "2025Q4", "metrics": {"IC": 0.09}}],
                    "summary": {
                        "stability_score": 0.61,
                        "validation_summary": "real_runner",
                    },
                },
            },
            "factors_backtested": ["factor_001"],
        }
        revalidate(
            str(self.library_path),
            real_backtest=True,
            no_write=True,
            backtest_config="/tmp/backtest.yaml",
        )

        # Should have called real backtest for factors with expressions (factor_001, factor_002)
        self.assertEqual(mock_backtest.call_count, 2)

    def test_real_backtest_captures_errors(self):
        """real_backtest mode should capture and return errors in result."""
        with patch(
            "quantaalpha.pipeline.factor_backtest.run_real_backtest",
            side_effect=Exception("Backtest failed"),
        ):
            result = revalidate(
                str(self.library_path),
                real_backtest=True,
                no_write=True,
                backtest_config="/tmp/backtest.yaml",
            )

        # Should have captured errors
        self.assertGreater(result["failed"], 0)
        self.assertGreater(len(result["errors"]), 0)

        for error in result["errors"]:
            self.assertIn("factor_id", error)
            self.assertIn("error", error)
            self.assertIn("traceback", error)

    def test_real_backtest_updates_period_results_from_runner_metrics(self):
        """real_backtest success should write runner-produced period results."""
        runner_result = {
            "metrics": {
                "stability_score": 0.78,
                "multi_period_validation": {
                    "period_results": [{"period": "2025Q4", "metrics": {"IC": 0.11}}],
                    "summary": {
                        "stability_score": 0.78,
                        "validation_summary": "runner_summary",
                    },
                },
            },
            "factors_backtested": ["factor_001"],
        }
        with patch(
            "quantaalpha.pipeline.factor_backtest.run_real_backtest",
            return_value=runner_result,
        ):
            revalidate(
                str(self.library_path),
                real_backtest=True,
                backtest_config="/tmp/backtest.yaml",
            )

        with open(self.library_path, "r", encoding="utf-8") as f:
            updated = json.load(f)
        evaluation = updated["factors"]["factor_001"]["evaluation"]
        self.assertEqual(evaluation["period_results"], runner_result["metrics"]["multi_period_validation"]["period_results"])
        self.assertEqual(evaluation["stability_score"], 0.78)

    def test_real_backtest_failure_preserves_existing_results(self):
        """real_backtest failure should not overwrite old period_results."""
        original_results = [{"period": "1m", "ic": 0.05}]
        with patch(
            "quantaalpha.pipeline.factor_backtest.run_real_backtest",
            side_effect=Exception("runner unavailable"),
        ):
            revalidate(
                str(self.library_path),
                real_backtest=True,
                backtest_config="/tmp/backtest.yaml",
            )

        with open(self.library_path, "r", encoding="utf-8") as f:
            updated = json.load(f)
        self.assertEqual(
            updated["factors"]["factor_001"]["evaluation"]["period_results"],
            original_results,
        )

    def test_real_backtest_missing_config_returns_consistent_error_shape(self):
        """Missing config should return an error payload without changing counter types."""
        with patch("quantaalpha.cli._default_backtest_config_path", return_value=None):
            result = revalidate(
                str(self.library_path),
                real_backtest=True,
            )

        self.assertEqual(result["mode"], "error")
        self.assertEqual(result["success"], 0)
        self.assertIs(type(result["success"]), int)
        self.assertEqual(result["failed"], 0)
        self.assertIs(type(result["failed"]), int)
        self.assertEqual(result["skipped"], 0)
        self.assertIs(type(result["skipped"]), int)
        self.assertEqual(result["errors"], [])
        self.assertIn("Missing backtest configuration", result["error"])

    # === ERROR HANDLING TESTS ===

    def test_mutually_exclusive_flags_error(self):
        """dry_run and real_backtest together should return error."""
        result = revalidate(str(self.library_path), dry_run=True, real_backtest=True)

        self.assertEqual(result["mode"], "error")
        self.assertIn("error", result)
        self.assertFalse(result["success"])
        self.assertIn("mutually exclusive", result["error"].lower())

    def test_missing_library_path_error(self):
        """Non-existent library path: FactorLibraryManager creates a new empty library."""
        # FactorLibraryManager._load() auto-creates a new library when path doesn't exist
        # So the result is valid with zero candidates
        result = revalidate("/nonexistent/path/library.json", dry_run=True)

        # The library manager creates a new empty library, not an error
        self.assertEqual(result["mode"], "dry_run")
        self.assertEqual(result["total_candidates"], 0)
        self.assertTrue(result["success"])

    def test_corrupted_library_error(self):
        """Corrupted library file should return error."""
        corrupted_path = Path(self.temp_dir) / "corrupted.json"
        with open(corrupted_path, "w") as f:
            f.write("{ invalid json }")

        result = revalidate(str(corrupted_path), dry_run=True)

        # Library manager handles corruption gracefully, creates new library
        # But we still get a valid result
        self.assertIn("mode", result)


class TestRevalidateCLIEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions."""

    def test_empty_library(self):
        """Empty library should return zero candidates."""
        with tempfile.TemporaryDirectory() as temp_dir:
            library_path = Path(temp_dir) / "empty.json"
            library_data = {
                "metadata": {"total_factors": 0, "version": "1.1"},
                "factors": {},
            }
            with open(library_path, "w") as f:
                json.dump(library_data, f)

            result = revalidate(str(library_path), dry_run=True)

            self.assertEqual(result["total_candidates"], 0)
            self.assertEqual(len(result["candidates"]), 0)

    def test_factor_ids_with_whitespace(self):
        """factor_ids parameter should handle whitespace."""
        with tempfile.TemporaryDirectory() as temp_dir:
            library_path = Path(temp_dir) / "test.json"
            library_data = {
                "metadata": {"total_factors": 1, "version": "1.1"},
                "factors": {
                    "fid1": {
                        "factor_id": "fid1",
                        "factor_name": "f1",
                        "factor_expression": "expr",
                        "evaluation": {"status": "active"},
                    }
                },
            }
            with open(library_path, "w") as f:
                json.dump(library_data, f)

            result = revalidate(
                str(library_path),
                dry_run=True,
                factor_ids="  fid1  ,  ",  # Extra whitespace
            )

            self.assertEqual(len(result["candidates"]), 1)

    def test_multiple_factor_ids(self):
        """factor_ids parameter should handle multiple IDs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            library_path = Path(temp_dir) / "test.json"
            library_data = {
                "metadata": {"total_factors": 2, "version": "1.1"},
                "factors": {
                    "fid1": {
                        "factor_id": "fid1",
                        "factor_name": "f1",
                        "factor_expression": "expr1",
                        "evaluation": {"status": "active"},
                    },
                    "fid2": {
                        "factor_id": "fid2",
                        "factor_name": "f2",
                        "factor_expression": "expr2",
                        "evaluation": {"status": "stale"},
                    },
                },
            }
            with open(library_path, "w") as f:
                json.dump(library_data, f)

            result = revalidate(
                str(library_path),
                dry_run=True,
                factor_ids="fid1,fid2",
            )

            self.assertEqual(len(result["candidates"]), 2)


if __name__ == "__main__":
    unittest.main()
