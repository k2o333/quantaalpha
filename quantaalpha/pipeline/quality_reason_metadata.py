"""Fine-grained quality reason compatibility metadata."""

from __future__ import annotations


def legacy_reason_to_quality_reason(reason: str) -> str:
    """Map legacy quality-overlay reason strings to stable enum values."""
    from quantaalpha.factors.failure_tracker import QualityFailureReason

    mapping = {
        "lookahead_risk": QualityFailureReason.LOOKAHEAD_DETECTED.value,
        "too_many_nan": QualityFailureReason.TOO_MANY_NAN.value,
        "constant_signal": QualityFailureReason.CONSTANT_SIGNAL.value,
        "high_similarity": QualityFailureReason.HIGH_SIMILARITY.value,
        "high_turnover": QualityFailureReason.HIGH_TURNOVER.value,
        "weak_oos_ic": QualityFailureReason.WEAK_OOS_IC.value,
        "weak_ic": QualityFailureReason.WEAK_OOS_IC.value,
    }
    return mapping.get(str(reason or ""), QualityFailureReason.UNKNOWN.value)


def quality_reason_metadata(reason: str) -> dict[str, str]:
    """Return stable group and severity metadata for a fine-grained reason."""
    high = {"LOOKAHEAD_DETECTED", "ANTI_PATTERN_DETECTED"}
    medium = {"LOW_COVERAGE", "TOO_MANY_NAN", "CONSTANT_SIGNAL", "EXTREME_VALUE_SIGNAL", "HIGH_SIMILARITY"}
    groups = {
        "LOOKAHEAD_DETECTED": "data_leakage",
        "ANTI_PATTERN_DETECTED": "data_leakage",
        "LOW_COVERAGE": "data_quality",
        "TOO_MANY_NAN": "data_quality",
        "CONSTANT_SIGNAL": "signal_shape",
        "EXTREME_VALUE_SIGNAL": "signal_shape",
        "HIGH_SIMILARITY": "redundancy",
        "HIGH_TURNOVER": "tradability",
        "WEAK_OOS_IC": "predictive_power",
        "POOR_MONOTONICITY": "predictive_power",
    }
    return {
        "group": groups.get(str(reason), "unknown"),
        "severity": "high" if reason in high else "medium" if reason in medium else "low",
    }
