"""Fire-facing factor_ops command group."""

from __future__ import annotations

from quantaalpha.factor_ops.acceptance import FactorOpsAcceptanceRunner
from quantaalpha.factor_ops.workflows.daily import DailyWorkflowRunner
from quantaalpha.factor_ops.workflows.evaluate import EvaluateWorkflowRunner
from quantaalpha.factor_ops.workflows.gate import GateWorkflowRunner
from quantaalpha.factor_ops.workflows.lifecycle import ApplyStatusWorkflowRunner
from quantaalpha.factor_ops.workflows.mining import PostMiningWorkflowRunner
from quantaalpha.factor_ops.workflows.report import MonthlyReportWorkflowRunner
from quantaalpha.factor_ops.workflows.status import StatusWorkflowRunner


class FactorOpsCommands:
    """factor_ops CLI 命令组。"""

    def validate_training_evidence(self, evidence_path: str):
        """验证 training production evidence parquet 是否可供 factor_ops 消费。"""
        import polars as pl

        frame = pl.read_parquet(evidence_path)
        required = {"factor_id", "factor_name", "evidence_source"}
        missing = sorted(required - set(frame.columns))
        if missing:
            return {
                "status": "error",
                "reason": "missing columns: " + ", ".join(missing),
                "rows": frame.height,
            }
        sources = sorted(str(value) for value in frame.get_column("evidence_source").unique().to_list())
        if sources != ["production"]:
            return {
                "status": "error",
                "reason": "expected evidence_source=production",
                "evidence_sources": sources,
                "rows": frame.height,
            }
        return {
            "status": "ok",
            "evidence_source": "production",
            "rows": frame.height,
            "factor_ids": frame.get_column("factor_id").drop_nulls().unique().to_list(),
        }

    def status(self, library_path: str):
        """返回因子池运营状态。"""
        return StatusWorkflowRunner().run(library_path=library_path)

    def gate(
        self,
        factor_id: str,
        factor_values: str,
        storage_root: str = "log/factor_ops",
        pool_values: str | None = None,
        expression_similarity_score: float | None = None,
        dry_run: bool = False,
        no_write: bool = False,
    ):
        """运行单因子 Gate。"""
        return GateWorkflowRunner(storage_root=storage_root).run(
            factor_id,
            factor_values=factor_values,
            pool_values=pool_values,
            expression_similarity_score=expression_similarity_score,
            dry_run=dry_run,
            no_write=no_write,
        )

    def evaluate(
        self,
        factor_id: str,
        factor_values: str,
        returns: str,
        library_path: str | None = None,
        registry_path: str | None = None,
        regime_labels: str | None = None,
        regime_column: str = "regime_label",
        no_write: bool = False,
        dry_run: bool = False,
    ):
        """评估单因子。"""
        return EvaluateWorkflowRunner().run(
            factor_id,
            factor_values=factor_values,
            returns=returns,
            registry_path=registry_path or library_path,
            regime_labels=regime_labels,
            regime_column=regime_column,
            no_write=no_write,
            dry_run=dry_run,
        )

    def post_mining(
        self,
        library_path: str,
        factor_values: str | None = None,
        returns: str | None = None,
        storage_root: str = "log/factor_ops",
        factor_ids: str | None = None,
        data_root: str | None = None,
        run_date: str = "2026-05-05",
        apply: bool = False,
        dry_run: bool = False,
        no_write: bool = False,
        new_only: bool = False,
    ):
        """运行 post-mining 批处理。"""
        return PostMiningWorkflowRunner(storage_root=storage_root).run(
            library_path=library_path,
            factor_values=factor_values,
            returns=returns,
            factor_ids=factor_ids,
            data_root=data_root,
            run_date=run_date,
            apply=apply,
            dry_run=dry_run,
            no_write=no_write,
            new_only=new_only,
        )

    def apply_status(
        self,
        factor_id: str,
        library_path: str,
        to: str,
        storage_root: str = "log/factor_ops",
        tier: str = "",
        health_score: float | None = None,
        expected_version: int | None = None,
        reason: str = "",
        dry_run: bool = False,
        no_write: bool = False,
    ):
        """应用状态写回。"""
        return ApplyStatusWorkflowRunner(storage_root=storage_root).run(
            factor_id,
            library_path=library_path,
            to_status=to,
            tier=tier,
            health_score=health_score,
            expected_version=expected_version,
            reason=reason,
            dry_run=dry_run,
            no_write=no_write,
        )

    def daily(
        self,
        library_path: str | None = None,
        factor_values: str | None = None,
        returns: str | None = None,
        storage_root: str = "log/factor_ops",
        data_root: str | None = None,
        run_date: str = "2026-05-05",
        dry_run: bool = False,
        no_write: bool = False,
    ):
        """运行 daily 工作流。"""
        return DailyWorkflowRunner(storage_root=storage_root).run(
            library_path=library_path,
            factor_values=factor_values,
            returns=returns,
            data_root=data_root,
            run_date=run_date,
            dry_run=dry_run,
            no_write=no_write,
        )

    def monthly_report(
        self,
        library_path: str,
        month: str,
        storage_root: str = "log/factor_ops",
        output: str | None = None,
        format: str = "json",
        dry_run: bool = False,
        no_write: bool = False,
    ):
        """生成月报。"""
        return MonthlyReportWorkflowRunner(storage_root=storage_root).run(
            library_path=library_path,
            month=month,
            output=output,
            format=format,
            dry_run=dry_run,
            no_write=no_write,
        )

    def acceptance(self, storage_root: str = "log/factor_ops"):
        """运行最小闭环验收。"""
        import polars as pl

        result = FactorOpsAcceptanceRunner(storage_root).run_minimal_loop(
            factor_id="factor_001",
            factor_values=pl.DataFrame(
                {
                    "date": ["2026-05-01", "2026-05-01"],
                    "stock_id": ["A", "B"],
                    "factor_001": [1.0, 2.0],
                }
            ),
            returns=pl.DataFrame(
                {
                    "date": ["2026-05-01", "2026-05-01"],
                    "stock_id": ["A", "B"],
                    "return_t_plus_1": [0.01, 0.02],
                }
            ),
        )
        return {"success": True, **result}


factor_ops_commands = FactorOpsCommands()
