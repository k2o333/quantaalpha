"""continuous runtime 到 factor_ops 工作流的共享 hook。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quantaalpha.continuous.app5_data_adapter import App5DataAutomationAdapter
from quantaalpha.factor_ops.workflows.daily import DailyWorkflowRunner
from quantaalpha.factor_ops.workflows.mining import PostMiningWorkflowRunner


def run_factor_ops_cycle(
    pipeline_config: Any,
    cycle_result: dict[str, Any],
    *,
    skip_update: bool,
    trigger_source: str,
) -> dict[str, Any]:
    """运行 continuous cycle 后的 factor_ops 自动化检查。"""
    factor_ops_config = dict(getattr(pipeline_config, "factor_ops", {}) or {})
    app5_config = dict(getattr(pipeline_config, "app5_data", {}) or {})
    app5_summary = App5DataAutomationAdapter(app5_config).inspect(skip_update=skip_update)
    library_path = factor_ops_config.get("library_path") or getattr(pipeline_config.factor, "library_path", None)
    factor_values = factor_ops_config.get("factor_values")
    returns = factor_ops_config.get("returns")
    storage_root = Path(factor_ops_config.get("storage_root", "log/factor_ops"))
    data_root = app5_config.get("data_root")

    daily = DailyWorkflowRunner(storage_root=storage_root).run(
        library_path=library_path,
        factor_values=factor_values,
        returns=returns,
        data_root=data_root,
        data_update=cycle_result.get("data_update", {}),
        cycle_result=cycle_result,
        skip_update=skip_update,
        dry_run=bool(factor_ops_config.get("dry_run", True)),
    )
    post_mining = {"success": True, "selected_count": 0, "accepted_count": 0, "details": []}
    mining = cycle_result.get("mining") or {}
    if int(mining.get("added", 0) or mining.get("generated", 0) or 0) > 0 and library_path:
        post_mining = PostMiningWorkflowRunner(storage_root=storage_root).run(
            library_path=library_path,
            factor_values=factor_values,
            returns=returns,
            data_root=data_root,
            dry_run=bool(factor_ops_config.get("dry_run", True)),
        )
    return {
        "success": bool(daily.get("success")) and bool(post_mining.get("success")),
        "trigger_source": trigger_source,
        "skip_update": skip_update,
        "data_backend": "app5",
        "app5_data": app5_summary,
        "daily": daily,
        "post_mining": post_mining,
        "uses_app4_bridge": False,
    }
