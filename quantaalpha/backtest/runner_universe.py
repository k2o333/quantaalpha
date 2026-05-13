"""Universe helper functions for the qlib backtest runner."""

from __future__ import annotations

from typing import Any


def load_stock_filter_metadata(config: dict[str, Any], instruments: list[str]) -> dict[str, dict[str, Any]]:
    """Load listing metadata for stock-filter rules."""
    from qlib.data import D

    all_instruments = D.list_instruments(
        D.instruments("all"),
        start_time=config["data"].get("start_time"),
        end_time=config["data"].get("end_time"),
        as_list=False,
    )
    metadata: dict[str, dict[str, Any]] = {}
    for instrument in instruments:
        instrument_meta: dict[str, Any] = {}
        if isinstance(all_instruments, dict) and instrument in all_instruments:
            date_range = all_instruments[instrument]
            if isinstance(date_range, (list, tuple)) and date_range:
                instrument_meta["list_date"] = str(date_range[0])
        metadata[instrument] = instrument_meta
    return metadata
