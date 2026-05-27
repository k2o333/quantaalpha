from datetime import datetime

from quantaalpha.continuous.revalidation_scheduler import (
    select_revalidation_candidates_by_lifecycle,
)


def _record(factor_id, status, last_validated="2026-04-01T00:00:00"):
    return {
        "factor_id": factor_id,
        "factor_name": factor_id,
        "factor_expression": "close / open",
        "evaluation_status": status,
        "metadata_json": '{"last_validated": "%s"}' % last_validated,
    }


def test_lifecycle_policy_revalidates_stale_active_candidate_and_degraded_only():
    records = [
        _record("active_old", "active"),
        _record("candidate_old", "candidate"),
        _record("degraded_old", "degraded"),
        _record("rejected_old", "rejected"),
        _record("quarantine_old", "quarantine"),
        _record("retired_old", "retired"),
        _record("active_recent", "active", "2026-05-20T00:00:00"),
    ]

    selected = select_revalidation_candidates_by_lifecycle(
        records,
        days_threshold=21,
        now=datetime(2026, 5, 26),
    )

    assert [row["factor_id"] for row in selected] == [
        "active_old",
        "candidate_old",
        "degraded_old",
    ]
    assert selected[2]["lifecycle_revalidation_reason"] == "degraded_observation"
