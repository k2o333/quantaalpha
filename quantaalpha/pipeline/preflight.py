"""Pipeline startup checks for App5-backed standard-frame sources."""

from __future__ import annotations

from quantaalpha.backtest.standard_frame import App5StandardFrameBuilder, request_from_mapping


def run_standard_frame_source_preflight(backtest_noqlib_config: dict) -> None:
    """Reject incomplete standard-frame sources before capability materialization."""
    standard_frame_config = dict(backtest_noqlib_config.get("standard_frame") or {})
    if not standard_frame_config:
        return
    storage_root = backtest_noqlib_config.get("app5_storage_root") or standard_frame_config.get("storage_root") or "data"
    request = request_from_mapping(
        {
            **standard_frame_config,
            "storage_root": str(storage_root),
        }
    )
    App5StandardFrameBuilder(storage_root=storage_root).validate_source_readiness(request)
