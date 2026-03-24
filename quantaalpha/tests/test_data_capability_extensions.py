"""Tests for data capability extensions (S04): available_from and auto_discover_capabilities."""

import json
import tempfile
from pathlib import Path

import pytest

from quantaalpha.factors.data_capability import (
    normalize_capability_spec,
    get_data_capabilities,
    render_data_capabilities,
    auto_discover_capabilities,
    infer_available_from_from_parquet,
    DATA_CAPABILITIES,
    DEFAULT_CAPABILITY_SPEC,
    _FREQ_TO_JOIN_MODE,
)


class TestAvailableFromField:
    """Verify available_from is normalized correctly."""

    def test_spec_with_available_from(self):
        spec = normalize_capability_spec({
            "fields": ["$close"],
            "freq": "daily",
            "available_from": "2015-06-01",
        })
        assert spec["available_from"] == "2015-06-01"

    def test_spec_without_available_from_becomes_none(self):
        spec = normalize_capability_spec({
            "fields": ["$close"],
            "freq": "daily",
        })
        assert spec["available_from"] is None

    def test_spec_with_none_available_from_stays_none(self):
        spec = normalize_capability_spec({
            "fields": ["$close"],
            "freq": "daily",
            "available_from": None,
        })
        assert spec["available_from"] is None

    def test_default_capability_spec_available_from_is_none(self):
        assert DEFAULT_CAPABILITY_SPEC["available_from"] is None


class TestJoinModeInference:
    """Verify join_mode is inferred from freq when not explicitly set."""

    def test_daily_freq_infers_same_day(self):
        spec = normalize_capability_spec({"fields": [], "freq": "daily"})
        assert spec["join_mode"] == "same_day"

    def test_weekly_freq_infers_same_day(self):
        spec = normalize_capability_spec({"fields": [], "freq": "weekly"})
        assert spec["join_mode"] == "same_day"

    def test_quarterly_freq_infers_forward_fill(self):
        spec = normalize_capability_spec({"fields": [], "freq": "quarterly"})
        assert spec["join_mode"] == "forward_fill"

    def test_monthly_freq_infers_forward_fill(self):
        spec = normalize_capability_spec({"fields": [], "freq": "monthly"})
        assert spec["join_mode"] == "forward_fill"

    def test_annual_freq_infers_forward_fill(self):
        spec = normalize_capability_spec({"fields": [], "freq": "annual"})
        assert spec["join_mode"] == "forward_fill"

    def test_explicit_join_mode_overrides_freq_inference(self):
        spec = normalize_capability_spec({
            "fields": [],
            "freq": "quarterly",
            "join_mode": "same_day",  # override quarterly's default forward_fill
        })
        assert spec["join_mode"] == "same_day"

    def test_freq_to_join_mode_mapping_complete(self):
        assert set(_FREQ_TO_JOIN_MODE.keys()) == {
            "daily", "weekly", "monthly", "quarterly", "annual"
        }


class TestDataCapabilitiesRegistry:
    """Verify existing registry entries have available_from set."""

    def test_price_volume_has_available_from(self):
        caps = get_data_capabilities()
        assert caps["price_volume"]["available_from"] is not None
        assert caps["price_volume"]["available_from"] == "2010-01-01"

    def test_financial_has_available_from(self):
        caps = get_data_capabilities()
        assert caps["financial"]["available_from"] is not None
        assert caps["financial"]["available_from"] == "2008-01-01"

    def test_price_volume_join_mode_is_same_day(self):
        caps = get_data_capabilities()
        assert caps["price_volume"]["join_mode"] == "same_day"

    def test_financial_join_mode_is_forward_fill(self):
        caps = get_data_capabilities()
        assert caps["financial"]["join_mode"] == "forward_fill"


class TestRenderDataCapabilities:
    """Verify rendered output includes available_from and join_mode."""

    def test_render_includes_available_from(self):
        output = render_data_capabilities()
        assert "available_from=" in output

    def test_render_includes_join_mode(self):
        output = render_data_capabilities()
        assert "join_mode=" in output

    def test_render_shows_price_volume_date(self):
        output = render_data_capabilities()
        assert "price_volume" in output
        assert "2010-01-01" in output

    def test_render_shows_financial_date(self):
        output = render_data_capabilities()
        assert "financial" in output
        assert "2008-01-01" in output

    def test_render_shows_unknown_for_missing_date(self):
        caps = get_data_capabilities({
            "test_cap": {
                "fields": ["$x"],
                "freq": "daily",
            }
        })
        output = render_data_capabilities(caps)
        assert "test_cap" in output
        assert "available_from=(unknown)" in output


class TestAutoDiscoverCapabilities:
    """Verify auto_discover_capabilities handles missing dirs and new files."""

    def test_nonexistent_dir_returns_existing_registry(self):
        caps = auto_discover_capabilities("/nonexistent/path")
        assert "price_volume" in caps
        assert "financial" in caps

    def test_new_parquet_without_name_in_registry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            caps = auto_discover_capabilities(tmpdir)
            # No parquet files, should return original registry
            assert "price_volume" in caps

    def test_auto_discover_preserves_existing_available_from(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            caps = auto_discover_capabilities(tmpdir)
            # existing entry should retain its hardcoded date
            assert caps["price_volume"]["available_from"] == "2010-01-01"

    def test_auto_discover_json_serializable(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            caps = auto_discover_capabilities(tmpdir)
            json_str = json.dumps(caps)
            parsed = json.loads(json_str)
            assert "price_volume" in parsed


class TestInferAvailableFrom:
    """Verify parquet earliest-date inference is defensive."""

    def test_nonexistent_file_returns_none(self):
        result = infer_available_from_from_parquet("/nonexistent/file.parquet")
        assert result is None

    def test_invalid_parquet_returns_none(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bad_file = Path(tmpdir) / "bad.parquet"
            bad_file.write_text("not a parquet file")
            result = infer_available_from_from_parquet(bad_file)
            assert result is None
