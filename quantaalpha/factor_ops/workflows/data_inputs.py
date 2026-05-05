"""factor_ops 运行输入自动化。"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from quantaalpha.factor_ops.workflows.app5_inputs import App5FactorOpsDataResolver
from quantaalpha.factor_ops.workflows.io import load_factor_records


class FactorOpsRunInputResolver:
    """把 app5/registry/parquet 输入转换为 factor_ops 运行摘要。"""

    def __init__(self, *, data_root: str | Path | None = None) -> None:
        """初始化 resolver。"""
        self.data_root = Path(data_root) if data_root is not None else None

    def resolve(
        self,
        *,
        library_path: str | Path | None,
        factor_values: str | Path | None,
        returns: str | Path | None,
        run_date: str,
        skip_update: bool,
    ) -> dict[str, Any]:
        """返回本轮 data/factor input 版本摘要。"""
        records = load_factor_records(library_path) if library_path else []
        app5_summary = _empty_app5_summary(skip_update)
        if self.data_root is not None:
            app5_summary = App5FactorOpsDataResolver(self.data_root).resolve(["daily"])
            app5_summary["skipped"] = skip_update
        missing_factor_values = [] if factor_values and Path(factor_values).exists() else [str(record.get("factor_id")) for record in records]
        missing_returns = not returns or not Path(returns).exists()
        input_version = _input_version([library_path, factor_values, returns])
        return {
            "success": not missing_factor_values and not missing_returns,
            "run_date": run_date,
            "data_update": {
                "skipped": skip_update,
                "source": "app5",
                "interfaces_checked": app5_summary.get("interfaces", ["daily"]),
                "freshness_pass": _all_audits(app5_summary, "freshness_pass"),
                "schema_pass": _all_audits(app5_summary, "schema_pass"),
                "manifest_pass": _all_audits(app5_summary, "manifest_pass"),
                "latest_dates": {
                    key: value.get("latest_date", "")
                    for key, value in (app5_summary.get("audits") or {}).items()
                },
                "schema_hashes": {
                    key: value.get("schema_hash", "")
                    for key, value in (app5_summary.get("audits") or {}).items()
                },
            },
            "factor_inputs": {
                "candidate_count": len(records),
                "missing_factor_values": missing_factor_values,
                "missing_returns": missing_returns,
                "library_backend": "parquet" if library_path and Path(library_path).is_dir() else "json",
                "factor_values": str(factor_values) if factor_values else "",
                "returns": str(returns) if returns else "",
            },
            "coverage_key": {
                "window": "",
                "universe": "default",
                "input_version": input_version,
            },
            "reason": "" if not missing_factor_values and not missing_returns else "missing_input",
        }


def _empty_app5_summary(skip_update: bool) -> dict[str, Any]:
    return {
        "source": "app5",
        "skipped": skip_update,
        "interfaces": [],
        "audits": {},
        "success": False,
    }


def _all_audits(summary: dict[str, Any], key: str) -> bool:
    audits = summary.get("audits") or {}
    if not audits:
        return False
    return all(bool(audit.get(key)) for audit in audits.values())


def _input_version(paths: list[str | Path | None]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        if path is None:
            continue
        target = Path(path)
        digest.update(str(target).encode())
        if target.exists() and target.is_file():
            digest.update(str(target.stat().st_mtime_ns).encode())
    return digest.hexdigest()[:16]
