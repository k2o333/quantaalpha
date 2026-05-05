"""截面相关性公共计算引擎。"""

from __future__ import annotations

import itertools
from typing import Literal

import polars as pl

from quantaalpha.factor_ops.utils._stats import pearson_corr, spearman_corr


class CorrelationEngine:
    """截面 Spearman / Pearson 相关系数计算引擎。"""

    def compute_spearman_matrix(
        self,
        factor_values: pl.DataFrame,
        window_days: int = 60,
        method: Literal["spearman", "pearson"] = "spearman",
    ) -> pl.DataFrame:
        """计算每个交易日的因子两两截面相关。

        Args:
            factor_values: 包含 `date`、`stock_id` 和多个因子列的 Polars DataFrame。
            window_days: 保留最近多少个日期。
            method: 相关系数方法。

        Returns:
            columns 为 `date`、`factor_i`、`factor_j`、`correlation` 的 DataFrame。
        """
        factor_columns = [col for col in factor_values.columns if col not in {"date", "stock_id"}]
        records: list[dict[str, object]] = []
        for date_value in self._recent_dates(factor_values, window_days):
            day_df = factor_values.filter(pl.col("date") == date_value).sort("stock_id")
            for factor_i, factor_j in itertools.combinations(factor_columns, 2):
                records.append(
                    {
                        "date": date_value,
                        "factor_i": factor_i,
                        "factor_j": factor_j,
                        "correlation": self._corr(
                            day_df[factor_i].to_list(),
                            day_df[factor_j].to_list(),
                            method,
                        ),
                    }
                )
        return pl.DataFrame(records, schema=self._matrix_schema())

    def compute_pairwise_corr(
        self,
        candidate_df: pl.DataFrame,
        pool_df: pl.DataFrame,
        window_days: int = 60,
        method: Literal["spearman", "pearson"] = "spearman",
    ) -> pl.DataFrame:
        """计算候选因子与已入池因子的逐日两两相关。"""
        candidate_columns = [col for col in candidate_df.columns if col not in {"date", "stock_id"}]
        pool_columns = [col for col in pool_df.columns if col not in {"date", "stock_id"}]
        joined = candidate_df.join(pool_df, on=["date", "stock_id"], how="inner").sort(["date", "stock_id"])
        records: list[dict[str, object]] = []
        for date_value in self._recent_dates(joined, window_days):
            day_df = joined.filter(pl.col("date") == date_value)
            for candidate_factor in candidate_columns:
                for pool_factor in pool_columns:
                    records.append(
                        {
                            "date": date_value,
                            "candidate_factor": candidate_factor,
                            "pool_factor": pool_factor,
                            "correlation": self._corr(
                                day_df[candidate_factor].to_list(),
                                day_df[pool_factor].to_list(),
                                method,
                            ),
                        }
                    )
        return pl.DataFrame(
            records,
            schema={
                "date": pl.String,
                "candidate_factor": pl.String,
                "pool_factor": pl.String,
                "correlation": pl.Float64,
            },
        )

    @staticmethod
    def _corr(left: list[float], right: list[float], method: str) -> float:
        if method == "pearson":
            return pearson_corr(left, right)
        if method == "spearman":
            return spearman_corr(left, right)
        raise ValueError(f"Unsupported correlation method: {method}")

    @staticmethod
    def _recent_dates(df: pl.DataFrame, window_days: int) -> list[object]:
        dates = sorted(df["date"].unique().to_list())
        if window_days <= 0:
            return dates
        return dates[-window_days:]

    @staticmethod
    def _matrix_schema() -> dict[str, pl.DataType]:
        return {
            "date": pl.String,
            "factor_i": pl.String,
            "factor_j": pl.String,
            "correlation": pl.Float64,
        }

