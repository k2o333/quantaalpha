from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any


# Solidified factor status thresholds
DEFAULT_FACTOR_STATUS_CONFIG = {
    "stale_threshold_days": 30,           # Factor becomes stale if not validated within 30 days
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
    """
    Update factor evaluation status based on new validation results.
    
    State transitions:
    - pending_validation -> active (success + stability >= threshold)
    - pending_validation -> degraded (success + stability < threshold OR failure)
    - active -> degraded (failure OR stability drop)
    - active -> stale (time threshold)
    - degraded -> active (success + stability >= threshold)
    - degraded -> deprecated (consecutive failures)
    """
    cfg = {**DEFAULT_FACTOR_STATUS_CONFIG, **(config or {})}
    entry = deepcopy(factor_entry)
    evaluation = entry.setdefault("evaluation", {})
    
    # Initialize evaluation fields if missing
    evaluation.setdefault("status", "pending_validation")
    evaluation.setdefault("last_validated", None)
    evaluation.setdefault("stability_score", None)
    evaluation.setdefault("period_results", [])
    evaluation.setdefault("validation_summary", "")
    evaluation.setdefault("consecutive_failures", 0)

    current_now = now or datetime.now()
    prev_status = evaluation["status"]
    status = prev_status

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
            # Solidified active threshold check
            if stability is not None and stability >= cfg["active_stability_threshold"]:
                status = "active"
            elif stability is not None and stability < cfg["degraded_stability_threshold"]:
                status = "degraded"
            elif prev_status == "active" and stability is not None and stability < cfg["active_stability_threshold"]:
                # If was active but now stability is between degraded and active threshold
                status = "degraded"
            elif prev_status == "pending_validation" and stability is not None and stability < cfg["active_stability_threshold"]:
                status = "degraded"
        else:
            evaluation["consecutive_failures"] = int(evaluation.get("consecutive_failures", 0)) + 1
            if evaluation["consecutive_failures"] >= cfg["consecutive_failures_to_deprecate"]:
                status = "deprecated"
            elif status == "active":
                status = "degraded"
            elif status == "stale":
                status = "degraded"

    # Stale check only applies to active factors
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
