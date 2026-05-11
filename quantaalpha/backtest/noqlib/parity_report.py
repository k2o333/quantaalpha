"""Standalone qlib/no-qlib metric parity reporter."""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ParityReport:
    """Metric-level qlib/no-qlib parity report."""

    tolerance: float
    metrics: dict[str, dict[str, Any]]

    @property
    def passed(self) -> bool:
        return all(bool(item["passed"]) for item in self.metrics.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "metrics": self.metrics,
            "passed": self.passed,
            "tolerance": self.tolerance,
        }


def build_parity_report(
    *,
    qlib_result: dict[str, Any],
    noqlib_result: dict[str, Any],
    tolerance: float = 1e-6,
) -> ParityReport:
    """Compare metric dictionaries from qlib and no-qlib runs."""

    if tolerance < 0:
        raise ValueError("tolerance must be non-negative.")
    metrics = {
        key: _compare_value(qlib_result.get(key), noqlib_result.get(key), tolerance=tolerance)
        for key in sorted(set(qlib_result) | set(noqlib_result))
    }
    return ParityReport(tolerance=tolerance, metrics=metrics)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""

    parser = argparse.ArgumentParser(description="Compare qlib and no-qlib metric JSON files.")
    parser.add_argument("--qlib-result", required=True)
    parser.add_argument("--noqlib-result", required=True)
    parser.add_argument("--tolerance", type=float, default=1e-6)
    parser.add_argument("--output-path")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)

    report = build_parity_report(
        qlib_result=_load_json_object(Path(args.qlib_result)),
        noqlib_result=_load_json_object(Path(args.noqlib_result)),
        tolerance=args.tolerance,
    )
    payload = report.to_dict()
    encoded = (
        json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True)
        if args.format == "json"
        else _format_text(report)
    )
    if args.output_path:
        Path(args.output_path).write_text(encoded + "\n", encoding="utf-8")
    sys.stdout.write(encoded)
    sys.stdout.write("\n")
    return 0 if report.passed else 1


def _compare_value(left: Any, right: Any, *, tolerance: float) -> dict[str, Any]:
    left_number = _to_finite_float(left)
    right_number = _to_finite_float(right)
    if left_number is not None and right_number is not None:
        abs_diff = abs(left_number - right_number)
        return {
            "abs_diff": abs_diff,
            "noqlib": right,
            "passed": abs_diff <= tolerance,
            "qlib": left,
        }
    return {
        "abs_diff": None,
        "noqlib": right,
        "passed": left == right,
        "qlib": left,
    }


def _to_finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _load_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"metric JSON must be an object: {path}")
    return payload


def _format_text(report: ParityReport) -> str:
    lines = [
        "Qlib/No-Qlib Parity Report",
        "==========================",
        f"tolerance: {report.tolerance}",
        f"passed: {str(report.passed).lower()}",
    ]
    for key, payload in report.metrics.items():
        lines.append(
            f"  [{key}] passed={str(payload['passed']).lower()} "
            f"qlib={payload['qlib']} noqlib={payload['noqlib']} abs_diff={payload['abs_diff']}"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
