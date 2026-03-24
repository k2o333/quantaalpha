from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any


DATA_CAPABILITIES: dict[str, dict[str, Any]] = {
    "price_volume": {
        "fields": ["$open", "$close", "$high", "$low", "$volume", "$amount"],
        "freq": "daily",
        "lag_days": 0,
        "available_from": "2010-01-01",
        "join_mode": "same_day",
        "factor_hints": ["momentum", "reversal", "volatility", "liquidity"],
    },
    "financial": {
        "fields": ["$roa", "$roe", "$net_profit_margin"],
        "freq": "quarterly",
        "lag_days": 45,
        "available_from": "2008-01-01",
        "join_mode": "forward_fill",
        "factor_hints": ["quality", "value"],
    },
}


DEFAULT_CAPABILITY_SPEC: dict[str, Any] = {
    "fields": [],
    "freq": "daily",
    "lag_days": 0,
    "available_from": None,
    "join_mode": "same_day",
    "factor_hints": [],
}


# Mapping from freq to default join_mode
_FREQ_TO_JOIN_MODE: dict[str, str] = {
    "daily": "same_day",
    "weekly": "same_day",
    "monthly": "forward_fill",
    "quarterly": "forward_fill",
    "annual": "forward_fill",
}


def normalize_capability_spec(spec: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(spec, Mapping):
        raise TypeError("Capability spec must be a mapping.")

    fields = spec.get("fields") or DEFAULT_CAPABILITY_SPEC["fields"]
    freq = spec.get("freq") or DEFAULT_CAPABILITY_SPEC["freq"]
    lag_days = spec.get("lag_days")
    join_mode = spec.get("join_mode") or _FREQ_TO_JOIN_MODE.get(str(freq), DEFAULT_CAPABILITY_SPEC["join_mode"])
    available_from = spec.get("available_from")
    factor_hints = spec.get("factor_hints") or DEFAULT_CAPABILITY_SPEC["factor_hints"]

    normalized = {
        "fields": [str(field) for field in fields],
        "freq": str(freq),
        "lag_days": DEFAULT_CAPABILITY_SPEC["lag_days"] if lag_days is None else lag_days,
        "join_mode": str(join_mode),
        "available_from": str(available_from) if available_from is not None else None,
        "factor_hints": [str(hint) for hint in factor_hints],
    }
    return normalized


def get_data_capabilities(
    capabilities: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    registry = capabilities or DATA_CAPABILITIES
    normalized_registry: dict[str, dict[str, Any]] = {}
    for name in sorted(registry):
        normalized_registry[str(name)] = normalize_capability_spec(registry[name])
    return normalized_registry


def render_data_capabilities(capabilities: Mapping[str, Mapping[str, Any]] | None = None) -> str:
    registry = get_data_capabilities(capabilities)
    sections = []
    for name, spec in registry.items():
        fields = ", ".join(spec.get("fields", [])) or "(unspecified)"
        freq = spec.get("freq", DEFAULT_CAPABILITY_SPEC["freq"])
        lag_days = spec.get("lag_days", DEFAULT_CAPABILITY_SPEC["lag_days"])
        available_from = spec.get("available_from") or "(unknown)"
        join_mode = spec.get("join_mode", DEFAULT_CAPABILITY_SPEC["join_mode"])
        hints = ", ".join(spec.get("factor_hints", [])) or "general research"
        sections.append(
            f"- {name}: fields={fields}; freq={freq}; lag_days={lag_days}; "
            f"available_from={available_from}; join_mode={join_mode}; typical_uses={hints}"
        )
    return "Available data capabilities:\n" + "\n".join(sections)


def infer_available_from_from_parquet(parquet_path: str | Path) -> str | None:
    """
    Read the earliest date from a Parquet file's date/index column.
    Returns ISO date string (YYYY-MM-DD) or None if unreadable.
    """
    try:
        import polars as pl
        df = pl.read_parquet(str(parquet_path), n_rows=1)
        date_col = None
        for col in ["date", "trade_date", "$date", "$trade_date"]:
            if col in df.columns:
                date_col = col
                break
        if date_col is None:
            # Try first column if it looks like a date
            first_col = df.columns[0]
            series = df[first_col]
            if series.dtype in (pl.Date, pl.Datetime, pl.Time):
                date_col = first_col
        if date_col is None:
            return None
        min_val = df[date_col].min()
        if min_val is None:
            return None
        if hasattr(min_val, "date"):
            return min_val.date().isoformat()
        return str(min_val)[:10]
    except Exception:
        return None


def auto_discover_capabilities(
    data_dir: str | Path,
    capabilities: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    """
    Scan data_dir for Parquet files and infer available_from dates.
    Returns normalized capabilities with discovered dates merged in.
    """
    registry = dict(get_data_capabilities(capabilities))
    data_path = Path(data_dir)
    if not data_path.exists():
        return registry
    for parquet_file in data_path.glob("*.parquet"):
        name = parquet_file.stem
        discovered_date = infer_available_from_from_parquet(parquet_file)
        if name in registry:
            if registry[name].get("available_from") is None and discovered_date:
                registry[name]["available_from"] = discovered_date
        else:
            # Register new capability based on filename
            inferred_freq = "daily"
            if "_q" in name or "quarterly" in name:
                inferred_freq = "quarterly"
            registry[name] = {
                "fields": [],
                "freq": inferred_freq,
                "lag_days": 0,
                "available_from": discovered_date,
                "join_mode": _FREQ_TO_JOIN_MODE.get(inferred_freq, "same_day"),
                "factor_hints": [],
            }
    return registry
