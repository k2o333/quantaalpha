"""Long-only daily report parity checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

import numpy as np
import pandas as pd


DAILY_REPORT_COLUMNS = ("return", "bench", "cost", "turnover", "cash", "equity")
REQUIRED_DAILY_SERIES = ("return", "bench", "cost")


@dataclass(frozen=True)
class SeriesParityResult:
    """Parity result for one daily report column."""

    column: str
    passed: bool
    max_abs_diff: float | None
    mean_abs_diff: float | None
    row_count: int


@dataclass(frozen=True)
class LongOnlyParityReport:
    """Long-only parity result across daily report and positions."""

    passed: bool
    daily_series: dict[str, SeriesParityResult]
    positions_passed: bool | None = None
    summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "daily_series": {
                key: {
                    "passed": value.passed,
                    "max_abs_diff": value.max_abs_diff,
                    "mean_abs_diff": value.mean_abs_diff,
                    "row_count": value.row_count,
                }
                for key, value in self.daily_series.items()
            },
            "positions_passed": self.positions_passed,
            "summary": dict(self.summary),
        }


def compare_long_only_daily_reports(
    left: pd.DataFrame,
    right: pd.DataFrame,
    *,
    columns: tuple[str, ...] = REQUIRED_DAILY_SERIES,
    rtol: float = 1e-6,
    atol: float = 1e-8,
) -> LongOnlyParityReport:
    """Compare named long-only daily series before summary metrics are trusted."""
    _require_columns(left, columns, "left")
    _require_columns(right, columns, "right")
    left_aligned, right_aligned = left.align(right, join="inner", axis=0)
    if len(left_aligned) != len(left) or len(right_aligned) != len(right):
        raise ValueError("daily report indexes are not identical for long-only parity")
    results: dict[str, SeriesParityResult] = {}
    for column in columns:
        diff = (left_aligned[column].astype(float) - right_aligned[column].astype(float)).abs()
        passed = bool(np.allclose(left_aligned[column], right_aligned[column], rtol=rtol, atol=atol, equal_nan=True))
        results[column] = SeriesParityResult(
            column=column,
            passed=passed,
            max_abs_diff=float(diff.max()) if len(diff) else 0.0,
            mean_abs_diff=float(diff.mean()) if len(diff) else 0.0,
            row_count=len(diff),
        )
    return LongOnlyParityReport(
        passed=all(item.passed for item in results.values()),
        daily_series=results,
        summary={"columns": list(columns), "rtol": rtol, "atol": atol},
    )


def normalize_qlib_daily_report(report: pd.DataFrame) -> pd.DataFrame:
    """Map qlib portfolio report columns onto the long-only daily contract."""
    normalized = report.copy()
    if "equity" not in normalized.columns and "account" in normalized.columns:
        normalized["equity"] = normalized["account"]
    return normalized


def qlib_positions_to_frame(positions: Mapping[Any, Any]) -> pd.DataFrame:
    """Convert qlib position snapshots into the long-only position row contract."""
    rows: list[dict[str, Any]] = []
    for date, snapshot in positions.items():
        if isinstance(snapshot, Mapping):
            position = snapshot.get("position", {})
        else:
            position = getattr(snapshot, "position", {})
        if not isinstance(position, Mapping):
            continue
        for instrument, payload in position.items():
            if instrument in {"cash", "now_account_value"}:
                continue
            if not isinstance(payload, Mapping):
                continue
            rows.append(
                {
                    "date": pd.Timestamp(date),
                    "instrument": str(instrument),
                    "weight": float(payload.get("weight", 0.0)),
                    "amount": float(payload.get("amount", 0.0)),
                    "value": float(payload.get("amount", 0.0)) * float(payload.get("price", 0.0)),
                }
            )
    return pd.DataFrame(rows, columns=["date", "instrument", "weight", "amount", "value"])


def compare_long_only_positions(
    left: pd.DataFrame,
    right: pd.DataFrame,
    *,
    rtol: float = 1e-6,
    atol: float = 1e-6,
) -> LongOnlyParityReport:
    """Compare long-only position rows by date/instrument and numeric position fields."""
    columns = ("weight", "amount", "value")
    _require_position_columns(left, "left")
    _require_position_columns(right, "right")
    left_indexed = left.copy()
    right_indexed = right.copy()
    left_indexed["date"] = pd.to_datetime(left_indexed["date"])
    right_indexed["date"] = pd.to_datetime(right_indexed["date"])
    left_indexed = left_indexed.set_index(["date", "instrument"]).sort_index()
    right_indexed = right_indexed.set_index(["date", "instrument"]).sort_index()
    if not left_indexed.index.equals(right_indexed.index):
        raise ValueError("position indexes are not identical for long-only parity")
    results: dict[str, SeriesParityResult] = {}
    for column in columns:
        diff = (left_indexed[column].astype(float) - right_indexed[column].astype(float)).abs()
        passed = bool(np.allclose(left_indexed[column], right_indexed[column], rtol=rtol, atol=atol, equal_nan=True))
        results[column] = SeriesParityResult(
            column=column,
            passed=passed,
            max_abs_diff=float(diff.max()) if len(diff) else 0.0,
            mean_abs_diff=float(diff.mean()) if len(diff) else 0.0,
            row_count=len(diff),
        )
    return LongOnlyParityReport(
        passed=all(item.passed for item in results.values()),
        daily_series=results,
        positions_passed=all(item.passed for item in results.values()),
        summary={"columns": list(columns), "rtol": rtol, "atol": atol},
    )


def assert_annualized_return_comparable(parity_report: LongOnlyParityReport, provenance: Mapping[str, Any]) -> None:
    """Block annualized-return comparison until daily series parity is proven."""
    if not parity_report.passed:
        raise ValueError("annualized return cannot be compared before daily series parity passes")
    if not provenance.get("source_series_proven_identical"):
        raise ValueError("annualized return provenance does not mark source_series_proven_identical")


def _require_columns(frame: pd.DataFrame, columns: tuple[str, ...], side: str) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise ValueError(f"{side} long-only daily report missing columns: {missing}")


def _require_position_columns(frame: pd.DataFrame, side: str) -> None:
    missing = sorted({"date", "instrument", "weight", "amount", "value"} - set(frame.columns))
    if missing:
        raise ValueError(f"{side} long-only positions missing columns: {missing}")
