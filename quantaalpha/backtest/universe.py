from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class UniverseResolution:
    instruments: list[str]
    metadata: dict[str, Any]
    warnings: list[str]


def normalize_stock_filter_config(config: dict[str, Any] | None) -> dict[str, Any]:
    cfg = dict(config or {})
    return {
        "enabled": bool(cfg.get("enabled", False)),
        "exclude_markets": [str(m).lower() for m in cfg.get("exclude_markets", [])],
        "exclude_st": bool(cfg.get("exclude_st", False)),
        "min_list_days": max(int(cfg.get("min_list_days", 0) or 0), 0),
    }


def instrument_market_code(instrument: str) -> str:
    if "." not in instrument:
        return ""
    return instrument.rsplit(".", 1)[-1].lower()


def filter_by_market(instruments: list[str], exclude_markets: list[str]) -> list[str]:
    excluded = {m.lower() for m in exclude_markets}
    if not excluded:
        return list(instruments)
    return [inst for inst in instruments if instrument_market_code(inst) not in excluded]


def filter_stocks(
    instruments: list[str],
    instrument_meta: dict[str, dict[str, Any]] | None,
    *,
    exclude_st: bool = False,
    min_list_days: int = 0,
    as_of_date: str | datetime | None = None,
) -> tuple[list[str], list[str]]:
    meta_map = instrument_meta or {}
    warnings: list[str] = []
    resolved_date = _coerce_date(as_of_date)

    filtered = list(instruments)
    if exclude_st:
        st_missing = [
            inst for inst in filtered
            if "is_st" not in meta_map.get(inst, {}) and "name" not in meta_map.get(inst, {})
        ]
        if st_missing:
            warnings.append("ST metadata missing for some instruments; skipped ST filter for those entries.")
        filtered = [
            inst for inst in filtered
            if not _is_st_stock(inst, meta_map.get(inst, {}))
        ]

    if min_list_days > 0:
        list_days_missing = [
            inst for inst in filtered
            if "list_date" not in meta_map.get(inst, {})
        ]
        if list_days_missing:
            warnings.append("Listing-date metadata missing for some instruments; skipped min_list_days filter for those entries.")
        filtered = [
            inst for inst in filtered
            if _has_min_list_days(meta_map.get(inst, {}), min_list_days, resolved_date)
        ]

    return filtered, warnings


def build_universe_metadata(
    *,
    market: str,
    rules: dict[str, Any],
    before_count: int,
    after_count: int,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "market": market,
        "filter_enabled": bool(rules.get("enabled")),
        "rules": {
            "exclude_markets": list(rules.get("exclude_markets", [])),
            "exclude_st": bool(rules.get("exclude_st", False)),
            "min_list_days": int(rules.get("min_list_days", 0) or 0),
        },
        "instrument_count_before": before_count,
        "instrument_count_after": after_count,
        "warnings": list(warnings or []),
    }


def _coerce_date(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        logger.warning("Failed to parse as_of_date=%s for stock universe filtering", value)
        return None


def _is_st_stock(instrument: str, meta: dict[str, Any]) -> bool:
    if "is_st" in meta:
        return bool(meta.get("is_st"))
    name = str(meta.get("name", "")).upper()
    return "ST" in name if name else False


def _has_min_list_days(meta: dict[str, Any], min_list_days: int, as_of_date: datetime | None) -> bool:
    list_date = meta.get("list_date")
    if list_date is None:
        return True
    try:
        list_dt = datetime.fromisoformat(str(list_date))
    except ValueError:
        return True
    if as_of_date is None:
        return True
    return (as_of_date - list_dt).days >= min_list_days
