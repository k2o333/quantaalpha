"""Market-input parity report for qlib and noqlib/vnpy routes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Sequence

import polars as pl

from quantaalpha.backtest.noqlib.data_provider import NoQlibMarketDataProvider


COMPARE_FIELDS = ("$open", "$high", "$low", "$close", "$volume", "$return")


def build_market_parity_report(
    *,
    qlib_config: dict[str, Any],
    candidate_config: dict[str, Any],
    tolerance: float = 1e-6,
) -> dict[str, Any]:
    """Build a field-level parity report between qlib-bin oracle and a candidate route."""
    qlib_frame = NoQlibMarketDataProvider(qlib_config).load_market_frame()
    candidate_frame = NoQlibMarketDataProvider(candidate_config).load_market_frame()
    return compare_market_frames(qlib_frame=qlib_frame, candidate_frame=candidate_frame, tolerance=tolerance)


def compare_market_frames(
    *,
    qlib_frame: pl.DataFrame,
    candidate_frame: pl.DataFrame,
    tolerance: float = 1e-6,
    fields: Sequence[str] = COMPARE_FIELDS,
) -> dict[str, Any]:
    """Compare two normalized standard market frames."""
    qlib_prepared = _prepare_frame(qlib_frame, fields, prefix="qlib")
    candidate_prepared = _prepare_frame(candidate_frame, fields, prefix="candidate")
    joined = qlib_prepared.join(candidate_prepared, on=["datetime", "instrument"], how="inner")
    q_keys = qlib_prepared.select(["datetime", "instrument"])
    c_keys = candidate_prepared.select(["datetime", "instrument"])
    missing_in_candidate = q_keys.join(c_keys, on=["datetime", "instrument"], how="anti").height
    extra_in_candidate = c_keys.join(q_keys, on=["datetime", "instrument"], how="anti").height
    field_reports = {
        field: _field_report(joined, field=field, tolerance=tolerance)
        for field in fields
    }
    return {
        "passed": bool(
            missing_in_candidate == 0
            and extra_in_candidate == 0
            and all(item["passed"] for item in field_reports.values())
        ),
        "row_counts": {
            "qlib": qlib_frame.height,
            "candidate": candidate_frame.height,
            "joined": joined.height,
            "missing_in_candidate": missing_in_candidate,
            "extra_in_candidate": extra_in_candidate,
        },
        "tolerance": tolerance,
        "fields": field_reports,
    }


def _prepare_frame(frame: pl.DataFrame, fields: Sequence[str], *, prefix: str) -> pl.DataFrame:
    required = {"datetime", "instrument", *fields}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{prefix} market frame missing columns: {missing}")
    return (
        frame.select(
            pl.col("datetime").cast(pl.Date),
            pl.col("instrument").cast(pl.Utf8),
            *[pl.col(field).cast(pl.Float64).alias(f"{prefix}_{_field_key(field)}") for field in fields],
        )
        .unique(subset=["datetime", "instrument"], keep="first", maintain_order=True)
        .sort(["datetime", "instrument"])
    )


def _field_report(frame: pl.DataFrame, *, field: str, tolerance: float) -> dict[str, Any]:
    left = f"qlib_{_field_key(field)}"
    right = f"candidate_{_field_key(field)}"
    if frame.is_empty():
        return {
            "passed": False,
            "non_null_pairs": 0,
            "max_abs_diff": None,
            "mean_abs_diff": None,
        }
    diff_expr = (pl.col(left) - pl.col(right)).abs()
    stats = frame.select(
        diff_expr.max().alias("max_abs_diff"),
        diff_expr.mean().alias("mean_abs_diff"),
        diff_expr.is_not_null().sum().alias("non_null_pairs"),
    ).to_dicts()[0]
    max_abs = stats["max_abs_diff"]
    return {
        "passed": bool(max_abs is not None and max_abs <= tolerance),
        "non_null_pairs": int(stats["non_null_pairs"] or 0),
        "max_abs_diff": None if max_abs is None else float(max_abs),
        "mean_abs_diff": None if stats["mean_abs_diff"] is None else float(stats["mean_abs_diff"]),
    }


def _field_key(field: str) -> str:
    return field.replace("$", "")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare qlib-bin market input with a noqlib/vnpy candidate route.")
    parser.add_argument("--qlib-config", required=True, help="JSON file containing the qlib oracle config")
    parser.add_argument("--candidate-config", required=True, help="JSON file containing the candidate config")
    parser.add_argument("--output", required=True)
    parser.add_argument("--tolerance", type=float, default=1e-6)
    args = parser.parse_args(argv)
    report = build_market_parity_report(
        qlib_config=json.loads(Path(args.qlib_config).read_text(encoding="utf-8")),
        candidate_config=json.loads(Path(args.candidate_config).read_text(encoding="utf-8")),
        tolerance=args.tolerance,
    )
    Path(args.output).write_text(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
