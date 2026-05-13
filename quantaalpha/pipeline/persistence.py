import datetime
import hashlib
import json
import re
from typing import Any, Iterable

import pandas as pd

from quantaalpha.log import logger


def maybe_compact_after_save(store, compact_config: dict | None) -> dict:
    """Maybe compact the Parquet store after a save batch."""
    cfg = compact_config or {}
    if not cfg.get("enabled", True):
        return {"triggered": False, "reason": "disabled"}
    if not cfg.get("compact_on_save_batch_end", True):
        return {"triggered": False, "reason": "batch_end_disabled"}

    threshold = int(cfg.get("delta_file_threshold", 100))
    if threshold <= 0:
        return {
            "triggered": False,
            "reason": "invalid_threshold",
            "delta_file_threshold": threshold,
        }

    delta_count = store.delta_file_count()
    if delta_count < threshold:
        return {
            "triggered": False,
            "reason": "below_threshold",
            "delta_count": delta_count,
            "delta_file_threshold": threshold,
        }

    try:
        if "archive_retention" in cfg:
            store.compact(archive_retention=cfg.get("archive_retention"))
        else:
            store.compact()
    except Exception as exc:
        logger.warning(f"Parquet factor compact failed after save: {exc}")
        return {
            "triggered": False,
            "reason": "compact_failed",
            "delta_count": delta_count,
            "delta_file_threshold": threshold,
            "error": str(exc),
        }

    return {
        "triggered": True,
        "reason": "delta_file_threshold",
        "delta_count": delta_count,
        "delta_file_threshold": threshold,
    }


def _parse_data_requirements(expression: str) -> dict[str, Any]:
    fields = sorted(set(re.findall(r"\$([A-Za-z_][A-Za-z0-9_]*)", expression or "")))
    return {
        "dimensions": ["price_volume"],
        "fields": fields,
        "data_frequency": "daily",
    }


def _extract_metric(result: Any, metric_name: str) -> float | None:
    if result is None:
        return None
    try:
        if isinstance(result, pd.Series):
            value = result.get(metric_name)
        elif isinstance(result, pd.DataFrame):
            if metric_name not in result.index:
                return None
            row = result.loc[metric_name]
            if isinstance(row, pd.Series):
                value = row.get("value", row.iloc[0] if len(row) else None)
            else:
                value = row
        else:
            return None
        if value is None or pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def _extract_first_metric(result: Any, metric_names: Iterable[str]) -> float | None:
    for metric_name in metric_names:
        value = _extract_metric(result, metric_name)
        if value is not None:
            return value
    return None


def _round_summary_value(round_summary, key: str, default=None):
    if round_summary is None:
        return default
    if isinstance(round_summary, dict):
        return round_summary.get(key, default)
    return getattr(round_summary, key, default)


def append_combined_backtest_performance_history(
    *,
    experiment,
    store,
    performance_history_config: dict,
    execution_periods: dict[str, tuple[str, str]] | None = None,
    round_summary=None,
    evolution_phase: str = "original",
    trajectory_id: str = "",
    round_number: int = 0,
) -> int:
    """Persist combined-backtest metrics for every factor in an experiment."""

    if experiment is None or store is None:
        return 0

    sub_tasks = getattr(experiment, "sub_tasks", []) or []
    if not sub_tasks:
        return 0

    result = getattr(experiment, "result", None)
    metrics = {
        "IC": _extract_metric(result, "IC"),
        "ICIR": _extract_metric(result, "ICIR"),
        "Rank IC": _extract_metric(result, "Rank IC"),
        "Rank ICIR": _extract_metric(result, "Rank ICIR"),
        "annualized_return": _extract_first_metric(
            result,
            (
                "1day.excess_return_with_cost.annualized_return",
                "annualized_return",
            ),
        ),
        "information_ratio": _extract_first_metric(
            result,
            (
                "1day.excess_return_with_cost.information_ratio",
                "information_ratio",
            ),
        ),
        "max_drawdown": _extract_first_metric(
            result,
            (
                "1day.excess_return_with_cost.max_drawdown",
                "max_drawdown",
            ),
        ),
    }

    successful_ids = set(_round_summary_value(round_summary, "successful_factor_ids", []) or [])
    failed_ids = set(_round_summary_value(round_summary, "failed_factor_ids", []) or [])
    failed_reasons = _round_summary_value(round_summary, "failed_reasons", {}) or {}
    has_factor_tracking = bool(successful_ids or failed_ids)

    from quantaalpha.factor_ops.performance_history import build_summary_row

    written = 0
    for idx, task in enumerate(sub_tasks):
        factor_name = getattr(task, "factor_name", getattr(task, "name", f"factor_{idx}"))
        factor_expression = getattr(task, "factor_expression", "")
        factor_id = hashlib.md5(f"{factor_name}_{factor_expression}".encode()).hexdigest()[:16]
        if has_factor_tracking and factor_id not in successful_ids:
            logger.info(f"Skipping failed factor during performance history save: {factor_name} ({factor_id})")
            continue
        if factor_id in successful_ids:
            status = "success"
            error_message = None
        elif factor_id in failed_ids:
            status = "failure"
            error_message = "; ".join(failed_reasons.get(factor_id, [])) or "factor failed before combined backtest"
        else:
            status = "success" if result is not None else "failure"
            error_message = None if result is not None else "combined backtest result missing"

        row = build_summary_row(
            factor_id=factor_id,
            factor_name=factor_name,
            factor_expression=factor_expression,
            translated_expression=factor_expression,
            source="mining_combined_backtest",
            validated_at=None,
            execution_periods=execution_periods,
            status=status,
            passed=status == "success",
            ic_mean=metrics["IC"],
            icir=metrics["ICIR"],
            rank_ic_mean=metrics["Rank IC"],
            rank_icir=metrics["Rank ICIR"],
            annualized_return=metrics["annualized_return"],
            information_ratio=metrics["information_ratio"],
            max_drawdown=metrics["max_drawdown"],
            run_id=trajectory_id or None,
            error_message=error_message,
            extra={
                "performance_scope": "combined_factor_backtest",
                "factor_count": len(sub_tasks),
                "evolution_phase": evolution_phase,
                "trajectory_id": trajectory_id,
                "round_number": round_number,
                "combined_metrics": metrics,
            },
        )
        store.append_summary(row)
        written += 1

    if written and performance_history_config.get("update_latest_snapshot", True):
        store.refresh_latest_by_factor()
    return written


def save_factors_to_parquet(
    experiment,
    parquet_store_path: str,
    experiment_id: str = "unknown",
    round_number: int = 0,
    hypothesis=None,
    feedback=None,
    initial_direction=None,
    user_initial_direction=None,
    planning_direction=None,
    evolution_phase: str = "original",
    trajectory_id: str = "",
    parent_trajectory_ids: list | None = None,
    compact_config: dict | None = None,
    round_summary=None,
):
    """Save factors from experiment to the Parquet factor library."""
    from quantaalpha.factors.factor_store_facade import FactorStoreFacade

    if experiment is None:
        logger.warning("experiment is None, skip saving factors")
        return None

    store = FactorStoreFacade(store_path=parquet_store_path)
    now_iso = datetime.datetime.now().isoformat()
    base_sequence = int(datetime.datetime.now(datetime.timezone.utc).timestamp() * 1_000_000)

    sub_tasks = getattr(experiment, "sub_tasks", []) or []
    successful_ids = set(_round_summary_value(round_summary, "successful_factor_ids", []) or [])
    failed_ids = set(_round_summary_value(round_summary, "failed_factor_ids", []) or [])
    has_factor_tracking = bool(successful_ids or failed_ids)

    skipped = 0
    for idx, task in enumerate(sub_tasks):
        factor_name = getattr(task, "factor_name", getattr(task, "name", f"factor_{idx}"))
        factor_expr = getattr(task, "factor_expression", "")
        factor_desc = getattr(task, "factor_description", getattr(task, "description", ""))

        factor_id = hashlib.md5(f"{factor_name}_{factor_expr}".encode()).hexdigest()[:16]
        if has_factor_tracking and factor_id not in successful_ids:
            skipped += 1
            logger.info(f"Skipping failed factor during Parquet save: {factor_name} ({factor_id})")
            continue

        expression_hash = hashlib.sha256(factor_expr.encode()).hexdigest()[:16]
        metadata = {
            "experiment_id": experiment_id,
            "round_number": round_number,
            "evolution_phase": evolution_phase,
            "trajectory_id": trajectory_id,
            "parent_trajectory_ids": parent_trajectory_ids or [],
            "hypothesis": str(hypothesis) if hypothesis else "",
            "initial_direction": initial_direction or "",
            "planning_direction": planning_direction or "",
            "created_at": now_iso,
            "factor_description": factor_desc,
            "field_schema_version": "1.0",
            "source": evolution_phase or "unknown",
            "data_requirements": _parse_data_requirements(factor_expr),
            "llm_model_version": "unknown",
            "prompt_template_hash": None,
            "parent_factor_id": None,
        }

        entry = {
            "factor_id": factor_id,
            "factor_name": factor_name,
            "factor_expression": factor_expr,
            "factor_expression_normalized": factor_expr,
            "expression_hash": expression_hash,
            "evaluation_status": "pending_validation",
            "created_at": now_iso,
            "updated_at": now_iso,
            "sequence": base_sequence + idx,
            "op": "upsert",
            "tags_json": json.dumps([]),
            "metadata_json": json.dumps(metadata),
            "backtest_results_json": json.dumps({}),
        }
        store.write_factor(entry)

    saved = len(sub_tasks) - skipped
    logger.info(f"Saved {saved} factors to Parquet store: {parquet_store_path}")
    return maybe_compact_after_save(store, compact_config)
