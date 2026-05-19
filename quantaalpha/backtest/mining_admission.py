"""Governed mining-admission profiles for App5-backed factor mining."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import yaml

from quantaalpha.backtest.contracts import (
    EXPLICIT_APP5_INTERFACE_CLASSIFICATION,
    OptionalStandardFrameField,
    validate_optional_standard_frame_field,
)
from quantaalpha.backtest.data_admission import ALLOWED_USAGES


@dataclass(frozen=True)
class SourceKindSpec:
    materializer: str
    required_payload_keys: tuple[str, ...]
    allowed_time_policies: tuple[str, ...]
    prompt_group: str
    allowed_primary_classes: tuple[str, ...]
    layer: str
    freq: str = "daily"
    expression_allowed: bool = True


SOURCE_KIND_REGISTRY: dict[str, SourceKindSpec] = {
    "daily_panel": SourceKindSpec(
        materializer="_join_daily_panel_batch",
        required_payload_keys=("source_interface", "source_field"),
        allowed_time_policies=("same_trade_date_no_lookahead",),
        prompt_group="daily_panel_features",
        allowed_primary_classes=("daily_panel",),
        layer="daily_panel",
        freq="daily",
    ),
    "canonical_financial_asof": SourceKindSpec(
        materializer="_join_canonical_financial_asof_batch",
        required_payload_keys=("canonical_table", "source_interface", "source_field"),
        allowed_time_policies=("ann_date_asof_no_lookahead",),
        prompt_group="financial_asof_features",
        allowed_primary_classes=("pit_panel",),
        layer="financial_asof",
        freq="quarterly",
    ),
    "pit_panel_asof": SourceKindSpec(
        materializer="_join_pit_panel_asof_batch",
        required_payload_keys=("source_interface", "source_field", "visibility_column", "aggregation"),
        allowed_time_policies=("ann_date_asof_no_lookahead",),
        prompt_group="pit_asof_features",
        allowed_primary_classes=("pit_panel",),
        layer="pit_asof",
        freq="quarterly",
    ),
    "event_window": SourceKindSpec(
        materializer="_join_event_window_batch",
        required_payload_keys=("source_interface", "event_date_column", "visibility_column", "window_days"),
        allowed_time_policies=("event_visible_window_no_lookahead",),
        prompt_group="event_window_features",
        allowed_primary_classes=("event_state",),
        layer="event_window",
        freq="daily",
    ),
    "dimension_asof": SourceKindSpec(
        materializer="_join_dimension_asof_batch",
        required_payload_keys=("source_interface", "source_field", "effective_date_column"),
        allowed_time_policies=("effective_date_asof_no_lookahead",),
        prompt_group="dimension_asof_features",
        allowed_primary_classes=("dimension",),
        layer="dimension_asof",
        freq="daily",
        expression_allowed=False,
    ),
}


@dataclass(frozen=True)
class MiningAdmissionField:
    base: OptionalStandardFrameField
    source_kind: str
    payload: Mapping[str, object]
    rationale: str | None = None
    admitted_by: str | None = None
    semantic_type: str | None = None
    unit: str | None = None
    scale: float | None = None
    source_methodology: str | None = None
    duplicate_of: str | None = None

    @property
    def feature_name(self) -> str:
        return self.base.feature_name

    @property
    def source_interface(self) -> str:
        return self.base.source_interface

    @property
    def source_field(self) -> str:
        return self.base.source_field

    @property
    def dtype(self) -> str:
        return self.base.dtype

    @property
    def join_key(self) -> tuple[str, ...]:
        return self.base.join_key

    @property
    def time_policy(self) -> str:
        return self.base.time_policy

    @property
    def missing_policy(self) -> str:
        return self.base.missing_policy

    @property
    def allowed_usage(self) -> tuple[str, ...]:
        return self.base.allowed_usage

    def batch_key(self) -> tuple[object, ...]:
        if self.source_kind == "daily_panel":
            return (self.source_kind, self.source_interface, self.time_policy)
        if self.source_kind == "canonical_financial_asof":
            return (self.source_kind, self.payload.get("canonical_table"), self.time_policy)
        if self.source_kind == "pit_panel_asof":
            return (
                self.source_kind,
                self.source_interface,
                self.payload.get("visibility_column"),
                self.payload.get("aggregation"),
                self.time_policy,
            )
        if self.source_kind == "event_window":
            return (
                self.source_kind,
                self.source_interface,
                self.payload.get("event_date_column"),
                self.payload.get("visibility_column"),
                self.payload.get("window_days"),
                self.time_policy,
            )
        if self.source_kind == "dimension_asof":
            return (
                self.source_kind,
                self.source_interface,
                self.payload.get("effective_date_column"),
                self.time_policy,
            )
        return (self.source_kind, self.source_interface, self.time_policy)

    def identity(self) -> dict[str, object]:
        return {
            "base": asdict(self.base),
            "source_kind": self.source_kind,
            "payload": dict(self.payload),
            "rationale": self.rationale,
            "admitted_by": self.admitted_by,
            "semantic_type": self.semantic_type,
            "unit": self.unit,
            "scale": self.scale,
            "source_methodology": self.source_methodology,
            "duplicate_of": self.duplicate_of,
        }


@dataclass(frozen=True)
class MiningAdmissionProfile:
    name: str
    version: int
    base_standard_frame: Mapping[str, object]
    fields: tuple[MiningAdmissionField, ...]
    declared_hash: str | None = None

    def expression_feature_names(self) -> tuple[str, ...]:
        return tuple(field.feature_name for field in self.fields if "expression" in field.allowed_usage)

    def daily_panel_optional_fields(self) -> tuple[OptionalStandardFrameField, ...]:
        return tuple(
            field.base
            for field in self.fields
            if field.source_kind == "daily_panel" and "backtest_standard_frame" in field.allowed_usage
        )

    def version_hash(self) -> str:
        return self.declared_hash or self.computed_hash()

    def computed_hash(self) -> str:
        payload = json.dumps(
            {
                "name": self.name,
                "version": self.version,
                "base_standard_frame": dict(self.base_standard_frame),
                "fields": [field.identity() for field in self.fields],
            },
            ensure_ascii=True,
            sort_keys=True,
            default=str,
        ).encode("utf-8")
        return "sha256:" + hashlib.sha256(payload).hexdigest()


def load_mining_admission_profile(
    path: str | Path,
    profile_name: str,
    *,
    registry_path: str | Path | None = None,
) -> MiningAdmissionProfile:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ValueError("mining admission profile must be a YAML mapping")
    version = int(payload.get("version", 0))
    if version != 1:
        raise ValueError(f"unsupported mining admission profile version: {version}")
    profiles = payload.get("profiles")
    if not isinstance(profiles, Mapping) or profile_name not in profiles:
        raise ValueError(f"mining admission profile not found: {profile_name}")
    raw_profile = profiles[profile_name]
    if not isinstance(raw_profile, Mapping):
        raise ValueError(f"mining admission profile must be a mapping: {profile_name}")
    raw_fields = raw_profile.get("fields", ()) or ()
    if not isinstance(raw_fields, Sequence) or isinstance(raw_fields, (str, bytes)):
        raise ValueError("mining admission profile fields must be a sequence")
    fields = tuple(_field_from_mapping(item, registry_path=registry_path) for item in raw_fields)
    _validate_duplicate_feature_names(fields)
    return MiningAdmissionProfile(
        name=profile_name,
        version=version,
        base_standard_frame=dict(raw_profile.get("base_standard_frame", {}) or {}),
        fields=fields,
    )


def capabilities_from_mining_admission_profile(
    profile: MiningAdmissionProfile,
) -> dict[str, dict[str, object]]:
    groups: dict[str, list[MiningAdmissionField]] = {}
    for field in profile.fields:
        if "expression" not in field.allowed_usage:
            continue
        spec = SOURCE_KIND_REGISTRY[field.source_kind]
        groups.setdefault(spec.prompt_group, []).append(field)

    capabilities: dict[str, dict[str, object]] = {}
    for group_name, fields in sorted(groups.items()):
        spec = SOURCE_KIND_REGISTRY[fields[0].source_kind]
        capabilities[group_name] = {
            "fields": sorted(field.feature_name for field in fields),
            "freq": spec.freq,
            "lag_days": 0,
            "available_from": None,
            "join_mode": fields[0].time_policy,
            "factor_hints": [f"expanded app5 {spec.layer} admitted features"],
            "layer": spec.layer,
            "field_metadata": {
                field.feature_name: _field_metadata(field)
                for field in sorted(fields, key=lambda item: item.feature_name)
            },
            "source_manifest_version": profile.version_hash(),
        }
    return capabilities


def profile_from_standard_frame_config(config: Mapping[str, object]) -> MiningAdmissionProfile:
    raw_fields = config.get("admitted_fields", ()) or ()
    if not isinstance(raw_fields, Sequence) or isinstance(raw_fields, (str, bytes)):
        raise ValueError("standard_frame.admitted_fields must be a sequence")
    fields = tuple(_admitted_field_from_identity(item) for item in raw_fields)
    return MiningAdmissionProfile(
        name=str(config.get("admission_profile") or "expanded_app5_v1"),
        version=1,
        base_standard_frame={},
        fields=fields,
        declared_hash=str(config["admission_profile_hash"]) if config.get("admission_profile_hash") else None,
    )


def validate_admission_profile(path: str | Path, profile_name: str) -> dict[str, object]:
    profile = load_mining_admission_profile(path, profile_name)
    capabilities = capabilities_from_mining_admission_profile(profile)
    prompt_groups = {name: list(spec.get("fields", ())) for name, spec in capabilities.items()}
    routes: dict[str, dict[str, object]] = {}
    for field in profile.fields:
        spec = SOURCE_KIND_REGISTRY[field.source_kind]
        routes[field.feature_name] = {
            "source_kind": field.source_kind,
            "materializer": spec.materializer,
            "prompt_group": spec.prompt_group,
            "prompt_visible": "expression" in field.allowed_usage,
            "allowed_usage": list(field.allowed_usage),
            "batch_key": list(field.batch_key()),
            "semantic_type": field.semantic_type,
            "unit": field.unit,
            "scale": field.scale,
            "source_methodology": field.source_methodology,
            "duplicate_of": field.duplicate_of,
        }
    return {
        "profile_name": profile.name,
        "profile_hash": profile.version_hash(),
        "accepted_fields": [field.feature_name for field in profile.fields],
        "prompt_groups": prompt_groups,
        "routes": routes,
    }


def _field_from_mapping(payload: object, *, registry_path: str | Path | None) -> MiningAdmissionField:
    if not isinstance(payload, Mapping):
        raise ValueError("mining admission field must be a mapping")
    required = {"feature_name", "source_kind", "dtype", "join_key", "time_policy", "missing_policy", "allowed_usage"}
    missing = sorted(required - set(payload))
    if missing:
        raise ValueError(f"mining admission field missing metadata: {missing}")

    source_kind = str(payload["source_kind"])
    if source_kind not in SOURCE_KIND_REGISTRY:
        raise ValueError(
            f"unsupported source_kind for {payload.get('feature_name')}: {source_kind}. "
            "Remediation: add a registry entry or keep the field blocked."
        )
    spec = SOURCE_KIND_REGISTRY[source_kind]
    missing_payload = sorted(key for key in spec.required_payload_keys if key not in payload)
    if missing_payload:
        raise ValueError(f"{source_kind} field {payload.get('feature_name')} missing payload keys: {missing_payload}")
    time_policy = str(payload["time_policy"])
    if time_policy not in spec.allowed_time_policies:
        raise ValueError(
            f"unsupported time_policy for {payload.get('feature_name')}: {time_policy}. "
            f"Allowed for {source_kind}: {spec.allowed_time_policies}"
        )
    allowed_usage = tuple(str(item) for item in payload["allowed_usage"])
    unknown_usage = sorted(set(allowed_usage) - ALLOWED_USAGES)
    if unknown_usage:
        raise ValueError(f"unsupported allowed_usage for {payload.get('feature_name')}: {unknown_usage}")
    if "expression" in allowed_usage and not spec.expression_allowed:
        raise ValueError(f"{source_kind} is not expression-safe: {payload.get('feature_name')}")
    if "expression" in allowed_usage:
        _validate_expression_semantic_metadata(payload)

    source_interface = str(payload.get("source_interface", ""))
    if source_interface:
        _validate_interface_class(source_interface, source_kind, spec)
    if source_kind == "canonical_financial_asof":
        _validate_canonical_field(payload, registry_path=registry_path)

    source_field = str(payload.get("source_field") or payload.get("amount_column") or payload["feature_name"])
    base = OptionalStandardFrameField(
        source_interface=source_interface,
        source_field=source_field,
        feature_name=str(payload["feature_name"]),
        dtype=str(payload["dtype"]),
        join_key=tuple(str(item) for item in payload["join_key"]),
        time_policy=time_policy,
        missing_policy=str(payload["missing_policy"]),
        allowed_usage=allowed_usage,
    )
    validate_optional_standard_frame_field(base)
    if not base.feature_name.startswith("$"):
        raise ValueError(f"mining admission feature_name must start with '$': {base.feature_name}")

    payload_keys = set(spec.required_payload_keys) | {"amount_column"}
    field_payload = {key: payload[key] for key in payload_keys if key in payload}
    return MiningAdmissionField(
        base=base,
        source_kind=source_kind,
        payload=field_payload,
        rationale=str(payload["rationale"]) if "rationale" in payload else None,
        admitted_by=str(payload["admitted_by"]) if "admitted_by" in payload else None,
        semantic_type=str(payload["semantic_type"]) if "semantic_type" in payload else None,
        unit=str(payload["unit"]) if "unit" in payload else None,
        scale=float(payload["scale"]) if "scale" in payload else None,
        source_methodology=str(payload["source_methodology"]) if "source_methodology" in payload else None,
        duplicate_of=str(payload["duplicate_of"]) if "duplicate_of" in payload else None,
    )


def _admitted_field_from_identity(payload: object) -> MiningAdmissionField:
    if not isinstance(payload, Mapping):
        raise ValueError("admitted field identity must be a mapping")
    base_payload = payload.get("base")
    if not isinstance(base_payload, Mapping):
        raise ValueError("admitted field identity requires base mapping")
    base = OptionalStandardFrameField(
        source_interface=str(base_payload["source_interface"]),
        source_field=str(base_payload["source_field"]),
        feature_name=str(base_payload["feature_name"]),
        dtype=str(base_payload["dtype"]),
        join_key=tuple(str(item) for item in base_payload["join_key"]),
        time_policy=str(base_payload["time_policy"]),
        missing_policy=str(base_payload["missing_policy"]),
        allowed_usage=tuple(str(item) for item in base_payload["allowed_usage"]),
    )
    return MiningAdmissionField(
        base=base,
        source_kind=str(payload["source_kind"]),
        payload=dict(payload.get("payload", {}) or {}),
        rationale=payload.get("rationale"),
        admitted_by=payload.get("admitted_by"),
        semantic_type=payload.get("semantic_type"),
        unit=payload.get("unit"),
        scale=float(payload["scale"]) if payload.get("scale") is not None else None,
        source_methodology=payload.get("source_methodology"),
        duplicate_of=payload.get("duplicate_of"),
    )


def _field_metadata(field: MiningAdmissionField) -> dict[str, object]:
    metadata: dict[str, object] = {
        "semantic_type": field.semantic_type,
        "unit": field.unit,
        "scale": field.scale,
        "source_methodology": field.source_methodology,
    }
    if field.duplicate_of:
        metadata["duplicate_of"] = field.duplicate_of
    return metadata


def _validate_expression_semantic_metadata(payload: Mapping[str, object]) -> None:
    required = ("semantic_type", "unit", "scale", "source_methodology")
    missing = [key for key in required if key not in payload or payload[key] in {None, ""}]
    if missing:
        raise ValueError(
            f"expression field {payload.get('feature_name')} missing semantic metadata: {missing}. "
            "Required: semantic_type, unit, scale, source_methodology"
        )
    try:
        float(payload["scale"])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"expression field {payload.get('feature_name')} has non-numeric scale: {payload.get('scale')}") from exc


def _validate_interface_class(source_interface: str, source_kind: str, spec: SourceKindSpec) -> None:
    if source_interface not in EXPLICIT_APP5_INTERFACE_CLASSIFICATION:
        raise ValueError(f"source_interface is not classified for mining admission: {source_interface}")
    primary_class = EXPLICIT_APP5_INTERFACE_CLASSIFICATION[source_interface][0]
    if primary_class not in spec.allowed_primary_classes:
        raise ValueError(
            f"source_kind {source_kind} is incompatible with source_interface {source_interface} "
            f"primary_class={primary_class}; expected one of {spec.allowed_primary_classes}"
        )


def _validate_canonical_field(payload: Mapping[str, object], *, registry_path: str | Path | None) -> None:
    try:
        from app5.canonical.registry import FieldRegistry
    except ImportError as exc:
        raise ValueError(
            "app5 canonical registry is required for canonical_financial_asof validation. "
            "Ensure the repository root is on PYTHONPATH before loading mining admission profiles."
        ) from exc

    table = str(payload["canonical_table"])
    source_field = str(payload["source_field"])
    registry = FieldRegistry(registry_path) if registry_path is not None else FieldRegistry()
    for entry in registry.active_entries(table):
        if entry.canonical_name == source_field or entry.source_field == source_field:
            return
    raise ValueError(f"canonical registry has no active field for {table}.{source_field}")


def _validate_duplicate_feature_names(fields: Sequence[MiningAdmissionField]) -> None:
    seen: set[str] = set()
    for field in fields:
        if field.feature_name in seen:
            raise ValueError(f"duplicate feature_name in mining admission profile: {field.feature_name}")
        seen.add(field.feature_name)
