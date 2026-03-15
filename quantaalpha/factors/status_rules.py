from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any


DEFAULT_FACTOR_STATUS_CONFIG = {
    "stale_threshold_days": 30,
    "degraded_stability_threshold": 0.3,
    "active_stability_threshold": 0.5,
    "consecutive_failures_to_deprecate": 3,
}


def update_factor_status(
    factor_entry: dict[str, Any],
    validation_result: dict[str, Any] | None,
    now: datetime | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = {**DEFAULT_FACTOR_STATUS_CONFIG, **(config or {})}
    entry = deepcopy(factor_entry)
    evaluation = entry.setdefault("evaluation", {})
    evaluation.setdefault("status", "pending_validation")
    evaluation.setdefault("last_validated", None)
    evaluation.setdefault("stability_score", None)
    evaluation.setdefault("period_results", [])
    evaluation.setdefault("validation_summary", "")
    evaluation.setdefault("consecutive_failures", 0)

    current_now = now or datetime.now()
    status = evaluation["status"]

    if validation_result is not None:
        success = validation_result.get("status", "success") == "success"
        summary = validation_result.get("summary", validation_result)
        evaluation["last_validated"] = current_now.isoformat()
        evaluation["period_results"] = validation_result.get("period_results", evaluation.get("period_results", []))
        evaluation["stability_score"] = summary.get("stability_score")
        evaluation["validation_summary"] = summary.get("validation_summary", "")
        if success:
            evaluation["consecutive_failures"] = 0
            stability = summary.get("stability_score")
            if stability is not None and stability < cfg["degraded_stability_threshold"]:
                status = "degraded"
            else:
                status = "active"
        else:
            evaluation["consecutive_failures"] = int(evaluation.get("consecutive_failures", 0)) + 1
            if evaluation["consecutive_failures"] >= cfg["consecutive_failures_to_deprecate"]:
                status = "deprecated"
            elif status == "active":
                status = "degraded"

    last_validated = evaluation.get("last_validated")
    if status == "active" and last_validated:
        try:
            validated_at = datetime.fromisoformat(str(last_validated))
            if (current_now - validated_at).days >= int(cfg["stale_threshold_days"]):
                status = "stale"
        except ValueError:
            pass

    evaluation["status"] = status
    entry["evaluation"] = evaluation
    return entry
