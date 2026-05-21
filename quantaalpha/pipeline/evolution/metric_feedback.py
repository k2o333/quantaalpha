"""Backtest metric formatting for LLM feedback prompts."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pandas as pd


METRIC_ALIASES: dict[str, tuple[str, ...]] = {
    "IC": ("IC", "ic", "ic_mean"),
    "Rank IC": ("Rank IC", "RankIC", "rank_ic", "rank_ic_mean"),
    "Information Ratio": (
        "Information Ratio",
        "information_ratio",
        "Sharpe",
        "sharpe",
        "1day.excess_return_without_cost.information_ratio",
        "1day.excess_return_with_cost.information_ratio",
    ),
    "Annualized Return": (
        "Annualized Return",
        "annualized_return",
        "1day.excess_return_without_cost.annualized_return",
        "1day.excess_return_with_cost.annualized_return",
    ),
}


def _coerce_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        scalar = value.item() if hasattr(value, "item") else value
        numeric = float(scalar)
    except (TypeError, ValueError):
        return None
    if pd.isna(numeric):
        return None
    return numeric


def _flatten_metrics(metrics: Any) -> dict[str, Any]:
    if metrics is None:
        return {}
    if isinstance(metrics, pd.DataFrame):
        if metrics.empty:
            return {}
        if metrics.shape[1] == 1:
            return metrics.iloc[:, 0].to_dict()
        flattened: dict[str, Any] = {}
        for column in metrics.columns:
            for index, value in metrics[column].items():
                flattened[str(index)] = value
                flattened[f"{index}.{column}"] = value
        return flattened
    if isinstance(metrics, pd.Series):
        return metrics.to_dict()
    if isinstance(metrics, Mapping):
        return dict(metrics)
    return {}


def extract_backtest_metrics(metrics: Any) -> dict[str, float]:
    """Extract the core optimization metrics from backtest output."""
    flattened = _flatten_metrics(metrics)
    extracted: dict[str, float] = {}
    for display_name, aliases in METRIC_ALIASES.items():
        for alias in aliases:
            if alias in flattened:
                value = _coerce_float(flattened[alias])
                if value is not None:
                    extracted[display_name] = value
                    break
    return extracted


def format_metric_feedback(metrics: Any, *, label: str = "Backtest Metrics") -> str:
    """Format IC/Rank IC/IR/annualized return for the next LLM step."""
    extracted = extract_backtest_metrics(metrics)
    if not extracted:
        return f"{label}: unavailable"

    ordered_names = ("IC", "Rank IC", "Information Ratio", "Annualized Return")
    metric_text = "; ".join(
        f"{name}={extracted[name]:.4f}"
        for name in ordered_names
        if name in extracted
    )

    warnings: list[str] = []
    ic = extracted.get("IC")
    rank_ic = extracted.get("Rank IC")
    if (ic is not None and abs(ic) < 0.01) or (rank_ic is not None and abs(rank_ic) < 0.01):
        warnings.append("low predictive power; next iteration should materially change signal construction")

    if warnings:
        return f"{label}: {metric_text}. Warning: {'; '.join(warnings)}."
    return f"{label}: {metric_text}."


def format_text_feedback(
    feedback: str | None,
    feedback_details: Mapping[str, Any] | None = None,
    *,
    label: str = "Evaluation Feedback",
    max_chars: int = 600,
) -> str:
    """Format bounded evaluator feedback for prompt reuse."""
    parts: list[str] = []
    if feedback:
        parts.append(str(feedback).strip())
    for key, value in (feedback_details or {}).items():
        if value:
            parts.append(f"{key}: {value}")

    text = "\n".join(part for part in parts if part)
    if not text:
        return f"{label}: unavailable"
    if len(text) > max_chars:
        text = text[: max_chars - 3].rstrip() + "..."
    return f"{label}: {text}"
