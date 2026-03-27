"""
Tests for continuous run_store.py - Run Persistence Layer.
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest


class TestRunSummary:
    """Tests for RunSummary dataclass."""

    def test_to_dict_contains_required_keys(self):
        """Verify to_dict produces all required artifact keys."""
        from quantaalpha.continuous.run_store import (
            DataUpdateSummary,
            MiningSummary,
            RunSummary,
            ValidationSummary,
        )

        summary = RunSummary(
            schema_version="1.0",
            cycle_timestamp="2026-03-27T10:00:00",
            cycle_type="once",
            config_snapshot={"min_ic": 0.02},
            data_update=DataUpdateSummary(
                updated=True,
                updated_interfaces=["daily"],
                stale_interfaces=[],
                latest_dates={"daily": "20260327"},
            ),
            impact_groups=["price_volume"],
            candidate_factors_count=5,
            candidate_factors_source="revalidation",
            validation_summary=ValidationSummary(
                total=5, passed=3, failed=2, errors=[]
            ),
            mining_summary=MiningSummary(
                generated=2, validated=2, added=1, errors=[]
            ),
            duration_seconds=120.5,
            errors=[],
        )

        d = summary.to_dict()

        # Schema version check
        assert d["schema_version"] == "1.0"
        assert d["cycle_timestamp"] == "2026-03-27T10:00:00"
        assert d["cycle_type"] == "once"
        assert "config_snapshot" in d
        assert "data_update" in d
        assert "impact_groups" in d
        assert "candidate_factors" in d
        assert "validation_summary" in d
        assert "mining_summary" in d
        assert "run_summary" in d

    def test_to_json_produces_valid_json(self):
        """Verify to_json produces valid parseable JSON."""
        from quantaalpha.continuous.run_store import RunSummary

        summary = RunSummary(
            cycle_timestamp="2026-03-27T10:00:00",
            cycle_type="start",
        )

        json_str = summary.to_json()
        parsed = json.loads(json_str)
        assert parsed["schema_version"] == "1.0"
        assert parsed["cycle_type"] == "start"

    def test_from_dict_reconstructs_summary(self):
        """Verify from_dict reconstructs RunSummary correctly."""
        from quantaalpha.continuous.run_store import RunSummary

        data = {
            "schema_version": "1.0",
            "cycle_timestamp": "2026-03-27T10:00:00",
            "cycle_type": "once",
            "config_snapshot": {"min_ic": 0.02, "max_revalidation_per_run": 10},
            "data_update": {
                "updated": True,
                "updated_interfaces": ["daily", "moneyflow"],
                "stale_interfaces": [],
                "latest_dates": {"daily": "20260327"},
            },
            "impact_groups": ["price_volume", "moneyflow"],
            "candidate_factors": {
                "count": 7,
                "source": "mining",
            },
            "validation_summary": {
                "total": 7,
                "passed": 5,
                "failed": 2,
                "errors": ["factor_xyz failed"],
            },
            "mining_summary": {
                "generated": 3,
                "validated": 3,
                "added": 2,
                "errors": [],
            },
            "run_summary": {
                "duration_seconds": 45.5,
                "errors": [],
            },
        }

        summary = RunSummary.from_dict(data)

        assert summary.cycle_type == "once"
        assert summary.candidate_factors_count == 7
        assert summary.candidate_factors_source == "mining"
        assert summary.validation_summary.total == 7
        assert summary.validation_summary.passed == 5
        assert summary.validation_summary.failed == 2
        assert summary.mining_summary.generated == 3
        assert summary.mining_summary.added == 2
        assert summary.duration_seconds == 45.5

    def test_default_values_are_sensible(self):
        """Verify default RunSummary has sensible empty values."""
        from quantaalpha.continuous.run_store import RunSummary

        summary = RunSummary()

        assert summary.schema_version == "1.0"
        assert summary.cycle_timestamp == ""
        assert summary.cycle_type == ""
        assert summary.candidate_factors_count == 0
        assert summary.validation_summary.total == 0
        assert summary.mining_summary.generated == 0
        assert summary.duration_seconds == 0.0


class TestRunStore:
    """Tests for RunStore persistence."""

    def test_save_creates_file(self, tmp_path):
        """Verify save creates a JSON artifact file."""
        from quantaalpha.continuous.run_store import RunStore, RunSummary

        store = RunStore(str(tmp_path))
        summary = RunSummary(
            cycle_timestamp=datetime.now().isoformat(),
            cycle_type="once",
        )

        filepath = store.save(summary)

        assert Path(filepath).exists()
        assert filepath.endswith(".json")

    def test_save_and_load_roundtrip(self, tmp_path):
        """Verify save then load reconstructs the same summary."""
        from quantaalpha.continuous.run_store import (
            DataUpdateSummary,
            RunStore,
            RunSummary,
            ValidationSummary,
        )

        original = RunSummary(
            schema_version="1.0",
            cycle_timestamp="2026-03-27T10:00:00",
            cycle_type="once",
            config_snapshot={"min_ic": 0.02},
            data_update=DataUpdateSummary(
                updated=True,
                updated_interfaces=["daily"],
                stale_interfaces=[],
                latest_dates={"daily": "20260327"},
            ),
            impact_groups=["price_volume"],
            candidate_factors_count=5,
            candidate_factors_source="revalidation",
            validation_summary=ValidationSummary(
                total=5, passed=3, failed=2, errors=[]
            ),
            duration_seconds=120.5,
            errors=[],
        )

        store = RunStore(str(tmp_path))
        filepath = store.save(original)

        loaded = store.load(filepath)

        assert loaded.cycle_type == original.cycle_type
        assert loaded.candidate_factors_count == original.candidate_factors_count
        assert loaded.validation_summary.total == original.validation_summary.total
        assert loaded.validation_summary.passed == original.validation_summary.passed

    def test_list_runs_returns_newest_first(self, tmp_path):
        """Verify list_runs returns runs in reverse chronological order."""
        from quantaalpha.continuous.run_store import RunStore, RunSummary

        store = RunStore(str(tmp_path))

        # Create runs with different timestamps
        timestamps = [
            "2026-03-27T08:00:00",
            "2026-03-27T09:00:00",
            "2026-03-27T10:00:00",
        ]

        for ts in timestamps:
            summary = RunSummary(
                cycle_timestamp=ts,
                cycle_type="once",
            )
            store.save(summary)

        runs = store.list_runs(limit=10)

        assert len(runs) == 3
        # Newest first
        assert runs[0].cycle_timestamp == "2026-03-27T10:00:00"
        assert runs[1].cycle_timestamp == "2026-03-27T09:00:00"
        assert runs[2].cycle_timestamp == "2026-03-27T08:00:00"

    def test_list_runs_filters_by_cycle_type(self, tmp_path):
        """Verify list_runs can filter by cycle_type."""
        from quantaalpha.continuous.run_store import RunStore, RunSummary

        store = RunStore(str(tmp_path))

        store.save(RunSummary(cycle_timestamp="2026-03-27T08:00:00", cycle_type="once"))
        store.save(RunSummary(cycle_timestamp="2026-03-27T09:00:00", cycle_type="start"))
        store.save(RunSummary(cycle_timestamp="2026-03-27T10:00:00", cycle_type="once"))

        once_runs = store.list_runs(cycle_type="once")
        start_runs = store.list_runs(cycle_type="start")

        assert len(once_runs) == 2
        assert len(start_runs) == 1

    def test_list_runs_respects_limit(self, tmp_path):
        """Verify list_runs respects the limit parameter."""
        from quantaalpha.continuous.run_store import RunStore, RunSummary

        store = RunStore(str(tmp_path))

        for i in range(10):
            ts = f"2026-03-27T{10 + i:02d}:00:00"
            store.save(RunSummary(cycle_timestamp=ts, cycle_type="once"))

        runs = store.list_runs(limit=3)

        assert len(runs) == 3

    def test_get_latest_run_returns_newest(self, tmp_path):
        """Verify get_latest_run returns the most recent run."""
        from quantaalpha.continuous.run_store import RunStore, RunSummary

        store = RunStore(str(tmp_path))

        store.save(RunSummary(cycle_timestamp="2026-03-27T08:00:00", cycle_type="once"))
        store.save(RunSummary(cycle_timestamp="2026-03-27T10:00:00", cycle_type="once"))
        store.save(RunSummary(cycle_timestamp="2026-03-27T09:00:00", cycle_type="once"))

        latest = store.get_latest_run()

        assert latest is not None
        assert latest.cycle_timestamp == "2026-03-27T10:00:00"

    def test_get_latest_run_returns_none_when_empty(self, tmp_path):
        """Verify get_latest_run returns None when no runs exist."""
        from quantaalpha.continuous.run_store import RunStore

        store = RunStore(str(tmp_path))
        latest = store.get_latest_run()

        assert latest is None

    def test_get_run_count(self, tmp_path):
        """Verify get_run_count returns correct count."""
        from quantaalpha.continuous.run_store import RunStore, RunSummary

        store = RunStore(str(tmp_path))

        assert store.get_run_count() == 0

        for i in range(5):
            store.save(RunSummary(cycle_timestamp=f"2026-03-27T{10+i:02d}:00:00", cycle_type="once"))

        assert store.get_run_count() == 5

    def test_run_filename_is_unique(self, tmp_path):
        """Verify run filenames are unique per save when timestamps differ."""
        from quantaalpha.continuous.run_store import RunStore, RunSummary

        store = RunStore(str(tmp_path))

        # Save with different timestamps (at least 1 second apart)
        timestamps = [
            "2026-03-27T10:00:00",
            "2026-03-27T10:00:01",
            "2026-03-27T10:00:02",
        ]

        files = []
        for ts in timestamps:
            summary = RunSummary(cycle_timestamp=ts, cycle_type="once")
            f = store.save(summary)
            files.append(Path(f))

        # All files should exist and be unique
        assert len(set(files)) == 3
        for f in files:
            assert f.exists()
