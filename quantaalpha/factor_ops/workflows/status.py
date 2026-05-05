"""factor_ops status 工作流。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quantaalpha.factor_ops.cli import build_status_summary
from quantaalpha.factor_ops.workflows.io import load_registry_frame


class StatusWorkflowRunner:
    """构建因子池运营状态摘要。"""

    def run(self, *, library_path: str | Path) -> dict[str, Any]:
        """返回 status/tier/model eligible 计数。"""
        summary = build_status_summary(load_registry_frame(library_path))
        return {"success": True, **summary}
