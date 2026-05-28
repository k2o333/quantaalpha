from __future__ import annotations

from quantaalpha.core.developer import Developer
from quantaalpha.core.experiment import ASpecificExp
from quantaalpha.factors.coder.factor import FactorFBWorkspace
from quantaalpha.log import logger


class DirectPolarsCoder(Developer[ASpecificExp]):
    """直接用 polars parquet runtime 计算因子表达式。

    该 coder 只适用于 `QUANTAALPHA_FACTOR_CODER_RUNTIME=polars_parquet`。
    它不生成可执行因子代码，`factor.py` 只作为现有 Step 4 workspace
    过滤和 cache identity 的兼容文件。
    """

    def develop(self, exp: ASpecificExp) -> ASpecificExp:
        """为实验中的每个因子表达式生成可被 Step 4 消费的 workspace。"""

        sub_workspace_list = []
        for task in getattr(exp, "sub_tasks", []) or []:
            workspace = FactorFBWorkspace(target_task=task, raise_exception=True)
            workspace.inject_code(**{"factor.py": _render_placeholder_factor_py(task)})
            try:
                message, frame = workspace.execute("Debug")
            except Exception as exc:
                logger.warning(
                    "Direct polars factor debug execution failed: "
                    f"factor_name={getattr(task, 'factor_name', '<unknown>')}; error={exc}"
                )
                sub_workspace_list.append(None)
                continue
            if frame is None:
                logger.warning(
                    "Direct polars factor debug execution produced no dataframe: "
                    f"factor_name={getattr(task, 'factor_name', '<unknown>')}; message={message}"
                )
                sub_workspace_list.append(None)
                continue
            sub_workspace_list.append(workspace)

        exp.sub_workspace_list = sub_workspace_list
        return exp


def _render_placeholder_factor_py(task: object) -> str:
    """渲染不会在 polars runtime 中执行、但能区分 cache key 的占位代码。"""

    factor_name = str(getattr(task, "factor_name", ""))
    expression = str(getattr(task, "factor_expression", ""))
    return (
        "# Placeholder for polars_parquet direct factor execution.\n"
        "# FactorFBWorkspace.execute() reads target_task.factor_expression in this runtime.\n"
        f"factor_name = {factor_name!r}\n"
        f"factor_expression = {expression!r}\n"
    )
