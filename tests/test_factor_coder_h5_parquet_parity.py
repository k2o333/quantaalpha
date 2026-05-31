from __future__ import annotations

import pandas as pd
import polars as pl
import pytest
import sys
from pathlib import Path


QUANTAALPHA_ROOT = Path(__file__).resolve().parents[1]


def _standard_frame() -> pl.DataFrame:
    rows = []
    for instrument, offset in [("000001.SZ", 0.0), ("000002.SZ", 1.0)]:
        for day in range(1, 5):
            close = float(day + offset)
            rows.append(
                {
                    "datetime": pd.Timestamp(f"2020-01-0{day}"),
                    "instrument": instrument,
                    "$open": close,
                    "$high": close + 0.5,
                    "$low": close - 0.5,
                    "$close": close,
                    "$volume": 100.0 + day,
                    "$vwap": close,
                    "$return": 0.01 * day,
                    "$daily_basic_turnover_rate": 0.1 * day,
                }
            )
    return pl.DataFrame(rows)


def test_h5_and_parquet_outputs_match_for_expanded_field(tmp_path) -> None:
    from quantaalpha.factors.coder.runtime_data import (
        assert_factor_frame_parity,
        compute_factor_output_parquet,
        compute_h5_oracle_output,
        write_standard_frame_runtime_data,
    )

    write_standard_frame_runtime_data(
        frame=_standard_frame(),
        target_root=tmp_path,
        source_manifest={"cache_identity": "fixture"},
        write_h5_oracle=True,
    )

    expression = "TS_MEAN($daily_basic_turnover_rate, 2) + $close / DELAY($close, 1)"
    h5_result = compute_h5_oracle_output(
        data_root=tmp_path,
        expression=expression,
        factor_name="expanded_alpha",
        output_path=tmp_path / "result.h5",
    )
    parquet_result = compute_factor_output_parquet(
        data_root=tmp_path,
        expression=expression,
        factor_name="expanded_alpha",
        output_path=tmp_path / "result.parquet",
    )

    summary = assert_factor_frame_parity(h5_result, parquet_result, factor_name="expanded_alpha")

    assert summary["rows"] == len(h5_result)
    assert summary["max_abs_diff"] == pytest.approx(0.0)


def test_h5_and_parquet_outputs_match_for_loose_window_pctchange_expression(tmp_path) -> None:
    from quantaalpha.factors.coder.runtime_data import (
        assert_factor_frame_parity,
        compute_factor_output_parquet,
        compute_h5_oracle_output,
        write_standard_frame_runtime_data,
    )

    write_standard_frame_runtime_data(
        frame=_standard_frame(),
        target_root=tmp_path,
        source_manifest={"cache_identity": "fixture"},
        write_h5_oracle=True,
    )

    expression = "RANK(TS_PCTCHANGE($return, 2) / (TS_STD($return, 3) + 1e-8))"
    h5_result = compute_h5_oracle_output(
        data_root=tmp_path,
        expression=expression,
        factor_name="vol_mom",
        output_path=tmp_path / "result.h5",
    )
    parquet_result = compute_factor_output_parquet(
        data_root=tmp_path,
        expression=expression,
        factor_name="vol_mom",
        output_path=tmp_path / "result.parquet",
    )

    summary = assert_factor_frame_parity(h5_result, parquet_result, factor_name="vol_mom")

    assert summary["rows"] == len(h5_result)


def test_h5_and_parquet_outputs_match_for_rank_with_float_noise(tmp_path) -> None:
    from quantaalpha.backtest.expression import SharedPolarsExpressionKernel

    frame = pl.DataFrame(
        {
            "datetime": [pd.Timestamp("2026-01-02")] * 3,
            "instrument": ["000001.SZ", "000002.SZ", "000003.SZ"],
            "$x": [10_000_000.0, 10_000_000.000000002, 1.0],
        }
    )
    result = SharedPolarsExpressionKernel(frame, compat_mode="h5_coder").compute_expression("RANK($x)", "ranked")

    assert result.loc[(pd.Timestamp("2026-01-02"), "000001.SZ"), "ranked"] == pytest.approx(5 / 6)
    assert result.loc[(pd.Timestamp("2026-01-02"), "000002.SZ"), "ranked"] == pytest.approx(5 / 6)


def test_h5_and_parquet_rank_keeps_distinct_small_decimal_values(tmp_path) -> None:
    from quantaalpha.backtest.expression import SharedPolarsExpressionKernel

    frame = pl.DataFrame(
        {
            "datetime": [pd.Timestamp("2026-01-02")] * 3,
            "instrument": ["000001.SZ", "000002.SZ", "000003.SZ"],
            "$x": [-0.19555555512098763, -0.19555555501, 1.0],
        }
    )
    result = SharedPolarsExpressionKernel(frame, compat_mode="h5_coder").compute_expression("RANK($x)", "ranked")

    assert result.loc[(pd.Timestamp("2026-01-02"), "000001.SZ"), "ranked"] == pytest.approx(1 / 3)
    assert result.loc[(pd.Timestamp("2026-01-02"), "000002.SZ"), "ranked"] == pytest.approx(2 / 3)


def test_h5_and_parquet_outputs_match_for_loose_ts_rank_expression(tmp_path) -> None:
    from quantaalpha.factors.coder.runtime_data import (
        assert_factor_frame_parity,
        compute_factor_output_parquet,
        compute_h5_oracle_output,
        write_standard_frame_runtime_data,
    )

    write_standard_frame_runtime_data(
        frame=_standard_frame(),
        target_root=tmp_path,
        source_manifest={"cache_identity": "fixture"},
        write_h5_oracle=True,
    )

    expression = "TS_RANK($return, 5) * ($daily_basic_turnover_rate / TS_MEDIAN($daily_basic_turnover_rate, 2))"
    h5_result = compute_h5_oracle_output(
        data_root=tmp_path,
        expression=expression,
        factor_name="loose_ts_rank",
        output_path=tmp_path / "result.h5",
    )
    parquet_result = compute_factor_output_parquet(
        data_root=tmp_path,
        expression=expression,
        factor_name="loose_ts_rank",
        output_path=tmp_path / "result.parquet",
    )

    summary = assert_factor_frame_parity(h5_result, parquet_result, factor_name="loose_ts_rank")

    assert summary["rows"] == len(h5_result)
    assert summary["nan_count"] < summary["rows"]


def test_factor_workspace_dual_runtime_keeps_h5_and_writes_parquet_result(tmp_path, monkeypatch) -> None:
    from jinja2 import Template

    from quantaalpha.factors.coder.config import FACTOR_COSTEER_SETTINGS
    from quantaalpha.factors.coder.factor import FactorFBWorkspace, FactorTask
    from quantaalpha.factors.coder.runtime_data import write_standard_frame_runtime_data

    data_root = tmp_path / "data"
    write_standard_frame_runtime_data(
        frame=_standard_frame(),
        target_root=data_root,
        source_manifest={"cache_identity": "fixture"},
        write_h5_oracle=True,
    )
    expression = "TS_MEAN($daily_basic_turnover_rate, 2) + $close / DELAY($close, 1)"
    template = Template((QUANTAALPHA_ROOT / "quantaalpha/factors/coder/template.jinjia2").read_text(encoding="utf-8"))
    task = FactorTask(
        factor_name="expanded_alpha",
        factor_description="fixture",
        factor_formulation="fixture",
        factor_expression=expression,
    )
    workspace = FactorFBWorkspace(target_task=task, raise_exception=True)
    workspace.workspace_path = tmp_path / "workspace"
    workspace.inject_code(
        **{
            "factor.py": template.render(
                expression=expression,
                factor_name="expanded_alpha",
            )
        }
    )

    monkeypatch.setattr(FACTOR_COSTEER_SETTINGS, "data_folder", str(data_root))
    monkeypatch.setattr(FACTOR_COSTEER_SETTINGS, "data_folder_debug", str(data_root))
    monkeypatch.setattr(FACTOR_COSTEER_SETTINGS, "python_bin", sys.executable)
    monkeypatch.setenv("QUANTAALPHA_FACTOR_CODER_RUNTIME", "dual_h5_parquet")

    message, result = workspace.execute("All")

    assert "Parquet runtime parity passed" in message
    assert result is not None
    assert (workspace.workspace_path / "result.h5").exists()
    assert (workspace.workspace_path / "result.parquet").exists()
    assert (workspace.workspace_path / "factor_runtime_parity.json").exists()


def test_factor_workspace_polars_runtime_returns_feedback_for_expression_errors(tmp_path, monkeypatch) -> None:
    from jinja2 import Template

    from quantaalpha.factors.coder.config import FACTOR_COSTEER_SETTINGS
    from quantaalpha.factors.coder.factor import FactorFBWorkspace, FactorTask
    from quantaalpha.factors.coder.runtime_data import write_standard_frame_runtime_data

    data_root = tmp_path / "data"
    write_standard_frame_runtime_data(
        frame=_standard_frame(),
        target_root=data_root,
        source_manifest={"cache_identity": "fixture"},
        write_h5_oracle=True,
    )
    expression = "UNSUPPORTED($close, 2)"
    template = Template((QUANTAALPHA_ROOT / "quantaalpha/factors/coder/template.jinjia2").read_text(encoding="utf-8"))
    task = FactorTask(
        factor_name="bad_expr",
        factor_description="fixture",
        factor_formulation="fixture",
        factor_expression=expression,
    )
    workspace = FactorFBWorkspace(target_task=task, raise_exception=False)
    workspace.workspace_path = tmp_path / "workspace"
    workspace.inject_code(
        **{
            "factor.py": template.render(
                expression=expression,
                factor_name="bad_expr",
            )
        }
    )

    monkeypatch.setattr(FACTOR_COSTEER_SETTINGS, "data_folder", str(data_root))
    monkeypatch.setattr(FACTOR_COSTEER_SETTINGS, "data_folder_debug", str(data_root))
    monkeypatch.setenv("QUANTAALPHA_FACTOR_CODER_RUNTIME", "polars_parquet")

    message, result = workspace.execute("All")

    assert result is None
    assert "Runtime Error: unsupported function or arity: UNSUPPORTED/2" in message
    assert "Expected parquet output file not found." in message
