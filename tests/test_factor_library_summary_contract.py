# ruff: noqa: D100,D103,I001

from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from quantaalpha.factors.library import FactorLibraryManager


def test_get_status_summary_exposes_unified3_required_keys(tmp_path):
    library_path = tmp_path / "library.json"
    manager = FactorLibraryManager(str(library_path))
    manager.data = {
        "metadata": {"last_updated": "2026-05-06", "version": "test"},
        "factors": {
            "f1": {"evaluation": {"status": "active", "last_validated": "2026-05-06"}},
            "f2": {"evaluation": {"status": "candidate"}},
            "f3": {"evaluation": {"status": "pending_validation"}},
        },
    }

    summary = manager.get_status_summary()

    for key in (
        "total_factors",
        "active_count",
        "candidate_count",
        "pending_count",
        "degraded_count",
        "last_validated",
        "last_updated",
        "status_distribution",
    ):
        assert key in summary
    assert summary["active_count"] == 1
    assert summary["candidate_count"] == 1
    assert summary["pending_count"] == 1
