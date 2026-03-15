from __future__ import annotations

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


def render_data_capabilities(capabilities: dict[str, dict[str, Any]] | None = None) -> str:
    registry = capabilities or DATA_CAPABILITIES
    sections = []
    for name, spec in registry.items():
        fields = ", ".join(spec.get("fields", [])) or "(unspecified)"
        freq = spec.get("freq", "unknown")
        lag_days = spec.get("lag_days", "unknown")
        join_mode = spec.get("join_mode", "unknown")
        hints = ", ".join(spec.get("factor_hints", [])) or "general research"
        sections.append(
            f"- {name}: fields={fields}; freq={freq}; lag_days={lag_days}; "
            f"join_mode={join_mode}; typical_uses={hints}"
        )
    return "Available data capabilities:\n" + "\n".join(sections)
