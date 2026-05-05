"""Lifecycle 写回工作流。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from quantaalpha.factor_ops.registry import RegistryUpdater
from quantaalpha.factor_ops.workflows.io import load_factor_records


class ApplyStatusWorkflowRunner:
    """把状态建议写入 metadata_json.ops 与 lifecycle_log。"""

    def __init__(self, *, storage_root: str | Path) -> None:
        """初始化 runner。"""
        self.storage_root = Path(storage_root)

    def run(
        self,
        factor_id: str,
        *,
        library_path: str | Path,
        to_status: str,
        tier: str = "",
        health_score: float | None = None,
        expected_version: int | None = None,
        reason: str = "",
        timestamp: str = "2026-05-05T16:00:00",
        dry_run: bool = False,
        no_write: bool = False,
    ) -> dict[str, Any]:
        """执行状态写回或返回 dry-run 摘要。"""
        store = _JsonLibraryStore(library_path)
        record = store.find(factor_id)
        if record is None:
            return {"success": False, "factor_id": factor_id, "error": "factor not found", "written": False}
        ops = _ops(record)
        old_version = int(ops.get("version", 0) or 0)
        before_status = str(ops.get("status", ""))
        if expected_version is not None and expected_version != old_version:
            return {
                "success": False,
                "factor_id": factor_id,
                "error": "version conflict",
                "before_status": before_status,
                "after_status": to_status,
                "written": False,
            }
        ops_update: dict[str, Any] = {"status": to_status}
        if tier:
            ops_update["tier"] = tier
        if health_score is not None:
            ops_update["health_score"] = float(health_score)
        if dry_run or no_write:
            return {
                "success": True,
                "factor_id": factor_id,
                "before_status": before_status,
                "after_status": to_status,
                "written": False,
                "lifecycle_log_written": False,
                "old_version": old_version,
                "new_version": old_version,
            }
        result = RegistryUpdater(store, lifecycle_storage_root=self.storage_root).update_ops(
            factor_id,
            ops_update=ops_update,
            expected_version=expected_version,
            reason=reason,
            timestamp=timestamp,
            operator="factor_ops.apply_status",
        )
        return {
            "success": result.success,
            "factor_id": factor_id,
            "before_status": result.old_status,
            "after_status": result.new_status,
            "written": result.success,
            "lifecycle_log_written": bool(result.lifecycle_log_id),
            "old_version": result.old_version,
            "new_version": result.new_version,
            "error": result.error,
        }


class _JsonLibraryStore:
    def __init__(self, library_path: str | Path) -> None:
        self.library_path = Path(library_path)
        self.data = json.loads(self.library_path.read_text(encoding="utf-8"))

    def read_effective_factor_records(self) -> list[dict[str, Any]]:
        return load_factor_records(self.library_path)

    def find(self, factor_id: str) -> dict[str, Any] | None:
        for record in self.read_effective_factor_records():
            if str(record.get("factor_id")) == factor_id:
                return record
        return None

    def write_factor(self, event: dict[str, Any]) -> None:
        factor_id = str(event["factor_id"])
        metadata = json.loads(event.get("metadata_json") or "{}")
        entry = dict(self.data.setdefault("factors", {}).get(factor_id, {}))
        entry.update({
            "factor_id": factor_id,
            "factor_name": event.get("factor_name", factor_id),
            "factor_expression": event.get("factor_expression", entry.get("factor_expression", "")),
            "metadata": metadata,
        })
        self.data["factors"][factor_id] = entry
        self.library_path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def _ops(record: dict[str, Any]) -> dict[str, Any]:
    metadata = record.get("metadata_json") or {}
    if isinstance(metadata, str):
        metadata = json.loads(metadata or "{}")
    return dict((metadata.get("ops") or {}))
