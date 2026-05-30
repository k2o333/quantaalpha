from __future__ import annotations

from pathlib import Path

import polars as pl
import pytest


def _write_active(root: Path, interface: str, frame: pl.DataFrame) -> None:
    active = root / interface / "clean" / "active"
    active.mkdir(parents=True)
    frame.write_parquet(active / "part-000.parquet")


def test_generate_daily_panel_field_inventory_classifies_keys_and_numeric_candidates(tmp_path: Path) -> None:
    from quantaalpha.backtest.data_admission import generate_daily_panel_field_inventory

    _write_active(
        tmp_path,
        "daily_basic",
        pl.DataFrame(
            {
                "ts_code": ["000001.SZ"],
                "trade_date": ["20240102"],
                "turnover_rate": [1.2],
                "_update_time": ["2024-01-02 12:00:00"],
            }
        ),
    )

    inventory = generate_daily_panel_field_inventory(tmp_path, interfaces=["daily_basic"])

    rows = {(row["source_interface"], row["source_field"]): row for row in inventory}
    assert rows[("daily_basic", "ts_code")]["role"] == "join_key"
    assert rows[("daily_basic", "trade_date")]["role"] == "date_key"
    assert rows[("daily_basic", "turnover_rate")]["role"] == "numeric_candidate"
    assert rows[("daily_basic", "turnover_rate")]["first_stage_status"] == "needs_review"
    assert rows[("daily_basic", "_update_time")]["role"] == "audit_metadata"


def test_build_daily_panel_allowlist_validates_metadata_and_renders_prompt_capability() -> None:
    from quantaalpha.backtest.data_admission import (
        build_daily_panel_allowlist,
        render_prompt_capabilities_from_allowlist,
        validate_requested_expression_fields,
    )

    allowlist = build_daily_panel_allowlist(
        [
            {
                "source_interface": "daily_basic",
                "source_field": "turnover_rate",
                "feature_name": "$daily_basic_turnover_rate",
                "dtype": "float64",
                "join_key": ("datetime", "instrument"),
                "time_policy": "same_trade_date_no_lookahead",
                "missing_policy": "nan",
                "allowed_usage": ("expression",),
            },
            {
                "source_interface": "moneyflow_mkt_dc",
                "source_field": "net_amount",
                "feature_name": "$moneyflow_mkt_dc_net_amount",
                "dtype": "float64",
                "join_key": ("datetime",),
                "time_policy": "same_trade_date_no_lookahead",
                "missing_policy": "nan",
                "allowed_usage": ("context",),
            },
        ]
    )
    capabilities = render_prompt_capabilities_from_allowlist(allowlist, source_manifest_version="test-v1")

    assert capabilities["expression_fields"] == ["$daily_basic_turnover_rate"]
    assert capabilities["context_fields"] == ["$moneyflow_mkt_dc_net_amount"]
    assert capabilities["source_manifest_version"] == "test-v1"
    validate_requested_expression_fields(["$daily_basic_turnover_rate"], allowlist)
    with pytest.raises(ValueError, match="not admitted as expression field"):
        validate_requested_expression_fields(["$moneyflow_mkt_dc_net_amount"], allowlist)


def test_daily_panel_allowlist_rejects_missing_time_policy_and_duplicate_features() -> None:
    from quantaalpha.backtest.data_admission import build_daily_panel_allowlist

    with pytest.raises(ValueError, match="time_policy"):
        build_daily_panel_allowlist(
            [
                {
                    "source_interface": "daily_basic",
                    "source_field": "turnover_rate",
                    "feature_name": "$daily_basic_turnover_rate",
                    "dtype": "float64",
                    "join_key": ("datetime", "instrument"),
                    "missing_policy": "nan",
                    "allowed_usage": ("expression",),
                }
            ]
        )
    with pytest.raises(ValueError, match="duplicate feature_name"):
        build_daily_panel_allowlist(
            [
                {
                    "source_interface": "daily_basic",
                    "source_field": "turnover_rate",
                    "feature_name": "$dup",
                    "dtype": "float64",
                    "join_key": ("datetime", "instrument"),
                    "time_policy": "same_trade_date_no_lookahead",
                    "missing_policy": "nan",
                    "allowed_usage": ("expression",),
                },
                {
                    "source_interface": "moneyflow",
                    "source_field": "buy_sm_vol",
                    "feature_name": "$dup",
                    "dtype": "float64",
                    "join_key": ("datetime", "instrument"),
                    "time_policy": "same_trade_date_no_lookahead",
                    "missing_policy": "nan",
                    "allowed_usage": ("expression",),
                },
            ]
        )


def test_non_daily_daily_panel_field_reaches_standard_frame_and_prompt_capability() -> None:
    from quantaalpha.backtest.data_admission import build_daily_panel_allowlist, render_prompt_capabilities_from_allowlist
    from quantaalpha.backtest.standard_frame import App5StandardFrameBuilder, StandardFrameRequest

    daily_frame = pl.DataFrame(
        {
            "ts_code": ["000001.SZ"],
            "trade_date": ["20240102"],
            "open": [10.0],
            "high": [10.5],
            "low": [9.5],
            "close": [10.2],
            "vol": [1000.0],
            "amount": [1020.0],
            "pct_chg": [1.0],
        }
    )
    daily_basic_frame = pl.DataFrame(
        {
            "ts_code": ["000001.SZ"],
            "trade_date": ["20240102"],
            "turnover_rate": [1.2],
        }
    )

    class FakeAdapter:
        def read(self, interface_name: str, **kwargs: object) -> pl.DataFrame:
            del kwargs
            return {"daily": daily_frame, "daily_basic": daily_basic_frame}[interface_name]

    allowlist = build_daily_panel_allowlist(
        [
            {
                "source_interface": "daily_basic",
                "source_field": "turnover_rate",
                "feature_name": "$daily_basic_turnover_rate",
                "dtype": "float64",
                "join_key": ("datetime", "instrument"),
                "time_policy": "same_trade_date_no_lookahead",
                "missing_policy": "required",
                "allowed_usage": ("expression", "backtest_standard_frame"),
            }
        ]
    )
    result = App5StandardFrameBuilder(adapter=FakeAdapter(), storage_root="data").build(
        StandardFrameRequest(optional_fields=tuple(allowlist.expression_fields()))
    )
    capabilities = render_prompt_capabilities_from_allowlist(allowlist, source_manifest_version="test-v1")

    assert result.frame["$daily_basic_turnover_rate"].to_list() == [1.2]
    assert capabilities["expression_fields"] == ["$daily_basic_turnover_rate"]


def test_daily_panel_inventory_marks_ambiguous_amount_and_return_fields_blocked(tmp_path: Path) -> None:
    from quantaalpha.backtest.data_admission import generate_daily_panel_field_inventory

    _write_active(
        tmp_path,
        "moneyflow",
        pl.DataFrame(
            {
                "ts_code": ["000001.SZ"],
                "trade_date": ["20240102"],
                "amount": [100.0],
                "pct_chg": [1.0],
                "buy_sm_amount": [2.0],
            }
        ),
    )

    inventory = generate_daily_panel_field_inventory(tmp_path, interfaces=["moneyflow"])
    rows = {row["source_field"]: row for row in inventory}

    assert rows["amount"]["first_stage_status"] == "blocked"
    assert rows["pct_chg"]["first_stage_status"] == "blocked"
    assert rows["buy_sm_amount"]["first_stage_status"] == "needs_review"
    assert rows["amount"]["duplicate_of"] == "amount"
    assert "ambiguous" in rows["amount"]["block_reason"]
    assert "nullability" in rows["buy_sm_amount"]


def test_build_default_daily_panel_allowlist_admits_conservative_multi_interface_fields() -> None:
    from quantaalpha.backtest.data_admission import build_default_daily_panel_allowlist

    allowlist = build_default_daily_panel_allowlist()
    names = {field.feature_name for field in allowlist.expression_fields()}

    assert "$daily_basic_turnover_rate" in names
    assert "$moneyflow_buy_sm_amount" in names
    assert "$cyq_perf_winner_rate" in names
    assert "$cyq_perf_cost_5pct" in names
    assert "$cyq_perf_cost_50pct" in names
    assert "$cyq_perf_cost_95pct" in names
    assert "$cyq_chips_chip_entropy" in names
    assert "$cyq_chips_peak_price" in names
    assert "$cyq_chips_peak_percent" in names
    assert "$cyq_chips_top5_concentration" in names
    assert "$cyq_chips_width_5_95" in names
    assert not any(name.startswith("$stock_hsgt") for name in names)


def test_cyq_perf_cost_tranche_reaches_standard_frame_and_prompt_capability() -> None:
    from quantaalpha.backtest.data_admission import build_default_daily_panel_allowlist, render_prompt_capabilities_from_allowlist
    from quantaalpha.backtest.standard_frame import App5StandardFrameBuilder, StandardFrameRequest

    daily_frame = pl.DataFrame(
        {
            "ts_code": ["000001.SZ"],
            "trade_date": ["20240102"],
            "open": [10.0],
            "high": [10.5],
            "low": [9.5],
            "close": [10.2],
            "vol": [1000.0],
            "amount": [1020.0],
            "pct_chg": [1.0],
        }
    )
    cyq_perf_frame = pl.DataFrame(
        {
            "ts_code": ["000001.SZ"],
            "trade_date": ["20240102"],
            "cost_5pct": [8.8],
            "cost_50pct": [9.7],
            "cost_95pct": [11.4],
        }
    )

    class FakeAdapter:
        def read(self, interface_name: str, **kwargs: object) -> pl.DataFrame:
            del kwargs
            if interface_name == "daily":
                return daily_frame
            if interface_name == "cyq_perf":
                return cyq_perf_frame
            if interface_name == "trade_cal":
                raise KeyError(interface_name)
            raise AssertionError(interface_name)

    allowlist = build_default_daily_panel_allowlist()
    cyq_cost_fields = tuple(
        field
        for field in allowlist.expression_fields()
        if field.feature_name in {"$cyq_perf_cost_5pct", "$cyq_perf_cost_50pct", "$cyq_perf_cost_95pct"}
    )
    result = App5StandardFrameBuilder(adapter=FakeAdapter(), storage_root="data").build(
        StandardFrameRequest(optional_fields=cyq_cost_fields)
    )
    capabilities = render_prompt_capabilities_from_allowlist(allowlist, source_manifest_version="test-v1")

    assert result.frame.select("$cyq_perf_cost_5pct", "$cyq_perf_cost_50pct", "$cyq_perf_cost_95pct").row(0) == (8.8, 9.7, 11.4)
    assert "$cyq_perf_cost_5pct" in capabilities["expression_fields"]
    assert "$cyq_perf_cost_50pct" in capabilities["expression_fields"]
    assert "$cyq_perf_cost_95pct" in capabilities["expression_fields"]


def test_cyq_chips_scalar_fields_reach_standard_frame_and_prompt_capability() -> None:
    from quantaalpha.backtest.data_admission import build_default_daily_panel_allowlist, render_prompt_capabilities_from_allowlist
    from quantaalpha.backtest.standard_frame import App5StandardFrameBuilder, StandardFrameRequest

    daily_frame = pl.DataFrame(
        {
            "ts_code": ["000001.SZ"],
            "trade_date": ["20240102"],
            "open": [10.0],
            "high": [10.5],
            "low": [9.5],
            "close": [10.2],
            "vol": [1000.0],
            "amount": [1020.0],
            "pct_chg": [1.0],
        }
    )
    scalar_frame = pl.DataFrame(
        {
            "ts_code": ["000001.SZ"],
            "trade_date": ["20240102"],
            "chip_entropy": [1.2],
            "peak_price": [9.8],
            "peak_percent": [12.0],
            "top5_concentration": [0.4],
            "width_5_95": [3.1],
        }
    )

    class FakeAdapter:
        def read(self, interface_name: str, **kwargs: object) -> pl.DataFrame:
            del kwargs
            if interface_name == "daily":
                return daily_frame
            if interface_name == "cyq_chips_scalar":
                return scalar_frame
            if interface_name == "trade_cal":
                raise KeyError(interface_name)
            raise AssertionError(interface_name)

    allowlist = build_default_daily_panel_allowlist()
    chip_fields = tuple(field for field in allowlist.expression_fields() if field.source_interface == "cyq_chips_scalar")
    result = App5StandardFrameBuilder(adapter=FakeAdapter(), storage_root="data").build(StandardFrameRequest(optional_fields=chip_fields))
    capabilities = render_prompt_capabilities_from_allowlist(allowlist, source_manifest_version="test-v1")

    assert result.frame.select("$cyq_chips_peak_price", "$cyq_chips_top5_concentration").row(0) == (9.8, 0.4)
    assert "$cyq_chips_chip_entropy" in capabilities["expression_fields"]
    assert "$cyq_chips_width_5_95" in capabilities["expression_fields"]
