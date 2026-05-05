"""Rank IC 公共计算引擎。"""

from __future__ import annotations

import math
from typing import Literal

import polars as pl

from quantaalpha.factor_ops.utils._stats import mean, sample_std, spearman_corr


class RankICCalculator:
    """Rank IC / ICIR 计算引擎。"""

    def compute_rank_ic(
        self,
        factor_values: pl.DataFrame,
        returns: pl.DataFrame,
        horizon: int = 1,
        method: Literal["spearman", "pearson"] = "spearman",
    ) -> pl.DataFrame:
        """计算单 horizon 的每日 Rank IC 序列。"""
        return_column = f"return_t_plus_{horizon}"
        if method != "spearman":
            raise ValueError("RankICCalculator currently supports only spearman Rank IC")
        joined = factor_values.join(returns, on=["date", "stock_id"], how="inner").sort(["date", "stock_id"])
        records: list[dict[str, object]] = []
        for date_value in sorted(joined["date"].unique().to_list()):
            day_df = joined.filter(pl.col("date") == date_value)
            ic = spearman_corr(day_df["factor_value"].to_list(), day_df[return_column].to_list())
            records.append({"date": date_value, "ic": ic, "ic_abs": abs(ic) if math.isfinite(ic) else math.nan})
        return pl.DataFrame(records, schema={"date": pl.String, "ic": pl.Float64, "ic_abs": pl.Float64})

    def compute_icir(self, ic_series: pl.Series, annualize: bool = True) -> float:
        """计算 ICIR。"""
        values = [float(value) for value in ic_series.to_list() if isinstance(value, (int, float))]
        std = sample_std(values)
        if not math.isfinite(std) or std == 0:
            return math.nan
        icir = mean(values) / std
        if annualize:
            icir *= math.sqrt(252)
        return icir

    def compute_multi_horizon_ic(
        self,
        factor_values: pl.DataFrame,
        returns: pl.DataFrame,
        horizons: list[int] | None = None,
    ) -> pl.DataFrame:
        """计算多 horizon Rank IC。"""
        horizons = horizons or [1, 2, 5, 10, 20]
        frames = [
            self.compute_rank_ic(factor_values, returns, horizon=horizon).with_columns(pl.lit(horizon).alias("horizon"))
            for horizon in horizons
        ]
        if not frames:
            return pl.DataFrame(schema={"date": pl.String, "ic": pl.Float64, "ic_abs": pl.Float64, "horizon": pl.Int64})
        return pl.concat(frames).select(["date", "horizon", "ic", "ic_abs"])

