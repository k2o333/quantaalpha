from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import polars as pl
import pytest


def _standard_frame() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "datetime": [pd.Timestamp("2020-01-01"), pd.Timestamp("2020-01-02")],
            "instrument": ["000001.SZ", "000001.SZ"],
            "$open": [10.0, 11.0],
            "$high": [10.5, 11.5],
            "$low": [9.5, 10.5],
            "$close": [10.0, 12.0],
            "$volume": [100.0, 120.0],
            "$vwap": [10.0, 12.0],
            "$return": [0.0, 0.2],
            "$daily_basic_turnover_rate": [1.0, 2.0],
        }
    )


def test_runtime_data_writes_and_loads_standard_frame_parquet(tmp_path) -> None:
    from quantaalpha.factors.coder.runtime_data import (
        load_standard_frame_runtime_data,
        write_standard_frame_runtime_data,
    )

    manifest = write_standard_frame_runtime_data(
        frame=_standard_frame(),
        target_root=tmp_path,
        source_manifest={"cache_identity": "fixture"},
    )

    loaded = load_standard_frame_runtime_data(tmp_path)

    assert manifest["runtime_data"]["format"] == "parquet"
    assert manifest["runtime_data"]["row_count"] == 2
    assert (tmp_path / "standard_frame.parquet").exists()
    assert (tmp_path / "standard_frame_manifest.json").exists()
    assert loaded.select("datetime", "instrument", "$daily_basic_turnover_rate").to_dicts() == [
        {"datetime": pd.Timestamp("2020-01-01").date(), "instrument": "000001.SZ", "$daily_basic_turnover_rate": 1.0},
        {"datetime": pd.Timestamp("2020-01-02").date(), "instrument": "000001.SZ", "$daily_basic_turnover_rate": 2.0},
    ]


def test_compute_factor_output_parquet_from_standard_frame(tmp_path) -> None:
    from quantaalpha.factors.coder.runtime_data import (
        compute_factor_output_parquet,
        write_standard_frame_runtime_data,
    )

    write_standard_frame_runtime_data(
        frame=_standard_frame(),
        target_root=tmp_path,
        source_manifest={"cache_identity": "fixture"},
    )

    result = compute_factor_output_parquet(
        data_root=tmp_path,
        expression="$close / DELAY($close, 1) - 1",
        factor_name="ret1",
        output_path=tmp_path / "result.parquet",
    )

    assert (tmp_path / "result.parquet").exists()
    assert isinstance(result, pl.DataFrame)
    value = result.filter((pl.col("datetime") == pd.Timestamp("2020-01-02")) & (pl.col("instrument") == "000001.SZ")).select("ret1").item()
    assert value == pytest.approx(0.2)


def test_factor_frame_parity_accepts_float_kernel_noise() -> None:
    from quantaalpha.factors.coder.runtime_data import assert_factor_frame_parity

    index = pd.MultiIndex.from_tuples(
        [(pd.Timestamp("2020-01-01"), "000001.SZ")],
        names=["datetime", "instrument"],
    )
    h5_result = pd.DataFrame({"alpha": [1.0]}, index=index)
    parquet_result = pd.DataFrame({"alpha": [1.0 + 9e-8]}, index=index)

    summary = assert_factor_frame_parity(h5_result, parquet_result, factor_name="alpha")

    assert summary["max_abs_diff"] == pytest.approx(9e-8)


def test_factor_frame_parity_rejects_material_value_difference() -> None:
    from quantaalpha.factors.coder.runtime_data import assert_factor_frame_parity

    index = pd.MultiIndex.from_tuples(
        [(pd.Timestamp("2020-01-01"), "000001.SZ")],
        names=["datetime", "instrument"],
    )
    h5_result = pd.DataFrame({"alpha": [1.0]}, index=index)
    parquet_result = pd.DataFrame({"alpha": [1.0002]}, index=index)

    with pytest.raises(AssertionError, match="factor parity value mismatch"):
        assert_factor_frame_parity(h5_result, parquet_result, factor_name="alpha")


def test_data_folder_intro_supports_standard_frame_parquet(tmp_path, monkeypatch) -> None:
    from quantaalpha.factors.coder.config import FACTOR_COSTEER_SETTINGS
    from quantaalpha.factors.coder.runtime_data import write_standard_frame_runtime_data
    from quantaalpha.factors.qlib_utils import get_data_folder_intro

    data_root = tmp_path / "data"
    debug_root = tmp_path / "debug"
    write_standard_frame_runtime_data(
        frame=_standard_frame(),
        target_root=debug_root,
        source_manifest={"cache_identity": "fixture"},
    )
    data_root.mkdir()
    monkeypatch.setattr(FACTOR_COSTEER_SETTINGS, "data_folder", str(data_root))
    monkeypatch.setattr(FACTOR_COSTEER_SETTINGS, "data_folder_debug", str(debug_root))

    intro = get_data_folder_intro(fname_reg=r".*standard_frame\.parquet$")

    assert "standard_frame.parquet" in intro
    assert "$daily_basic_turnover_rate" in intro


def test_prepare_standard_frame_uses_configured_parquet_runtime_without_h5_oracle(tmp_path, monkeypatch) -> None:
    from quantaalpha.backtest import standard_frame as standard_frame_module
    from quantaalpha.factors import qlib_utils
    from quantaalpha.factors.coder import config as coder_config
    from quantaalpha.factors.coder import runtime_data

    data_root = tmp_path / "factor_data"
    debug_root = tmp_path / "factor_data_debug"
    monkeypatch.setattr(coder_config.FACTOR_COSTEER_SETTINGS, "data_folder", str(data_root))
    monkeypatch.setattr(coder_config.FACTOR_COSTEER_SETTINGS, "data_folder_debug", str(debug_root))
    monkeypatch.setattr(qlib_utils.FACTOR_COSTEER_SETTINGS, "data_folder", str(data_root))
    monkeypatch.setattr(qlib_utils.FACTOR_COSTEER_SETTINGS, "data_folder_debug", str(debug_root))
    monkeypatch.setattr(qlib_utils.shutil, "copy2", lambda *_args, **_kwargs: None)

    class FakeBuilder:
        def __init__(self, **_kwargs) -> None:
            pass

        def build(self, _request):
            return SimpleNamespace(
                frame=_standard_frame(),
                manifest={"cache_identity": "fixture"},
            )

    write_h5_flags = []

    def fake_write_standard_frame_runtime_data(*, frame, target_root, source_manifest, write_h5_oracle):
        del source_manifest
        write_h5_flags.append(write_h5_oracle)
        target_root.mkdir(parents=True, exist_ok=True)
        frame.write_parquet(target_root / "standard_frame.parquet")
        (target_root / "standard_frame_manifest.json").write_text("{}", encoding="utf-8")
        if write_h5_oracle:
            (target_root / "daily_pv.h5").write_text("unexpected", encoding="utf-8")

    monkeypatch.setattr(standard_frame_module, "App5StandardFrameBuilder", FakeBuilder)
    monkeypatch.setattr(runtime_data, "write_standard_frame_runtime_data", fake_write_standard_frame_runtime_data)

    assert qlib_utils.prepare_data_folder_from_standard_frame(
        {
            "project_root": str(Path(__file__).resolve().parents[3]),
            "factor_coder_runtime": "parquet",
            "standard_frame": {
                "optional_fields": [
                    {
                        "source_interface": "daily_basic",
                        "source_field": "turnover_rate",
                        "feature_name": "$daily_basic_turnover_rate",
                        "time_policy": "same_trade_date_no_lookahead",
                    }
                ]
            },
        }
    )

    assert write_h5_flags == [False, False]
    assert (data_root / "standard_frame.parquet").exists()
    assert not (data_root / "daily_pv.h5").exists()


def test_prepare_standard_frame_loads_admission_profile_path_without_expanded_cli_profile(tmp_path, monkeypatch) -> None:
    from quantaalpha.backtest import standard_frame as standard_frame_module
    from quantaalpha.factors import qlib_utils
    from quantaalpha.factors.coder import config as coder_config
    from quantaalpha.factors.coder import runtime_data

    project_root = tmp_path / "project"
    (project_root / "docs" / "01-govern").mkdir(parents=True)
    profile_path = project_root / "config" / "factor_mining_data_admission.yaml"
    profile_path.parent.mkdir(parents=True)
    profile_path.write_text(
        """
version: 1
profiles:
  expanded_app5_v1:
    fields:
      - feature_name: "$daily_basic_turnover_rate"
        source_kind: daily_panel
        source_interface: daily_basic
        source_field: turnover_rate
        dtype: float64
        join_key: ["datetime", "instrument"]
        time_policy: same_trade_date_no_lookahead
        missing_policy: nan
        allowed_usage: ["expression", "backtest_standard_frame"]
        semantic_type: turnover
        unit: ratio
        scale: 1.0
        source_methodology: same-day daily panel field
""",
        encoding="utf-8",
    )

    data_root = tmp_path / "factor_data"
    debug_root = tmp_path / "factor_data_debug"
    monkeypatch.setattr(coder_config.FACTOR_COSTEER_SETTINGS, "data_folder", str(data_root))
    monkeypatch.setattr(coder_config.FACTOR_COSTEER_SETTINGS, "data_folder_debug", str(debug_root))
    monkeypatch.setattr(qlib_utils.FACTOR_COSTEER_SETTINGS, "data_folder", str(data_root))
    monkeypatch.setattr(qlib_utils.FACTOR_COSTEER_SETTINGS, "data_folder_debug", str(debug_root))
    monkeypatch.setattr(qlib_utils.shutil, "copy2", lambda *_args, **_kwargs: None)

    seen_admitted_fields = []

    class FakeBuilder:
        def __init__(self, **_kwargs) -> None:
            pass

        def build(self, request):
            seen_admitted_fields.extend(field.feature_name for field in request.admitted_fields)
            return SimpleNamespace(
                frame=_standard_frame(),
                manifest={"cache_identity": "fixture"},
            )

    def fake_write_standard_frame_runtime_data(*, frame, target_root, source_manifest, write_h5_oracle):
        del source_manifest
        target_root.mkdir(parents=True, exist_ok=True)
        frame.write_parquet(target_root / "standard_frame.parquet")
        (target_root / "standard_frame_manifest.json").write_text("{}", encoding="utf-8")
        assert write_h5_oracle is False

    monkeypatch.setattr(standard_frame_module, "App5StandardFrameBuilder", FakeBuilder)
    monkeypatch.setattr(runtime_data, "write_standard_frame_runtime_data", fake_write_standard_frame_runtime_data)

    assert qlib_utils.prepare_data_folder_from_standard_frame(
        {
            "project_root": str(project_root),
            "app5_storage_root": str(tmp_path / "data"),
            "factor_coder_runtime": "polars_parquet",
            "standard_frame": {
                "admission_profile_path": "config/factor_mining_data_admission.yaml",
                "admission_profile": "expanded_app5_v1",
            },
        }
    )
    assert seen_admitted_fields == ["$daily_basic_turnover_rate"]
    assert (data_root / "standard_frame.parquet").exists()


def test_standard_frame_latest_available_policy_records_effective_window(tmp_path) -> None:
    from quantaalpha.backtest.standard_frame import App5StandardFrameBuilder, request_from_mapping

    class FakeAdapter:
        def read(self, interface, *, start_date=None, end_date=None, columns=None, unique=True):
            assert end_date is None
            if interface == "daily":
                return pl.DataFrame(
                    {
                        "trade_date": ["20260102", "20260103"],
                        "ts_code": ["000001.SZ", "000001.SZ"],
                        "open": [10.0, 11.0],
                        "high": [10.5, 11.5],
                        "low": [9.5, 10.5],
                        "close": [10.2, 11.2],
                        "vol": [100.0, 120.0],
                        "amount": [1000.0, 1320.0],
                        "pct_chg": [0.0, 1.0],
                    }
                )
            if interface == "trade_cal":
                return pl.DataFrame(
                    {
                        "cal_date": ["20260102", "20260103"],
                        "is_open": [1, 1],
                    }
                )
            raise AssertionError(interface)

    request = request_from_mapping(
        {
            "start_date": "2026-01-01",
            "end_date_policy": "latest_available",
            "daily_interface": "daily",
            "storage_root": str(tmp_path),
        }
    )

    result = App5StandardFrameBuilder(adapter=FakeAdapter(), storage_root=tmp_path).build(request)

    assert result.manifest["request"]["end_date_policy"] == "latest_available"
    assert result.manifest["request"]["requested_end_date"] is None
    assert result.manifest["standard_frame"]["effective_start_date"] == "2026-01-02"
    assert result.manifest["standard_frame"]["effective_end_date"] == "2026-01-03"
    assert result.manifest["standard_frame"]["data_max_date"] == "2026-01-03"


def test_standard_frame_latest_available_lookback_bounds_materialization_window(tmp_path) -> None:
    from quantaalpha.backtest.standard_frame import App5StandardFrameBuilder, request_from_mapping

    calls: list[tuple[str, str | None, str | None, tuple[str, ...] | None]] = []

    class FakeAdapter:
        def read(self, interface, *, start_date=None, end_date=None, columns=None, unique=True):
            calls.append((interface, start_date, end_date, tuple(columns) if columns else None))
            if interface == "daily" and columns == ["trade_date"]:
                return pl.DataFrame({"trade_date": ["20260102", "20260520"]})
            if interface == "daily":
                assert start_date == "2025-05-20"
                assert end_date == "2026-05-20"
                return pl.DataFrame(
                    {
                        "trade_date": ["20260519", "20260520"],
                        "ts_code": ["000001.SZ", "000001.SZ"],
                        "open": [10.0, 11.0],
                        "high": [10.5, 11.5],
                        "low": [9.5, 10.5],
                        "close": [10.2, 11.2],
                        "vol": [100.0, 120.0],
                        "amount": [1000.0, 1320.0],
                        "pct_chg": [0.0, 1.0],
                    }
                )
            if interface == "trade_cal":
                assert start_date == "2025-05-20"
                assert end_date == "2026-05-20"
                return pl.DataFrame(
                    {
                        "cal_date": ["20260519", "20260520"],
                        "is_open": [1, 1],
                    }
                )
            raise AssertionError(interface)

    request = request_from_mapping(
        {
            "start_date": "2019-01-01",
            "end_date_policy": "latest_available",
            "lookback_days": 365,
            "daily_interface": "daily",
            "storage_root": str(tmp_path),
        }
    )

    result = App5StandardFrameBuilder(adapter=FakeAdapter(), storage_root=tmp_path).build(request)

    assert calls[0] == ("daily", "2019-01-01", None, ("trade_date",))
    assert result.manifest["request"]["start_date"] == "2025-05-20"
    assert result.manifest["request"]["end_date"] == "2026-05-20"
    assert result.manifest["request"]["end_date_policy"] == "latest_available"
    assert result.manifest["request"]["lookback_days"] == 365


def test_prepare_standard_frame_parquet_runtime_reuses_cache_without_h5(tmp_path, monkeypatch) -> None:
    from quantaalpha.backtest import standard_frame as standard_frame_module
    from quantaalpha.backtest.standard_frame import request_from_mapping
    from quantaalpha.backtest.standard_frame_source_contract import (
        source_interfaces_for_request,
        source_manifest_fingerprints,
    )
    from quantaalpha.factors import qlib_utils
    from quantaalpha.factors.coder import config as coder_config

    data_root = tmp_path / "factor_data"
    debug_root = tmp_path / "factor_data_debug"
    optional_fields = [
        {
            "source_interface": "daily_basic",
            "source_field": "turnover_rate",
            "feature_name": "$daily_basic_turnover_rate",
            "time_policy": "same_trade_date_no_lookahead",
        }
    ]
    request = request_from_mapping(
        {
            "storage_root": str(tmp_path / "data"),
            "optional_fields": optional_fields,
        }
    )
    request_hash = request.identity_hash()
    fingerprints = source_manifest_fingerprints(tmp_path / "data", source_interfaces_for_request(request))
    for root in (data_root, debug_root):
        root.mkdir(parents=True)
        _standard_frame().write_parquet(root / "standard_frame.parquet")
        (root / "standard_frame_manifest.json").write_text("{}", encoding="utf-8")
    (data_root / ".standard_frame_source.json").write_text(
        json.dumps(
            {
                "request_hash": request_hash,
                "columns": ["$daily_basic_turnover_rate"],
                "source_manifest_fingerprints": fingerprints,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(coder_config.FACTOR_COSTEER_SETTINGS, "data_folder", str(data_root))
    monkeypatch.setattr(coder_config.FACTOR_COSTEER_SETTINGS, "data_folder_debug", str(debug_root))
    monkeypatch.setattr(qlib_utils.FACTOR_COSTEER_SETTINGS, "data_folder", str(data_root))
    monkeypatch.setattr(qlib_utils.FACTOR_COSTEER_SETTINGS, "data_folder_debug", str(debug_root))

    class ShouldNotBuild:
        def __init__(self, **_kwargs) -> None:
            pass

        def build(self, _request):
            raise AssertionError("parquet runtime should reuse cache without requiring daily_pv.h5")

    monkeypatch.setattr(standard_frame_module, "App5StandardFrameBuilder", ShouldNotBuild)

    assert qlib_utils.prepare_data_folder_from_standard_frame(
        {
            "project_root": str(Path(__file__).resolve().parents[3]),
            "factor_coder_runtime": "parquet",
            "standard_frame": {
                "storage_root": str(tmp_path / "data"),
                "optional_fields": optional_fields,
            },
        }
    )


def test_factor_coder_universe_scope_can_decouple_from_backtest_instruments() -> None:
    from quantaalpha.factors.qlib_utils import _factor_coder_uses_backtest_universe

    assert _factor_coder_uses_backtest_universe({"factor_coder_universe_scope": "backtest"})
    assert not _factor_coder_uses_backtest_universe({"factor_coder_universe_scope": "all"})


def test_standard_frame_marker_reuse_rejects_changed_source_manifest() -> None:
    from quantaalpha.factors.qlib_utils import _standard_frame_marker_matches_source

    marker = {"source_manifest_fingerprints": {"daily": {"status": "active", "sha256": "sha256:old"}}}
    current = {"daily": {"status": "active", "sha256": "sha256:new"}}

    assert not _standard_frame_marker_matches_source(marker, current)


def test_standard_frame_preflight_rejects_uncovered_execution_segments() -> None:
    from quantaalpha.factors.qlib_utils import _standard_frame_preflight_summary

    frame = pl.DataFrame(
        {
            "datetime": [pd.Timestamp("2024-01-02"), pd.Timestamp("2024-01-03")],
            "instrument": ["A", "A"],
        }
    )

    with pytest.raises(ValueError, match="standard-frame coverage preflight failed") as exc_info:
        _standard_frame_preflight_summary(
            frame,
            {
                "train": ("2023-01-01", "2023-12-31"),
                "test": ("2024-01-02", "2024-01-03"),
            },
        )

    message = str(exc_info.value)
    assert "requested train=('2023-01-01', '2023-12-31')" in message
    assert "actual standard-frame bounds=('2024-01-02', '2024-01-03')" in message
