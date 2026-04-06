"""Tests proving quantaalpha prefers semantic.join_mode from report over freq-based inference.

Covers:
- semantic.join_mode wins over freq-to-join_mode mapping
- absent semantic.join_mode falls back to existing inference
- conflicting fixture proves declaration precedence
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


class TestQuantaalphaSemanticJoinModePrecedence:
    """Prove semantic.join_mode wins over freq-based inference."""

    def test_semantic_join_mode_wins_over_freq_inference(self):
        """When semantic.join_mode is declared, it must win over _FREQ_TO_JOIN_MODE inference."""
        report_path = _make_report(
            {
                "income_vip": {
                    "semantic": {
                        "field_aliases": ["$basic_eps", "$n_income"],
                        "freq": "quarterly",
                        "lag_days": 45,
                        "join_mode": "same_day",
                    },
                }
            }
        )
        try:
            caps = load_from_report(report_path)
            assert "income_vip" in caps
            assert caps["income_vip"]["join_mode"] == "same_day", f"Expected semantic join_mode='same_day', got {caps['income_vip']['join_mode']}"
        finally:
            report_path.unlink()

    def test_semantic_join_mode_wins_daily_with_forward_fill(self):
        """freq=daily but semantic.join_mode=forward_fill -> declaration must win."""
        report_path = _make_report(
            {
                "daily": {
                    "semantic": {
                        "field_aliases": ["$open", "$close"],
                        "freq": "daily",
                        "join_mode": "forward_fill",
                    },
                }
            }
        )
        try:
            caps = load_from_report(report_path)
            assert "daily" in caps
            assert caps["daily"]["join_mode"] == "forward_fill", f"Expected semantic join_mode='forward_fill', got {caps['daily']['join_mode']}"
        finally:
            report_path.unlink()

    def test_absent_semantic_join_mode_falls_back_to_freq_inference(self):
        """When semantic.join_mode is absent, freq-based inference must still work."""
        report_path = _make_report(
            {
                "daily": {
                    "semantic": {
                        "field_aliases": ["$open", "$close"],
                        "freq": "daily",
                    },
                }
            }
        )
        try:
            caps = load_from_report(report_path)
            assert "daily" in caps
            assert caps["daily"]["join_mode"] == "same_day", f"Expected fallback join_mode='same_day' for daily freq, got {caps['daily']['join_mode']}"
        finally:
            report_path.unlink()

    def test_quarterly_freq_falls_back_to_forward_fill(self):
        """When semantic.join_mode is absent and freq=quarterly, fallback must be forward_fill."""
        report_path = _make_report(
            {
                "income_vip": {
                    "semantic": {
                        "field_aliases": ["$basic_eps"],
                        "freq": "quarterly",
                    },
                }
            }
        )
        try:
            caps = load_from_report(report_path)
            assert "income_vip" in caps
            assert caps["income_vip"]["join_mode"] == "forward_fill", f"Expected fallback join_mode='forward_fill' for quarterly freq, got {caps['income_vip']['join_mode']}"
        finally:
            report_path.unlink()

    def test_real_report_income_vip_join_mode_forward_fill(self):
        """Real generated report must have income_vip join_mode=forward_fill."""
        from quantaalpha.factors.data_capability import _PROJECT_REPORT_FALLBACK

        if _PROJECT_REPORT_FALLBACK.exists():
            caps = load_from_report()
            if "income_vip" in caps:
                assert caps["income_vip"]["join_mode"] == "forward_fill", f"Expected income_vip join_mode='forward_fill', got {caps['income_vip'].get('join_mode')}"
