"""
Multi-period validation judge module.

Provides automatic judgment of factor validity based on IC/Rank IC thresholds
and minimum passing periods across multiple backtest periods.

Usage:
    from quantaalpha.backtest.validation_judge import evaluate_multi_period_results

    result = evaluate_multi_period_results(
        period_results=[
            {"name": "period_1", "metrics": {"IC": 0.03, "Rank IC": 0.04, "status": "success"}},
            {"name": "period_2", "metrics": {"IC": 0.01, "Rank IC": 0.02, "status": "success"}},
        ],
        pass_criteria={"min_ic": 0.02, "min_rank_ic": 0.02, "min_periods_pass": 2},
        require_all_pass=True,
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union


class PeriodMetrics:
    """Type definition for period metrics."""
    IC: Optional[float] = None
    "Pearson correlation coefficient between predictions and returns"
    Rank_IC: Optional[float] = None
    "Rank correlation coefficient between predictions and returns"
    status: str = "success"
    "Period status: 'success' or 'failure'"


class PeriodResult:
    """Type definition for a single period result."""
    name: str = ""
    "Unique identifier for the period"
    metrics: Dict[str, Any] = {}
    "Metrics dictionary containing IC, Rank IC values"


@dataclass
class EvaluationResult:
    """
    Structured result of multi-period validation evaluation.

    Attributes:
        overall_pass: Whether the factor passed the multi-period validation
        passing_periods: List of period names that passed all criteria
        failing_periods: List of period names that failed criteria
        period_judgments: Per-period pass/fail judgment with details
        total_periods: Total number of periods evaluated
        passing_count: Number of periods that passed
        failing_count: Number of periods that failed
        ic_values: IC values per period
        rank_ic_values: Rank IC values per period
        min_ic: Configured minimum IC threshold
        min_rank_ic: Configured minimum Rank IC threshold
        min_periods_pass: Configured minimum required passing periods
        require_all_pass: Whether all periods must pass
    """
    overall_pass: bool
    passing_periods: List[str]
    failing_periods: List[str]
    period_judgments: List[Dict[str, Any]]
    total_periods: int
    passing_count: int
    failing_count: int
    ic_values: Dict[str, Optional[float]]
    rank_ic_values: Dict[str, Optional[float]]
    min_ic: float
    min_rank_ic: float
    min_periods_pass: int
    require_all_pass: bool


def evaluate_multi_period_results(
    period_results: List[Dict[str, Any]],
    pass_criteria: Dict[str, Any],
    require_all_pass: bool = True,
) -> EvaluationResult:
    """
    Evaluate multi-period backtest results against pass criteria.

    This function judges whether a factor passes multi-period validation based on:
    - IC (Pearson correlation) threshold
    - Rank IC (Spearman correlation) threshold
    - Minimum number of periods that must pass

    Args:
        period_results: List of period result dictionaries. Each should contain:
            - name (str): Period identifier
            - metrics (dict): Contains IC and Rank IC values:
                - IC (float, optional): Pearson correlation
                - Rank IC (float, optional): Rank correlation
                - status (str): 'success' or 'failure'
        pass_criteria: Dictionary containing:
            - min_ic (float): Minimum IC threshold (default: 0.0)
            - min_rank_ic (float): Minimum Rank IC threshold (default: 0.0)
            - min_periods_pass (int): Minimum passing periods required (default: 1)
        require_all_pass: If True, all periods must pass criteria. If False,
            at least min_periods_pass periods must pass. (default: True)

    Returns:
        EvaluationResult: Structured judgment result containing:
            - overall_pass (bool): Final pass/fail judgment
            - passing_periods (list[str]): Periods that passed
            - failing_periods (list[str]): Periods that failed
            - period_judgments (list[dict]): Detailed per-period judgment
            - Passing/failing counts and IC values

    Examples:
        Basic usage:
        >>> result = evaluate_multi_period_results(
        ...     period_results=[
        ...         {"name": "2020", "metrics": {"IC": 0.05, "Rank IC": 0.04}},
        ...         {"name": "2021", "metrics": {"IC": 0.03, "Rank IC": 0.03}},
        ...     ],
        ...     pass_criteria={"min_ic": 0.02, "min_rank_ic": 0.02, "min_periods_pass": 2},
        ...     require_all_pass=True,
        ... )
        >>> result.overall_pass
        True

        Partial pass:
        >>> result = evaluate_multi_period_results(
        ...     period_results=[
        ...         {"name": "2020", "metrics": {"IC": 0.05, "Rank IC": 0.04}},
        ...         {"name": "2021", "metrics": {"IC": 0.01, "Rank IC": 0.01}},
        ...     ],
        ...     pass_criteria={"min_ic": 0.02, "min_rank_ic": 0.02, "min_periods_pass": 1},
        ...     require_all_pass=False,
        ... )
        >>> result.overall_pass
        True
        >>> len(result.passing_periods)
        1
    """
    # Extract criteria with defaults for defensiveness
    min_ic = float(pass_criteria.get("min_ic", 0.0))
    min_rank_ic = float(pass_criteria.get("min_rank_ic", 0.0))
    min_periods_pass = int(pass_criteria.get("min_periods_pass", 1))

    # Defensive handling for empty or invalid input
    if not period_results:
        return EvaluationResult(
            overall_pass=False,
            passing_periods=[],
            failing_periods=[],
            period_judgments=[],
            total_periods=0,
            passing_count=0,
            failing_count=0,
            ic_values={},
            rank_ic_values={},
            min_ic=min_ic,
            min_rank_ic=min_rank_ic,
            min_periods_pass=min_periods_pass,
            require_all_pass=require_all_pass,
        )

    passing_periods: List[str] = []
    failing_periods: List[str] = []
    period_judgments: List[Dict[str, Any]] = []
    ic_values: Dict[str, Optional[float]] = {}
    rank_ic_values: Dict[str, Optional[float]] = {}

    for period in period_results:
        # Extract period info with defensive defaults
        name = str(period.get("name", "unknown"))
        metrics = period.get("metrics", {})

        # Extract IC values (handle None/missing)
        ic_value = metrics.get("IC")
        rank_ic_value = metrics.get("Rank IC")

        # Convert to float if possible, None if not available
        try:
            ic_float = float(ic_value) if ic_value is not None else None
        except (TypeError, ValueError):
            ic_float = None

        try:
            rank_ic_float = float(rank_ic_value) if rank_ic_value is not None else None
        except (TypeError, ValueError):
            rank_ic_float = None

        # Store IC values for reporting
        ic_values[name] = ic_float
        rank_ic_values[name] = rank_ic_float

        # Check if period failed (status check)
        status = metrics.get("status", "success")
        if status != "success":
            period_judgments.append({
                "name": name,
                "pass": False,
                "reason": f"Period status is '{status}'",
                "ic_value": ic_float,
                "rank_ic_value": rank_ic_float,
                "ic_threshold_met": False,
                "rank_ic_threshold_met": False,
            })
            failing_periods.append(name)
            continue

        # Evaluate IC threshold
        ic_threshold_met = ic_float is not None and ic_float > min_ic

        # Evaluate Rank IC threshold
        rank_ic_threshold_met = rank_ic_float is not None and rank_ic_float > min_rank_ic

        # Period passes if both IC and Rank IC meet thresholds
        period_passes = ic_threshold_met and rank_ic_threshold_met

        if period_passes:
            passing_periods.append(name)
            reason = "IC and Rank IC both meet thresholds"
        else:
            failing_periods.append(name)
            reasons = []
            if ic_float is None:
                reasons.append("IC not available")
            elif not ic_threshold_met:
                reasons.append(f"IC ({ic_float:.4f}) <= threshold ({min_ic:.4f})")
            if rank_ic_float is None:
                reasons.append("Rank IC not available")
            elif not rank_ic_threshold_met:
                reasons.append(f"Rank IC ({rank_ic_float:.4f}) <= threshold ({min_rank_ic:.4f})")
            reason = "; ".join(reasons) if reasons else "Unknown failure reason"

        period_judgments.append({
            "name": name,
            "pass": period_passes,
            "reason": reason,
            "ic_value": ic_float,
            "rank_ic_value": rank_ic_float,
            "ic_threshold_met": ic_threshold_met,
            "rank_ic_threshold_met": rank_ic_threshold_met,
        })

    # Determine overall pass
    passing_count = len(passing_periods)
    failing_count = len(failing_periods)
    total_periods = len(period_results)

    if require_all_pass:
        # All periods must pass
        overall_pass = passing_count == total_periods and failing_count == 0
    else:
        # At least min_periods_pass periods must pass
        overall_pass = passing_count >= min_periods_pass

    return EvaluationResult(
        overall_pass=overall_pass,
        passing_periods=passing_periods,
        failing_periods=failing_periods,
        period_judgments=period_judgments,
        total_periods=total_periods,
        passing_count=passing_count,
        failing_count=failing_count,
        ic_values=ic_values,
        rank_ic_values=rank_ic_values,
        min_ic=min_ic,
        min_rank_ic=min_rank_ic,
        min_periods_pass=min_periods_pass,
        require_all_pass=require_all_pass,
    )


def format_evaluation_result(result: EvaluationResult) -> str:
    """
    Format evaluation result as human-readable string.

    Args:
        result: EvaluationResult from evaluate_multi_period_results()

    Returns:
        Formatted string representation
    """
    status = "PASS" if result.overall_pass else "FAIL"
    lines = [
        f"Multi-Period Validation Result: {status}",
        f"Passing: {result.passing_count}/{result.total_periods} periods",
        f"Criteria: IC > {result.min_ic:.4f}, Rank IC > {result.min_rank_ic:.4f}",
    ]

    if result.require_all_pass:
        lines.append(f"Requirement: All periods must pass")
    else:
        lines.append(f"Requirement: At least {result.min_periods_pass} period(s) must pass")

    if result.passing_periods:
        lines.append(f"Passing periods: {', '.join(result.passing_periods)}")
    if result.failing_periods:
        lines.append(f"Failing periods: {', '.join(result.failing_periods)}")

    return "\n".join(lines)
