"""
Tests for continuous run_store.py - Run Persistence Layer.
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest


class TestDataUpdateSummaryDocSchemaMatch:
    """Tests verifying DataUpdateSummary docstring matches actual dataclass schema."""

    def test_docstring_freshness_delta_is_dict_not_int(self):
        """Verify docstring artifact example shows freshness_delta as dict[str, int], not int.

        The actual dataclass field is:
            freshness_delta: dict[str, int] = field(default_factory=dict)

        So the artifact doc must show:
            "freshness_delta": dict[str, int],
        NOT:
            "freshness_delta": int,
        """
        import re
        import quantaalpha.continuous.run_store as run_store_module

        # Read the source file to check docstring
        import inspect
        source = inspect.getsource(run_store_module)

        # The docstring should NOT contain the old incorrect type
        # Find the data_update section in the docstring
        doc_match = re.search(
            r'"data_update":\s*\{[^}]+\}', source, re.DOTALL
        )
        assert doc_match, "data_update section not found in docstring"
        data_update_doc = doc_match.group()

        # Freshness delta should be described as dict[str, int], not int
        assert "freshness_delta" in data_update_doc
        # Should NOT match the incorrect "freshness_delta": int pattern
        incorrect_pattern = r'"freshness_delta":\s*int\s*[,}]'
        assert not re.search(incorrect_pattern, data_update_doc), \
            "Docstring still shows freshness_delta as int, should be dict[str, int]"

    def test_docstring_unchanged_after_update_is_list_not_bool(self):
        """Verify docstring artifact example shows unchanged_after_update as list[str], not bool.

        The actual dataclass field is:
            unchanged_after_update: list[str] = field(default_factory=list)

        So the artifact doc must show:
            "unchanged_after_update": list[str],
        NOT:
            "unchanged_after_update": bool,
        """
        import re
        import quantaalpha.continuous.run_store as run_store_module

        import inspect
        source = inspect.getsource(run_store_module)

        doc_match = re.search(
            r'"data_update":\s*\{[^}]+\}', source, re.DOTALL
        )
        assert doc_match, "data_update section not found in docstring"
        data_update_doc = doc_match.group()

        # unchanged_after_update should NOT be described as bool
        incorrect_pattern = r'"unchanged_after_update":\s*bool\s*[,}]'
        assert not re.search(incorrect_pattern, data_update_doc), \
            "Docstring still shows unchanged_after_update as bool, should be list[str]"

    def test_schema_example_freshness_delta_dict_roundtrip(self):
        """Verify a DataUpdateSummary with dict freshness_delta survives to_dict roundtrip."""
        from quantaalpha.continuous.run_store import DataUpdateSummary

        summary = DataUpdateSummary(
            updated=True,
            updated_interfaces=["daily"],
            stale_interfaces=[],
            latest_dates={"daily": "20260327"},
            freshness_delta={"daily": 5, "moneyflow": 3},
            advanced_interfaces=["minutely"],
            unchanged_after_update=["moneyflow"],
        )

        d = summary.to_dict()

        # freshness_delta must be dict in output
        assert isinstance(d["freshness_delta"], dict), \
            f"freshness_delta should be dict, got {type(d['freshness_delta'])}"
        assert d["freshness_delta"] == {"daily": 5, "moneyflow": 3}

    def test_schema_example_unchanged_after_update_list_roundtrip(self):
        """Verify a DataUpdateSummary with list unchanged_after_update survives to_dict roundtrip."""
        from quantaalpha.continuous.run_store import DataUpdateSummary

        summary = DataUpdateSummary(
            updated=False,
            updated_interfaces=[],
            stale_interfaces=["daily"],
            latest_dates={"daily": "20260327"},
            unchanged_after_update=["moneyflow", "minutely"],
        )

        d = summary.to_dict()

        # unchanged_after_update must be list in output
        assert isinstance(d["unchanged_after_update"], list), \
            f"unchanged_after_update should be list, got {type(d['unchanged_after_update'])}"
        assert d["unchanged_after_update"] == ["moneyflow", "minutely"]


class TestDataUpdateSummaryNewFields:
    """Tests for DataUpdateSummary Wave A/B new fields."""

    def test_data_update_summary_freshness_delta_serialization(self):
        """Verify DataUpdateSummary serializes freshness_delta field."""
        from quantaalpha.continuous.run_store import DataUpdateSummary

        summary = DataUpdateSummary(
            updated=True,
            updated_interfaces=["daily"],
            stale_interfaces=[],
            latest_dates={"daily": "20260327"},
            freshness_delta=3600,
        )

        d = summary.to_dict()
        assert "freshness_delta" in d
        assert d["freshness_delta"] == 3600

    def test_data_update_summary_advanced_interfaces_serialization(self):
        """Verify DataUpdateSummary serializes advanced_interfaces field."""
        from quantaalpha.continuous.run_store import DataUpdateSummary

        summary = DataUpdateSummary(
            updated=True,
            updated_interfaces=["daily"],
            stale_interfaces=[],
            latest_dates={"daily": "20260327"},
            advanced_interfaces=["minutely", "tick"],
        )

        d = summary.to_dict()
        assert "advanced_interfaces" in d
        assert d["advanced_interfaces"] == ["minutely", "tick"]

    def test_data_update_summary_unchanged_after_update_serialization(self):
        """Verify DataUpdateSummary serializes unchanged_after_update field."""
        from quantaalpha.continuous.run_store import DataUpdateSummary

        summary = DataUpdateSummary(
            updated=False,
            updated_interfaces=[],
            stale_interfaces=["daily"],
            latest_dates={"daily": "20260327"},
            unchanged_after_update=True,
        )

        d = summary.to_dict()
        assert "unchanged_after_update" in d
        assert d["unchanged_after_update"] is True

    def test_data_update_summary_roundtrip_with_new_fields(self):
        """Verify DataUpdateSummary deserializes new fields correctly."""
        from quantaalpha.continuous.run_store import DataUpdateSummary

        data = {
            "updated": True,
            "updated_interfaces": ["daily", "moneyflow"],
            "stale_interfaces": [],
            "latest_dates": {"daily": "20260327"},
            "freshness_delta": {"daily": 5, "moneyflow": 3},
            "advanced_interfaces": ["daily"],
            "unchanged_after_update": ["moneyflow"],
        }

        summary = DataUpdateSummary.from_dict(data)

        assert summary.freshness_delta == {"daily": 5, "moneyflow": 3}
        assert summary.advanced_interfaces == ["daily"]
        assert summary.unchanged_after_update == ["moneyflow"]

    def test_data_update_summary_default_values_for_new_fields(self):
        """Verify new fields have sensible defaults when not provided."""
        from quantaalpha.continuous.run_store import DataUpdateSummary

        summary = DataUpdateSummary()

        assert summary.freshness_delta == {}
        assert summary.advanced_interfaces == []
        assert summary.unchanged_after_update == []


class TestRunSummaryBudgetFields:
    """Tests for RunSummary budget-related Wave A/B fields."""

    def test_run_summary_budget_exhausted_serialization(self):
        """Verify run_summary serializes budget_exhausted field."""
        from quantaalpha.continuous.run_store import RunSummary

        summary = RunSummary(
            cycle_timestamp="2026-03-27T10:00:00",
            cycle_type="once",
            budget_exhausted=True,
        )

        d = summary.to_dict()
        assert "budget_exhausted" in d["run_summary"]
        assert d["run_summary"]["budget_exhausted"] is True

    def test_run_summary_budget_remaining_seconds_serialization(self):
        """Verify run_summary serializes budget_remaining_seconds field."""
        from quantaalpha.continuous.run_store import RunSummary

        summary = RunSummary(
            cycle_timestamp="2026-03-27T10:00:00",
            cycle_type="once",
            budget_remaining_seconds=1800.5,
        )

        d = summary.to_dict()
        assert "budget_remaining_seconds" in d["run_summary"]
        assert d["run_summary"]["budget_remaining_seconds"] == 1800.5

    def test_run_summary_budget_fields_roundtrip(self):
        """Verify budget fields survive save/load roundtrip."""
        from quantaalpha.continuous.run_store import RunStore, RunSummary

        original = RunSummary(
            schema_version="1.0",
            cycle_timestamp="2026-03-27T10:00:00",
            cycle_type="once",
            budget_exhausted=False,
            budget_remaining_seconds=3600.0,
            duration_seconds=120.5,
        )

        store = RunStore("/tmp/test_budget_roundtrip")
        filepath = store.save(original)
        loaded = store.load(filepath)

        assert loaded.budget_exhausted == original.budget_exhausted
        assert loaded.budget_remaining_seconds == original.budget_remaining_seconds

        import shutil
        shutil.rmtree("/tmp/test_budget_roundtrip", ignore_errors=True)

    def test_run_summary_from_dict_budget_fields(self):
        """Verify from_dict reconstructs budget fields correctly."""
        from quantaalpha.continuous.run_store import RunSummary

        data = {
            "schema_version": "1.0",
            "cycle_timestamp": "2026-03-27T10:00:00",
            "cycle_type": "once",
            "run_summary": {
                "duration_seconds": 45.5,
                "errors": [],
                "budget_exhausted": True,
                "budget_remaining_seconds": 0.0,
            },
        }

        summary = RunSummary.from_dict(data)

        assert summary.budget_exhausted is True
        assert summary.budget_remaining_seconds == 0.0

    def test_run_summary_default_budget_values(self):
        """Verify budget fields have sensible defaults."""
        from quantaalpha.continuous.run_store import RunSummary

        summary = RunSummary()

        assert summary.budget_exhausted is False
        assert summary.budget_remaining_seconds == 0.0


class TestRunSummary:
    """Tests for RunSummary dataclass."""

    def test_training_summary_roundtrip_is_preserved(self):
        """Verify RunSummary persists training summary and keeps old payloads compatible."""
        from quantaalpha.continuous.run_store import RunSummary

        summary = RunSummary(
            cycle_timestamp="2026-03-27T10:00:00",
            cycle_type="once",
            training_summary={
                "hosted": True,
                "triggered": True,
                "errors": [],
            },
        )

        payload = summary.to_dict()
        loaded = RunSummary.from_dict(payload)

        assert payload["training_summary"] == {
            "hosted": True,
            "triggered": True,
            "errors": [],
        }
        assert loaded.training_summary == payload["training_summary"]

    def test_training_summary_from_dict_defaults_when_missing(self):
        """Verify older artifacts without training_summary still deserialize cleanly."""
        from quantaalpha.continuous.run_store import RunSummary

        summary = RunSummary.from_dict(
            {
                "schema_version": "1.0",
                "cycle_timestamp": "2026-03-27T10:00:00",
                "cycle_type": "once",
                "run_summary": {"duration_seconds": 1.5, "errors": []},
            }
        )

        assert summary.training_summary == {
            "hosted": False,
            "triggered": False,
            "errors": [],
        }

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
