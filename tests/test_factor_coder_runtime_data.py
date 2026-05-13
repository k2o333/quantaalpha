from __future__ import annotations

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
