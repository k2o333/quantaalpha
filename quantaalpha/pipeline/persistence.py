import datetime
import hashlib
import json
import re
import shutil
from pathlib import Path
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


def _extract_backtest_metric_payload(result: Any) -> dict[str, float | None]:
    """Extract durable backtest metrics for factor-library persistence."""
    return {
        "IC": _extract_metric(result, "IC"),
        "ICIR": _extract_metric(result, "ICIR"),
        "Rank IC": _extract_first_metric(result, ("Rank IC", "RankIC", "rank_ic", "rank_ic_mean")),
        "Rank ICIR": _extract_first_metric(result, ("Rank ICIR", "RankICIR", "rank_icir")),
        "annualized_return": _extract_first_metric(
            result,
            (
                "1day.excess_return_with_cost.annualized_return",
                "annualized_return",
                "Annualized Return",
            ),
        ),
        "information_ratio": _extract_first_metric(
            result,
            (
                "1day.excess_return_with_cost.information_ratio",
                "information_ratio",
                "Information Ratio",
                "Sharpe",
                "sharpe",
            ),
        ),
        "max_drawdown": _extract_first_metric(
            result,
            (
                "1day.excess_return_with_cost.max_drawdown",
                "max_drawdown",
                "Max Drawdown",
            ),
        ),
        "signal_aligned_rows": _extract_metric(result, "signal_aligned_rows"),
        "signal_active_days": _extract_metric(result, "signal_active_days"),
        "signal_mean_cross_section_size": _extract_metric(result, "signal_mean_cross_section_size"),
        "signal_valid_ratio": _extract_metric(result, "signal_valid_ratio"),
    }


def _quality_gate_status(
    metrics: dict[str, float | None],
    quality_gate_config: dict | None,
) -> tuple[str, dict[str, Any]]:
    """Assign explicit factor lifecycle status from configured promotion gates."""
    if not quality_gate_config:
        return "pending_validation", {"enabled": False, "reason": "quality_gate_config_missing"}

    cfg = dict(quality_gate_config or {})
    persistence_cfg = dict(cfg.get("persistence") or {})
    promotion_cfg = dict(cfg.get("promotion") or {})
    below_status = str(persistence_cfg.get("below_threshold") or "candidate")
    missing_status = str(persistence_cfg.get("missing_metrics") or "rejected")
    active_status = str(promotion_cfg.get("status") or "active")

    min_rank_ic = float(promotion_cfg.get("min_rank_ic", cfg.get("min_rank_ic", 0.03)) or 0.0)
    min_information_ratio = promotion_cfg.get("min_information_ratio", cfg.get("min_information_ratio"))
    if min_information_ratio is None:
        min_information_ratio = cfg.get("min_sharpe", 0.3)
    min_information_ratio = float(min_information_ratio or 0.0)

    required_thresholds = {
        "rank_ic": ("Rank IC", min_rank_ic),
        "information_ratio": ("information_ratio", min_information_ratio),
    }
    optional_capacity_thresholds = {
        "signal_valid_ratio": "min_signal_valid_ratio",
        "signal_active_days": "min_signal_active_days",
        "signal_mean_cross_section_size": "min_signal_mean_cross_section_size",
    }
    for metric_key, threshold_key in optional_capacity_thresholds.items():
        if threshold_key in promotion_cfg:
            required_thresholds[metric_key] = (metric_key, float(promotion_cfg.get(threshold_key) or 0.0))

    extracted_values = {
        decision_key: metrics.get(metric_key)
        for decision_key, (metric_key, _threshold) in required_thresholds.items()
    }
    rank_ic = extracted_values["rank_ic"]
    information_ratio = extracted_values["information_ratio"]
    decision = {
        "enabled": True,
        "min_rank_ic": min_rank_ic,
        "min_information_ratio": min_information_ratio,
        **{
            f"min_{decision_key}": threshold
            for decision_key, (_metric_key, threshold) in required_thresholds.items()
            if decision_key not in {"rank_ic", "information_ratio"}
        },
        **extracted_values,
    }
    missing_metrics = [
        metric_key
        for decision_key, (metric_key, _threshold) in required_thresholds.items()
        if extracted_values[decision_key] is None
    ]
    if missing_metrics:
        decision.update(
            {
                "status": missing_status,
                "reason": "missing_required_metrics",
                "missing_metrics": missing_metrics,
            }
        )
        return missing_status, decision
    below_metrics = [
        metric_key
        for decision_key, (metric_key, threshold) in required_thresholds.items()
        if float(extracted_values[decision_key]) < threshold
    ]
    if not below_metrics:
        decision.update({"status": active_status, "reason": "passed_promotion_gate"})
        return active_status, decision
    decision.update(
        {
            "status": below_status,
            "reason": "below_promotion_gate",
            "below_metrics": below_metrics,
        }
    )
    return below_status, decision


def _round_summary_value(round_summary, key: str, default=None):
    if round_summary is None:
        return default
    if isinstance(round_summary, dict):
        return round_summary.get(key, default)
    return getattr(round_summary, key, default)


def _write_workspace_audit_summary(
    *,
    audit_dir: str | Path,
    factor_id: str,
    factor_name: str,
    factor_expression: str,
    status: str,
    reason: str,
    workspace_path: str | Path | None,
    details: dict[str, Any] | None = None,
) -> Path:
    target_dir = Path(audit_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{factor_id}.{status}.json"
    payload = {
        "factor_id": factor_id,
        "factor_name": factor_name,
        "factor_expression_hash": hashlib.sha256(str(factor_expression).encode()).hexdigest()[:16],
        "status": status,
        "reason": reason,
        "workspace_path": str(workspace_path) if workspace_path else "",
        "details": details or {},
        "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }
    target.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return target


def _delete_workspace_path(workspace_path: str | Path | None) -> bool:
    if not workspace_path:
        return False
    path = Path(workspace_path)
    if not path.exists():
        return True
    if not path.is_dir():
        return False
    shutil.rmtree(path, ignore_errors=False)
    return not path.exists()


def _fingerprint_factor_value_file(path: str | Path) -> str:
    import polars as pl

    frame = (
        pl.read_parquet(path)
        .select(["trade_date", "instrument", "factor_id", "factor_value"])
        .sort(["trade_date", "instrument", "factor_id"])
    )
    payload = frame.write_csv()
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _metric_isolation_status(fingerprints: dict[str, str], factor_count: int) -> str:
    if factor_count < 2:
        return "not_required"
    if len(fingerprints) < factor_count:
        return "incomplete"
    if len(set(fingerprints.values())) < len(fingerprints):
        return "collision_possible"
    return "isolated"


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
    quality_gate_config: dict | None = None,
    factor_value_dir: str | None = None,
    publish_factor_values_on_pass: bool = True,
    failed_workspace_retention: str = "full",
    passed_workspace_retention: str = "keep",
):
    """Save factors from experiment to the Parquet factor library."""
    from quantaalpha.factors.factor_store_facade import FactorStoreFacade
    from quantaalpha.factors.factor_values import publish_factor_values_from_workspace

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
    backtest_metrics = _extract_backtest_metric_payload(getattr(experiment, "result", None))
    filtered_backtest_metrics = {key: value for key, value in backtest_metrics.items() if value is not None}

    skipped = 0
    lifecycle_counts = {"evaluated": 0, "active_promoted": 0, "candidate_only": 0, "rejected": 0}
    value_publication_enabled = bool(factor_value_dir) and bool(publish_factor_values_on_pass)
    value_publication = {
        "enabled": value_publication_enabled,
        "published": 0,
        "skipped": 0,
        "failed": 0,
    }
    metric_isolation = {
        "factor_count": len(sub_tasks),
        "metric_signature": dict(filtered_backtest_metrics),
        "factor_value_fingerprints": {},
        "status": "not_required",
    }
    workspace_cleanup_enabled = failed_workspace_retention == "summary_only" or passed_workspace_retention == "delete_after_publish"
    workspace_cleanup = {
        "enabled": workspace_cleanup_enabled,
        "deleted": 0,
        "retained": 0,
        "failed": 0,
    }
    sub_workspaces = getattr(experiment, "sub_workspace_list", []) or []
    audit_dir = Path(parquet_store_path) / "artifact_audit"
    for idx, task in enumerate(sub_tasks):
        factor_name = getattr(task, "factor_name", getattr(task, "name", f"factor_{idx}"))
        factor_expr = getattr(task, "factor_expression", "")
        factor_desc = getattr(task, "factor_description", getattr(task, "description", ""))

        factor_id = hashlib.md5(f"{factor_name}_{factor_expr}".encode()).hexdigest()[:16]
        workspace = sub_workspaces[idx] if idx < len(sub_workspaces) else None
        workspace_path = getattr(workspace, "workspace_path", None) if workspace is not None else None
        if has_factor_tracking and factor_id not in successful_ids:
            if failed_workspace_retention == "summary_only":
                try:
                    _write_workspace_audit_summary(
                        audit_dir=audit_dir,
                        factor_id=factor_id,
                        factor_name=factor_name,
                        factor_expression=factor_expr,
                        status="failure",
                        reason="; ".join((_round_summary_value(round_summary, "failed_reasons", {}) or {}).get(factor_id, []))
                        or "factor failed before persistence",
                        workspace_path=workspace_path,
                    )
                    if _delete_workspace_path(workspace_path):
                        workspace_cleanup["deleted"] += 1
                    else:
                        workspace_cleanup["failed"] += 1
                except Exception as exc:
                    workspace_cleanup["failed"] += 1
                    logger.warning(f"Failed to clean failed factor workspace for {factor_name} ({factor_id}): {exc}")
            elif workspace_cleanup_enabled:
                workspace_cleanup["retained"] += 1
            skipped += 1
            logger.info(f"Skipping failed factor during Parquet save: {factor_name} ({factor_id})")
            continue

        expression_hash = hashlib.sha256(factor_expr.encode()).hexdigest()[:16]
        lifecycle_status, lifecycle_decision = _quality_gate_status(
            backtest_metrics,
            quality_gate_config,
        )
        lifecycle_counts["evaluated"] += 1
        if lifecycle_status == "active":
            lifecycle_counts["active_promoted"] += 1
            logger.info(
                "quality_gate: promoted active "
                f"factor={factor_name} rank_ic={lifecycle_decision.get('rank_ic')} "
                f"information_ratio={lifecycle_decision.get('information_ratio')}"
            )
        elif lifecycle_status == "candidate":
            lifecycle_counts["candidate_only"] += 1
            logger.info(
                "quality_gate: stored candidate "
                f"factor={factor_name} rank_ic={lifecycle_decision.get('rank_ic')} "
                f"information_ratio={lifecycle_decision.get('information_ratio')}"
            )
        elif lifecycle_status == "rejected":
            lifecycle_counts["rejected"] += 1
            logger.info(
                "quality_gate: rejected "
                f"factor={factor_name} reason={lifecycle_decision.get('reason')} "
                f"rank_ic={lifecycle_decision.get('rank_ic')} "
                f"information_ratio={lifecycle_decision.get('information_ratio')}"
            )

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
            "quality_gate_decision": lifecycle_decision,
        }

        entry = {
            "factor_id": factor_id,
            "factor_name": factor_name,
            "factor_expression": factor_expr,
            "factor_expression_normalized": factor_expr,
            "expression_hash": expression_hash,
            "evaluation_status": lifecycle_status,
            "created_at": now_iso,
            "updated_at": now_iso,
            "sequence": base_sequence + idx,
            "op": "upsert",
            "tags_json": json.dumps([]),
            "metadata_json": json.dumps(metadata),
            "backtest_results_json": json.dumps(filtered_backtest_metrics),
        }
        store.write_factor(entry)

        current_value_published = False
        if value_publication_enabled:
            if lifecycle_status != "active":
                value_publication["skipped"] += 1
            elif not workspace_path:
                value_publication["failed"] += 1
                logger.warning(f"Cannot publish factor values without workspace path: {factor_name} ({factor_id})")
            else:
                try:
                    publication = publish_factor_values_from_workspace(
                        workspace_path=workspace_path,
                        factor_name=factor_name,
                        factor_id=factor_id,
                        output_dir=factor_value_dir,
                        metadata={
                            "experiment_id": experiment_id,
                            "round_number": round_number,
                            "evolution_phase": evolution_phase,
                            "trajectory_id": trajectory_id,
                        },
                    )
                    metric_isolation["factor_value_fingerprints"][factor_id] = _fingerprint_factor_value_file(
                        publication.output_path
                    )
                    value_publication["published"] += 1
                    current_value_published = True
                except Exception as exc:
                    value_publication["failed"] += 1
                    logger.warning(f"Failed to publish factor values for {factor_name} ({factor_id}): {exc}")

        if workspace_cleanup_enabled:
            should_delete_passed = (
                lifecycle_status == "active"
                and passed_workspace_retention == "delete_after_publish"
                and current_value_published
            )
            should_delete_non_passed = lifecycle_status != "active" and failed_workspace_retention == "summary_only"
            if should_delete_non_passed:
                _write_workspace_audit_summary(
                    audit_dir=audit_dir,
                    factor_id=factor_id,
                    factor_name=factor_name,
                    factor_expression=factor_expr,
                    status=lifecycle_status,
                    reason=str(lifecycle_decision.get("reason") or lifecycle_status),
                    workspace_path=workspace_path,
                    details=lifecycle_decision,
                )
            if should_delete_passed or should_delete_non_passed:
                try:
                    if _delete_workspace_path(workspace_path):
                        workspace_cleanup["deleted"] += 1
                    else:
                        workspace_cleanup["failed"] += 1
                except Exception as exc:
                    workspace_cleanup["failed"] += 1
                    logger.warning(f"Failed to delete factor workspace for {factor_name} ({factor_id}): {exc}")
            else:
                workspace_cleanup["retained"] += 1

    saved = len(sub_tasks) - skipped
    logger.info(f"Saved {saved} factors to Parquet store: {parquet_store_path}")
    compact_result = maybe_compact_after_save(store, compact_config)
    compact_result["quality_gate_lifecycle"] = lifecycle_counts
    compact_result["best_metrics"] = filtered_backtest_metrics
    metric_isolation["status"] = _metric_isolation_status(
        metric_isolation["factor_value_fingerprints"],
        len(sub_tasks) - skipped,
    )
    compact_result["metric_isolation"] = metric_isolation
    compact_result["factor_value_publication"] = value_publication
    compact_result["workspace_cleanup"] = workspace_cleanup
    return compact_result


def get_cross_run_historical_best_reference(parquet_store_path: str) -> dict[str, Any]:
    """Return active-factor historical best metrics for feedback prompt context."""
    result: dict[str, Any] = {
        "available": False,
        "total_active": 0,
        "best_rank_ic": None,
        "best_information_ratio": None,
        "best_rank_ic_factor_name": None,
        "best_information_ratio_factor_name": None,
    }
    try:
        from quantaalpha.factors.factor_store_facade import FactorStoreFacade

        store = FactorStoreFacade(store_path=str(parquet_store_path))
        records = store.read_effective_factor_records()
        active_records = [r for r in records if str(r.get("evaluation_status") or "") == "active"]
        result["total_active"] = len(active_records)

        best_rank_ic = -float("inf")
        best_ir = -float("inf")
        best_rank_ic_name = None
        best_ir_name = None

        for rec in active_records:
            name = rec.get("factor_name") or rec.get("factor_id") or "unknown"
            backtest_json = rec.get("backtest_results_json", "{}")
            try:
                backtest = json.loads(backtest_json) if isinstance(backtest_json, str) else backtest_json
            except (TypeError, json.JSONDecodeError):
                backtest = {}
            if not isinstance(backtest, dict):
                backtest = {}

            rank_ic = _coerce_float(
                backtest.get("Rank IC")
                or backtest.get("RankIC")
                or backtest.get("rank_ic")
                or backtest.get("rank_ic_mean")
            )
            if rank_ic is not None and rank_ic > best_rank_ic:
                best_rank_ic = float(rank_ic)
                best_rank_ic_name = name

            information_ratio = _coerce_float(
                backtest.get("information_ratio")
                or backtest.get("1day.excess_return_with_cost.information_ratio")
                or backtest.get("1day.excess_return_without_cost.information_ratio")
                or backtest.get("Information Ratio")
                or backtest.get("Sharpe")
                or backtest.get("sharpe")
            )
            if information_ratio is not None and information_ratio > best_ir:
                best_ir = float(information_ratio)
                best_ir_name = name

        if best_rank_ic > -float("inf"):
            result["best_rank_ic"] = best_rank_ic
            result["best_rank_ic_factor_name"] = best_rank_ic_name
            result["available"] = True
        if best_ir > -float("inf"):
            result["best_information_ratio"] = best_ir
            result["best_information_ratio_factor_name"] = best_ir_name
            result["available"] = True

    except Exception as exc:
        logger.warning(f"Failed to query cross-run historical best: {exc}")

    return result


def _coerce_float(value: Any) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None
