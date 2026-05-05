"""Continuous-facing app5 data automation adapter."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from quantaalpha.factor_ops.workflows.app5_inputs import App5SchemaFreshnessAuditor


class App5DataAutomationAdapter:
    """给 continuous/factor_ops 提供 app5 inspect/update/freshness 摘要。"""

    def __init__(self, config: dict[str, Any] | Any | None = None) -> None:
        """初始化 adapter。"""
        if config is None:
            config = {}
        if not isinstance(config, dict):
            config = getattr(config, "app5_data", {}) or {}
        self.config = dict(config)
        self.enabled = bool(self.config.get("enabled", True))
        self.data_root = Path(self.config.get("data_root", "data/app5"))
        self.interface_dir = str(self.config.get("interface_dir", "app5/config/interfaces"))
        self.groups = list(self.config.get("groups") or self.config.get("interfaces") or ["daily"])
        self.python_executable = str(self.config.get("python_executable", "python"))
        self.transport = str(self.config.get("transport", ""))

    def inspect(self, *, skip_update: bool = False) -> dict[str, Any]:
        """检查 app5 manifest/freshness/schema 证据。"""
        audits = {
            interface: App5SchemaFreshnessAuditor(self.data_root).audit_interface(interface)
            for interface in self.groups
        }
        return {
            "success": self.enabled,
            "skipped": skip_update,
            "source": "app5",
            "interfaces_checked": self.groups,
            "audits": audits,
            "freshness_pass": all(bool(audit.get("freshness_pass")) for audit in audits.values()) if audits else False,
            "schema_pass": all(bool(audit.get("schema_pass")) for audit in audits.values()) if audits else False,
            "manifest_pass": all(bool(audit.get("manifest_pass")) for audit in audits.values()) if audits else False,
            "latest_dates": {key: value.get("latest_date", "") for key, value in audits.items()},
            "schema_hashes": {key: value.get("schema_hash", "") for key, value in audits.items()},
        }

    def should_update(self) -> bool:
        """根据 freshness/manifest 证据判断是否需要更新。"""
        summary = self.inspect(skip_update=True)
        return not (summary["freshness_pass"] and summary["schema_pass"] and summary["manifest_pass"])

    def run_update(self, *, dry_run: bool = False) -> dict[str, Any]:
        """调用 app5 update-all；无 transport 且非 dry-run 时返回缺少证据。"""
        if dry_run:
            return {"success": True, "status": "dry_run", "source": "app5", "interfaces": self.groups}
        if not self.transport:
            return {"success": False, "source": "app5", "error": "missing_transport"}
        cmd = [
            self.python_executable,
            "-m",
            "app5",
            "update-all",
            "--interface-dir",
            self.interface_dir,
            "--data-root",
            str(self.data_root),
            "--transport",
            self.transport,
        ]
        for group in self.groups:
            cmd.extend(["--group", group])
        completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if completed.returncode != 0:
            return {"success": False, "source": "app5", "error": completed.stderr.strip(), "returncode": completed.returncode}
        try:
            payload = json.loads(completed.stdout or "{}")
        except json.JSONDecodeError:
            payload = {"stdout": completed.stdout}
        return {"success": True, "source": "app5", "report": payload}

    def summarize_freshness(self) -> dict[str, Any]:
        """返回 freshness 摘要。"""
        return self.inspect(skip_update=True)
