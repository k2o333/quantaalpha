"""Reporting helpers for :mod:`quantaalpha.backtest.runner`."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Mapping

logger = logging.getLogger(__name__)


def print_results(metrics: Mapping[str, Any], total_time: float) -> None:
    """Print the qlib runner summary."""

    def _f(val, fmt=".6f"):
        return format(val, fmt) if isinstance(val, (int, float)) else "N/A"

    print(f"\n{'=' * 50}")
    print("Backtest Results")
    print(f"{'=' * 50}")
    print("[IC Metrics]")
    print(f"  IC: {_f(metrics.get('IC'))}  ICIR: {_f(metrics.get('ICIR'))}")
    print(
        f"  Rank IC: {_f(metrics.get('Rank IC'))}  Rank ICIR: {_f(metrics.get('Rank ICIR'))}"
    )
    print("[Strategy Metrics]")
    print(
        f"  Ann. Return: {_f(metrics.get('annualized_return'), '.4f')}  Max DD: {_f(metrics.get('max_drawdown'), '.4f')}"
    )
    print(
        f"  Info Ratio: {_f(metrics.get('information_ratio'), '.4f')}  Calmar: {_f(metrics.get('calmar_ratio'), '.4f')}"
    )
    print(f"Total time: {total_time:.1f}s")
    print(f"{'=' * 50}")


def save_results(
    *,
    config: Mapping[str, Any],
    metrics: Mapping[str, Any],
    exp_name: str,
    factor_source: str,
    num_factors: int,
    elapsed: float,
    output_name: str | None = None,
    active_universe_metadata: Mapping[str, Any] | None = None,
) -> None:
    """Save qlib runner metrics and append batch summary."""
    output_dir = Path(config["experiment"].get("output_dir", "./backtest_v2_results"))
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = (
        f"{output_name}_backtest_metrics.json"
        if output_name
        else config["experiment"]["output_metrics_file"]
    )
    output_path = output_dir / output_file

    result_data: dict[str, Any] = {
        "experiment_name": exp_name,
        "factor_source": factor_source,
        "num_factors": num_factors,
        "metrics": dict(metrics),
        "config": {
            "data_range": f"{config['data']['start_time']} ~ {config['data']['end_time']}",
            "test_range": f"{config['dataset']['segments']['test'][0]} ~ {config['dataset']['segments']['test'][1]}",
            "backtest_range": f"{config['backtest']['backtest']['start_time']} ~ {config['backtest']['backtest']['end_time']}",
            "market": config["data"]["market"],
            "benchmark": config["backtest"]["backtest"]["benchmark"],
        },
        "elapsed_seconds": elapsed,
    }
    if active_universe_metadata:
        result_data["universe"] = dict(active_universe_metadata)

    output_path.write_text(
        json.dumps(result_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Results saved: {output_path}")
    summary_file = output_dir / "batch_summary.json"
    summary_data = []
    if summary_file.exists():
        try:
            summary_data = json.loads(summary_file.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            summary_data = []

    ann_ret = metrics.get("annualized_return")
    mdd = metrics.get("max_drawdown")
    calmar_ratio = None
    if ann_ret is not None and mdd is not None and mdd != 0:
        calmar_ratio = ann_ret / abs(mdd)

    summary_data.append(
        {
            "name": output_name or exp_name,
            "num_factors": num_factors,
            "IC": metrics.get("IC"),
            "ICIR": metrics.get("ICIR"),
            "Rank_IC": metrics.get("Rank IC"),
            "Rank_ICIR": metrics.get("Rank ICIR"),
            "annualized_return": ann_ret,
            "information_ratio": metrics.get("information_ratio"),
            "max_drawdown": mdd,
            "calmar_ratio": calmar_ratio,
            "elapsed_seconds": elapsed,
        }
    )
    summary_file.write_text(
        json.dumps(summary_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    logger.debug("Appended to summary: %s", summary_file)
