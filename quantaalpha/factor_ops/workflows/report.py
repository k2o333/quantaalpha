"""Monthly factor_ops report workflow。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quantaalpha.factor_ops.gate.log_writer import GateLogReader
from quantaalpha.factor_ops.workflows.io import load_registry_frame, write_json_report, write_markdown_report
from quantaalpha.factor_ops.workflows.status import StatusWorkflowRunner


class MonthlyReportWorkflowRunner:
    """生成月度 JSON/Markdown 运营报告。"""

    def __init__(self, *, storage_root: str | Path | None = None) -> None:
        """初始化 runner。"""
        self.storage_root = Path(storage_root or "log/factor_ops")

    def run(
        self,
        *,
        library_path: str | Path,
        month: str,
        output: str | Path | None = None,
        format: str = "json",
        dry_run: bool = False,
        no_write: bool = False,
    ) -> dict[str, Any]:
        """构建并写出月报。"""
        registry = load_registry_frame(library_path)
        status = StatusWorkflowRunner().run(library_path=library_path)
        gate_log = GateLogReader(self.storage_root).query(start=f"{month}-01") if self.storage_root.exists() else None
        gate_failures: dict[str, int] = {}
        if gate_log is not None and not gate_log.is_empty():
            for reason in gate_log["reason"].to_list():
                gate_failures[str(reason)] = gate_failures.get(str(reason), 0) + 1
        health_scores = _health_scores(registry)
        payload = {
            "success": True,
            "title": f"Factor Ops Monthly Report {month}",
            "month": month,
            "status_distribution": status["status_counts"],
            "tier_distribution": status["tier_counts"],
            "gate_failure_reasons": gate_failures,
            "health_score_summary": {
                "count": len(health_scores),
                "avg": sum(health_scores) / len(health_scores) if health_scores else 0.0,
            },
            "degradation_suggestions": [],
            "model_contribution_downgrade": [],
            "mining_prompt_feedback": {
                "gate_failure_reasons": gate_failures,
                "low_health_factor_count": sum(1 for value in health_scores if value < 40),
            },
        }
        if format == "markdown":
            return write_markdown_report(payload, output, dry_run=dry_run, no_write=no_write)
        return write_json_report(payload, output, dry_run=dry_run, no_write=no_write)


def _health_scores(registry) -> list[float]:
    import json

    scores = []
    for row in registry.to_dicts():
        metadata = row.get("metadata_json") or {}
        if isinstance(metadata, str):
            metadata = json.loads(metadata or "{}")
        value = (metadata.get("ops") or {}).get("health_score")
        if isinstance(value, (int, float)):
            scores.append(float(value))
    return scores
