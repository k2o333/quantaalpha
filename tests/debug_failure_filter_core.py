"""
Tests for debug failure filter functionality.

This module tests:
1. Mixed success/failure scenarios - only failed factors proceed to next round
2. All success scenario - debug early exit
3. All failure scenario - respect max_rounds limit
4. Failure reason recording and aggregation
5. Successful factors are not re-processed by coder/backtest
"""

import ast
import hashlib
import sys
import types
import unittest
from unittest.mock import MagicMock, patch
import hashlib
from pathlib import Path

from quantaalpha.factors.failure_tracker import (
    FactorFailureTracker,
    FactorStatus,
    FailureReason,
    DebugRoundSummary,
)


class TestFactorStatus(unittest.TestCase):
    """Test cases for FactorStatus class."""

    def test_successful_factor_detection(self):
        """Test that a factor with all passes is detected as successful."""
        status = FactorStatus(
            factor_id="test_factor_1",
            factor_name="momentum_alpha",
            factor_expression="ts_rank($close, 5)",
        )

        # Initially not successful
        self.assertFalse(status.is_successful)

        # Mark all stages as passed
        status.passed_coder = True
        status.passed_quality_gate = True
        status.passed_backtest = True

        self.assertTrue(status.is_successful)
        self.assertFalse(status.is_failed)

    def test_failed_factor_detection(self):
        """Test that a factor with failures is detected as failed."""
        status = FactorStatus(
            factor_id="test_factor_2",
            factor_name="bad_factor",
            factor_expression="invalid_expr",
        )

        # Add a failure reason
        status.add_failure(FailureReason.EXPRESSION_PARSE_FAILED, "Parse error")

        self.assertTrue(status.is_failed)
        self.assertFalse(status.is_successful)

    def test_multiple_failure_reasons(self):
        """Test that multiple failure reasons can be recorded."""
        status = FactorStatus(
            factor_id="test_factor_3",
            factor_name="multi_fail",
            factor_expression="complex_expr",
        )

        status.add_failure(FailureReason.CODER_NO_WORKSPACE, "No workspace")
        status.add_failure(FailureReason.BACKTEST_EMPTY_RESULT, "Empty result")

        self.assertEqual(len(status.failure_reasons), 2)
        self.assertIn(FailureReason.CODER_NO_WORKSPACE, status.failure_reasons)
        self.assertIn(FailureReason.BACKTEST_EMPTY_RESULT, status.failure_reasons)

    def test_failure_details_recording(self):
        """Test that failure details are properly recorded."""
        status = FactorStatus(
            factor_id="test_factor_4",
            factor_name="detail_test",
            factor_expression="expr",
        )

        status.add_failure(FailureReason.QUALITY_GATE_FAILED, "Complexity check failed")

        self.assertIn("quality_gate_failed", status.failure_details)
        self.assertIn("Complexity check failed", status.failure_details["quality_gate_failed"])

    def test_to_dict_serialization(self):
        """Test that status can be serialized to dict."""
        status = FactorStatus(
            factor_id="test_factor_5",
            factor_name="serialize_test",
            factor_expression="ts_mean($close, 10)",
        )
        status.passed_coder = True
        status.add_failure(FailureReason.BACKTEST_EXCEPTION, "Timeout")

        result = status.to_dict()

        self.assertEqual(result["factor_id"], "test_factor_5")
        self.assertEqual(result["factor_name"], "serialize_test")
        self.assertTrue(result["passed_coder"])
        self.assertFalse(result["is_successful"])
        self.assertEqual(result["failure_reasons"], ["backtest_exception"])


class TestDebugRoundSummary(unittest.TestCase):
    """Test cases for DebugRoundSummary class."""

    def test_all_succeeded_detection(self):
        """Test detection of all succeeded round."""
        summary = DebugRoundSummary(
            round_idx=0,
            total_factors=3,
            successful_count=3,
            failed_count=0,
            successful_factor_ids=["f1", "f2", "f3"],
        )

        self.assertTrue(summary.all_succeeded)
        self.assertFalse(summary.all_failed)

    def test_all_failed_detection(self):
        """Test detection of all failed round."""
        summary = DebugRoundSummary(
            round_idx=0,
            total_factors=3,
            successful_count=0,
            failed_count=3,
            failed_factor_ids=["f1", "f2", "f3"],
        )

        self.assertFalse(summary.all_succeeded)
        self.assertTrue(summary.all_failed)

    def test_partial_success_detection(self):
        """Test detection of partial success round."""
        summary = DebugRoundSummary(
            round_idx=0,
            total_factors=3,
            successful_count=2,
            failed_count=1,
            successful_factor_ids=["f1", "f2"],
            failed_factor_ids=["f3"],
            factors_to_retry=["f3"],
        )

        self.assertFalse(summary.all_succeeded)
        self.assertFalse(summary.all_failed)

    def test_failure_reason_counts(self):
        """Test aggregation of failure reason counts."""
        summary = DebugRoundSummary(
            round_idx=0,
            total_factors=3,
            successful_count=0,
            failed_count=3,
            failed_factor_ids=["f1", "f2", "f3"],
            failed_reasons={
                "f1": ["coder_no_workspace"],
                "f2": ["backtest_empty_result", "quality_gate_failed"],
                "f3": ["backtest_empty_result"],
            },
        )

        counts = summary.get_failure_reason_counts()

        self.assertEqual(counts.get("backtest_empty_result"), 2)
        self.assertEqual(counts.get("coder_no_workspace"), 1)
        self.assertEqual(counts.get("quality_gate_failed"), 1)


class TestFactorFailureTracker(unittest.TestCase):
    """Test cases for FactorFailureTracker class."""

    def setUp(self):
        """Set up test fixtures."""
        self.tracker = FactorFailureTracker(max_debug_rounds=5)

    def test_register_factor(self):
        """Test factor registration."""
        status = self.tracker.register_factor(
            factor_id="f1",
            factor_name="alpha_momentum",
            factor_expression="ts_rank($close, 5)",
        )

        self.assertEqual(status.factor_id, "f1")
        self.assertEqual(status.factor_name, "alpha_momentum")
        self.assertIn("f1", self.tracker.factor_statuses)

    def test_successful_factor_ids(self):
        """Test getting successful factor IDs."""
        self.tracker.register_factor("f1", "success_factor", "expr1")
        self.tracker.register_factor("f2", "failed_factor", "expr2")

        # Mark f1 as successful
        self.tracker.update_factor_status(
            "f1",
            passed_coder=True,
            passed_quality_gate=True,
            passed_backtest=True,
        )

        # Mark f2 as failed
        self.tracker.update_factor_status(
            "f2",
            passed_coder=False,
            failure_reason=FailureReason.CODER_NO_WORKSPACE,
        )

        successful = self.tracker.successful_factor_ids
        failed = self.tracker.failed_factor_ids

        self.assertIn("f1", successful)
        self.assertIn("f2", failed)

    def test_mixed_success_failure_only_failed_retry(self):
        """Test 1: Mixed success/failure - only failed factors proceed to next round."""
        # Register 5 factors
        for i in range(5):
            self.tracker.register_factor(f"f{i}", f"factor_{i}", f"expr_{i}")

        # Mark factors 0, 1, 2 as successful
        for i in [0, 1, 2]:
            self.tracker.update_factor_status(
                f"f{i}",
                passed_coder=True,
                passed_quality_gate=True,
                passed_backtest=True,
            )

        # Mark factors 3, 4 as failed
        self.tracker.update_factor_status(
            "f3",
            passed_coder=False,
            failure_reason=FailureReason.CODER_NO_WORKSPACE,
        )
        self.tracker.update_factor_status(
            "f4",
            passed_coder=True,
            passed_quality_gate=False,
            failure_reason=FailureReason.QUALITY_GATE_FAILED,
        )

        # Get factors for retry
        to_retry = self.tracker.get_factors_for_retry()

        # Only failed factors should be in retry list
        self.assertEqual(set(to_retry), {"f3", "f4"})
        self.assertNotIn("f0", to_retry)
        self.assertNotIn("f1", to_retry)
        self.assertNotIn("f2", to_retry)

    def test_all_success_early_exit(self):
        """Test 2: All success - debug should exit early."""
        # Register 3 factors
        for i in range(3):
            self.tracker.register_factor(f"f{i}", f"factor_{i}", f"expr_{i}")

        # Mark all as successful
        for i in range(3):
            self.tracker.update_factor_status(
                f"f{i}",
                passed_coder=True,
                passed_quality_gate=True,
                passed_backtest=True,
            )

        # Should not continue debug
        self.assertFalse(self.tracker.should_continue_debug())

        # No factors to retry
        self.assertEqual(len(self.tracker.get_factors_for_retry()), 0)

    def test_all_failure_respect_max_rounds(self):
        """Test 3: All failure - respect max_rounds limit."""
        tracker = FactorFailureTracker(max_debug_rounds=3)

        # Register 3 factors
        for i in range(3):
            tracker.register_factor(f"f{i}", f"factor_{i}", f"expr_{i}")

        # Mark all as failed
        for i in range(3):
            tracker.update_factor_status(
                f"f{i}",
                failure_reason=FailureReason.BACKTEST_EXCEPTION,
                failure_detail="Test failure",
            )

        # Round 0
        tracker.start_round()
        tracker.finalize_round()
        # After finalize, current_round_idx = 1

        # Should continue (round 0 completed < max_rounds=3)
        self.assertTrue(tracker.should_continue_debug())

        # Round 1
        tracker.start_round()
        tracker.finalize_round()
        # After finalize, current_round_idx = 2

        # Should continue (round 1 completed < max_rounds=3)
        self.assertTrue(tracker.should_continue_debug())

        # Round 2
        tracker.start_round()
        tracker.finalize_round()
        # After finalize, current_round_idx = 3

        # Should NOT continue (round 3 >= max_rounds=3)
        self.assertFalse(tracker.should_continue_debug())

    def test_failure_reason_recording_and_aggregation(self):
        """Test 4: Failure reasons can be recorded and aggregated."""
        # Register factors with different failure types
        self.tracker.register_factor("f1", "factor_1", "expr_1")
        self.tracker.register_factor("f2", "factor_2", "expr_2")
        self.tracker.register_factor("f3", "factor_3", "expr_3")

        # Record different failure reasons
        self.tracker.update_factor_status("f1", failure_reason=FailureReason.EXPRESSION_PARSE_FAILED)
        self.tracker.update_factor_status("f2", failure_reason=FailureReason.CODER_NO_WORKSPACE)
        self.tracker.update_factor_status("f3", failure_reason=FailureReason.EXPRESSION_PARSE_FAILED)

        # Start and finalize round
        self.tracker.start_round()
        summary = self.tracker.finalize_round()

        # Check failure reason counts
        reason_counts = summary.get_failure_reason_counts()

        self.assertEqual(reason_counts.get("expression_parse_failed"), 2)
        self.assertEqual(reason_counts.get("coder_no_workspace"), 1)

    def test_successful_factors_not_reprocessed(self):
        """Test 5: Successful factors do not enter coder/backtest again."""
        # Register 5 factors
        for i in range(5):
            self.tracker.register_factor(f"f{i}", f"factor_{i}", f"expr_{i}")

        # Mark f0, f1 as successful in first round
        for i in [0, 1]:
            self.tracker.update_factor_status(
                f"f{i}",
                passed_coder=True,
                passed_quality_gate=True,
                passed_backtest=True,
            )

        # Mark f2, f3, f4 as failed
        for i in [2, 3, 4]:
            self.tracker.update_factor_status(
                f"f{i}",
                failure_reason=FailureReason.BACKTEST_EMPTY_RESULT,
            )

        # Finalize first round
        self.tracker.start_round()
        summary = self.tracker.finalize_round()

        # Check that successful factors are not in retry list
        retry_ids = summary.factors_to_retry

        self.assertNotIn("f0", retry_ids)
        self.assertNotIn("f1", retry_ids)

        # Failed factors should be in retry
        self.assertIn("f2", retry_ids)
        self.assertIn("f3", retry_ids)
        self.assertIn("f4", retry_ids)

    def test_mark_coder_success(self):
        """Test marking coder stage success."""
        self.tracker.register_factor("f1", "factor_1", "expr_1")
        self.tracker.mark_coder_success("f1")

        status = self.tracker.factor_statuses["f1"]
        self.assertTrue(status.passed_coder)

    def test_mark_coder_failure(self):
        """Test marking coder stage failure."""
        self.tracker.register_factor("f1", "factor_1", "expr_1")
        self.tracker.mark_coder_failure(
            "f1",
            reason=FailureReason.CODER_NO_WORKSPACE,
            detail="No workspace produced",
        )

        status = self.tracker.factor_statuses["f1"]
        self.assertFalse(status.passed_coder)
        self.assertIn(FailureReason.CODER_NO_WORKSPACE, status.failure_reasons)

    def test_mark_quality_gate_success(self):
        """Test marking quality gate success."""
        self.tracker.register_factor("f1", "factor_1", "expr_1")
        self.tracker.mark_quality_gate_success("f1")

        status = self.tracker.factor_statuses["f1"]
        self.assertTrue(status.passed_quality_gate)

    def test_mark_quality_gate_failure(self):
        """Test marking quality gate failure."""
        self.tracker.register_factor("f1", "factor_1", "expr_1")
        self.tracker.mark_quality_gate_failure("f1", detail="Complexity check failed")

        status = self.tracker.factor_statuses["f1"]
        self.assertFalse(status.passed_quality_gate)
        self.assertIn(FailureReason.QUALITY_GATE_FAILED, status.failure_reasons)

    def test_mark_backtest_success(self):
        """Test marking backtest success."""
        self.tracker.register_factor("f1", "factor_1", "expr_1")
        self.tracker.mark_backtest_success("f1", result={"rank_ic": 0.05})

        status = self.tracker.factor_statuses["f1"]
        self.assertTrue(status.passed_backtest)
        self.assertEqual(status.backtest_result, {"rank_ic": 0.05})

    def test_mark_backtest_failure(self):
        """Test marking backtest failure."""
        self.tracker.register_factor("f1", "factor_1", "expr_1")
        self.tracker.mark_backtest_failure(
            "f1",
            reason=FailureReason.BACKTEST_EXCEPTION,
            detail="Timeout error",
        )

        status = self.tracker.factor_statuses["f1"]
        self.assertFalse(status.passed_backtest)
        self.assertIn(FailureReason.BACKTEST_EXCEPTION, status.failure_reasons)

    def test_round_summaries_tracking(self):
        """Test that round summaries are properly tracked."""
        # Register factors
        for i in range(3):
            self.tracker.register_factor(f"f{i}", f"factor_{i}", f"expr_{i}")

        # First round - partial success
        self.tracker.start_round()
        self.tracker.update_factor_status("f0", passed_coder=True, passed_quality_gate=True, passed_backtest=True)
        self.tracker.update_factor_status("f1", failure_reason=FailureReason.CODER_NO_WORKSPACE)
        self.tracker.update_factor_status("f2", failure_reason=FailureReason.BACKTEST_EMPTY_RESULT)
        summary1 = self.tracker.finalize_round()

        # Second round - all success (reset failed factors first)
        # In real flow, failed factors would be re-registered
        self.tracker.register_factor("f1", "factor_1", "expr_1")
        self.tracker.register_factor("f2", "factor_2", "expr_2")
        self.tracker.start_round()
        self.tracker.update_factor_status("f1", passed_coder=True, passed_quality_gate=True, passed_backtest=True)
        self.tracker.update_factor_status("f2", passed_coder=True, passed_quality_gate=True, passed_backtest=True)
        summary2 = self.tracker.finalize_round()

        # Check round tracking
        self.assertEqual(len(self.tracker.round_summaries), 2)
        # Round idx is the round number when summary was created
        self.assertEqual(summary1.round_idx, 0)
        self.assertEqual(summary2.round_idx, 1)
        # First round has 1 successful
        self.assertEqual(summary1.successful_count, 1)
        # Second round has all 3 successful
        self.assertEqual(summary2.successful_count, 3)

    def test_get_summary_stats(self):
        """Test getting overall summary statistics."""
        # Register factors
        for i in range(5):
            self.tracker.register_factor(f"f{i}", f"factor_{i}", f"expr_{i}")

        # Mark some as successful, some as failed
        self.tracker.update_factor_status("f0", passed_coder=True, passed_quality_gate=True, passed_backtest=True)
        self.tracker.update_factor_status("f1", passed_coder=True, passed_quality_gate=True, passed_backtest=True)
        self.tracker.update_factor_status("f2", failure_reason=FailureReason.CODER_NO_WORKSPACE)
        self.tracker.update_factor_status("f3", failure_reason=FailureReason.BACKTEST_EMPTY_RESULT)
        # f4 remains pending (no status set yet)

        stats = self.tracker.get_summary_stats()

        self.assertEqual(stats["total_factors"], 5)
        self.assertEqual(stats["successful_factors"], 2)
        self.assertEqual(stats["failed_factors"], 2)
        # Pending = failed factors that need retry
        self.assertEqual(stats["pending_factors"], 2)  # f2, f3


class TestFailureReasonEnum(unittest.TestCase):
    """Test cases for FailureReason enum."""

    def test_all_failure_reasons_defined(self):
        """Test that all expected failure reasons are defined."""
        expected_reasons = [
            "expression_parse_failed",
            "coder_no_workspace",
            "quality_gate_failed",
            "backtest_empty_result",
            "backtest_exception",
            "unknown",
        ]

        actual_values = [r.value for r in FailureReason]

        for reason in expected_reasons:
            self.assertIn(reason, actual_values)

    def test_failure_reason_values(self):
        """Test that failure reason values are correct."""
        self.assertEqual(FailureReason.EXPRESSION_PARSE_FAILED.value, "expression_parse_failed")
        self.assertEqual(FailureReason.CODER_NO_WORKSPACE.value, "coder_no_workspace")
        self.assertEqual(FailureReason.QUALITY_GATE_FAILED.value, "quality_gate_failed")
        self.assertEqual(FailureReason.BACKTEST_EMPTY_RESULT.value, "backtest_empty_result")
        self.assertEqual(FailureReason.BACKTEST_EXCEPTION.value, "backtest_exception")


class TestIntegrationScenarios(unittest.TestCase):
    """Integration test scenarios for debug failure filter."""

    def test_complete_debug_cycle(self):
        """Test a complete debug cycle with multiple rounds."""
        tracker = FactorFailureTracker(max_debug_rounds=3)

        # Initial factors
        factors = [
            ("f1", "alpha_1", "ts_rank($close, 5)"),
            ("f2", "alpha_2", "ts_mean($volume, 10)"),
            ("f3", "alpha_3", "invalid_expression"),
        ]

        for fid, name, expr in factors:
            tracker.register_factor(fid, name, expr)

        # Round 0: f1 succeeds, f2 and f3 fail
        tracker.start_round()
        tracker.update_factor_status("f1", passed_coder=True, passed_quality_gate=True, passed_backtest=True)
        tracker.update_factor_status("f2", failure_reason=FailureReason.CODER_NO_WORKSPACE)
        tracker.update_factor_status("f3", failure_reason=FailureReason.EXPRESSION_PARSE_FAILED)
        summary0 = tracker.finalize_round()

        self.assertEqual(summary0.successful_count, 1)
        self.assertEqual(summary0.failed_count, 2)
        self.assertTrue(tracker.should_continue_debug())

        # Round 1: f2 fixed, f3 still fails (re-register to reset)
        tracker.register_factor("f2", "alpha_2", "ts_mean($volume, 10)")
        tracker.register_factor("f3", "alpha_3", "invalid_expression")
        tracker.start_round()
        tracker.update_factor_status("f2", passed_coder=True, passed_quality_gate=True, passed_backtest=True)
        tracker.update_factor_status("f3", failure_reason=FailureReason.EXPRESSION_PARSE_FAILED)
        summary1 = tracker.finalize_round()

        self.assertEqual(summary1.successful_count, 2)
        self.assertTrue(tracker.should_continue_debug())

        # Round 2: Last attempt for f3 (re-register to reset)
        tracker.register_factor("f3", "alpha_3", "invalid_expression")
        tracker.start_round()
        tracker.update_factor_status("f3", failure_reason=FailureReason.BACKTEST_EMPTY_RESULT)
        summary2 = tracker.finalize_round()

        # After max rounds (3), should stop
        self.assertFalse(tracker.should_continue_debug())

        # Final stats
        stats = tracker.get_summary_stats()
        self.assertEqual(stats["successful_factors"], 2)
        self.assertEqual(stats["rounds_completed"], 3)
