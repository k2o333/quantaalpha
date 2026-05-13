"""Factor-library integration for the qlib backtest runner."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


def run_from_library_impl(
    runner: Any,
    library_path: str,
    factor_ids: Optional[list[str]] = None,
    status_filter: Optional[str] = None,
    output_name: Optional[str] = None,
    skip_uncached: bool = False,
) -> dict:
    """Run a runner on factors selected from a factor-library JSON file."""
    with open(library_path, "r", encoding="utf-8") as f:
        lib_data = json.load(f)

    factors_raw = lib_data.get("factors", {})
    custom_factors: list[dict[str, Any]] = []

    for fid, finfo in factors_raw.items():
        if factor_ids and fid not in factor_ids:
            continue
        status = finfo.get("evaluation", {}).get("status", "pending_validation")
        if status_filter and status != status_filter:
            continue
        expr = finfo.get("factor_expression", "")
        if not expr:
            continue
        custom_factors.append(
            {
                "factor_id": fid,
                "factor_name": finfo.get("factor_name", fid),
                "factor_expression": expr,
                "metadata": finfo.get("metadata", {}),
            }
        )

    if not custom_factors:
        logger.warning("No factors found in library %s matching criteria", library_path)
        return {
            "error": "no_matching_factors",
            "factors_checked": list(factors_raw.keys()),
        }

    lib_json_tmp = Path(library_path).parent / f".{Path(library_path).name}.tmp_factors.json"
    try:
        with open(lib_json_tmp, "w", encoding="utf-8") as f:
            json.dump(
                [
                    {
                        "factor_id": c["factor_id"],
                        "factor_name": c["factor_name"],
                        "factor_expression": c["factor_expression"],
                    }
                    for c in custom_factors
                ],
                f,
            )
        metrics = runner.run(
            factor_source="custom",
            factor_json=[str(lib_json_tmp)],
            output_name=output_name or "library_backtest",
            skip_uncached=skip_uncached,
        )
        return {
            "metrics": metrics,
            "factors_backtested": [c["factor_id"] for c in custom_factors],
            "library_path": library_path,
        }
    finally:
        if lib_json_tmp.exists():
            lib_json_tmp.unlink()
