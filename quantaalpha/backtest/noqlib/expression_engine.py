"""No-qlib 表达式计算。"""

from __future__ import annotations

import re
import importlib.util
import sys
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from quantaalpha.backtest.safe_eval import safe_eval


class NoQlibExpressionEngine:
    """no-qlib 表达式引擎。

    优先使用本模块的 qlib-expression 子集求值器。只有遇到尚未覆盖的
    自定义表达式时，才 fallback 到旧 `CustomFactorCalculator`。
    """

    def __init__(self, market_data: pd.DataFrame) -> None:
        self.market_data = market_data
        self._calculator = None

    def compute(self, factors: Iterable[dict[str, str]]) -> pd.DataFrame:
        """计算因子列表，返回 MultiIndex feature frame。"""
        native_results = {}
        remaining = []
        for factor in factors:
            expr = str(factor.get("factor_expression", ""))
            name = str(factor.get("factor_name") or factor.get("factor_id") or expr)
            native = _evaluate_native_expression(self.market_data, expr)
            if native is not None:
                native_results[name] = native.rename(name)
            else:
                remaining.append(factor)
        if native_results and not remaining:
            return pd.DataFrame(native_results)
        prepared = []
        for factor in remaining:
            item = dict(factor)
            item["factor_expression"] = _prepare_expression(str(item.get("factor_expression", "")))
            prepared.append(item)
        result = self._custom_calculator().calculate_factors_batch(prepared, use_cache=False, skip_compute=False)
        if native_results:
            if result is not None and not result.empty:
                return pd.concat([pd.DataFrame(native_results), result], axis=1)
            return pd.DataFrame(native_results)
        if result is None or result.empty:
            raise ValueError("noqlib factor computation produced no features")
        return result

    def compute_label(self, label_expr: str) -> pd.DataFrame:
        """计算 qlib label 表达式。"""
        direct = _evaluate_native_expression(self.market_data, label_expr)
        if direct is not None:
            return pd.DataFrame({"LABEL0": direct})
        series = self._custom_calculator().calculate_factor("LABEL0", _prepare_expression(label_expr))
        if series is None or series.empty:
            raise ValueError("noqlib label computation produced no rows")
        return pd.DataFrame({"LABEL0": series})

    def _custom_calculator(self):
        if self._calculator is None:
            func_lib = _load_function_lib()
            _install_qlib_aliases(func_lib)
            from quantaalpha.backtest.custom_factor_calculator import CustomFactorCalculator

            self._calculator = CustomFactorCalculator(data_df=self.market_data)
        return self._calculator


def _evaluate_native_expression(market_data: pd.DataFrame, expr: str) -> pd.Series | None:
    """求值常见 qlib 表达式子集。"""
    expression = str(expr).strip()
    if not expression:
        return None
    shared_result = _evaluate_shared_polars_expression(market_data, expression)
    if shared_result is not None:
        return shared_result
    normalized_expr, field_map = _normalize_field_names(expression)
    globals_map = _native_globals(market_data, field_map)
    try:
        result = safe_eval(normalized_expr, globals_map)
    except Exception:
        return None
    if isinstance(result, pd.DataFrame):
        result = result.iloc[:, 0]
    if isinstance(result, pd.Series):
        return result.astype("float32").sort_index()
    return pd.Series(float(result), index=market_data.index).astype("float32")


def _evaluate_shared_polars_expression(market_data: pd.DataFrame, expr: str) -> pd.Series | None:
    """Use shared canonical polars kernel when the expression is covered."""
    try:
        from quantaalpha.backtest.expression import SharedPolarsExpressionKernel, UnsupportedExpressionError

        frame = SharedPolarsExpressionKernel(market_data).compute_expression(expr, "value")
    except (UnsupportedExpressionError, SyntaxError, ValueError, KeyError):
        return None
    return frame["value"].astype("float32").sort_index()


def _normalize_field_names(expr: str) -> tuple[str, dict[str, str]]:
    fields = sorted(set(re.findall(r"\$[A-Za-z_][A-Za-z0-9_]*", expr)), key=len, reverse=True)
    field_map = {field: f"field_{field[1:]}" for field in fields}
    result = expr
    for field, name in field_map.items():
        result = result.replace(field, name)
    return result, field_map


def _native_globals(market_data: pd.DataFrame, field_map: dict[str, str]) -> dict:
    globals_map = {
        "__builtins__": {},
        "np": np,
        "Ref": _ref,
        "Mean": _rolling_mean,
        "Std": _rolling_std,
        "Sum": _rolling_sum,
        "Max": _rolling_max,
        "Min": _rolling_min,
        "Rank": _rolling_rank,
        "Quantile": _rolling_quantile,
        "IdxMax": _rolling_idxmax,
        "IdxMin": _rolling_idxmin,
        "Corr": _rolling_corr,
        "Slope": _rolling_slope,
        "Rsquare": _rolling_rsquare,
        "Resi": _rolling_resi,
        "Abs": lambda value: value.abs(),
        "Log": lambda value: np.log(value),
        "Greater": lambda left, right: np.maximum(left, right),
        "Less": lambda left, right: np.minimum(left, right),
    }
    for field, name in field_map.items():
        if field not in market_data.columns:
            raise KeyError(field)
        globals_map[name] = market_data[field].astype("float32")
    return globals_map


def _by_instrument(series: pd.Series):
    return series.groupby(level="instrument", group_keys=False)


def _ref(series: pd.Series, period: int = 1) -> pd.Series:
    return _by_instrument(series).shift(int(period))


def _rolling_mean(series: pd.Series, window: int) -> pd.Series:
    return _rolling(series, window).mean().droplevel(0)


def _rolling_std(series: pd.Series, window: int) -> pd.Series:
    return _rolling(series, window).std(ddof=1).droplevel(0)


def _rolling_sum(series: pd.Series, window: int) -> pd.Series:
    return _rolling(series, window).sum().droplevel(0)


def _rolling_max(series: pd.Series, window: int) -> pd.Series:
    return _rolling(series, window).max().droplevel(0)


def _rolling_min(series: pd.Series, window: int) -> pd.Series:
    return _rolling(series, window).min().droplevel(0)


def _rolling_rank(series: pd.Series, window: int) -> pd.Series:
    def last_rank(values: pd.Series) -> float:
        return float(values.rank(pct=True).iloc[-1])

    return _rolling(series, window).apply(last_rank, raw=False).droplevel(0)


def _rolling_quantile(series: pd.Series, window: int, q: float) -> pd.Series:
    return _rolling(series, window).quantile(float(q)).droplevel(0)


def _rolling_idxmax(series: pd.Series, window: int) -> pd.Series:
    return _rolling(series, window).apply(lambda values: int(np.argmax(values)) + 1, raw=True).droplevel(0)


def _rolling_idxmin(series: pd.Series, window: int) -> pd.Series:
    return _rolling(series, window).apply(lambda values: int(np.argmin(values)) + 1, raw=True).droplevel(0)


def _rolling_corr(left: pd.Series, right: pd.Series, window: int) -> pd.Series:
    window = int(window)
    pieces = []
    for instrument, left_part in left.groupby(level="instrument", group_keys=False):
        try:
            right_part = right.xs(instrument, level="instrument")
        except KeyError:
            continue
        left_by_date = left_part.droplevel("instrument")
        corr = left_by_date.rolling(window, min_periods=window).corr(right_part)
        corr.index = pd.MultiIndex.from_arrays(
            [corr.index, [instrument] * len(corr)], names=["datetime", "instrument"]
        )
        pieces.append(corr)
    if not pieces:
        return pd.Series(dtype=float, index=left.index)
    return pd.concat(pieces).sort_index()


def _rolling_slope(series: pd.Series, window: int) -> pd.Series:
    return _rolling_regression_stat(series, window, "slope")


def _rolling_rsquare(series: pd.Series, window: int) -> pd.Series:
    result = _rolling_regression_stat(series, window, "rsquare")
    rolling_std = _rolling(series, int(window)).std().droplevel(0)
    return result.mask(np.isclose(rolling_std, 0, atol=2e-05))


def _rolling_resi(series: pd.Series, window: int) -> pd.Series:
    return _rolling_regression_stat(series, window, "resi")


def _rolling_regression_stat(series: pd.Series, window: int, stat: str) -> pd.Series:
    def calc(values: np.ndarray) -> float:
        if np.isnan(values).any():
            return np.nan
        x = np.arange(1, len(values) + 1, dtype=float)
        x_mean = x.mean()
        y_mean = values.mean()
        denom = float(((x - x_mean) ** 2).sum())
        if denom <= 0:
            return np.nan
        slope = float(((x - x_mean) * (values - y_mean)).sum() / denom)
        intercept = y_mean - slope * x_mean
        fitted = slope * x + intercept
        if stat == "slope":
            return slope
        residual = values - fitted
        if stat == "resi":
            return float(residual[-1])
        total = float(((values - y_mean) ** 2).sum())
        if total <= 0:
            return np.nan
        return float(1.0 - ((residual**2).sum() / total))

    return _rolling(series, int(window)).apply(calc, raw=True).droplevel(0)


def _rolling(series: pd.Series, window: int):
    window = int(window)
    return _by_instrument(series).rolling(window, min_periods=window)


def _prepare_expression(expr: str) -> str:
    """把常见 qlib 表达式函数名转换到 function_lib 口径。"""
    replacements = {
        "Ref": "DELAY",
        "Mean": "TS_MEAN",
        "Std": "TS_STD",
        "Sum": "TS_SUM",
        "Rank": "TS_RANK",
        "IdxMax": "TS_ARGMAX",
        "IdxMin": "TS_ARGMIN",
        "Corr": "TS_CORR",
        "Abs": "ABS",
        "Log": "LOG",
        "Greater": "GREATER",
        "Less": "LESS",
    }
    result = expr
    result = re.sub(r"\bRef\(([^,]+),\s*-([0-9]+)\)", r"LEAD(\1, \2)", result)
    result = re.sub(r"\bQuantile\(([^,]+),\s*([^,]+),\s*([^)]+)\)", r"PERCENTILE(\1, \3, \2)", result)
    for old, new in replacements.items():
        result = re.sub(rf"\b{old}\s*\(", f"{new}(", result)
    result = re.sub(r"\bMax\(([^,]+),\s*([0-9]+)\)", r"TS_MAX(\1, \2)", result)
    result = re.sub(r"\bMin\(([^,]+),\s*([0-9]+)\)", r"TS_MIN(\1, \2)", result)
    return result


def _load_function_lib():
    """直接加载 function_lib.py，避免触发 factors.coder 包级副作用。"""
    module_path = Path(__file__).resolve().parents[2] / "factors" / "coder" / "function_lib.py"
    spec = importlib.util.spec_from_file_location("quantaalpha_noqlib_function_lib", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load function_lib from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.modules.setdefault("quantaalpha.factors.coder.function_lib", module)
    return module


def _install_qlib_aliases(func_lib) -> None:
    """为 qlib 常见 element-wise 函数安装 no-qlib aliases。"""
    if not hasattr(func_lib, "GREATER"):
        func_lib.GREATER = lambda left, right: np.maximum(left, right)
    if not hasattr(func_lib, "LESS"):
        func_lib.LESS = lambda left, right: np.minimum(left, right)
    if not hasattr(func_lib, "LEAD"):
        func_lib.LEAD = lambda frame, period=1: frame.groupby("instrument").transform(lambda x: x.shift(-int(period)))
