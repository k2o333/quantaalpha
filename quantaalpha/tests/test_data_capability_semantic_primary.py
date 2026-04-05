"""Tests proving quantaalpha uses interfaces.<name>.semantic as primary read path.

Key proof: when nested semantic and flat fields DISAGREE, semantic must win.
"""

import json
import tempfile
from pathlib import Path

import pytest

from quantaalpha.factors.data_capability import load_from_report


def _make_report(interfaces: dict) -> Path:
    """Create a temporary report JSON and return its path."""
    report = {"_meta": {"schema_version": 2}, "interfaces": interfaces}
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump(report, tmp)
    tmp.close()
    return Path(tmp.name)


class TestQuantaalphaSemanticFieldAliasesPrecedence:
    """Prove semantic.field_aliases wins over flat field_aliases when both exist and disagree."""

    def test_semantic_field_aliases_wins_over_flat(self):
        """When semantic.field_aliases and flat field_aliases disagree, semantic must be used."""
        report_path = _make_report(
            {
                "daily": {
                    "semantic": {
                        "field_aliases": ["$open_semantic", "$close_semantic"],
                        "freq": "daily",
                        "lag_days": 0,
                    },
                    "field_aliases": ["$open_flat", "$close_flat"],
                    "freq": "daily",
                    "lag_days": 0,
                }
            }
        )
        try:
            caps = load_from_report(report_path)
            assert "daily" in caps
            # Must use semantic aliases, not flat
            assert caps["daily"]["fields"] == ["$open_semantic", "$close_semantic"], f"Expected semantic aliases, got {caps['daily']['fields']}"
        finally:
            report_path.unlink()

    def test_flat_only_interface_is_not_consumed(self):
        """When semantic block is absent, the interface must not be consumed."""
        report_path = _make_report(
            {
                "daily": {
                    "field_aliases": ["$open_flat", "$close_flat"],
                    "freq": "daily",
                    "lag_days": 0,
                }
            }
        )
        try:
            caps = load_from_report(report_path)
            from quantaalpha.factors.data_capability import DATA_CAPABILITIES

            assert caps == DATA_CAPABILITIES
        finally:
            report_path.unlink()

    def test_semantic_field_aliases_used_when_flat_absent(self):
        """When only semantic.field_aliases exists, it must be used."""
        report_path = _make_report(
            {
                "daily": {
                    "semantic": {
                        "field_aliases": ["$open_semantic"],
                        "freq": "daily",
                    },
                }
            }
        )
        try:
            caps = load_from_report(report_path)
            assert "daily" in caps
            assert caps["daily"]["fields"] == ["$open_semantic"]
        finally:
            report_path.unlink()


class TestQuantaalphaSemanticModePrecedence:
    """Prove semantic.mode is read and used when present."""

    def test_semantic_mode_in_result(self):
        """semantic.mode should appear in the loaded capability when present."""
        report_path = _make_report(
            {
                "daily": {
                    "semantic": {
                        "mode": "reverse_date_range",
                        "field_aliases": ["$open"],
                        "freq": "daily",
                    },
                    "mode": "flat_mode_value",
                }
            }
        )
        try:
            caps = load_from_report(report_path)
            assert "daily" in caps
            # mode should come from semantic, not flat
            assert caps["daily"].get("mode") == "reverse_date_range", f"Expected semantic mode, got {caps['daily'].get('mode')}"
        finally:
            report_path.unlink()


class TestQuantaalphaSemanticIsAuxiliaryPrecedence:
    """Prove semantic.is_auxiliary is read when present."""

    def test_semantic_is_auxiliary_in_result(self):
        """semantic.is_auxiliary should be used when both nested and flat exist."""
        report_path = _make_report(
            {
                "daily": {
                    "semantic": {
                        "is_auxiliary": True,
                        "field_aliases": ["$open"],
                        "freq": "daily",
                    },
                    "is_auxiliary": False,
                }
            }
        )
        try:
            caps = load_from_report(report_path)
            assert "daily" in caps
            assert caps["daily"].get("is_auxiliary") is True, f"Expected semantic is_auxiliary=True, got {caps['daily'].get('is_auxiliary')}"
        finally:
            report_path.unlink()


class TestQuantaalphaSemanticFreqPrecedence:
    """Prove semantic.freq wins over flat freq when both exist and disagree."""

    def test_semantic_freq_wins_over_flat(self):
        report_path = _make_report(
            {
                "daily": {
                    "semantic": {
                        "field_aliases": ["$open"],
                        "freq": "quarterly",
                        "lag_days": 45,
                    },
                    "freq": "daily",
                    "lag_days": 0,
                }
            }
        )
        try:
            caps = load_from_report(report_path)
            assert "daily" in caps
            assert caps["daily"]["freq"] == "quarterly", f"Expected semantic freq='quarterly', got {caps['daily']['freq']}"
            assert caps["daily"]["lag_days"] == 45, f"Expected semantic lag_days=45, got {caps['daily']['lag_days']}"
        finally:
            report_path.unlink()


class TestQuantaalphaSemanticFactorHintsPrecedence:
    """Prove semantic.factor_hints wins over flat factor_hints."""

    def test_semantic_factor_hints_wins(self):
        report_path = _make_report(
            {
                "daily": {
                    "semantic": {
                        "field_aliases": ["$open"],
                        "factor_hints": ["semantic_momentum"],
                    },
                    "factor_hints": ["flat_momentum"],
                }
            }
        )
        try:
            caps = load_from_report(report_path)
            assert "daily" in caps
            assert caps["daily"]["factor_hints"] == ["semantic_momentum"], f"Expected semantic factor_hints, got {caps['daily']['factor_hints']}"
        finally:
            report_path.unlink()


class TestQuantaalphaSemanticLayerPrecedence:
    """Prove semantic.layer is read when present."""

    def test_semantic_layer_in_result(self):
        report_path = _make_report(
            {
                "daily": {
                    "semantic": {
                        "field_aliases": ["$open"],
                        "layer": "daily_panel",
                    },
                }
            }
        )
        try:
            caps = load_from_report(report_path)
            assert "daily" in caps
            assert caps["daily"].get("layer") == "daily_panel"
        finally:
            report_path.unlink()


class TestQuantaalphaSemanticRequired:
    """Prove flat-only interface entries are no longer consumed."""

    def test_flat_only_report_falls_back_to_data_capabilities(self):
        """A flat-only interface entry must not be consumed as a valid capability."""
        report_path = _make_report(
            {
                "daily": {
                    "field_aliases": ["$flat_open", "$flat_close"],
                    "freq": "daily",
                    "lag_days": 1,
                    "join_mode": "same_day",
                    "factor_hints": ["flat_hint"],
                }
            }
        )
        try:
            caps = load_from_report(report_path)
            from quantaalpha.factors.data_capability import DATA_CAPABILITIES

            assert caps == DATA_CAPABILITIES
        finally:
            report_path.unlink()

    def test_no_semantic_no_crash(self):
        """Interface without semantic should not crash and should not be consumed."""
        report_path = _make_report(
            {
                "daily": {
                    "field_aliases": ["$open"],
                }
            }
        )
        try:
            caps = load_from_report(report_path)
            from quantaalpha.factors.data_capability import DATA_CAPABILITIES

            assert caps == DATA_CAPABILITIES
        finally:
            report_path.unlink()
