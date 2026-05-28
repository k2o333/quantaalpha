from __future__ import annotations

import hashlib
import json
from pathlib import Path

from quantaalpha.backtest.expression import ADMISSION_SCHEMA_VERSION, admit_expression
from quantaalpha.core.conf import RD_AGENT_SETTINGS
from quantaalpha.core.developer import Developer
from quantaalpha.core.experiment import ASpecificExp
from quantaalpha.factors.coder.config import FACTOR_COSTEER_SETTINGS
from quantaalpha.factors.coder.factor import FactorFBWorkspace
from quantaalpha.factors.coder.runtime_data import read_standard_frame_runtime_columns
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
        admission_evidence = []
        for task in getattr(exp, "sub_tasks", []) or []:
            workspace = FactorFBWorkspace(target_task=task, raise_exception=True)
            workspace.inject_code(**{"factor.py": _render_placeholder_factor_py(task)})
            admission = admit_expression(
                str(getattr(task, "factor_expression", "") or ""),
                available_fields=_debug_runtime_columns(workspace),
            )
            if not admission.accepted:
                logger.warning(
                    "Direct polars factor admission failed: "
                    f"factor_name={getattr(task, 'factor_name', '<unknown>')}; "
                    f"reason={admission.reason_code}; message={admission.message}"
                )
                admission_evidence.append(_admission_evidence_entry(task, admission))
                sub_workspace_list.append(None)
                continue
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
        if admission_evidence:
            evidence_path = _write_admission_evidence(exp, admission_evidence)
            setattr(exp, "polars_expression_admission_evidence", admission_evidence)
            setattr(exp, "polars_expression_admission_evidence_path", evidence_path)
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


def _debug_runtime_columns(workspace: FactorFBWorkspace) -> list[str] | None:
    """读取 Debug standard-frame 列；缺失时降级为纯静态准入。"""

    source_data_path = Path(FACTOR_COSTEER_SETTINGS.data_folder_debug)
    if not source_data_path.is_absolute():
        source_data_path = workspace.workspace_path.parent.parent.parent / source_data_path
    try:
        return read_standard_frame_runtime_columns(source_data_path)
    except Exception as exc:
        logger.warning(f"Direct polars admission field validation skipped: {exc}")
        return None


def _admission_evidence_entry(task: object, admission: object) -> dict[str, object]:
    """构造 unsupported expression evidence 条目。"""

    expression = str(getattr(task, "factor_expression", "") or "")
    canonical = str(getattr(admission, "canonical", "") or "")
    digest = hashlib.md5(canonical.encode("utf-8")).hexdigest()
    return {
        "factor_name": str(getattr(task, "factor_name", "")),
        "factor_expression": expression,
        "canonical_expression": canonical,
        "canonical_expression_hash": digest,
        "admission": admission.to_dict(),
    }


def _write_admission_evidence(exp: ASpecificExp, entries: list[dict[str, object]]) -> str:
    """写入本次 develop 的表达式准入 evidence。"""

    seed = "|".join(
        f"{getattr(task, 'factor_name', '')}:{getattr(task, 'factor_expression', '')}"
        for task in getattr(exp, "sub_tasks", []) or []
    )
    digest = hashlib.md5(seed.encode("utf-8")).hexdigest()[:12]
    root = Path(RD_AGENT_SETTINGS.workspace_path)
    root.mkdir(parents=True, exist_ok=True)
    evidence_path = root / f"polars_expression_admission_evidence_{digest}.json"
    payload = {
        "schema_version": ADMISSION_SCHEMA_VERSION,
        "rejected_count": len(entries),
        "entries": entries,
    }
    evidence_path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True), encoding="utf-8")
    return str(evidence_path)
