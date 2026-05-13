from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any


# Path to the experiment config file (quantaalpha/configs/experiment.yaml)
EXPERIMENT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "configs" / "experiment.yaml"

# Project-level fallback path for the data capability report
_PROJECT_REPORT_FALLBACK = Path(__file__).resolve().parents[3] / "data" / ".data_capability_report.json"


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


def _load_experiment_config() -> dict[str, Any]:
    """Load the experiment configuration from experiment.yaml."""
    if not EXPERIMENT_CONFIG_PATH.exists():
        return {}
    try:
        import yaml

        return yaml.safe_load(EXPERIMENT_CONFIG_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _resolve_report_path(explicit_path: str | Path | None = None) -> Path | None:
    """
    Resolve the report path according to the priority:
    1. explicit report_path parameter
    2. report_path from experiment.yaml config
    3. project-level fallback path

    Returns the resolved Path or None if no valid path found.
    """
    # Priority 1: explicit path
    if explicit_path is not None:
        path = Path(explicit_path)
        if path.exists():
            return path
        return None

    # Priority 2: from experiment.yaml config
    config = _load_experiment_config()
    registry_cfg = config.get("data_capability_registry", {})
    raw_path = registry_cfg.get("report_path")
    if raw_path:
        # Path is relative to the config file's parent directory
        path = (EXPERIMENT_CONFIG_PATH.parent / raw_path).resolve()
        if path.exists():
            return path

    # Priority 3: project-level fallback
    if _PROJECT_REPORT_FALLBACK.exists():
        return _PROJECT_REPORT_FALLBACK

    return None


def _load_raw_report(report_path: Path) -> dict[str, Any] | None:
    """
    Load and parse the raw JSON report from the given path.
    Returns None if the file cannot be read or parsed.
    """
    try:
        return json.loads(report_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _get_best_saturation(saturation: Any) -> float | None:
    """
    Extract the best (maximum) date_saturation value.

    Handles two shapes:
    - V1: _saturation is null -> returns None (unknown, do not filter)
    - Future: _saturation is a dict with periods -> returns max date_saturation

    Returns None when saturation data is unavailable (V1 null case).
    """
    if saturation is None:
        return None
    if isinstance(saturation, dict):
        best = 0.0
        for period_data in saturation.values():
            if isinstance(period_data, dict):
                sat = period_data.get("date_saturation")
                if isinstance(sat, (int, float)) and sat > best:
                    best = sat
        return best
    return None


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

    # Pass through semantic keys
    for key in ("mode", "layer", "is_auxiliary"):
        if key in spec:
            normalized[key] = spec[key]

    # Pass through financial PIT consumer-entry keys
    for key in ("storage_kind", "storage_path", "versioned", "disclosure_field", "revision_field", "next_revision_field"):
        if key in spec:
            normalized[key] = spec[key]

    return normalized


def load_from_report(
    report_path: str | Path | None = None,
    saturation_threshold: float = 0.5,
) -> dict[str, dict[str, Any]]:
    """
    Load data capabilities from a JSON report file.

    Path resolution priority:
    1. explicit report_path parameter
    2. report_path from experiment.yaml config
    3. project-level fallback path
    4. fallback to DATA_CAPABILITIES if report is missing or invalid

    Args:
        report_path: Explicit path to the report JSON file.
        saturation_threshold: Minimum date_saturation required for an interface
            to be included. Interfaces with best saturation below this threshold
            are filtered out.

    Returns:
        A dict mapping capability names to their specs, in the same format
        as returned by get_data_capabilities(). The 'fields' values come
        from the JSON's 'field_aliases', not raw source field names.
    """
    # Try to resolve and load the report
    resolved_path = _resolve_report_path(report_path)

    if resolved_path is None:
        # Fallback to DATA_CAPABILITIES
        return dict(DATA_CAPABILITIES)

    raw_report = _load_raw_report(resolved_path)
    if raw_report is None:
        # Fallback to DATA_CAPABILITIES
        return dict(DATA_CAPABILITIES)

    interfaces = raw_report.get("interfaces", {})
    if not interfaces:
        return dict(DATA_CAPABILITIES)

    capabilities: dict[str, dict[str, Any]] = {}

    storage_root = raw_report.get("_meta", {}).get("storage_root", "")

    for name, info in interfaces.items():
        # Require semantic block after flat-compat removal.
        semantic = info.get("semantic")
        if not semantic:
            continue
        field_aliases = semantic.get("field_aliases")

        # Skip if no field_aliases (not useful for factor mining)
        if not field_aliases:
            continue

        # V1: tolerate _saturation: null (do not filter by saturation)
        best_sat = _get_best_saturation(info.get("_saturation"))
        if best_sat is not None and best_sat < saturation_threshold:
            continue

        # Determine available_from (V1: leave as None)
        available_from = None

        # Build the capability spec using field_aliases for fields
        mode = semantic.get("mode")
        freq = semantic.get("freq", "daily")
        lag_days = semantic.get("lag_days", 0)
        join_mode = semantic.get("join_mode")
        if join_mode is None:
            join_mode = _FREQ_TO_JOIN_MODE.get(str(freq), "same_day")
        factor_hints = semantic.get("factor_hints", [])
        layer = semantic.get("layer")
        is_auxiliary = semantic.get("is_auxiliary")

        capabilities[name] = {
            "fields": list(field_aliases),
            "freq": str(freq),
            "lag_days": lag_days,
            "available_from": available_from,
            "join_mode": str(join_mode),
            "factor_hints": list(factor_hints) if factor_hints else [],
        }
        if mode is not None:
            capabilities[name]["mode"] = mode
        if layer is not None:
            capabilities[name]["layer"] = layer
        if is_auxiliary is not None:
            capabilities[name]["is_auxiliary"] = is_auxiliary

        # Financial PIT consumer-entry metadata derivation
        if layer == "financial_pit":
            runtime_block = info.get("runtime", {}) or {}
            runtime_pit_path = runtime_block.get("financial_pit_path")
            if runtime_pit_path:
                storage_path = runtime_pit_path
            elif storage_root:
                storage_path = f"{storage_root}/.financial_pit/{name}.parquet"
            else:
                storage_path = f"/home/quan/testdata/aspipe_v4/data/.financial_pit/{name}.parquet"

            capabilities[name]["storage_kind"] = "financial_pit_parquet"
            capabilities[name]["storage_path"] = storage_path
            capabilities[name]["versioned"] = True
            capabilities[name]["disclosure_field"] = "disclosure_date"
            capabilities[name]["revision_field"] = "revision_seq"
            capabilities[name]["next_revision_field"] = "next_disclosure_date"

    # If no capabilities loaded, fallback to DATA_CAPABILITIES
    if not capabilities:
        return dict(DATA_CAPABILITIES)

    return capabilities


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
        layer = spec.get("layer")
        storage_kind = spec.get("storage_kind")
        storage_path = spec.get("storage_path")
        versioned = spec.get("versioned")

        parts = [
            f"- {name}: fields={fields}; freq={freq}; lag_days={lag_days}; available_from={available_from}; join_mode={join_mode}; typical_uses={hints}",
        ]
        if layer is not None:
            parts.append(f"  layer={layer}")
        if storage_kind is not None:
            parts.append(f"  storage_kind={storage_kind}")
        if storage_path is not None:
            parts.append(f"  storage_path={storage_path}")
        if versioned is not None:
            parts.append(f"  versioned={versioned}")
        sections.append("; ".join(parts))
    return "Available data capabilities:\n" + "\n".join(sections)


def capabilities_from_standard_frame_optional_fields(
    optional_fields: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    manifest_version: str | None = None,
) -> dict[str, dict[str, Any]]:
    """Build prompt capabilities from governed standard-frame optional fields."""

    expression_fields = sorted(
        str(item["feature_name"])
        for item in optional_fields
        if "feature_name" in item and "expression" in tuple(item.get("allowed_usage", ()))
    )
    if not expression_fields:
        return {}
    capability = {
        "fields": expression_fields,
        "freq": "daily",
        "lag_days": 0,
        "available_from": None,
        "join_mode": "same_day",
        "factor_hints": ["expanded app5 daily panel", "liquidity", "moneyflow", "chip distribution"],
        "layer": "daily_panel",
        "source_manifest_version": manifest_version,
    }
    return {"expanded_daily_panel": capability}


def _load_financial_pit_frame_from_spec(interface_name: str, capability: Mapping[str, Any] | None):
    import polars as pl

    if not capability:
        raise ValueError(f"Unknown financial PIT interface: {interface_name}")

    if capability.get("layer") != "financial_pit":
        raise ValueError(f"Interface {interface_name} is not a financial_pit capability")

    storage_kind = capability.get("storage_kind")
    if storage_kind != "financial_pit_parquet":
        raise ValueError(f"Interface {interface_name} does not use supported storage_kind")

    storage_path = capability.get("storage_path")
    if not storage_path:
        raise ValueError(f"Interface {interface_name} has no financial PIT storage_path")

    return pl.read_parquet(str(storage_path))


def load_financial_pit_frame(
    interface_name: str,
    report_path: str | Path | None = None,
    latest_only: bool = True,
):
    """
    Load a minimal financial PIT frame for one interface.

    This is a first-round reader contract:
    - report-driven capability lookup
    - financial_pit interfaces only
    - disclosure_date versioned parquet only
    - optional latest_only filtering
    """
    import polars as pl

    capabilities = load_from_report(report_path)
    capability = capabilities.get(interface_name)
    df = _load_financial_pit_frame_from_spec(interface_name, capability)
    if latest_only:
        df = df.filter(pl.col("is_latest") == True)
    return df


def query_financial_pit_asof(
    interface_name: str,
    asof_date: str,
    report_path: str | Path | None = None,
    aliases: list[str] | None = None,
):
    """
    Query a financial PIT frame as of one disclosure-date cut.

    Semantics for this first round:
    - keep rows with disclosure_date <= asof_date
    - within each (instrument, report_period, alias) chain, keep the latest
      visible disclosure version as of that date
    - optional alias filtering
    """
    import polars as pl

    capabilities = load_from_report(report_path)
    capability = capabilities.get(interface_name)
    return _query_financial_pit_asof_from_spec(interface_name, capability, asof_date, aliases=aliases)


def query_financial_pit_panel_asof(
    interface_name: str,
    asof_date: str,
    report_path: str | Path | None = None,
    aliases: list[str] | None = None,
):
    """
    Convert financial PIT as-of rows into a single-day wide panel.

    Output shape:
    - index-like column: instrument
    - one value column per alias
    """
    df = query_financial_pit_asof(
        interface_name,
        asof_date,
        report_path=report_path,
        aliases=aliases,
    )
    if df.is_empty():
        return df.select(["instrument"]).unique()
    return (
        df.select(["instrument", "alias", "value"])
        .pivot(on="alias", index="instrument", values="value", aggregate_function="first")
        .sort("instrument")
    )


def _query_financial_pit_asof_from_spec(
    interface_name: str,
    capability_spec: Mapping[str, Any] | None,
    asof_date: str,
    aliases: list[str] | None = None,
):
    import polars as pl

    normalized_asof_date = str(asof_date).replace("-", "")

    df = _load_financial_pit_frame_from_spec(interface_name, capability_spec)
    df = df.with_columns(pl.col("disclosure_date").cast(pl.String).str.replace_all("-", "").alias("_cmp_disclosure_date"))
    df = df.filter(pl.col("_cmp_disclosure_date") <= normalized_asof_date)

    if aliases is not None:
        df = df.filter(pl.col("alias").is_in(list(aliases)))

    if df.is_empty():
        return df

    df = df.sort(["instrument", "report_period", "alias", "disclosure_date"])
    return (
        df.unique(subset=["instrument", "report_period", "alias"], keep="last")
        .drop("_cmp_disclosure_date")
        .sort(["instrument", "report_period", "alias"])
    )


def render_financial_pit_panel_preview(
    interface_name: str,
    capability_spec: Mapping[str, Any],
    asof_date: str | None = None,
    aliases: list[str] | None = None,
    max_rows: int = 5,
) -> str | None:
    """
    Render a compact financial PIT panel preview for upper-layer consumers.
    """
    import polars as pl

    try:
        df = _load_financial_pit_frame_from_spec(interface_name, capability_spec)
    except Exception:
        return None

    if df.is_empty():
        return None

    if asof_date is None:
        max_disclosure = df.select(pl.col("disclosure_date").cast(pl.String).str.replace_all("-", "").max()).item()
        asof_date = str(max_disclosure)

    panel = query_financial_pit_panel_from_spec(
        interface_name,
        capability_spec,
        asof_date=asof_date,
        aliases=aliases,
    )
    if panel.is_empty():
        return None

    preview = panel.head(max_rows)
    return (
        f"Financial PIT panel preview ({interface_name}, asof={asof_date}):\n"
        f"{preview}"
    )


def query_financial_pit_panel_from_spec(
    interface_name: str,
    capability_spec: Mapping[str, Any],
    asof_date: str,
    aliases: list[str] | None = None,
):
    df = _query_financial_pit_asof_from_spec(interface_name, capability_spec, asof_date, aliases=aliases)
    if df.is_empty():
        return df.select(["instrument"]).unique()
    return (
        df.select(["instrument", "alias", "value"])
        .pivot(on="alias", index="instrument", values="value", aggregate_function="first")
        .sort("instrument")
    )


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
