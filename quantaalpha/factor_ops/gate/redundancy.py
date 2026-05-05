"""冗余 Gate。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import polars as pl

from quantaalpha.factor_ops.gate.data_quality import RESULT_PRIORITY, GateResult
from quantaalpha.factor_ops.gate.log_writer import GateLogRecord, GateLogWriter
from quantaalpha.factor_ops.utils import CorrelationEngine


@dataclass(frozen=True)
class RedundancyGateConfig:
    """冗余 Gate 阈值配置。"""

    expression_similarity_threshold: float = 0.85
    correlation_threshold: float = 0.85
    window_days: int = 60


class RedundancyGate:
    """表达式相似和因子值相关双层冗余检查。"""

    def __init__(
        self,
        config: RedundancyGateConfig | None = None,
        gate_log_writer: GateLogWriter | None = None,
    ):
        """初始化 Gate。"""
        self.config = config or RedundancyGateConfig()
        self.gate_log_writer = gate_log_writer
        self.correlation_engine = CorrelationEngine()

    def run(
        self,
        factor_id: str,
        candidate_df: pl.DataFrame,
        pool_df: pl.DataFrame | None,
        expression_similarity_score: float | None = None,
        created_at: str | None = None,
        operator: str = "auto_gate",
    ) -> GateResult:
        """执行冗余检查。"""
        self._validate_candidate(candidate_df)
        created_at = created_at or datetime.now().isoformat()
        details = [
            self._check_expression_similarity(expression_similarity_score),
            self._check_factor_value_correlation(candidate_df, pool_df),
        ]
        gate_result = self._resolve_result(details)
        reason = self._reason(details, gate_result)
        result = GateResult(
            factor_id=factor_id,
            gate_name="redundancy",
            gate_result=gate_result,
            check_details=details,
            reason=reason,
        )
        if self.gate_log_writer is not None:
            gate_run_id = self.gate_log_writer.write(
                GateLogRecord(
                    factor_id=factor_id,
                    gate_name="redundancy",
                    gate_result=gate_result,
                    check_details=details,
                    reason=reason,
                    created_at=created_at,
                    operator=operator,
                )
            )
            result = GateResult(
                factor_id=factor_id,
                gate_name="redundancy",
                gate_result=gate_result,
                check_details=details,
                reason=reason,
                gate_run_id=gate_run_id,
            )
        return result

    @staticmethod
    def _validate_candidate(candidate_df: pl.DataFrame) -> None:
        if candidate_df.is_empty():
            raise ValueError("candidate_df is empty")
        missing = {"date", "stock_id"} - set(candidate_df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")
        candidate_columns = [col for col in candidate_df.columns if col not in {"date", "stock_id"}]
        if len(candidate_columns) != 1:
            raise ValueError("candidate_df must contain exactly one candidate factor column")

    def _check_expression_similarity(self, expression_similarity_score: float | None) -> dict[str, Any]:
        value = expression_similarity_score if expression_similarity_score is not None else 0.0
        return self._detail(
            "expression_similarity",
            value,
            self.config.expression_similarity_threshold,
            value < self.config.expression_similarity_threshold,
            "blacklist",
            {"skipped": expression_similarity_score is None},
        )

    def _check_factor_value_correlation(self, candidate_df: pl.DataFrame, pool_df: pl.DataFrame | None) -> dict[str, Any]:
        if pool_df is None or pool_df.is_empty():
            return self._detail(
                "factor_value_correlation",
                0.0,
                self.config.correlation_threshold,
                True,
                "blacklist",
                {"skipped": True, "nearest_factor_id": ""},
            )
        pairwise = self.correlation_engine.compute_pairwise_corr(
            candidate_df,
            pool_df,
            window_days=self.config.window_days,
        )
        if pairwise.is_empty():
            max_abs_corr = 0.0
            nearest = ""
        else:
            with_abs = pairwise.with_columns(pl.col("correlation").abs().alias("abs_corr")).sort(
                "abs_corr",
                descending=True,
            )
            max_abs_corr = float(with_abs["abs_corr"][0])
            nearest = str(with_abs["pool_factor"][0])
        return self._detail(
            "factor_value_correlation",
            max_abs_corr,
            self.config.correlation_threshold,
            max_abs_corr < self.config.correlation_threshold,
            "blacklist",
            {"nearest_factor_id": nearest},
        )

    @staticmethod
    def _detail(
        check_name: str,
        value: float,
        threshold: float,
        passed: bool,
        fail_result: str,
        details: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "check_name": check_name,
            "value": value,
            "threshold": threshold,
            "passed": passed,
            "fail_result": fail_result,
            "details": details,
        }

    @staticmethod
    def _resolve_result(details: list[dict[str, Any]]) -> str:
        result = "pass"
        for detail in details:
            if not detail["passed"] and RESULT_PRIORITY[detail["fail_result"]] < RESULT_PRIORITY[result]:
                result = detail["fail_result"]
        return result

    @staticmethod
    def _reason(details: list[dict[str, Any]], gate_result: str) -> str:
        if gate_result == "pass":
            return "all checks passed"
        for detail in details:
            if not detail["passed"] and detail["fail_result"] == gate_result:
                return f"{detail['check_name']} failed"
        return f"{gate_result} checks failed"
