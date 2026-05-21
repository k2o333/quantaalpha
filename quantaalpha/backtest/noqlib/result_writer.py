"""No-qlib 结果落盘。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from quantaalpha.backtest.artifacts import (
    write_cumulative_excess_parquet,
    write_daily_report_parquet,
    write_positions_parquet,
)


def save_results(
    *,
    config: dict[str, Any],
    metrics: dict[str, Any],
    exp_name: str,
    factor_source: str,
    num_factors: int,
    elapsed: float,
    output_name: str | None,
    daily_report: pd.DataFrame | None = None,
    positions: pd.DataFrame | None = None,
    backend: str = "noqlib",
) -> Path:
    """保存与 qlib BacktestRunner 兼容的 metrics JSON。"""
    output_dir = Path(config.get("experiment", {}).get("output_dir", "./backtest_v2_results"))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = f"{output_name}_backtest_metrics.json" if output_name else config.get("experiment", {}).get("output_metrics_file", "backtest_metrics.json")
    output_path = output_dir / output_file
    result_data = {
        "experiment_name": exp_name,
        "factor_source": factor_source,
        "num_factors": num_factors,
        "metrics": metrics,
        "config": {
            "data_range": f"{config.get('data', {}).get('start_time')} ~ {config.get('data', {}).get('end_time')}",
            "test_range": _segment_text(config, "test"),
            "backtest_range": f"{config.get('backtest', {}).get('backtest', {}).get('start_time')} ~ {config.get('backtest', {}).get('backtest', {}).get('end_time')}",
            "market": config.get("data", {}).get("market"),
            "benchmark": config.get("backtest", {}).get("backtest", {}).get("benchmark"),
        },
        "elapsed_seconds": elapsed,
        "backend": backend,
    }
    output_path.write_text(json.dumps(_json_safe(result_data), ensure_ascii=False, indent=2), encoding="utf-8")
    if daily_report is not None and not daily_report.empty:
        prefix = output_name if output_name else exp_name
        write_daily_report_parquet(daily_report, output_dir, prefix)
        write_cumulative_excess_parquet(daily_report, output_dir, prefix)
    if positions is not None and not positions.empty:
        prefix = output_name if output_name else exp_name
        write_positions_parquet(positions, output_dir, prefix)
    return output_path


def _segment_text(config: dict[str, Any], name: str) -> str:
    segment = config.get("dataset", {}).get("segments", {}).get(name, ["", ""])
    return f"{segment[0]} ~ {segment[1]}"


def _json_safe(value):
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
        return 0.0
    return value
