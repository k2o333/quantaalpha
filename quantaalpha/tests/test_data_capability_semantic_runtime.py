"""Tests for quantaalpha data_capability semantic block preference.

Covers:
- load_from_report prefers interfaces.<name>.semantic when present
- Falls back to flat layout when semantic block is absent
- Falls back to DATA_CAPABILITIES when report is missing/invalid/empty
"""

import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from quantaalpha.factors.data_capability import (
    load_from_report,
    DATA_CAPABILITIES,
)


class TestSemanticPreference:
    def test_loads_from_semantic_block_when_present(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "report.json"
            report = {
                "_meta": {"schema_version": 2, "generated_at": "test", "storage_root": tmpdir},
                "interfaces": {
                    "daily": {
                        "semantic": {
                            "mode": "reverse_date_range",
                            "fields": ["open", "close"],
                            "field_aliases": ["$open", "$close"],
                            "freq": "daily",
                            "lag_days": 0,
                            "factor_hints": ["momentum"],
                            "is_auxiliary": False,
                            "layer": "main_daily",
                            "consumer_targets": ["quantaalpha", "qlib_sync"],
                        },
                        "runtime": {
                            "parquet_present": True,
                            "qlib_sync_status": "synced",
                            "last_sync_at": "2024-01-01T00:00:00Z",
                            "problem_summary": {"warning_count": 0},
                        },
                        "mode": "reverse_date_range",
                        "fields": ["open", "close"],
                        "field_aliases": ["$open", "$close"],
                        "freq": "daily",
                        "lag_days": 0,
                        "factor_hints": ["momentum"],
                        "is_auxiliary": False,
                    }
                },
            }
            report_path.write_text(json.dumps(report))
            caps = load_from_report(report_path)
            assert "daily" in caps
            assert caps["daily"]["fields"] == ["$open", "$close"]
            assert caps["daily"]["freq"] == "daily"
            assert caps["daily"]["lag_days"] == 0
            assert caps["daily"]["factor_hints"] == ["momentum"]

    def test_semantic_layer_is_exposed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "report.json"
            report = {
                "_meta": {"schema_version": 2, "generated_at": "test", "storage_root": tmpdir},
                "interfaces": {
                    "daily": {
                        "semantic": {
                            "mode": "reverse_date_range",
                            "fields": ["open"],
                            "field_aliases": ["$open"],
                            "freq": "daily",
                            "lag_days": 0,
                            "factor_hints": [],
                            "is_auxiliary": False,
                            "layer": "main_daily",
                            "consumer_targets": ["quantaalpha"],
                        },
                        "runtime": {
                            "parquet_present": True,
                            "qlib_sync_status": "synced",
                            "last_sync_at": None,
                            "problem_summary": {"warning_count": 0},
                        },
                        "mode": "reverse_date_range",
                        "fields": ["open"],
                        "field_aliases": ["$open"],
                        "freq": "daily",
                        "lag_days": 0,
                        "factor_hints": [],
                        "is_auxiliary": False,
                    }
                },
            }
            report_path.write_text(json.dumps(report))
            caps = load_from_report(report_path)
            assert "daily" in caps
            assert caps["daily"].get("layer") == "main_daily"


class TestFlatFallback:
    def test_falls_back_to_flat_layout_when_semantic_absent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "report.json"
            report = {
                "_meta": {"schema_version": 1, "generated_at": "test", "storage_root": tmpdir},
                "interfaces": {
                    "daily": {
                        "mode": "reverse_date_range",
                        "fields": ["open", "close"],
                        "field_aliases": ["$open", "$close"],
                        "freq": "daily",
                        "lag_days": 0,
                        "factor_hints": ["momentum"],
                        "is_auxiliary": False,
                    }
                },
            }
            report_path.write_text(json.dumps(report))
            caps = load_from_report(report_path)
            assert "daily" in caps
            assert caps["daily"]["fields"] == ["$open", "$close"]
            assert caps["daily"]["freq"] == "daily"


class TestDataCapabilitiesFallback:
    def test_falls_back_to_data_capabilities_when_report_missing(self):
        caps = load_from_report("/nonexistent/path/report.json")
        assert caps == DATA_CAPABILITIES

    def test_falls_back_to_data_capabilities_when_report_invalid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "report.json"
            report_path.write_text("not valid json{{{")
            caps = load_from_report(report_path)
            assert caps == DATA_CAPABILITIES

    def test_falls_back_to_data_capabilities_when_report_empty(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "report.json"
            report_path.write_text(json.dumps({}))
            caps = load_from_report(report_path)
            assert caps == DATA_CAPABILITIES

    def test_falls_back_to_data_capabilities_when_no_interfaces(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "report.json"
            report_path.write_text(json.dumps({"_meta": {"schema_version": 2}}))
            caps = load_from_report(report_path)
            assert caps == DATA_CAPABILITIES

    def test_falls_back_to_data_capabilities_when_no_field_aliases(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = Path(tmpdir) / "report.json"
            report = {
                "_meta": {"schema_version": 2, "generated_at": "test", "storage_root": tmpdir},
                "interfaces": {
                    "daily": {
                        "semantic": {
                            "mode": "reverse_date_range",
                            "fields": ["open"],
                            "field_aliases": [],
                            "freq": "daily",
                            "lag_days": 0,
                            "factor_hints": [],
                            "is_auxiliary": False,
                        },
                        "runtime": {
                            "parquet_present": True,
                            "qlib_sync_status": "synced",
                            "last_sync_at": None,
                            "problem_summary": {"warning_count": 0},
                        },
                        "mode": "reverse_date_range",
                        "fields": ["open"],
                        "field_aliases": [],
                        "freq": "daily",
                        "lag_days": 0,
                        "factor_hints": [],
                        "is_auxiliary": False,
                    }
                },
            }
            report_path.write_text(json.dumps(report))
            caps = load_from_report(report_path)
            assert caps == DATA_CAPABILITIES
