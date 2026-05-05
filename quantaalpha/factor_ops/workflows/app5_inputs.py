"""app5 manifest/schema 证据读取。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl


class App5ManifestReader:
    """读取 app5 active manifest。"""

    def __init__(self, data_root: str | Path) -> None:
        """初始化 reader。"""
        self.data_root = Path(data_root)

    def read(self, interface: str) -> dict[str, Any]:
        """读取 `manifest/current.json`。"""
        path = self.data_root / interface / "manifest" / "current.json"
        if not path.exists():
            return {"interface_name": interface, "manifest_pass": False, "reason": "manifest_missing"}
        data = json.loads(path.read_text(encoding="utf-8"))
        data["manifest_pass"] = True
        data["active_file_paths"] = [str(self.data_root / interface / rel) for rel in data.get("active_files", [])]
        return data


class App5SchemaFreshnessAuditor:
    """用 Polars 检查 app5 active parquet schema/freshness/manifest drift。"""

    def __init__(self, data_root: str | Path) -> None:
        """初始化 auditor。"""
        self.data_root = Path(data_root)

    def audit_interface(
        self,
        interface: str,
        *,
        required_columns: list[str] | None = None,
    ) -> dict[str, Any]:
        """检查单个 interface 的 active 文件。"""
        required_columns = required_columns or []
        manifest = App5ManifestReader(self.data_root).read(interface)
        if not manifest.get("manifest_pass"):
            return {**manifest, "schema_pass": False, "freshness_pass": False, "manifest_drift": True}
        missing_files = [path for path in manifest["active_file_paths"] if not Path(path).exists()]
        columns: set[str] = set()
        row_count = 0
        latest_date = str((manifest.get("coverage_summary") or {}).get("latest_date", ""))
        for file_path in manifest["active_file_paths"]:
            if Path(file_path).exists():
                frame = pl.scan_parquet(file_path)
                columns.update(frame.collect_schema().names())
                row_count += frame.select(pl.len()).collect().item()
        missing_columns = sorted(set(required_columns) - columns)
        return {
            "interface_name": interface,
            "manifest_pass": not missing_files,
            "schema_pass": not missing_columns,
            "freshness_pass": bool(latest_date or row_count),
            "manifest_drift": bool(missing_files),
            "missing_files": missing_files,
            "missing_columns": missing_columns,
            "latest_date": latest_date,
            "row_count": row_count,
            "schema_hash": manifest.get("schema_hash", ""),
            "active_files": manifest.get("active_file_paths", []),
        }


class App5FactorOpsDataResolver:
    """把 app5 active files 映射成 factor_ops 数据证据。"""

    def __init__(self, data_root: str | Path) -> None:
        """初始化 resolver。"""
        self.data_root = Path(data_root)

    def resolve(self, interfaces: list[str] | None = None) -> dict[str, Any]:
        """返回 price/returns/trade calendar 等证据摘要。"""
        interfaces = interfaces or ["daily"]
        audits = {
            interface: App5SchemaFreshnessAuditor(self.data_root).audit_interface(interface)
            for interface in interfaces
        }
        return {
            "source": "app5",
            "interfaces": interfaces,
            "audits": audits,
            "success": all(audit.get("manifest_pass") and audit.get("schema_pass") for audit in audits.values()),
        }
