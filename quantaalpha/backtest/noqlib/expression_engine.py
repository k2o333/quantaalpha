"""No-qlib 表达式计算。"""

from __future__ import annotations

from typing import Iterable

import polars as pl


class NoQlibExpressionEngine:
    """no-qlib 表达式引擎。

    生产求值只允许走共享 polars kernel。历史 `safe_eval` 和
    `CustomFactorCalculator` 路径不能再为未知语义生成值。
    """

    def __init__(self, market_data: pl.DataFrame) -> None:
        self.market_data = market_data

    def compute(self, factors: Iterable[dict[str, str]]) -> pl.DataFrame:
        """计算因子列表，返回显式键列 feature frame。"""
        frames = []
        for factor in factors:
            expr = str(factor.get("factor_expression", ""))
            name = str(factor.get("factor_name") or factor.get("factor_id") or expr)
            try:
                native = _evaluate_native_expression(self.market_data, expr, name)
            except Exception as exc:
                raise ValueError(f"unsupported noqlib expression for {name}: {expr}: {exc}") from exc
            if native is None:
                raise ValueError(f"unsupported noqlib expression for {name}: empty expression")
            frames.append(native)
        if not frames:
            raise ValueError("noqlib factor computation produced no features")
        result = frames[0]
        for frame in frames[1:]:
            result = result.join(frame, on=["datetime", "instrument"], how="inner")
        return result.sort(["datetime", "instrument"])

    def compute_label(self, label_expr: str) -> pl.DataFrame:
        """计算 qlib label 表达式。"""
        try:
            direct = _evaluate_native_expression(self.market_data, label_expr, "LABEL0")
        except Exception as exc:
            raise ValueError(f"unsupported noqlib label expression: {label_expr}: {exc}") from exc
        if direct is not None:
            return direct
        raise ValueError("noqlib label computation produced no rows")


def _evaluate_native_expression(market_data: pl.DataFrame, expr: str, name: str) -> pl.DataFrame | None:
    """Evaluate one expression through the shared canonical polars kernel."""
    expression = str(expr).strip()
    if not expression:
        return None
    return _evaluate_shared_polars_expression(market_data, expression, name)


def _evaluate_shared_polars_expression(market_data: pl.DataFrame, expr: str, name: str) -> pl.DataFrame:
    """Use shared canonical polars kernel when the expression is covered."""
    from quantaalpha.backtest.expression import SharedPolarsExpressionKernel

    return SharedPolarsExpressionKernel(market_data).compute_expression_frame(expr, name).with_columns(pl.col(name).cast(pl.Float32))
