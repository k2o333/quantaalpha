"""Runtime contract guards for mining pipeline setup."""

from __future__ import annotations


def validate_factor_coder_runtime_contract(
    *,
    backtest_backend: str | None,
    backtest_noqlib_config: dict | None,
) -> str:
    """Validate the App5/noqlib runtime contract before coder construction."""
    backend = str(backtest_backend or "qlib").strip().lower()
    config = dict(backtest_noqlib_config or {})
    runtime = str(config.get("factor_coder_runtime") or "").strip().lower()
    standard_frame = config.get("standard_frame")
    noqlib_enabled = backend == "noqlib" or bool(config.get("enabled"))
    standard_frame_enabled = isinstance(standard_frame, dict) and bool(standard_frame)
    if noqlib_enabled and standard_frame_enabled and runtime != "polars_parquet":
        raise RuntimeError(
            "App5/noqlib standard-frame mining requires factor_coder_runtime='polars_parquet' "
            "so Step 3 uses DirectPolarsCoder instead of legacy CoSTEER."
        )
    return runtime
