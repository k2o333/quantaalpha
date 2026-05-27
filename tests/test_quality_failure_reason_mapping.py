from quantaalpha.factors.failure_tracker import (
    FactorFailureTracker,
    FactorStatus,
    FailureReason,
    QualityFailureReason,
    quality_failure_reasons_from_diagnostics,
)


def test_factor_status_serializes_coarse_and_quality_failure_reasons():
    status = FactorStatus("id-1", "alpha_one", "RANK($close)")

    status.add_failure(FailureReason.QUALITY_GATE_FAILED, "cheap gate failed")
    status.add_quality_failure(QualityFailureReason.LOW_COVERAGE, "coverage below threshold")
    status.add_quality_failure(QualityFailureReason.TOO_MANY_NAN)

    payload = status.to_dict()

    assert payload["failure_reasons"] == ["quality_gate_failed"]
    assert payload["quality_failure_reasons"] == ["LOW_COVERAGE", "TOO_MANY_NAN"]
    assert payload["quality_failure_details"]["LOW_COVERAGE"] == "coverage below threshold"


def test_quality_diagnostics_map_to_fine_grained_failure_reasons():
    reasons = quality_failure_reasons_from_diagnostics(
        metrics={
            "turnover": 1.2,
            "rank_ic_test": -0.01,
            "group_monotonicity_score": 0.2,
        },
        diagnostics={
            "lookahead_risk": "critical",
            "failure_reasons": [
                "low_coverage",
                "too_many_nan",
                "constant_signal",
                "extreme_values",
                "high_similarity",
            ],
        },
    )

    assert reasons == [
        QualityFailureReason.LOOKAHEAD_DETECTED.value,
        QualityFailureReason.LOW_COVERAGE.value,
        QualityFailureReason.TOO_MANY_NAN.value,
        QualityFailureReason.CONSTANT_SIGNAL.value,
        QualityFailureReason.EXTREME_VALUE_SIGNAL.value,
        QualityFailureReason.HIGH_SIMILARITY.value,
        QualityFailureReason.HIGH_TURNOVER.value,
        QualityFailureReason.WEAK_OOS_IC.value,
        QualityFailureReason.POOR_MONOTONICITY.value,
    ]


def test_tracker_quality_failure_gate_records_coarse_and_fine_reasons():
    tracker = FactorFailureTracker(max_debug_rounds=2)
    tracker.register_factor("f1", "alpha", "close / open")

    tracker.mark_quality_gate_failure(
        "f1",
        detail="quality overlay rejected",
        quality_failure_reasons=[QualityFailureReason.HIGH_SIMILARITY],
    )

    payload = tracker.get_status("f1").to_dict()
    assert payload["failure_reasons"] == ["quality_gate_failed"]
    assert payload["quality_failure_reasons"] == ["HIGH_SIMILARITY"]
