"""Tests for quantaalpha data_capability registry V2 report loading.

Proves:
- load_from_report() loads capabilities from the JSON bridge file
- fields come from field_aliases, not raw producer column names
- V1 loading tolerates _saturation: null (does not filter out interfaces)
- V1 loading does not depend on periods or date_saturation
- Path resolution priority: explicit > config > project fallback
- Safe fallback to DATA_CAPABILITIES when report is missing or invalid
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Import target module
# ---------------------------------------------------------------------------

# Ensure the package is importable
import sys

_THIRD_PARTY = Path(__file__).resolve().parents[1]
if str(_THIRD_PARTY) not in sys.path:
    sys.path.insert(0, str(_THIRD_PARTY))

from quantaalpha.factors.data_capability import (
    DATA_CAPABILITIES,
    _get_best_saturation,
    _load_raw_report,
    _resolve_report_path,
    get_data_capabilities,
    load_from_report,
)


# ---------------------------------------------------------------------------
# Real bridge path used across tests
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_REAL_BRIDGE_PATH = _PROJECT_ROOT / "data" / ".data_capability_report.json"


# ===========================================================================
# Section 1: load_from_report() with explicit path
# ===========================================================================


class TestLoadFromReportExplicitPath:
    """load_from_report() with explicit report_path loads the real bridge."""

    def test_returns_nonempty_capabilities(self):
        """Report loading must return at least one capability entry."""
        caps = load_from_report(report_path=_REAL_BRIDGE_PATH)
        assert len(caps) > 0, "load_from_report returned empty dict with real bridge"

    def test_daily_interface_present(self):
        """The 'daily' interface from the bridge must appear in output."""
        caps = load_from_report(report_path=_REAL_BRIDGE_PATH)
        assert "daily" in caps, "daily interface missing from loaded capabilities"

    def test_fields_come_from_field_aliases(self):
        """fields must be $-prefixed aliases, not raw column names."""
        caps = load_from_report(report_path=_REAL_BRIDGE_PATH)
        daily_fields = caps["daily"]["fields"]
        # Raw columns are: open, close, high, low, vol, amount
        # Aliases are: $open, $close, $high, $low, $vol, $amount
        assert "$open" in daily_fields, "fields should contain $open (alias), not open (raw)"
        assert "$close" in daily_fields, "fields should contain $close (alias)"
        assert "open" not in daily_fields, "fields must not contain raw column name 'open'"

    def test_all_interfaces_have_required_keys(self):
        """Every capability entry must have the consumer-contract shape."""
        caps = load_from_report(report_path=_REAL_BRIDGE_PATH)
        required_keys = {"fields", "freq", "lag_days", "available_from", "join_mode", "factor_hints"}
        for name, spec in caps.items():
            missing = required_keys - set(spec.keys())
            assert not missing, f"Interface '{name}' missing keys: {missing}"

    def test_daily_freq_is_daily(self):
        """daily interface must report freq='daily'."""
        caps = load_from_report(report_path=_REAL_BRIDGE_PATH)
        assert caps["daily"]["freq"] == "daily"

    def test_income_vip_freq_is_quarterly(self):
        """income_vip interface must report freq='quarterly'."""
        caps = load_from_report(report_path=_REAL_BRIDGE_PATH)
        assert "income_vip" in caps
        assert caps["income_vip"]["freq"] == "quarterly"

    def test_income_vip_lag_days_is_45(self):
        """income_vip interface must report lag_days=45."""
        caps = load_from_report(report_path=_REAL_BRIDGE_PATH)
        assert caps["income_vip"]["lag_days"] == 45

    def test_quarterly_join_mode_is_forward_fill(self):
        """Quarterly freq must derive join_mode='forward_fill'."""
        caps = load_from_report(report_path=_REAL_BRIDGE_PATH)
        assert caps["income_vip"]["join_mode"] == "forward_fill"

    def test_daily_join_mode_is_same_day(self):
        """Daily freq must derive join_mode='same_day'."""
        caps = load_from_report(report_path=_REAL_BRIDGE_PATH)
        assert caps["daily"]["join_mode"] == "same_day"

    def test_moneyflow_present(self):
        """moneyflow interface from the bridge must appear in output."""
        caps = load_from_report(report_path=_REAL_BRIDGE_PATH)
        assert "moneyflow" in caps

    def test_daily_basic_present(self):
        """daily_basic interface from the bridge must appear in output."""
        caps = load_from_report(report_path=_REAL_BRIDGE_PATH)
        assert "daily_basic" in caps


# ===========================================================================
# Section 2: V1 tolerates _saturation: null
# ===========================================================================


class TestSaturationNullTolerance:
    """V1 loading must not filter interfaces when _saturation is null."""

    def test_null_saturation_does_not_filter(self):
        """_get_best_saturation(None) must return None, not 0.0."""
        result = _get_best_saturation(None)
        assert result is None, "null saturation should return None (unknown)"

    def test_dict_saturation_returns_float(self):
        """_get_best_saturation(dict) must return a float."""
        sat = {"2020-2024": {"date_saturation": 0.8}}
        result = _get_best_saturation(sat)
        assert isinstance(result, float)
        assert result == 0.8

    def test_real_bridge_interfaces_not_filtered(self):
        """With real bridge (all _saturation: null), all interfaces with aliases must load."""
        caps = load_from_report(report_path=_REAL_BRIDGE_PATH)
        # The bridge has 4 interfaces: daily, daily_basic, income_vip, moneyflow
        # All have _saturation: null — none should be filtered
        assert "daily" in caps
        assert "daily_basic" in caps
        assert "income_vip" in caps
        assert "moneyflow" in caps

    def test_available_from_is_none_for_v1(self):
        """V1: available_from must be None (periods not used)."""
        caps = load_from_report(report_path=_REAL_BRIDGE_PATH)
        for name, spec in caps.items():
            assert spec["available_from"] is None, f"Interface '{name}' should have available_from=None in V1, got {spec['available_from']}"


# ===========================================================================
# Section 3: Path resolution priority
# ===========================================================================


class TestPathResolution:
    """Path resolution must follow: explicit > config > project fallback."""

    def test_explicit_path_takes_priority(self):
        """Explicit report_path must be used when it exists."""
        caps = load_from_report(report_path=_REAL_BRIDGE_PATH)
        assert len(caps) > 0

    def test_explicit_nonexistent_returns_fallback(self):
        """Explicit path that does not exist must trigger fallback."""
        caps = load_from_report(report_path="/nonexistent/path/report.json")
        # Must fall back to DATA_CAPABILITIES
        assert caps == dict(DATA_CAPABILITIES)

    def test_config_report_path_resolution(self):
        """experiment.yaml data_capability_registry.report_path must be resolved."""
        config = {
            "data_capability_registry": {
                "enabled": True,
                "report_path": "../../../data/.data_capability_report.json",
            }
        }
        with patch(
            "quantaalpha.factors.data_capability._load_experiment_config",
            return_value=config,
        ):
            path = _resolve_report_path()
            assert path is not None, "Config-based path resolution returned None"
            assert path.exists(), f"Resolved path does not exist: {path}"

    def test_config_nonexistent_path_returns_none(self):
        """Config report_path pointing to nonexistent file must return None."""
        config = {
            "data_capability_registry": {
                "report_path": "/nonexistent/report.json",
            }
        }
        with patch(
            "quantaalpha.factors.data_capability._load_experiment_config",
            return_value=config,
        ):
            # Also make the project fallback not exist for this test
            with patch(
                "quantaalpha.factors.data_capability._PROJECT_REPORT_FALLBACK",
                Path("/nonexistent/fallback.json"),
            ):
                path = _resolve_report_path()
                assert path is None


# ===========================================================================
# Section 4: Fallback to DATA_CAPABILITIES
# ===========================================================================


class TestFallback:
    """Safe fallback to DATA_CAPABILITIES when report is missing or invalid."""

    def test_missing_report_falls_back(self):
        """Missing report must return DATA_CAPABILITIES."""
        with patch(
            "quantaalpha.factors.data_capability._resolve_report_path",
            return_value=None,
        ):
            caps = load_from_report()
            assert caps == dict(DATA_CAPABILITIES)

    def test_invalid_json_falls_back(self):
        """Invalid JSON must return DATA_CAPABILITIES."""
        with patch(
            "quantaalpha.factors.data_capability._resolve_report_path",
            return_value=Path("/dev/null"),
        ):
            caps = load_from_report()
            assert caps == dict(DATA_CAPABILITIES)

    def test_empty_interfaces_falls_back(self):
        """Report with empty interfaces dict must return DATA_CAPABILITIES."""
        report_data = {"_meta": {"schema_version": 1}, "interfaces": {}}
        with patch(
            "quantaalpha.factors.data_capability._resolve_report_path",
            return_value=Path("/dev/null"),
        ):
            with patch(
                "quantaalpha.factors.data_capability._load_raw_report",
                return_value=report_data,
            ):
                caps = load_from_report()
                assert caps == dict(DATA_CAPABILITIES)

    def test_fallback_has_hardcoded_capabilities(self):
        """Fallback must contain the hardcoded price_volume and financial."""
        with patch(
            "quantaalpha.factors.data_capability._resolve_report_path",
            return_value=None,
        ):
            caps = load_from_report()
            assert "price_volume" in caps
            assert "financial" in caps

    def test_fallback_preserves_existing_consumer_shape(self):
        """Fallback capabilities must have the consumer-contract keys."""
        caps = dict(DATA_CAPABILITIES)
        required = {"fields", "freq", "lag_days", "available_from", "join_mode", "factor_hints"}
        for name, spec in caps.items():
            missing = required - set(spec.keys())
            assert not missing, f"Fallback '{name}' missing keys: {missing}"


# ===========================================================================
# Section 5: _load_raw_report
# ===========================================================================


class TestLoadRawReport:
    """_load_raw_report must parse valid JSON and return None on failure."""

    def test_valid_json(self, tmp_path):
        """Valid JSON file must be parsed."""
        f = tmp_path / "report.json"
        f.write_text('{"interfaces": {}}')
        result = _load_raw_report(f)
        assert result == {"interfaces": {}}

    def test_invalid_json_returns_none(self, tmp_path):
        """Invalid JSON must return None, not raise."""
        f = tmp_path / "bad.json"
        f.write_text("not json at all {{{")
        result = _load_raw_report(f)
        assert result is None

    def test_nonexistent_returns_none(self):
        """Nonexistent file must return None."""
        result = _load_raw_report(Path("/nonexistent/report.json"))
        assert result is None


# ===========================================================================
# Section 6: V1 does not depend on periods or date_saturation
# ===========================================================================


class TestV1NoDependencyOnPeriods:
    """V1 must not require 'periods' or 'date_saturation' in the JSON."""

    def test_report_without_periods_loads(self, tmp_path):
        """A report with _saturation: null and no periods must load correctly."""
        report = {
            "_meta": {"schema_version": 1},
            "interfaces": {
                "daily": {
                    "mode": "reverse_date_range",
                    "fields": ["open", "close"],
                    "field_aliases": ["$open", "$close"],
                    "freq": "daily",
                    "lag_days": 0,
                    "factor_hints": ["momentum"],
                    "is_auxiliary": False,
                    "_saturation": None,
                }
            },
        }
        f = tmp_path / "report.json"
        f.write_text(json.dumps(report))
        caps = load_from_report(report_path=f)
        assert "daily" in caps
        assert caps["daily"]["fields"] == ["$open", "$close"]

    def test_report_with_empty_saturation_dict(self, tmp_path):
        """A report with _saturation: {} (empty dict) must not crash."""
        report = {
            "_meta": {"schema_version": 1},
            "interfaces": {
                "test_interface": {
                    "mode": "reverse_date_range",
                    "fields": ["x"],
                    "field_aliases": ["$x"],
                    "freq": "daily",
                    "lag_days": 0,
                    "factor_hints": [],
                    "_saturation": {},
                }
            },
        }
        f = tmp_path / "report.json"
        f.write_text(json.dumps(report))
        caps = load_from_report(report_path=f)
        # Empty dict saturation -> _get_best_saturation returns 0.0 -> filtered
        # This is correct: empty dict means "known but all zero"
        # But the test proves it doesn't crash
        assert isinstance(caps, dict)

    def test_report_with_saturation_below_threshold_filtered(self, tmp_path):
        """A report with low saturation must be filtered when saturation is present."""
        report = {
            "_meta": {"schema_version": 1},
            "interfaces": {
                "low_sat": {
                    "mode": "reverse_date_range",
                    "fields": ["x"],
                    "field_aliases": ["$x"],
                    "freq": "daily",
                    "lag_days": 0,
                    "_saturation": {
                        "2020-2024": {"date_saturation": 0.1},
                    },
                }
            },
        }
        f = tmp_path / "report.json"
        f.write_text(json.dumps(report))
        caps = load_from_report(report_path=f, saturation_threshold=0.5)
        # low_sat has saturation 0.1 < 0.5, should be filtered -> fallback
        assert caps == dict(DATA_CAPABILITIES)

    def test_report_with_saturation_above_threshold_kept(self, tmp_path):
        """A report with high saturation must be kept."""
        report = {
            "_meta": {"schema_version": 1},
            "interfaces": {
                "high_sat": {
                    "mode": "reverse_date_range",
                    "fields": ["x"],
                    "field_aliases": ["$x"],
                    "freq": "daily",
                    "lag_days": 0,
                    "_saturation": {
                        "2020-2024": {"date_saturation": 0.9},
                    },
                }
            },
        }
        f = tmp_path / "report.json"
        f.write_text(json.dumps(report))
        caps = load_from_report(report_path=f, saturation_threshold=0.5)
        assert "high_sat" in caps


# ===========================================================================
# Section 7: Config block in experiment.yaml
# ===========================================================================


class TestConfigBlock:
    """experiment.yaml must support data_capability_registry config block."""

    def test_config_has_required_keys(self):
        """Config block must support enabled, report_path, saturation_threshold."""
        import yaml

        config_path = Path(__file__).resolve().parents[1] / "configs" / "experiment.yaml"
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        reg = config.get("data_capability_registry", {})
        assert "enabled" in reg, "Config missing data_capability_registry.enabled"
        assert "report_path" in reg, "Config missing data_capability_registry.report_path"
        assert "saturation_threshold" in reg, "Config missing data_capability_registry.saturation_threshold"

    def test_config_enabled_is_true(self):
        """data_capability_registry.enabled must be true."""
        import yaml

        config_path = Path(__file__).resolve().parents[1] / "configs" / "experiment.yaml"
        config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        assert config["data_capability_registry"]["enabled"] is True


# ===========================================================================
# Section 8: get_data_capabilities() compatibility
# ===========================================================================


class TestConsumerCompatibility:
    """load_from_report() output must be passable to get_data_capabilities()."""

    def test_report_caps_normalize_through_get_data_capabilities(self):
        """Capabilities from load_from_report must be normalizable."""
        caps = load_from_report(report_path=_REAL_BRIDGE_PATH)
        normalized = get_data_capabilities(caps)
        assert len(normalized) > 0
        for name, spec in normalized.items():
            assert isinstance(spec["fields"], list)
            assert isinstance(spec["freq"], str)
            assert isinstance(spec["lag_days"], (int, float))
            assert isinstance(spec["join_mode"], str)
            assert isinstance(spec["factor_hints"], list)

    def test_fallback_caps_normalize_through_get_data_capabilities(self):
        """Fallback capabilities must be normalizable."""
        caps = dict(DATA_CAPABILITIES)
        normalized = get_data_capabilities(caps)
        assert "price_volume" in normalized
        assert "financial" in normalized
