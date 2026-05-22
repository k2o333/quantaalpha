from __future__ import annotations

from quantaalpha.continuous.run_store import RunSummary


def test_run_summary_serializes_factor_quality_and_parent_injection_counts() -> None:
    summary = RunSummary(
        factor_quality_lifecycle={
            "evaluated": 3,
            "active_promoted": 1,
            "candidate_only": 1,
            "rejected": 1,
        },
        best_factor_metrics={
            "IC": 0.02,
            "Rank IC": 0.041,
            "annualized_return": 0.18,
            "information_ratio": 0.51,
        },
        historical_parent_injection_counts={
            "trajectory_pool": {"scanned": 8, "selected": 3},
            "factor_library": {"scanned": 10, "selected": 1},
        },
    )

    payload = summary.to_dict()["factor_quality"]

    assert payload["lifecycle"]["evaluated"] == 3
    assert payload["lifecycle"]["active_promoted"] == 1
    assert payload["best_metrics"]["Rank IC"] == 0.041
    assert payload["historical_parent_injection_counts"]["trajectory_pool"]["selected"] == 3


def test_run_summary_deserializes_factor_quality_fields() -> None:
    restored = RunSummary.from_dict(
        {
            "factor_quality": {
                "lifecycle": {"evaluated": 2, "active_promoted": 1, "candidate_only": 1, "rejected": 0},
                "best_metrics": {"Rank IC": 0.05},
                "historical_parent_injection_counts": {"factor_library": {"selected": 2}},
            }
        }
    )

    assert restored.factor_quality_lifecycle["candidate_only"] == 1
    assert restored.best_factor_metrics["Rank IC"] == 0.05
    assert restored.historical_parent_injection_counts["factor_library"]["selected"] == 2
