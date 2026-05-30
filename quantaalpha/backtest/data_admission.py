"""App5 daily-panel factor-mining data admission helpers."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import polars as pl

from quantaalpha.backtest.contracts import (
    EXPLICIT_APP5_INTERFACE_CLASSIFICATION,
    OptionalStandardFrameField,
    STANDARD_FRAME_FACTOR_FIELDS,
    validate_optional_standard_frame_field,
)


DAILY_PANEL_INTERFACES = tuple(
    interface for interface, (primary_class, _reason) in EXPLICIT_APP5_INTERFACE_CLASSIFICATION.items() if primary_class == "daily_panel"
)
JOIN_KEY_FIELDS = {"ts_code"}
DATE_KEY_FIELDS = {"trade_date"}
AUDIT_METADATA_FIELDS = {"_update_time", "update_time", "updated_at"}
RUNTIME_METADATA_PREFIXES = ("__", "_source_", "_runtime_")
CONTEXT_ONLY_INTERFACES = {"moneyflow_ind_dc", "moneyflow_ind_ths", "moneyflow_mkt_dc", "moneyflow_cnt_ths"}
ALLOWED_USAGES = {"expression", "context", "filter", "neutralization", "tradability", "benchmark", "backtest_standard_frame"}
AMBIGUOUS_DUPLICATE_FIELDS = {"open", "high", "low", "close", "vol", "volume", "amount", "pct_chg", "return"}
SUPPORTED_EXPRESSION_FUNCTIONS = {
    "ABS",
    "DELAY",
    "DELTA",
    "GREATER",
    "LESS",
    "LOG",
    "MAX",
    "RANK",
    "SIGN",
    "SQRT",
    "TS_CORR",
    "TS_MAX",
    "TS_MEAN",
    "TS_MIN",
    "TS_RANK",
    "TS_STD",
    "TS_SUM",
    "TS_ZSCORE",
}
REQUIRED_ALLOWLIST_KEYS = {
    "source_interface",
    "source_field",
    "feature_name",
    "dtype",
    "join_key",
    "time_policy",
    "missing_policy",
    "allowed_usage",
}


@dataclass(frozen=True)
class DailyPanelAllowlist:
    """Daily-panel field allowlist used by prompt and standard-frame consumers."""

    fields: tuple[OptionalStandardFrameField, ...]

    def expression_fields(self) -> tuple[OptionalStandardFrameField, ...]:
        return tuple(field for field in self.fields if "expression" in field.allowed_usage)

    def context_fields(self) -> tuple[OptionalStandardFrameField, ...]:
        return tuple(field for field in self.fields if "context" in field.allowed_usage)

    def by_feature_name(self) -> dict[str, OptionalStandardFrameField]:
        return {field.feature_name: field for field in self.fields}

    def version_hash(self) -> str:
        payload = json.dumps([asdict(field) for field in self.fields], ensure_ascii=True, sort_keys=True, default=str).encode("utf-8")
        return "sha256:" + hashlib.sha256(payload).hexdigest()


def generate_daily_panel_field_inventory(
    storage_root: str | Path,
    *,
    interfaces: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Generate deterministic schema inventory for daily-panel clean/active parquet files."""

    selected = _normalize_daily_panel_interfaces(interfaces)
    rows: list[dict[str, Any]] = []
    for interface in selected:
        schema = _collect_active_schema(Path(storage_root), interface)
        for field_name in sorted(schema):
            role = _classify_field_role(field_name, schema[field_name])
            status = _first_stage_status(interface, role)
            rows.append(
                {
                    "source_interface": interface,
                    "source_field": field_name,
                    "observed_dtype": str(schema[field_name]),
                    "role": role,
                    "unit_hint": "unknown",
                    "duplicate_of": _duplicate_of(field_name),
                    "first_stage_status": status,
                    "block_reason": _block_reason(interface, role, status),
                    "nullability": _nullability(field_name, role),
                }
            )
    return rows


def build_daily_panel_allowlist(items: Iterable[Mapping[str, Any] | OptionalStandardFrameField]) -> DailyPanelAllowlist:
    """Build and validate a daily-panel allowlist from explicit metadata."""

    fields: list[OptionalStandardFrameField] = []
    seen: set[str] = set()
    for item in items:
        field = item if isinstance(item, OptionalStandardFrameField) else _field_from_mapping(item)
        _validate_daily_panel_field(field)
        if field.feature_name in seen:
            raise ValueError(f"duplicate feature_name in daily-panel allowlist: {field.feature_name}")
        seen.add(field.feature_name)
        fields.append(field)
    return DailyPanelAllowlist(tuple(sorted(fields, key=lambda field: field.feature_name)))


def render_prompt_capabilities_from_allowlist(
    allowlist: DailyPanelAllowlist,
    *,
    source_manifest_version: str | None = None,
    blocked_fields_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Render prompt capabilities only from admitted allowlist fields."""

    return {
        "expression_fields": [field.feature_name for field in allowlist.expression_fields()],
        "context_fields": [field.feature_name for field in allowlist.context_fields()],
        "filter_fields": [field.feature_name for field in allowlist.fields if "filter" in field.allowed_usage],
        "neutralization_fields": [field.feature_name for field in allowlist.fields if "neutralization" in field.allowed_usage],
        "tradability_fields": [field.feature_name for field in allowlist.fields if "tradability" in field.allowed_usage],
        "benchmark_fields": [field.feature_name for field in allowlist.fields if "benchmark" in field.allowed_usage],
        "blocked_fields_summary": dict(blocked_fields_summary or {}),
        "source_manifest_version": source_manifest_version or allowlist.version_hash(),
    }


def build_default_daily_panel_allowlist() -> DailyPanelAllowlist:
    """Return the conservative built-in daily-panel expression allowlist."""

    return build_daily_panel_allowlist(
        [
            {
                "source_interface": "daily_basic",
                "source_field": "turnover_rate",
                "feature_name": "$daily_basic_turnover_rate",
                "dtype": "float64",
                "join_key": ("datetime", "instrument"),
                "time_policy": "same_trade_date_no_lookahead",
                "missing_policy": "nan",
                "allowed_usage": ("expression", "backtest_standard_frame"),
            },
            {
                "source_interface": "moneyflow",
                "source_field": "buy_sm_amount",
                "feature_name": "$moneyflow_buy_sm_amount",
                "dtype": "float64",
                "join_key": ("datetime", "instrument"),
                "time_policy": "same_trade_date_no_lookahead",
                "missing_policy": "nan",
                "allowed_usage": ("expression", "backtest_standard_frame"),
            },
            {
                "source_interface": "cyq_perf",
                "source_field": "winner_rate",
                "feature_name": "$cyq_perf_winner_rate",
                "dtype": "float64",
                "join_key": ("datetime", "instrument"),
                "time_policy": "same_trade_date_no_lookahead",
                "missing_policy": "nan",
                "allowed_usage": ("expression", "backtest_standard_frame"),
            },
            {
                "source_interface": "cyq_perf",
                "source_field": "cost_5pct",
                "feature_name": "$cyq_perf_cost_5pct",
                "dtype": "float64",
                "join_key": ("datetime", "instrument"),
                "time_policy": "same_trade_date_no_lookahead",
                "missing_policy": "nan",
                "allowed_usage": ("expression", "backtest_standard_frame"),
            },
            {
                "source_interface": "cyq_perf",
                "source_field": "cost_50pct",
                "feature_name": "$cyq_perf_cost_50pct",
                "dtype": "float64",
                "join_key": ("datetime", "instrument"),
                "time_policy": "same_trade_date_no_lookahead",
                "missing_policy": "nan",
                "allowed_usage": ("expression", "backtest_standard_frame"),
            },
            {
                "source_interface": "cyq_perf",
                "source_field": "cost_95pct",
                "feature_name": "$cyq_perf_cost_95pct",
                "dtype": "float64",
                "join_key": ("datetime", "instrument"),
                "time_policy": "same_trade_date_no_lookahead",
                "missing_policy": "nan",
                "allowed_usage": ("expression", "backtest_standard_frame"),
            },
            {
                "source_interface": "cyq_chips_scalar",
                "source_field": "chip_entropy",
                "feature_name": "$cyq_chips_chip_entropy",
                "dtype": "float64",
                "join_key": ("datetime", "instrument"),
                "time_policy": "same_trade_date_no_lookahead",
                "missing_policy": "nan",
                "allowed_usage": ("expression", "backtest_standard_frame"),
            },
            {
                "source_interface": "cyq_chips_scalar",
                "source_field": "peak_price",
                "feature_name": "$cyq_chips_peak_price",
                "dtype": "float64",
                "join_key": ("datetime", "instrument"),
                "time_policy": "same_trade_date_no_lookahead",
                "missing_policy": "nan",
                "allowed_usage": ("expression", "backtest_standard_frame"),
            },
            {
                "source_interface": "cyq_chips_scalar",
                "source_field": "peak_percent",
                "feature_name": "$cyq_chips_peak_percent",
                "dtype": "float64",
                "join_key": ("datetime", "instrument"),
                "time_policy": "same_trade_date_no_lookahead",
                "missing_policy": "nan",
                "allowed_usage": ("expression", "backtest_standard_frame"),
            },
            {
                "source_interface": "cyq_chips_scalar",
                "source_field": "top5_concentration",
                "feature_name": "$cyq_chips_top5_concentration",
                "dtype": "float64",
                "join_key": ("datetime", "instrument"),
                "time_policy": "same_trade_date_no_lookahead",
                "missing_policy": "nan",
                "allowed_usage": ("expression", "backtest_standard_frame"),
            },
            {
                "source_interface": "cyq_chips_scalar",
                "source_field": "width_5_95",
                "feature_name": "$cyq_chips_width_5_95",
                "dtype": "float64",
                "join_key": ("datetime", "instrument"),
                "time_policy": "same_trade_date_no_lookahead",
                "missing_policy": "nan",
                "allowed_usage": ("expression", "backtest_standard_frame"),
            },
        ]
    )


def validate_requested_expression_fields(requested_fields: Iterable[str], allowlist: DailyPanelAllowlist) -> None:
    """Fail before prompt/backtest work when a requested expression field is not admitted."""

    expression_names = {field.feature_name for field in allowlist.expression_fields()}
    expression_names.update(STANDARD_FRAME_FACTOR_FIELDS)
    all_fields = allowlist.by_feature_name()
    for requested in requested_fields:
        if requested in expression_names:
            continue
        if requested in all_fields:
            field = all_fields[requested]
            raise ValueError(
                f"{requested} is not admitted as expression field; allowed_usage={field.allowed_usage}. "
                "Remediation: change usage or add expression allowlist metadata."
            )
        raise ValueError(
            f"{requested} is not present in the daily-panel expression allowlist. "
            "Remediation: add allowlist metadata or keep the field blocked."
        )


def validate_factor_expression_against_allowlist(expression: str, allowlist: DailyPanelAllowlist) -> None:
    """Validate expression fields and functions before prompt/backtest execution."""

    fields = sorted(set(re.findall(r"\$[A-Za-z_][A-Za-z0-9_]*", expression)))
    try:
        validate_requested_expression_fields(fields, allowlist)
    except ValueError as exc:
        message = str(exc)
        reason = "FIELD_USAGE_NOT_EXPRESSION" if "not admitted as expression field" in message else "FIELD_NOT_ADMITTED"
        raise ValueError(f"{reason}: {message}") from exc

    functions = sorted(set(re.findall(r"\b([A-Z][A-Z0-9_]*)\s*\(", expression)))
    unsupported = [name for name in functions if name not in SUPPORTED_EXPRESSION_FUNCTIONS]
    if unsupported:
        raise ValueError(f"UNSUPPORTED_FUNCTION: {unsupported[0]}")
    lookahead = _lookahead_function_warning(expression)
    if lookahead:
        raise ValueError(f"LOOKAHEAD_FUNCTION: {lookahead}")


def build_structured_rejection_feedback(
    *,
    reason_code: str,
    expression: str,
    field: str | None = None,
    message: str,
) -> dict[str, str | None]:
    """Build prompt-safe feedback for an invalid factor proposal."""

    del expression
    remediation = (
        "Revise the expression using only current admitted expression_fields and supported functions. "
        "Do not invent fields; keep blocked or context-only data out of expression variables."
    )
    return {
        "reason_code": reason_code,
        "field": field,
        "message": message,
        "remediation": remediation,
    }


def _lookahead_function_warning(expression: str) -> str | None:
    from quantaalpha.pipeline.quality_overlay import lookahead_function_warning

    return lookahead_function_warning(expression)


def _normalize_daily_panel_interfaces(interfaces: Sequence[str] | None) -> tuple[str, ...]:
    selected = tuple(DAILY_PANEL_INTERFACES if interfaces is None else interfaces)
    invalid = sorted(interface for interface in selected if interface not in DAILY_PANEL_INTERFACES)
    if invalid:
        raise ValueError(f"interfaces are not daily_panel: {invalid}")
    return tuple(sorted(dict.fromkeys(selected)))


def _collect_active_schema(storage_root: Path, interface: str) -> dict[str, pl.DataType]:
    active_root = storage_root / interface / "clean" / "active"
    files = sorted(active_root.glob("*.parquet"))
    if not files:
        return {}
    schema = pl.scan_parquet([str(path) for path in files]).collect_schema()
    return {name: schema[name] for name in schema.names()}


def _classify_field_role(field_name: str, dtype: pl.DataType) -> str:
    if field_name in JOIN_KEY_FIELDS:
        return "join_key"
    if field_name in DATE_KEY_FIELDS:
        return "date_key"
    if field_name in AUDIT_METADATA_FIELDS:
        return "audit_metadata"
    if field_name.startswith(RUNTIME_METADATA_PREFIXES):
        return "runtime_metadata"
    if field_name in AMBIGUOUS_DUPLICATE_FIELDS:
        return "ambiguous_duplicate"
    if dtype.is_numeric():
        return "numeric_candidate"
    if dtype == pl.Utf8:
        return "identifier" if field_name.endswith(("_code", "_id")) else "text"
    return "blocked"


def _first_stage_status(interface: str, role: str) -> str:
    if role in {"join_key", "date_key"}:
        return "blocked"
    if role == "ambiguous_duplicate":
        return "blocked"
    if role == "numeric_candidate":
        return "context_only" if interface in CONTEXT_ONLY_INTERFACES else "needs_review"
    return "blocked"


def _block_reason(interface: str, role: str, status: str) -> str:
    if status == "admitted":
        return ""
    if role in {"join_key", "date_key"}:
        return "join/date key; not prompt-visible"
    if status == "context_only":
        return f"{interface} requires explicit broadcast semantics before expression usage"
    if role == "ambiguous_duplicate":
        return "ambiguous duplicate concept; use the canonical standard-frame field or an explicit unique feature alias"
    if role == "numeric_candidate":
        return "numeric candidate requires explicit allowlist metadata before admission"
    return f"{role} is not eligible for first-stage expression admission"


def _duplicate_of(field_name: str) -> str | None:
    return field_name if field_name in AMBIGUOUS_DUPLICATE_FIELDS else None


def _nullability(field_name: str, role: str) -> str:
    if field_name in JOIN_KEY_FIELDS or field_name in DATE_KEY_FIELDS:
        return "required"
    if role in {"numeric_candidate", "ambiguous_duplicate"}:
        return "nullable_unknown"
    return "not_profiled"


def _field_from_mapping(payload: Mapping[str, Any]) -> OptionalStandardFrameField:
    missing = sorted(REQUIRED_ALLOWLIST_KEYS - set(payload))
    if missing:
        raise ValueError(f"daily-panel allowlist item missing metadata: {missing}")
    return OptionalStandardFrameField(
        source_interface=str(payload["source_interface"]),
        source_field=str(payload["source_field"]),
        feature_name=str(payload["feature_name"]),
        dtype=str(payload["dtype"]),
        join_key=tuple(str(item) for item in payload["join_key"]),
        time_policy=str(payload["time_policy"]),
        missing_policy=str(payload["missing_policy"]),
        allowed_usage=tuple(str(item) for item in payload["allowed_usage"]),
    )


def _validate_daily_panel_field(field: OptionalStandardFrameField) -> None:
    validate_optional_standard_frame_field(field)
    primary_class = EXPLICIT_APP5_INTERFACE_CLASSIFICATION[field.source_interface][0]
    if primary_class != "daily_panel":
        raise ValueError(f"allowlist field source is not daily_panel: {field.source_interface}")
    unknown_usage = sorted(set(field.allowed_usage) - ALLOWED_USAGES)
    if unknown_usage:
        raise ValueError(f"unsupported allowed_usage for {field.feature_name}: {unknown_usage}")
    if "expression" in field.allowed_usage and field.source_interface in CONTEXT_ONLY_INTERFACES:
        raise ValueError(
            f"{field.source_interface} is context-only until broadcast semantics are frozen: {field.feature_name}"
        )
