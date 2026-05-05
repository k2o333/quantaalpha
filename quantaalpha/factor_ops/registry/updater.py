"""Registry ops updater with lifecycle log writeback."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from quantaalpha.factor_ops.lifecycle.log_writer import LifecycleLogRecord, LifecycleLogWriter


@dataclass(frozen=True)
class RegistryUpdateResult:
    """Registry 更新结果。"""

    factor_id: str
    success: bool
    old_status: str = ""
    new_status: str = ""
    old_tier: str = ""
    new_tier: str = ""
    old_version: int = 0
    new_version: int = 0
    lifecycle_log_id: str = ""
    error: str = ""


class RegistryUpdater:
    """更新 metadata_json.ops，并在状态变更后写 lifecycle_log。"""

    def __init__(
        self,
        factor_store: Any,
        *,
        lifecycle_storage_root: str | Path,
        lifecycle_writer: LifecycleLogWriter | None = None,
    ) -> None:
        """初始化 updater。"""
        self.factor_store = factor_store
        self.lifecycle_writer = lifecycle_writer or LifecycleLogWriter(lifecycle_storage_root)

    def update_ops(
        self,
        factor_id: str,
        *,
        ops_update: dict[str, Any],
        expected_version: int | None = None,
        reason: str = "",
        timestamp: str | None = None,
        operator: str = "registry_updater",
    ) -> RegistryUpdateResult:
        """追加一条 registry ops 更新事件。"""
        timestamp = timestamp or datetime.now().isoformat()
        record = self._find_record(factor_id)
        if record is None:
            return RegistryUpdateResult(factor_id=factor_id, success=False, error="factor not found")

        metadata = _loads_json(record.get("metadata_json"), {})
        ops = dict(metadata.get("ops", {}) or {})
        old_status = str(ops.get("status", ""))
        old_tier = str(ops.get("tier", ""))
        old_version = int(ops.get("version", 0) or 0)
        if expected_version is not None and expected_version != old_version:
            return RegistryUpdateResult(
                factor_id=factor_id,
                success=False,
                old_status=old_status,
                new_status=str(ops_update.get("status", old_status)),
                old_tier=old_tier,
                new_tier=str(ops_update.get("tier", old_tier)),
                old_version=old_version,
                new_version=old_version,
                error="version conflict",
            )

        new_ops = dict(ops)
        new_ops.update(ops_update)
        new_ops["version"] = old_version + 1
        metadata["ops"] = new_ops
        event = dict(record)
        event["metadata_json"] = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
        event["evaluation_status"] = str(new_ops.get("legacy_status", record.get("evaluation_status", "")))
        event["updated_at"] = timestamp
        event["sequence"] = int(record.get("sequence", 0) or 0) + 1
        event["op"] = "upsert"

        self.factor_store.write_factor(event)
        new_status = str(new_ops.get("status", old_status))
        new_tier = str(new_ops.get("tier", old_tier))
        log_id = ""
        if old_status != new_status or old_tier != new_tier:
            log_id = self.lifecycle_writer.write(
                LifecycleLogRecord(
                    factor_id=factor_id,
                    old_status=old_status,
                    new_status=new_status,
                    old_tier=old_tier,
                    new_tier=new_tier,
                    reason=reason,
                    metrics_snapshot={key: value for key, value in ops_update.items() if key not in {"status", "tier"}},
                    timestamp=timestamp,
                    created_at=timestamp,
                    operator=operator,
                )
            )
        return RegistryUpdateResult(
            factor_id=factor_id,
            success=True,
            old_status=old_status,
            new_status=new_status,
            old_tier=old_tier,
            new_tier=new_tier,
            old_version=old_version,
            new_version=old_version + 1,
            lifecycle_log_id=log_id,
        )

    def bulk_update(
        self,
        updates: list[dict[str, Any]],
        *,
        timestamp: str | None = None,
    ) -> list[RegistryUpdateResult]:
        """批量更新，逐项返回结果。"""
        return [
            self.update_ops(
                str(update["factor_id"]),
                ops_update=dict(update.get("ops_update", {})),
                expected_version=update.get("expected_version"),
                reason=str(update.get("reason", "")),
                timestamp=timestamp,
            )
            for update in updates
        ]

    def _find_record(self, factor_id: str) -> dict[str, Any] | None:
        for record in self.factor_store.read_effective_factor_records():
            if record.get("factor_id") == factor_id:
                return record
        return None


def _loads_json(value: Any, default: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default
