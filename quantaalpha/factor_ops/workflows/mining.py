"""Post-mining 批处理工作流。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quantaalpha.factor_ops.workflows.data_inputs import FactorOpsRunInputResolver
from quantaalpha.factor_ops.workflows.evaluate import EvaluateWorkflowRunner
from quantaalpha.factor_ops.workflows.gate import GateWorkflowRunner
from quantaalpha.factor_ops.workflows.io import load_factor_records
from quantaalpha.factor_ops.workflows.lifecycle import ApplyStatusWorkflowRunner


class PostMiningWorkflowRunner:
    """候选因子入池后的 Gate/Evaluate/状态建议批处理。"""

    def __init__(self, *, storage_root: str | Path | None = None) -> None:
        """初始化 runner。"""
        self.storage_root = Path(storage_root or "log/factor_ops")

    def run(
        self,
        *,
        library_path: str | Path,
        factor_values: str | Path | None = None,
        returns: str | Path | None = None,
        factor_ids: list[str] | str | None = None,
        data_root: str | Path | None = None,
        run_date: str = "2026-05-05",
        apply: bool = False,
        dry_run: bool = False,
        no_write: bool = False,
        new_only: bool = False,
    ) -> dict[str, Any]:
        """执行 post-mining 批处理。"""
        selected = _select_factor_ids(library_path, factor_ids=factor_ids, new_only=new_only)
        resolver_summary = FactorOpsRunInputResolver(data_root=data_root).resolve(
            library_path=library_path,
            factor_values=factor_values,
            returns=returns,
            run_date=run_date,
            skip_update=True,
        )
        details: list[dict[str, Any]] = []
        accepted = rejected = skipped = applied = 0
        for factor_id in selected:
            if not factor_values or not returns:
                skipped += 1
                details.append({"factor_id": factor_id, "status": "skipped", "reason": "missing_input"})
                continue
            gate = GateWorkflowRunner(storage_root=self.storage_root).run(
                factor_id,
                factor_values=factor_values,
                dry_run=dry_run,
                no_write=no_write,
                run_date=run_date,
            )
            if gate["gate_result"] != "pass":
                rejected += 1
                details.append({"factor_id": factor_id, "status": "rejected", "gate": gate})
                continue
            accepted += 1
            evaluation = EvaluateWorkflowRunner().run(
                factor_id,
                factor_values=factor_values,
                returns=returns,
                registry_path=library_path,
                no_write=True,
            )
            apply_result = None
            if apply and not dry_run and not no_write:
                apply_result = ApplyStatusWorkflowRunner(storage_root=self.storage_root).run(
                    factor_id,
                    library_path=library_path,
                    to_status=str(evaluation["suggested_status"]),
                    tier=str(evaluation["tier"]),
                    health_score=float(evaluation["health_score"]),
                    reason="post-mining suggestion",
                )
                if apply_result.get("written"):
                    applied += 1
            details.append({"factor_id": factor_id, "status": "accepted", "gate": gate, "evaluation": evaluation, "apply": apply_result})
        return {
            "success": True,
            "selected_count": len(selected),
            "accepted_count": accepted,
            "rejected_count": rejected,
            "skipped_count": skipped,
            "applied_count": applied,
            "written": apply and not dry_run and not no_write,
            "data_inputs": resolver_summary,
            "details": details,
        }


def _select_factor_ids(library_path: str | Path, *, factor_ids: list[str] | str | None, new_only: bool) -> list[str]:
    if isinstance(factor_ids, str):
        requested = [item.strip() for item in factor_ids.split(",") if item.strip()]
    else:
        requested = list(factor_ids or [])
    if requested:
        return requested
    selected = []
    for record in load_factor_records(library_path):
        ops = _ops(record)
        status = ops.get("status", "testing")
        if not new_only or status in {"draft", "testing", "candidate", ""}:
            selected.append(str(record.get("factor_id")))
    return selected


def _ops(record: dict[str, Any]) -> dict[str, Any]:
    import json

    metadata = record.get("metadata_json") or {}
    if isinstance(metadata, str):
        metadata = json.loads(metadata or "{}")
    return dict(metadata.get("ops") or {})
