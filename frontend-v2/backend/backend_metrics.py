"""Metric loading helpers for the QuantaAlpha frontend backend."""

from __future__ import annotations

import glob
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import yaml


def load_backtest_results(task: Dict[str, Any], project_root: Path) -> None:
    """Try to load backtest result metrics from the output directory."""
    try:
        config_path = task.get("config", {}).get("configPath") or str(project_root / "configs" / "backtest.yaml")
        with open(config_path, "r") as f:
            bt_config = yaml.safe_load(f)
        output_dir_raw = bt_config.get("experiment", {}).get("output_dir", "data/results/backtest_v2_results")
        # Resolve relative output_dir against project_root (run_backtest runs with cwd=project_root)
        output_dir = Path(output_dir_raw)
        if not output_dir.is_absolute():
            output_dir = project_root / output_dir
        output_dir_str = str(output_dir)

        # Look for most recent metrics JSON
        metrics_files = sorted(
            glob.glob(os.path.join(output_dir_str, "*_backtest_metrics.json")),
            key=os.path.getmtime,
            reverse=True,
        )
        if metrics_files:
            with open(metrics_files[0], "r") as f:
                metrics_data = json.load(f)
            # The JSON has a nested structure: { metrics: {...}, config: {...}, ... }
            # Flatten: put the inner metrics dict at the top level for the frontend,
            # but also keep meta fields like experiment_name and elapsed_seconds.
            inner_metrics = metrics_data.get("metrics", {})
            flat = {**inner_metrics}
            # Carry over useful metadata
            for key in ("experiment_name", "factor_source", "num_factors", "config", "elapsed_seconds"):
                if key in metrics_data:
                    flat[f"__{key}"] = metrics_data[key]

            # Load cumulative excess return data from CSV
            csv_path = metrics_files[0].replace("_backtest_metrics.json", "_cumulative_excess.csv")
            if os.path.exists(csv_path):
                import pandas as pd

                df = pd.read_csv(csv_path)
                if "date" in df.columns and "cumulative_excess_return" in df.columns:
                    cumulative_data = df[["date", "cumulative_excess_return"]].to_dict("records")
                    flat["cumulative_curve"] = [{"date": r["date"], "value": r["cumulative_excess_return"]} for r in cumulative_data]

            task["metrics"] = flat
    except Exception as e:
        import traceback

        traceback.print_exc()  # print for debugging, but don't crash


def update_mining_metrics(
    task: Dict[str, Any],
    project_root: Path,
    find_factor_jsons,
    load_factor_library,
    classify_quality,
) -> None:
    """
    Update mining task metrics from the generated factor library.
    Calculates best factor stats and extracts top 10 factors.
    """
    jsons = find_factor_jsons()
    # Prefer library with matching suffix if configured
    target_lib = None
    config = task.get("config", {})
    suffix = config.get("librarySuffix")

    if suffix:
        candidate = project_root / "data" / "factorlib" / f"all_factors_library_{suffix}.json"
        # Fix: If suffix is specified, we ONLY look at this file.
        # If it doesn't exist yet, it means no factors have been mined yet for this task.
        if candidate.exists():
            target_lib = str(candidate)
        else:
            # Task specific file not found -> assume empty state
            return

    elif jsons:
        # No suffix provided, fallback to latest existing library (legacy behavior)
        target_lib = jsons[0]

    if not target_lib:
        return

    # Check modification time
    try:
        mtime = os.path.getmtime(target_lib)
        created_at_str = task.get("createdAt")
        if created_at_str:
            created_at_dt = datetime.fromisoformat(created_at_str)
            # Add a small buffer (e.g. 1 second) to avoid race conditions where file is created immediately
            if mtime < created_at_dt.timestamp():
                # File is older than the task -> ignore it
                return
    except Exception:
        pass

    try:
        lib = load_factor_library(target_lib)
        factors = lib.get("factors", {})

        # 1. Update basic stats
        total = len(factors)
        task["metrics"]["totalFactors"] = total

        high = medium = low = 0
        factor_list = []

        for f_id, f_info in factors.items():
            # Check if this factor was created after task start
            # If we are using a shared library file (unlikely with new logic, but possible if user forces it),
            # we must ensure we don't display old factors.
            try:
                added_at_str = f_info.get("added_at", "")
                created_at_str = task.get("createdAt", "")
                if added_at_str and created_at_str:
                    # Parse timestamps
                    # added_at usually in isoformat
                    added_at_dt = datetime.fromisoformat(added_at_str)
                    created_at_dt = datetime.fromisoformat(created_at_str)
                    if added_at_dt < created_at_dt:
                        continue
            except Exception:
                pass  # If date parsing fails, be permissive or conservative? Permissive for now.

            bt = f_info.get("backtest_results", {})
            q = classify_quality(bt)
            if q == "high":
                high += 1
            elif q == "medium":
                medium += 1
            else:
                low += 1

            # Prepare for top 10 list
            # Normalize metrics
            ic = bt.get("IC", bt.get("1day.excess_return_without_cost.information_coefficient", 0))
            icir = bt.get("ICIR", bt.get("1day.excess_return_without_cost.information_coefficient_ir", 0))
            rank_ic = bt.get("Rank IC", bt.get("rank_ic", bt.get("1day.excess_return_without_cost.rank_ic", 0)))
            rank_icir = bt.get("Rank ICIR", bt.get("rank_ic_ir", bt.get("1day.excess_return_without_cost.rank_ic_ir", 0)))

            # Generate a mock equity curve for preview if real data is missing
            # In production, this should come from actual backtest result files (CSV/H5)
            # Here we generate a simple random walk with drift matching the annual return to show visual difference
            cumulative_curve = []
            annual_ret = bt.get("1day.excess_return_without_cost.annualized_return", 0)
            max_dd = bt.get("1day.excess_return_with_cost.max_drawdown", bt.get("1day.excess_return_without_cost.max_drawdown", 0))

            # Calmar Ratio = Annual Return / Max Drawdown (absolute value)
            # Avoid division by zero
            cr = 0
            if max_dd < 0:
                cr = annual_ret / abs(max_dd)
            elif max_dd > 0:
                cr = annual_ret / max_dd

            # Simple simulation: 20 data points for preview sparkline
            import random

            current_val = 1.0
            # Daily drift approx
            drift = (1 + annual_ret) ** (1 / 252) - 1 if annual_ret else 0
            vol = 0.02  # Assumed daily vol

            # Use factor name hash to seed random for consistency
            random.seed(hash(f_info.get("factor_name", f_id)))

            for i in range(20):
                # Generate last 20 points
                ret = random.gauss(drift, vol)
                current_val *= 1 + ret
                cumulative_curve.append({"value": current_val, "date": f"Day {i + 1}"})

            factor_list.append(
                {
                    "factorName": f_info.get("factor_name", f_id),
                    "factorExpression": f_info.get("factor_expression", ""),
                    "rankIc": rank_ic,
                    "rankIcir": rank_icir,
                    "ic": ic,
                    "icir": icir,
                    "annualReturn": annual_ret,
                    "sharpeRatio": bt.get("1day.excess_return_with_cost.information_ratio", bt.get("1day.excess_return_without_cost.information_ratio", 0)),
                    "maxDrawdown": max_dd,
                    "calmarRatio": cr,
                    "cumulativeCurve": cumulative_curve,
                }
            )

        task["metrics"]["highQualityFactors"] = high
        task["metrics"]["mediumQualityFactors"] = medium
        task["metrics"]["lowQualityFactors"] = low

        # 2. Find best factor
        if factor_list:
            # Sort by RankIC desc
            factor_list.sort(key=lambda x: x["rankIc"], reverse=True)
            best = factor_list[0]

            # Update task metrics with best factor's stats
            task["metrics"]["annualReturn"] = best["annualReturn"]
            task["metrics"]["rankIc"] = best["rankIc"]
            task["metrics"]["sharpeRatio"] = best["sharpeRatio"]
            task["metrics"]["maxDrawdown"] = best["maxDrawdown"]
            task["metrics"]["factorName"] = best["factorName"]

            # 3. Top 10 Factors
            task["metrics"]["top10Factors"] = factor_list[:10]

    except Exception:
        pass  # Best effort
