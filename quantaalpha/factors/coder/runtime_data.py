"""Runtime data helpers for factor coder H5/parquet parity migration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd
import polars as pl


STANDARD_FRAME_PARQUET = "standard_frame.parquet"
STANDARD_FRAME_MANIFEST = "standard_frame_manifest.json"
H5_ORACLE_INPUT = "daily_pv.h5"


def write_standard_frame_runtime_data(
    *,
    frame: pl.DataFrame | pd.DataFrame,
    target_root: str | Path,
    source_manifest: Mapping[str, Any] | None = None,
    write_h5_oracle: bool = False,
) -> dict[str, Any]:
    """Write a governed standard-frame runtime parquet artifact."""

    root = Path(target_root)
    root.mkdir(parents=True, exist_ok=True)
    normalized = _normalize_standard_frame(frame)
    parquet_path = root / STANDARD_FRAME_PARQUET
    normalized.write_parquet(parquet_path)
    manifest = {
        "runtime_data": {
            "format": "parquet",
            "path": STANDARD_FRAME_PARQUET,
            "row_count": normalized.height,
            "columns": normalized.columns,
        },
        "source_manifest": dict(source_manifest or {}),
    }
    (root / STANDARD_FRAME_MANIFEST).write_text(
        json.dumps(manifest, ensure_ascii=True, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    if write_h5_oracle:
        _write_h5_oracle_input(normalized, root / H5_ORACLE_INPUT)
    return manifest


def load_standard_frame_runtime_data(data_root: str | Path) -> pl.DataFrame:
    """Load the standard-frame parquet artifact for factor execution."""

    root = Path(data_root)
    parquet_path = root / STANDARD_FRAME_PARQUET
    if not parquet_path.exists():
        raise FileNotFoundError(f"factor runtime standard-frame parquet is missing: {parquet_path}")
    return _normalize_standard_frame(pl.scan_parquet(str(parquet_path)).collect())


def read_standard_frame_runtime_columns(data_root: str | Path) -> list[str]:
    """Read standard-frame parquet columns without materializing rows."""

    root = Path(data_root)
    parquet_path = root / STANDARD_FRAME_PARQUET
    if not parquet_path.exists():
        raise FileNotFoundError(f"factor runtime standard-frame parquet is missing: {parquet_path}")
    return list(pl.scan_parquet(str(parquet_path)).collect_schema().names())


def compute_factor_output_parquet(
    *,
    data_root: str | Path,
    expression: str,
    factor_name: str,
    output_path: str | Path,
) -> pd.DataFrame:
    """Compute one factor from standard-frame parquet and write parquet output."""

    from quantaalpha.backtest.expression import SharedPolarsExpressionKernel

    frame = load_standard_frame_runtime_data(data_root)
    result = SharedPolarsExpressionKernel(frame, compat_mode="h5_coder").compute_expression(expression, factor_name)
    result = _normalize_factor_result(result, factor_name=factor_name)
    output = result.reset_index()
    output.to_parquet(output_path, index=False)
    return result


def compute_h5_oracle_output(
    *,
    data_root: str | Path,
    expression: str,
    factor_name: str,
    output_path: str | Path,
) -> pd.DataFrame:
    """Compute one factor through the current pandas/H5 oracle path."""

    from quantaalpha.factors.coder import function_lib
    from quantaalpha.factors.coder.expr_parser import bind_expression_columns, parse_expression, parse_symbol

    root = Path(data_root)
    h5_input = root / H5_ORACLE_INPUT
    if not h5_input.exists():
        raise FileNotFoundError(f"H5 oracle input is missing: {h5_input}")
    df = pd.read_hdf(h5_input, key="data")
    parsed = parse_expression(parse_symbol(expression, df.columns))
    bound = bind_expression_columns(parsed, df.columns)
    eval_globals = {
        name: value
        for name, value in vars(function_lib).items()
        if not name.startswith("__")
    }
    eval_globals.update({"np": np, "pd": pd, "df": df})
    df[factor_name] = eval(bound, eval_globals, {})
    result = df[factor_name].astype(np.float64)
    result.to_hdf(output_path, key="data")
    return _normalize_factor_result(result, factor_name=factor_name)


def read_h5_oracle_result(path: str | Path, *, factor_name: str) -> pd.DataFrame:
    """Read a current H5 factor result into the normalized factor result contract."""

    result = pd.read_hdf(path, key="data")
    return _normalize_factor_result(result, factor_name=factor_name)


def read_parquet_factor_result(path: str | Path, *, factor_name: str) -> pd.DataFrame:
    """Read a parquet factor result into the normalized factor result contract."""

    frame = pd.read_parquet(path)
    if {"datetime", "instrument", factor_name}.issubset(frame.columns):
        return _normalize_factor_result(frame.set_index(["datetime", "instrument"])[[factor_name]], factor_name=factor_name)
    if {"datetime", "instrument", "value"}.issubset(frame.columns):
        return _normalize_factor_result(frame.set_index(["datetime", "instrument"])[["value"]], factor_name=factor_name)
    raise ValueError(f"unsupported parquet factor result schema: {list(frame.columns)}")


def assert_factor_frame_parity(
    h5_result: pd.DataFrame | pd.Series,
    parquet_result: pd.DataFrame | pd.Series,
    *,
    factor_name: str,
    rtol: float = 1e-7,
    atol: float = 1e-7,
) -> dict[str, Any]:
    """Assert H5 oracle and parquet runtime outputs match on keys and values."""

    left = _normalize_factor_result(h5_result, factor_name=factor_name)
    right = _normalize_factor_result(parquet_result, factor_name=factor_name)
    if not left.index.equals(right.index):
        missing_left = right.index.difference(left.index)
        missing_right = left.index.difference(right.index)
        raise AssertionError(
            "factor parity index mismatch: "
            f"missing_from_h5={len(missing_left)} missing_from_parquet={len(missing_right)}"
        )
    left_values = left[factor_name].to_numpy(dtype=float)
    right_values = right[factor_name].to_numpy(dtype=float)
    left_nan = np.isnan(left_values)
    right_nan = np.isnan(right_values)
    if not np.array_equal(left_nan, right_nan):
        raise AssertionError("factor parity NaN mask mismatch")
    comparable = ~(left_nan | right_nan)
    diffs = np.abs(left_values[comparable] - right_values[comparable])
    max_abs_diff = float(diffs.max()) if diffs.size else 0.0
    if not np.allclose(left_values, right_values, rtol=rtol, atol=atol, equal_nan=True):
        raise AssertionError(f"factor parity value mismatch: max_abs_diff={max_abs_diff}")
    return {
        "rows": len(left),
        "nan_count": int(left_nan.sum()),
        "max_abs_diff": max_abs_diff,
        "rtol": rtol,
        "atol": atol,
    }


def _normalize_standard_frame(frame: pl.DataFrame | pd.DataFrame) -> pl.DataFrame:
    if isinstance(frame, pd.DataFrame):
        if isinstance(frame.index, pd.MultiIndex) and {"datetime", "instrument"}.issubset(set(frame.index.names)):
            frame = frame.reset_index()
        frame = pl.from_pandas(frame)
    if "datetime" not in frame.columns or "instrument" not in frame.columns:
        raise ValueError("standard-frame runtime data requires datetime and instrument columns")
    return frame.with_columns(
        pl.col("datetime").cast(pl.Date),
        pl.col("instrument").cast(pl.Utf8),
    ).sort(["datetime", "instrument"])


def _write_h5_oracle_input(frame: pl.DataFrame, path: Path) -> None:
    pdf = frame.to_pandas()
    pdf["datetime"] = pd.to_datetime(pdf["datetime"])
    pdf = pdf.set_index(["datetime", "instrument"]).sort_index()
    pdf.to_hdf(path, key="data")


def _normalize_factor_result(result: pd.DataFrame | pd.Series, *, factor_name: str) -> pd.DataFrame:
    if isinstance(result, pd.Series):
        result = result.to_frame(name=factor_name)
    else:
        result = result.copy()
        if list(result.columns) == ["value"]:
            result.columns = [factor_name]
        elif factor_name not in result.columns and len(result.columns) == 1:
            result.columns = [factor_name]
    if not isinstance(result.index, pd.MultiIndex) or result.index.names != ["datetime", "instrument"]:
        if {"datetime", "instrument"}.issubset(result.columns):
            result = result.set_index(["datetime", "instrument"])
        else:
            raise ValueError("factor result requires MultiIndex(datetime, instrument)")
    index_df = result.index.to_frame(index=False)
    index_df["datetime"] = pd.Series(pd.to_datetime(index_df["datetime"]).to_numpy(dtype="datetime64[ns]"))
    normalized_index = pd.MultiIndex.from_frame(index_df[["datetime", "instrument"]])
    result.index = normalized_index
    result = result[[factor_name]].astype(float).sort_index()
    return result
