"""
Failure tracking and filtering for debug rounds.

This module provides classes to track factor failures across debug rounds
and determine which factors should be retried in subsequent rounds.
"""

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set


class FailureReason(Enum):
    """Reasons why a factor might fail during processing."""

    EXPRESSION_PARSE_FAILED = "expression_parse_failed"
    CODER_NO_WORKSPACE = "coder_no_workspace"
    QUALITY_GATE_FAILED = "quality_gate_failed"
    BACKTEST_EMPTY_RESULT = "backtest_empty_result"
    BACKTEST_EXCEPTION = "backtest_exception"
    UNKNOWN = "unknown"


@dataclass
class FactorStatus:
    """Status tracking for an individual factor across debug rounds."""

    factor_id: str
    factor_name: str
    factor_expression: str

    # Stage results
    passed_coder: bool = False
    passed_quality_gate: bool = False
    passed_backtest: bool = False

    # Failure tracking
    failure_reasons: Set[FailureReason] = field(default_factory=set)
    failure_details: Dict[str, str] = field(default_factory=dict)

    # Results
    backtest_result: Optional[Dict] = None

    @property
    def is_successful(self) -> bool:
        """Check if factor passed all stages."""
        return self.passed_coder and self.passed_quality_gate and self.passed_backtest

    @property
    def is_failed(self) -> bool:
        """Check if factor has any failures."""
        return len(self.failure_reasons) > 0

    def add_failure(self, reason: FailureReason, detail: str = ""):
        """Add a failure reason with optional detail."""
        self.failure_reasons.add(reason)
        if detail:
            self.failure_details[reason.value] = detail

    def to_dict(self) -> Dict:
        """Serialize status to dictionary."""
        return {
            "factor_id": self.factor_id,
            "factor_name": self.factor_name,
            "factor_expression": self.factor_expression,
            "passed_coder": self.passed_coder,
            "passed_quality_gate": self.passed_quality_gate,
            "passed_backtest": self.passed_backtest,
            "is_successful": self.is_successful,
            "failure_reasons": [r.value for r in self.failure_reasons],
            "failure_details": self.failure_details,
            "backtest_result": self.backtest_result,
        }


@dataclass
class DebugRoundSummary:
    """Summary of a debug round's results."""

    round_idx: int
    total_factors: int
    successful_count: int
    failed_count: int
    successful_factor_ids: List[str] = field(default_factory=list)
    failed_factor_ids: List[str] = field(default_factory=list)
    factors_to_retry: List[str] = field(default_factory=list)
    failed_reasons: Dict[str, List[str]] = field(default_factory=dict)

    @property
    def all_succeeded(self) -> bool:
        """Check if all factors succeeded."""
        return self.successful_count == self.total_factors and self.failed_count == 0

    @property
    def all_failed(self) -> bool:
        """Check if all factors failed."""
        return self.failed_count == self.total_factors and self.successful_count == 0

    def get_failure_reason_counts(self) -> Dict[str, int]:
        """Get counts of each failure reason across failed factors."""
        counts = {}
        for reasons in self.failed_reasons.values():
            for reason in reasons:
                counts[reason] = counts.get(reason, 0) + 1
        return counts


class FactorFailureTracker:
    """Tracks factor failures across debug rounds and manages retry logic."""

    def __init__(self, max_debug_rounds: int):
        self.max_debug_rounds = max_debug_rounds
        self.factor_statuses: Dict[str, FactorStatus] = {}
        self.round_summaries: List[DebugRoundSummary] = []
        self.current_round_idx: int = 0
        self._round_in_progress: bool = False

    @property
    def successful_factor_ids(self) -> List[str]:
        """Get IDs of successfully completed factors."""
        return [
            fid for fid, status in self.factor_statuses.items() if status.is_successful
        ]

    @property
    def failed_factor_ids(self) -> List[str]:
        """Get IDs of failed factors."""
        return [fid for fid, status in self.factor_statuses.items() if status.is_failed]

    def register_factor(
        self, factor_id: str, factor_name: str, factor_expression: str
    ) -> FactorStatus:
        """Register a factor for tracking."""
        status = FactorStatus(
            factor_id=factor_id,
            factor_name=factor_name,
            factor_expression=factor_expression,
        )
        self.factor_statuses[factor_id] = status
        return status

    def ensure_factor(
        self, factor_id: str, factor_name: str, factor_expression: str
    ) -> FactorStatus:
        """Register a factor if missing, otherwise preserve the existing status."""
        existing = self.factor_statuses.get(factor_id)
        if existing is not None:
            existing.factor_name = factor_name
            existing.factor_expression = factor_expression
            return existing
        return self.register_factor(factor_id, factor_name, factor_expression)

    def get_status(self, factor_id: str) -> Optional[FactorStatus]:
        """Get status of a factor."""
        return self.factor_statuses.get(factor_id)

    def update_factor_status(
        self,
        factor_id: str,
        passed_coder: Optional[bool] = None,
        passed_quality_gate: Optional[bool] = None,
        passed_backtest: Optional[bool] = None,
        failure_reason: Optional[FailureReason] = None,
        failure_detail: str = "",
    ):
        """Update factor status with results from various stages."""
        status = self.factor_statuses.get(factor_id)
        if not status:
            return

        if passed_coder is not None:
            status.passed_coder = passed_coder

        if passed_quality_gate is not None:
            status.passed_quality_gate = passed_quality_gate

        if passed_backtest is not None:
            status.passed_backtest = passed_backtest

        if failure_reason is not None:
            status.add_failure(failure_reason, failure_detail)

    def mark_coder_success(self, factor_id: str):
        """Mark factor as successfully processed by coder."""
        self.update_factor_status(factor_id, passed_coder=True)

    def mark_coder_failure(
        self, factor_id: str, reason: FailureReason, detail: str = ""
    ):
        """Mark factor as failed during coder processing."""
        self.update_factor_status(
            factor_id, passed_coder=False, failure_reason=reason, failure_detail=detail
        )

    def mark_quality_gate_success(self, factor_id: str):
        """Mark factor as passing quality gate."""
        self.update_factor_status(factor_id, passed_quality_gate=True)

    def mark_quality_gate_failure(self, factor_id: str, detail: str = ""):
        """Mark factor as failing quality gate."""
        self.update_factor_status(
            factor_id,
            passed_quality_gate=False,
            failure_reason=FailureReason.QUALITY_GATE_FAILED,
            failure_detail=detail,
        )

    def mark_backtest_success(self, factor_id: str, result: Dict):
        """Mark factor as successfully backtested."""
        status = self.factor_statuses.get(factor_id)
        if status:
            status.backtest_result = result
        self.update_factor_status(factor_id, passed_backtest=True)

    def mark_backtest_failure(
        self, factor_id: str, reason: FailureReason, detail: str = ""
    ):
        """Mark factor as failed during backtest."""
        self.update_factor_status(
            factor_id,
            passed_backtest=False,
            failure_reason=reason,
            failure_detail=detail,
        )

    def start_round(self):
        """Start a new debug round."""
        self._round_in_progress = True

    def finalize_round(self) -> DebugRoundSummary:
        """Finalize current round and return summary."""
        if not self._round_in_progress:
            raise ValueError("No round in progress")

        successful_ids = []
        failed_ids = []
        failed_reasons = {}

        for fid, status in self.factor_statuses.items():
            if status.is_successful:
                successful_ids.append(fid)
            elif status.is_failed:
                failed_ids.append(fid)
                failed_reasons[fid] = [r.value for r in status.failure_reasons]

        summary = DebugRoundSummary(
            round_idx=self.current_round_idx,
            total_factors=len(self.factor_statuses),
            successful_count=len(successful_ids),
            failed_count=len(failed_ids),
            successful_factor_ids=successful_ids,
            failed_factor_ids=failed_ids,
            factors_to_retry=failed_ids.copy(),
            failed_reasons=failed_reasons,
        )

        self.round_summaries.append(summary)
        self.current_round_idx += 1
        self._round_in_progress = False

        return summary

    def get_factors_for_retry(self) -> List[str]:
        """Get factor IDs that should be retried in next round."""
        if self.round_summaries:
            return list(self.round_summaries[-1].factors_to_retry)
        return self.failed_factor_ids

    def should_continue_debug(self) -> bool:
        """Determine if debug should continue to next round."""
        # Early exit if all factors are successful
        if (
            len(self.successful_factor_ids) == len(self.factor_statuses)
            and len(self.factor_statuses) > 0
        ):
            return False

        if not self.round_summaries:
            return True  # Always continue if no rounds completed

        last_summary = self.round_summaries[-1]

        # Continue if within max rounds and not all failed
        return self.current_round_idx < self.max_debug_rounds

    def get_summary_stats(self) -> Dict:
        """Get overall summary statistics."""
        total = len(self.factor_statuses)
        successful = len(self.successful_factor_ids)
        failed = len(self.failed_factor_ids)
        pending = failed  # Failed factors are pending retry

        return {
            "total_factors": total,
            "successful_factors": successful,
            "failed_factors": failed,
            "pending_factors": pending,
            "rounds_completed": len(self.round_summaries),
        }
