"""Tests for financial PIT consumer-entry metadata exposure.

Covers:
- load_from_report exposes financial PIT metadata for income_vip when layer=financial_pit
- runtime financial_pit_path wins over fallback path derivation
- fallback path derivation uses report storage root + .financial_pit/<interface>.parquet
- non-financial daily capabilities do NOT receive financial PIT metadata keys
- rendered output for income_vip includes financial PIT visibility markers
- report-driven derivation (not hardcoded DATA_CAPABILITIES)
"""

import json
import tempfile
from pathlib import Path

import pytest

from quantaalpha.factors.data_capability import (
    load_from_report,
    render_data_capabilities,
    DATA_CAPABILITIES,
)


def _make_report(interfaces: dict, meta_extra: dict | None = None) -> Path:
    """Create a temporary report JSON and return its path."""
    meta = {"schema_version": 2}
    if meta_extra:
        meta.update(meta_extra)
    report = {"_meta": meta, "interfaces": interfaces}
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(report, tmp)
    tmp.close()
    return Path(tmp.name)


class TestFinancialPitConsumerEntryMetadata:
    """Prove load_from_report exposes financial PIT metadata for income_vip."""

    def test_income_vip_layer_is_financial_pit(self):
        """income_vip capability must expose layer=financial_pit from report."""
        report_path = _make_report(
            {
                "income_vip": {
                    "semantic": {
                        "field_aliases": ["$basic_eps", "$n_income"],
                        "freq": "quarterly",
                        "lag_days": 45,
                        "join_mode": "forward_fill",
                        "factor_hints": ["fundamental", "earnings"],
                        "layer": "financial_pit",
                    },
                }
            }
        )
        try:
            caps = load_from_report(report_path)
            assert "income_vip" in caps
            assert caps["income_vip"]["layer"] == "financial_pit"
        finally:
            report_path.unlink()

    def test_income_vip_storage_kind_is_financial_pit_parquet(self):
        """income_vip capability must expose storage_kind=financial_pit_parquet."""
        report_path = _make_report(
            {
                "income_vip": {
                    "semantic": {
                        "field_aliases": ["$basic_eps"],
                        "freq": "quarterly",
                        "lag_days": 45,
                        "join_mode": "forward_fill",
                        "factor_hints": [],
                        "layer": "financial_pit",
                    },
                }
            },
            meta_extra={"storage_root": "/tmp/test_data"},
        )
        try:
            caps = load_from_report(report_path)
            assert caps["income_vip"]["storage_kind"] == "financial_pit_parquet"
        finally:
            report_path.unlink()

    def test_income_vip_storage_path_from_fallback(self):
        """When runtime financial_pit_path is missing, storage_path falls back to <storage_root>/.financial_pit/<interface>.parquet."""
        report_path = _make_report(
            {
                "income_vip": {
                    "semantic": {
                        "field_aliases": ["$basic_eps"],
                        "freq": "quarterly",
                        "lag_days": 45,
                        "join_mode": "forward_fill",
                        "factor_hints": [],
                        "layer": "financial_pit",
                    },
                }
            },
            meta_extra={"storage_root": "/home/quan/testdata/aspipe_v4/data"},
        )
        try:
            caps = load_from_report(report_path)
            expected_path = "/home/quan/testdata/aspipe_v4/data/.financial_pit/income_vip.parquet"
            assert caps["income_vip"]["storage_path"] == expected_path
        finally:
            report_path.unlink()

    def test_income_vip_versioned_is_true(self):
        """income_vip capability must expose versioned=True."""
        report_path = _make_report(
            {
                "income_vip": {
                    "semantic": {
                        "field_aliases": ["$basic_eps"],
                        "freq": "quarterly",
                        "lag_days": 45,
                        "join_mode": "forward_fill",
                        "factor_hints": [],
                        "layer": "financial_pit",
                    },
                }
            }
        )
        try:
            caps = load_from_report(report_path)
            assert caps["income_vip"]["versioned"] is True
        finally:
            report_path.unlink()

    def test_income_vip_disclosure_field(self):
        """income_vip capability must expose disclosure_field=disclosure_date."""
        report_path = _make_report(
            {
                "income_vip": {
                    "semantic": {
                        "field_aliases": ["$basic_eps"],
                        "freq": "quarterly",
                        "lag_days": 45,
                        "join_mode": "forward_fill",
                        "factor_hints": [],
                        "layer": "financial_pit",
                    },
                }
            }
        )
        try:
            caps = load_from_report(report_path)
            assert caps["income_vip"]["disclosure_field"] == "disclosure_date"
        finally:
            report_path.unlink()

    def test_income_vip_revision_field(self):
        """income_vip capability must expose revision_field=revision_seq."""
        report_path = _make_report(
            {
                "income_vip": {
                    "semantic": {
                        "field_aliases": ["$basic_eps"],
                        "freq": "quarterly",
                        "lag_days": 45,
                        "join_mode": "forward_fill",
                        "factor_hints": [],
                        "layer": "financial_pit",
                    },
                }
            }
        )
        try:
            caps = load_from_report(report_path)
            assert caps["income_vip"]["revision_field"] == "revision_seq"
        finally:
            report_path.unlink()

    def test_income_vip_next_revision_field(self):
        """income_vip capability must expose next_revision_field=next_disclosure_date."""
        report_path = _make_report(
            {
                "income_vip": {
                    "semantic": {
                        "field_aliases": ["$basic_eps"],
                        "freq": "quarterly",
                        "lag_days": 45,
                        "join_mode": "forward_fill",
                        "factor_hints": [],
                        "layer": "financial_pit",
                    },
                }
            }
        )
        try:
            caps = load_from_report(report_path)
            assert caps["income_vip"]["next_revision_field"] == "next_disclosure_date"
        finally:
            report_path.unlink()


class TestFinancialPitRuntimePathWins:
    """Prove runtime financial_pit_path wins over fallback derivation."""

    def test_runtime_financial_pit_path_wins(self):
        """When runtime block has financial_pit_path, storage_path must use that exact path."""
        report_path = _make_report(
            {
                "income_vip": {
                    "semantic": {
                        "field_aliases": ["$basic_eps"],
                        "freq": "quarterly",
                        "lag_days": 45,
                        "join_mode": "forward_fill",
                        "factor_hints": [],
                        "layer": "financial_pit",
                    },
                    "runtime": {
                        "financial_pit_path": "/custom/path/income_vip.parquet",
                    },
                }
            },
            meta_extra={"storage_root": "/home/quan/testdata/aspipe_v4/data"},
        )
        try:
            caps = load_from_report(report_path)
            assert caps["income_vip"]["storage_path"] == "/custom/path/income_vip.parquet"
        finally:
            report_path.unlink()

    def test_runtime_financial_pit_path_absent_uses_fallback(self):
        """When runtime block exists but lacks financial_pit_path, fallback derivation applies."""
        report_path = _make_report(
            {
                "income_vip": {
                    "semantic": {
                        "field_aliases": ["$basic_eps"],
                        "freq": "quarterly",
                        "lag_days": 45,
                        "join_mode": "forward_fill",
                        "factor_hints": [],
                        "layer": "financial_pit",
                    },
                    "runtime": {
                        "parquet_present": True,
                        "qlib_sync_status": "not_applicable",
                    },
                }
            },
            meta_extra={"storage_root": "/home/quan/testdata/aspipe_v4/data"},
        )
        try:
            caps = load_from_report(report_path)
            expected = "/home/quan/testdata/aspipe_v4/data/.financial_pit/income_vip.parquet"
            assert caps["income_vip"]["storage_path"] == expected
        finally:
            report_path.unlink()


class TestNonFinancialCapabilitiesNoPitMetadata:
    """Prove non-financial daily capabilities do NOT receive financial PIT metadata keys."""

    def test_daily_capability_no_storage_kind(self):
        """Daily panel capabilities must not receive storage_kind."""
        report_path = _make_report(
            {
                "daily": {
                    "semantic": {
                        "field_aliases": ["$open", "$close"],
                        "freq": "daily",
                        "lag_days": 0,
                        "join_mode": "same_day",
                        "factor_hints": ["momentum"],
                        "layer": "daily_panel",
                    },
                }
            }
        )
        try:
            caps = load_from_report(report_path)
            assert "daily" in caps
            assert "storage_kind" not in caps["daily"]
            assert "storage_path" not in caps["daily"]
            assert "versioned" not in caps["daily"]
            assert "disclosure_field" not in caps["daily"]
            assert "revision_field" not in caps["daily"]
            assert "next_revision_field" not in caps["daily"]
        finally:
            report_path.unlink()


class TestFinancialPitRenderedVisibility:
    """Prove render_data_capabilities makes financial PIT entry visibly different."""

    def test_rendered_income_vip_includes_financial_pit_markers(self):
        """Rendered output for income_vip must include financial PIT visibility markers."""
        caps = {
            "income_vip": {
                "fields": ["$basic_eps", "$n_income"],
                "freq": "quarterly",
                "lag_days": 45,
                "join_mode": "forward_fill",
                "factor_hints": ["fundamental", "earnings"],
                "layer": "financial_pit",
                "storage_kind": "financial_pit_parquet",
                "storage_path": "/home/quan/testdata/aspipe_v4/data/.financial_pit/income_vip.parquet",
                "versioned": True,
                "disclosure_field": "disclosure_date",
                "revision_field": "revision_seq",
                "next_revision_field": "next_disclosure_date",
            }
        }
        rendered = render_data_capabilities(caps)
        assert "layer=financial_pit" in rendered
        assert "storage_kind=financial_pit_parquet" in rendered
        assert "versioned=True" in rendered

    def test_rendered_income_vip_includes_storage_path(self):
        """Rendered output must include the storage path for financial PIT."""
        caps = {
            "income_vip": {
                "fields": ["$basic_eps"],
                "freq": "quarterly",
                "lag_days": 45,
                "join_mode": "forward_fill",
                "factor_hints": [],
                "layer": "financial_pit",
                "storage_kind": "financial_pit_parquet",
                "storage_path": "/home/quan/testdata/aspipe_v4/data/.financial_pit/income_vip.parquet",
                "versioned": True,
            }
        }
        rendered = render_data_capabilities(caps)
        assert "/home/quan/testdata/aspipe_v4/data/.financial_pit/income_vip.parquet" in rendered


class TestReportDrivenFinancialPit:
    """Prove financial PIT metadata comes from report, not hardcoded DATA_CAPABILITIES."""

    def test_data_capabilities_has_no_financial_pit_keys(self):
        """DATA_CAPABILITIES must not contain financial PIT metadata keys."""
        for name, spec in DATA_CAPABILITIES.items():
            assert "storage_kind" not in spec, f"{name} should not have storage_kind in DATA_CAPABILITIES"
            assert "storage_path" not in spec, f"{name} should not have storage_path in DATA_CAPABILITIES"
            assert "versioned" not in spec, f"{name} should not have versioned in DATA_CAPABILITIES"
            assert "disclosure_field" not in spec, f"{name} should not have disclosure_field in DATA_CAPABILITIES"
            assert "revision_field" not in spec, f"{name} should not have revision_field in DATA_CAPABILITIES"
            assert "next_revision_field" not in spec, f"{name} should not have next_revision_field in DATA_CAPABILITIES"

    def test_real_report_driven_financial_pit_metadata(self):
        """Real report must drive financial PIT metadata for income_vip."""
        from quantaalpha.factors.data_capability import _PROJECT_REPORT_FALLBACK

        if _PROJECT_REPORT_FALLBACK.exists():
            caps = load_from_report()
            if "income_vip" in caps:
                inc = caps["income_vip"]
                assert inc.get("layer") == "financial_pit", f"Expected layer=financial_pit, got {inc.get('layer')}"
                assert inc.get("storage_kind") == "financial_pit_parquet", f"Expected storage_kind=financial_pit_parquet, got {inc.get('storage_kind')}"
                assert inc.get("versioned") is True, f"Expected versioned=True, got {inc.get('versioned')}"
                assert inc.get("disclosure_field") == "disclosure_date", f"Expected disclosure_field=disclosure_date, got {inc.get('disclosure_field')}"
                assert inc.get("revision_field") == "revision_seq", f"Expected revision_field=revision_seq, got {inc.get('revision_field')}"
                assert inc.get("next_revision_field") == "next_disclosure_date", f"Expected next_revision_field=next_disclosure_date, got {inc.get('next_revision_field')}"
                assert inc.get("storage_path") is not None, "storage_path must not be None for financial_pit"
