from __future__ import annotations

from collections.abc import Mapping
from typing import Any


DATA_CAPABILITIES: dict[str, dict[str, Any]] = {
    "price_volume": {
        "fields": ["$open", "$close", "$high", "$low", "$volume", "$amount"],
        "freq": "daily",
        "lag_days": 0,
        "join_mode": "same_day",
        "factor_hints": ["momentum", "reversal", "volatility", "liquidity"],
    },
    "financial": {
        "fields": ["$roa", "$roe", "$net_profit_margin"],
        "freq": "quarterly",
        "lag_days": 45,
        "join_mode": "forward_fill",
        "factor_hints": ["quality", "value"],
    },
}


DEFAULT_CAPABILITY_SPEC: dict[str, Any] = {
    "fields": [],
    "freq": "daily",
    "lag_days": 0,
    "join_mode": "same_day",
    "factor_hints": [],
}


def normalize_capability_spec(spec: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(spec, Mapping):
        raise TypeError("Capability spec must be a mapping.")

    fields = spec.get("fields") or DEFAULT_CAPABILITY_SPEC["fields"]
    freq = spec.get("freq") or DEFAULT_CAPABILITY_SPEC["freq"]
    lag_days = spec.get("lag_days")
    join_mode = spec.get("join_mode") or DEFAULT_CAPABILITY_SPEC["join_mode"]
    factor_hints = spec.get("factor_hints") or DEFAULT_CAPABILITY_SPEC["factor_hints"]

    normalized = {
        "fields": [str(field) for field in fields],
        "freq": str(freq),
        "lag_days": DEFAULT_CAPABILITY_SPEC["lag_days"] if lag_days is None else lag_days,
        "join_mode": str(join_mode),
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
        join_mode = spec.get("join_mode", DEFAULT_CAPABILITY_SPEC["join_mode"])
        hints = ", ".join(spec.get("factor_hints", [])) or "general research"
        sections.append(
            f"- {name}: fields={fields}; freq={freq}; lag_days={lag_days}; "
            f"join_mode={join_mode}; typical_uses={hints}"
        )
    return "Available data capabilities:\n" + "\n".join(sections)
