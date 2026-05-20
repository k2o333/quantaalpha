from __future__ import annotations

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
    assert result.index.names == ["datetime", "instrument"]
    assert result.loc[(pd.Timestamp("2020-01-02"), "000001.SZ"), "ret1"] == pytest.approx(0.2)


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
    assert not (data_root / "daily_pv.h5").exists()


def test_prepare_standard_frame_parquet_runtime_reuses_cache_without_h5(tmp_path, monkeypatch) -> None:
    from quantaalpha.backtest import standard_frame as standard_frame_module
    from quantaalpha.backtest.standard_frame import request_from_mapping
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
    request_hash = request_from_mapping(
        {
            "storage_root": str(tmp_path / "data"),
            "optional_fields": optional_fields,
        }
    ).identity_hash()
    for root in (data_root, debug_root):
        root.mkdir(parents=True)
        _standard_frame().write_parquet(root / "standard_frame.parquet")
        (root / "standard_frame_manifest.json").write_text("{}", encoding="utf-8")
    (data_root / ".standard_frame_source.json").write_text(
        f'{{"request_hash": "{request_hash}", "columns": ["$daily_basic_turnover_rate"]}}',
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
