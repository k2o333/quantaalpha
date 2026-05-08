"""Daily factor_ops 自动化工作流。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quantaalpha.factor_ops.orchestration import DataMonitorRouter, RevalidationPlanner, TriggerConditionEvaluator
from quantaalpha.factor_ops.workflows.data_inputs import FactorOpsRunInputResolver
from quantaalpha.factor_ops.workflows.io import load_factor_records
from quantaalpha.factor_ops.workflows.mining import PostMiningWorkflowRunner


class DailyWorkflowRunner:
    """按数据更新、复验和触发条件编排每日运营检查。"""

    def __init__(self, *, storage_root: str | Path | None = None) -> None:
        """初始化 runner。"""
        self.storage_root = Path(storage_root or "log/factor_ops")

    def run(
        self,
        *,
        library_path: str | Path | None = None,
        factor_values: str | Path | None = None,
        returns: str | Path | None = None,
        data_root: str | Path | None = None,
        data_update: dict[str, Any] | None = None,
        regime_switch: dict[str, Any] | None = None,
        cycle_result: dict[str, Any] | None = None,
        run_date: str = "2026-05-05",
        skip_update: bool = True,
        dry_run: bool = False,
        no_write: bool = False,
    ) -> dict[str, Any]:
        """执行单日工作流。"""
        cycle_result = cycle_result or {}
        data_update = data_update or cycle_result.get("data_update") or {}
        route = DataMonitorRouter().route_update({"dataset": "daily_price", "major_update": bool(data_update.get("updated"))})
        records = load_factor_records(library_path) if library_path else []
        revalidation_ids = RevalidationPlanner().select_candidates(records)
        trigger = TriggerConditionEvaluator().evaluate(
            data_update=route,
            regime_switch=regime_switch,
            new_factor_count=int((cycle_result.get("mining") or {}).get("added", 0) or len(revalidation_ids)),
            mining_new_factor_threshold=1,
        )
        data_inputs = FactorOpsRunInputResolver(data_root=data_root).resolve(
            library_path=library_path,
            factor_values=factor_values,
            returns=returns,
            run_date=run_date,
            skip_update=skip_update,
        )
        post = {"success": True, "selected_count": 0, "accepted_count": 0, "details": []}
        if library_path is not None:
            post = PostMiningWorkflowRunner(storage_root=self.storage_root).run(
                library_path=library_path,
                factor_values=factor_values,
                returns=returns,
                data_root=data_root,
                factor_ids=revalidation_ids,
                run_date=run_date,
                dry_run=dry_run,
                no_write=no_write,
            )
        return {
            "success": True,
            "run_date": run_date,
            "route": route,
            "revalidation_factor_ids": revalidation_ids,
            "trigger": trigger,
            "data_inputs": data_inputs,
            "post_mining": post,
            "written": False if dry_run or no_write else post.get("written", False),
        }
