"""数据质量 Gate。"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import polars as pl

from quantaalpha.factor_ops.gate.log_writer import GateLogRecord, GateLogWriter
from quantaalpha.factor_ops.utils import OutlierDetector
from quantaalpha.factor_ops.utils._stats import spearman_corr

RESULT_PRIORITY = {
    "blacklist": 0,
    "reject": 1,
    "watchlist": 2,
    "re_winsorize": 3,
    "pass": 4,
}


@dataclass(frozen=True)
class DataQualityGateConfig:
    """数据质量 Gate 阈值配置。"""

    missing_rate_threshold: float = 0.40
    coverage_rate_threshold: float = 0.60
    min_cross_section_count: int = 500
    min_cross_section_pass_ratio: float = 0.90
    extreme_value_ratio_threshold: float = 0.05
    extreme_value_mad_multiplier: float = 5.0
    single_day_jump_zscore_threshold: float = 5.0
    suspension_ratio_threshold: float = 0.30
    future_corr_threshold: float = 0.50
    future_corr_window_days: int = 60


@dataclass(frozen=True)
class GateResult:
    """Gate 执行结果。"""

    factor_id: str
    gate_name: str
    gate_result: str
    check_details: list[dict[str, Any]]
    reason: str
    gate_run_id: str | None = None

    def detail_by_name(self, check_name: str) -> dict[str, Any]:
        """按检查名返回明细。"""
        for detail in self.check_details:
            if detail["check_name"] == check_name:
                return detail
        raise KeyError(check_name)


class DataQualityGate:
    """因子入池前的数据质量检查。"""

    def __init__(
        self,
        config: DataQualityGateConfig | None = None,
        gate_log_writer: GateLogWriter | None = None,
    ):
        """初始化 Gate。"""
        self.config = config or DataQualityGateConfig()
        self.gate_log_writer = gate_log_writer
        self.outlier_detector = OutlierDetector()

    def run(
        self,
        factor_id: str,
        factor_values_df: pl.DataFrame,
        created_at: str | None = None,
        operator: str = "auto_gate",
    ) -> GateResult:
        """执行非短路数据质量检查。"""
        self._validate_input(factor_values_df)
        created_at = created_at or datetime.now().isoformat()
        details = [
            self._check_missing_rate(factor_values_df),
            self._check_coverage_rate(factor_values_df),
            self._check_min_cross_section_count(factor_values_df),
            self._check_extreme_value_ratio(factor_values_df),
            self._check_single_day_jump(factor_values_df),
            self._check_future_function(factor_values_df),
            self._check_pit(factor_values_df),
            self._check_suspension_ratio(factor_values_df),
            self._check_st_or_delisted(factor_values_df),
        ]
        gate_result = self._resolve_result(details)
        reason = self._reason(details, gate_result)
        result = GateResult(
            factor_id=factor_id,
            gate_name="data_quality",
            gate_result=gate_result,
            check_details=details,
            reason=reason,
        )
        if self.gate_log_writer is not None:
            gate_run_id = self.gate_log_writer.write(
                GateLogRecord(
                    factor_id=factor_id,
                    gate_name="data_quality",
                    gate_result=gate_result,
                    check_details=details,
                    reason=reason,
                    created_at=created_at,
                    operator=operator,
                )
            )
            result = GateResult(
                factor_id=factor_id,
                gate_name="data_quality",
                gate_result=gate_result,
                check_details=details,
                reason=reason,
                gate_run_id=gate_run_id,
            )
        return result

    @staticmethod
    def _validate_input(df: pl.DataFrame) -> None:
        required = {"date", "stock_id", "factor_value"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Missing required columns: {sorted(missing)}")
        if df.is_empty():
            raise ValueError("factor_values_df is empty")

    def _check_missing_rate(self, df: pl.DataFrame) -> dict[str, Any]:
        total = df.height
        missing_count = df.filter(pl.col("factor_value").is_null() | pl.col("factor_value").is_nan()).height
        value = missing_count / total if total else math.nan
        return self._detail(
            "missing_rate",
            value,
            self.config.missing_rate_threshold,
            value <= self.config.missing_rate_threshold,
            "reject",
            {"missing_count": missing_count, "total_count": total},
        )

    def _check_coverage_rate(self, df: pl.DataFrame) -> dict[str, Any]:
        total = df.height
        valid_count = df.filter(pl.col("factor_value").is_not_null() & ~pl.col("factor_value").is_nan()).height
        value = valid_count / total if total else math.nan
        return self._detail(
            "coverage_rate",
            value,
            self.config.coverage_rate_threshold,
            value >= self.config.coverage_rate_threshold,
            "watchlist",
            {"valid_count": valid_count, "total_count": total},
        )

    def _check_min_cross_section_count(self, df: pl.DataFrame) -> dict[str, Any]:
        daily = (
            df.filter(pl.col("factor_value").is_not_null() & ~pl.col("factor_value").is_nan())
            .group_by("date")
            .agg(pl.len().alias("stock_count"))
        )
        if daily.is_empty():
            pass_ratio = 0.0
            min_count = 0
        else:
            pass_ratio = (
                daily.filter(pl.col("stock_count") >= self.config.min_cross_section_count).height / daily.height
            )
            min_count = int(daily["stock_count"].min())
        return self._detail(
            "min_cross_section_count",
            pass_ratio,
            self.config.min_cross_section_pass_ratio,
            pass_ratio >= self.config.min_cross_section_pass_ratio,
            "reject",
            {"min_stock_count": min_count, "required_stock_count": self.config.min_cross_section_count},
        )

    def _check_extreme_value_ratio(self, df: pl.DataFrame) -> dict[str, Any]:
        values = self._finite_values(df["factor_value"])
        if not values:
            ratio = 0.0
            extreme_count = 0
        else:
            median = self.outlier_detector._median(values)
            mad = self.outlier_detector._median([abs(value - median) for value in values])
            if mad == 0:
                extreme_count = sum(1 for value in values if value != median)
            else:
                lower = median - self.config.extreme_value_mad_multiplier * mad
                upper = median + self.config.extreme_value_mad_multiplier * mad
                extreme_count = sum(1 for value in values if value < lower or value > upper)
            ratio = extreme_count / len(values)
        return self._detail(
            "extreme_value_ratio",
            ratio,
            self.config.extreme_value_ratio_threshold,
            ratio <= self.config.extreme_value_ratio_threshold,
            "re_winsorize",
            {"extreme_count": extreme_count, "valid_count": len(values)},
        )

    def _check_single_day_jump(self, df: pl.DataFrame) -> dict[str, Any]:
        daily_values = (
            df.filter(pl.col("factor_value").is_not_null() & ~pl.col("factor_value").is_nan())
            .group_by("date")
            .agg(pl.col("factor_value").mean().alias("daily_mean"))
            .sort("date")["daily_mean"]
            .to_list()
        )
        jumped = self.outlier_detector.detect_single_day_jump(
            pl.Series("daily_mean", daily_values),
            zscore_threshold=self.config.single_day_jump_zscore_threshold,
        )
        return self._detail(
            "single_day_jump",
            1.0 if jumped else 0.0,
            self.config.single_day_jump_zscore_threshold,
            not jumped,
            "watchlist",
            {},
        )

    def _check_future_function(self, df: pl.DataFrame) -> dict[str, Any]:
        return_columns = [col for col in df.columns if col.startswith("return_t_plus_")]
        max_abs_corr = 0.0
        for date_value in sorted(df["date"].unique().to_list())[-self.config.future_corr_window_days :]:
            day_df = df.filter(pl.col("date") == date_value).sort("stock_id")
            for return_column in return_columns:
                corr = spearman_corr(day_df["factor_value"].to_list(), day_df[return_column].to_list())
                if math.isfinite(corr):
                    max_abs_corr = max(max_abs_corr, abs(corr))
        return self._detail(
            "future_function",
            max_abs_corr,
            self.config.future_corr_threshold,
            max_abs_corr <= self.config.future_corr_threshold,
            "blacklist",
            {"return_columns": return_columns},
        )

    def _check_pit(self, df: pl.DataFrame) -> dict[str, Any]:
        if "factor_type" not in df.columns or "pit_valid" not in df.columns:
            return self._detail("pit_validation", 1.0, 1.0, True, "blacklist", {"skipped": True})
        financial = df.filter(pl.col("factor_type") == "financial")
        if financial.is_empty():
            return self._detail("pit_validation", 1.0, 1.0, True, "blacklist", {"skipped": True})
        passed = financial.filter(~pl.col("pit_valid")).is_empty()
        return self._detail("pit_validation", 1.0 if passed else 0.0, 1.0, passed, "blacklist", {})

    def _check_suspension_ratio(self, df: pl.DataFrame) -> dict[str, Any]:
        if "is_suspended" not in df.columns:
            return self._detail("suspension_ratio", 0.0, self.config.suspension_ratio_threshold, True, "watchlist", {"skipped": True})
        ratio = df.filter(pl.col("is_suspended")).height / df.height
        return self._detail(
            "suspension_ratio",
            ratio,
            self.config.suspension_ratio_threshold,
            ratio <= self.config.suspension_ratio_threshold,
            "watchlist",
            {},
        )

    def _check_st_or_delisted(self, df: pl.DataFrame) -> dict[str, Any]:
        flag_columns = [col for col in ("is_st", "is_delisted") if col in df.columns]
        flagged = any(df.filter(pl.col(col)).height > 0 for col in flag_columns)
        return self._detail("st_or_delisted", 1.0 if flagged else 0.0, 0.0, not flagged, "watchlist", {"flag_columns": flag_columns})

    @staticmethod
    def _finite_values(series: pl.Series) -> list[float]:
        return [float(value) for value in series.to_list() if isinstance(value, (int, float)) and math.isfinite(value)]

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
