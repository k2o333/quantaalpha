"""Gate 工作流。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quantaalpha.factor_ops.gate.data_quality import DataQualityGate, DataQualityGateConfig
from quantaalpha.factor_ops.gate.log_writer import GateLogWriter
from quantaalpha.factor_ops.gate.redundancy import RedundancyGate, RedundancyGateConfig
from quantaalpha.factor_ops.workflows.io import factor_column_frame, load_factor_values, normalize_factor_values


class GateWorkflowRunner:
    """执行 data-quality 与 redundancy Gate。"""

    def __init__(self, *, storage_root: str | Path | None = None) -> None:
        """初始化 runner。"""
        self.storage_root = Path(storage_root) if storage_root is not None else None

    def run(
        self,
        factor_id: str,
        *,
        factor_values: str | Path,
        pool_values: str | Path | None = None,
        expression_similarity_score: float | None = None,
        dry_run: bool = False,
        no_write: bool = False,
        run_date: str | None = None,
    ) -> dict[str, Any]:
        """执行单因子 Gate。"""
        writer = None if dry_run or no_write or self.storage_root is None else GateLogWriter(self.storage_root)
        values = load_factor_values(factor_values)
        normalized = normalize_factor_values(values, factor_id)
        created_at = f"{run_date}T00:00:00" if run_date and "T" not in run_date else run_date
        dq_result = DataQualityGate(
            DataQualityGateConfig(min_cross_section_count=2, min_cross_section_pass_ratio=0.8),
            gate_log_writer=writer,
        ).run(factor_id, normalized, created_at=created_at)
        gate_results = [dq_result]

        if dq_result.gate_result == "pass" and (pool_values is not None or expression_similarity_score is not None):
            pool_df = load_factor_values(pool_values) if pool_values else None
            redundancy = RedundancyGate(
                RedundancyGateConfig(expression_similarity_threshold=0.85, correlation_threshold=0.85),
                gate_log_writer=writer,
            ).run(
                factor_id,
                factor_column_frame(values, factor_id),
                pool_df,
                expression_similarity_score=expression_similarity_score,
                created_at=created_at,
            )
            gate_results.append(redundancy)

        final = min(gate_results, key=lambda item: _gate_priority(item.gate_result))
        return {
            "success": True,
            "factor_id": factor_id,
            "gate_result": final.gate_result,
            "reasons": [item.reason for item in gate_results if item.gate_result != "pass"],
            "check_results": [
                {
                    "gate_name": item.gate_name,
                    "gate_result": item.gate_result,
                    "reason": item.reason,
                    "check_details": item.check_details,
                    "gate_run_id": item.gate_run_id,
                }
                for item in gate_results
            ],
            "written": writer is not None,
        }


def _gate_priority(result: str) -> int:
    return {"blacklist": 0, "reject": 1, "watchlist": 2, "re_winsorize": 3, "pass": 4}.get(result, 9)
