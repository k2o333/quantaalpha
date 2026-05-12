"""Shared polars kernel for canonical factor expressions."""

from __future__ import annotations

import ast
from dataclasses import dataclass
import re
from typing import Any

import numpy as np
import pandas as pd
import polars as pl

from .canonical import canonicalize_expression


class UnsupportedExpressionError(ValueError):
    """Expression is outside the current shared polars kernel coverage."""


@dataclass
class KernelAudit:
    """Shared kernel audit row."""

    source_expression: str
    canonical_expression: str
    warnings: tuple[str, ...]


class KernelValue:
    """Small aligned DataProxy used by the shared polars kernel."""

    def __init__(self, frame: pl.DataFrame) -> None:
        self.frame = frame.select(["datetime", "instrument", "data"])

    def binary_op(self, other: "KernelValue | float", op: str) -> "KernelValue":
        if isinstance(other, KernelValue):
            frame = self.frame.join(other.frame, on=["datetime", "instrument"], suffix="_right")
            left = pl.col("data")
            right = pl.col("data_right")
        else:
            frame = self.frame
            left = pl.col("data")
            right = pl.lit(float(other))
        operations = {
            "add": left + right,
            "sub": left - right,
            "mul": left * right,
            "div": left / right,
        }
        return KernelValue(frame.select("datetime", "instrument", operations[op].alias("data")))

    def __add__(self, other: "KernelValue | float") -> "KernelValue":
        return self.binary_op(other, "add")

    def __radd__(self, other: float) -> "KernelValue":
        return self.binary_op(other, "add")

    def __sub__(self, other: "KernelValue | float") -> "KernelValue":
        return self.binary_op(other, "sub")

    def __rsub__(self, other: float) -> "KernelValue":
        return KernelValue(self.frame.select("datetime", "instrument", (pl.lit(float(other)) - pl.col("data")).alias("data")))

    def __mul__(self, other: "KernelValue | float") -> "KernelValue":
        return self.binary_op(other, "mul")

    def __rmul__(self, other: float) -> "KernelValue":
        return self.binary_op(other, "mul")

    def __truediv__(self, other: "KernelValue | float") -> "KernelValue":
        return self.binary_op(other, "div")

    def __rtruediv__(self, other: float) -> "KernelValue":
        return KernelValue(self.frame.select("datetime", "instrument", (pl.lit(float(other)) / pl.col("data")).alias("data")))

    def __neg__(self) -> "KernelValue":
        return KernelValue(self.frame.select("datetime", "instrument", (-pl.col("data")).alias("data")))


@dataclass(frozen=True)
class KernelSequence:
    """Rolling regression helper sequence."""

    length: int
    log: bool = False

    def values(self) -> np.ndarray:
        values = np.linspace(1, self.length, self.length, dtype=np.float32)
        return np.log(values) if self.log else values


class SharedPolarsExpressionKernel:
    """Evaluate the currently covered canonical DSL subset with polars."""

    def __init__(self, market_data: pd.DataFrame | pl.DataFrame) -> None:
        self.market = _normalize_market(market_data)
        self.audit: list[KernelAudit] = []

    def compute(self, factors: list[dict[str, Any]]) -> pd.DataFrame:
        """Evaluate factors and return `(datetime, instrument)` pandas frame."""
        columns = []
        for factor in factors:
            name = str(factor.get("factor_name") or factor.get("factor_id"))
            expression = str(factor.get("factor_expression") or "")
            columns.append(self.compute_expression(expression, name).iloc[:, 0].rename(name))
        if not columns:
            raise ValueError("shared polars factor list is empty")
        return pd.concat(columns, axis=1).sort_index()

    def compute_expression(self, expression: str, name: str) -> pd.DataFrame:
        """Evaluate one expression."""
        canonical = canonicalize_expression(expression)
        self.audit.append(KernelAudit(canonical.source, canonical.canonical, canonical.warnings))
        prepared_expression = _prepare_expression_syntax(canonical.canonical)
        prepared, field_map = _prepare_for_ast(prepared_expression)
        tree = ast.parse(prepared, mode="eval")
        result = self._eval_node(tree.body, field_map)
        if not isinstance(result, KernelValue):
            result = KernelValue(self.market.select("datetime", "instrument", pl.lit(float(result)).alias("data")))
        pdf = result.frame.to_pandas().set_index(["datetime", "instrument"]).sort_index()
        pdf.columns = [name]
        return pdf

    def _eval_node(self, node: ast.AST, field_map: dict[str, str]) -> KernelValue | float | KernelSequence:
        if isinstance(node, ast.BinOp):
            left = self._eval_node(node.left, field_map)
            right = self._eval_node(node.right, field_map)
            if not isinstance(left, KernelValue):
                left = KernelValue(self.market.select("datetime", "instrument", pl.lit(float(left)).alias("data")))
            if isinstance(node.op, ast.Add):
                return left + right
            if isinstance(node.op, ast.Sub):
                return left - right
            if isinstance(node.op, ast.Mult):
                return left * right
            if isinstance(node.op, ast.Div):
                return left / right
            raise UnsupportedExpressionError(f"unsupported binary operator: {type(node.op).__name__}")
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            value = self._eval_node(node.operand, field_map)
            return -value if isinstance(value, KernelValue) else -float(value)
        if isinstance(node, ast.Compare):
            return self._eval_compare(node, field_map)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return float(node.value)
        if isinstance(node, ast.Name):
            if node.id not in field_map:
                raise UnsupportedExpressionError(f"unsupported name: {node.id}")
            return KernelValue(self.market.select("datetime", "instrument", pl.col(field_map[node.id]).alias("data")))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            args = [self._eval_node(arg, field_map) for arg in node.args]
            return self._call(node.func.id, args)
        raise UnsupportedExpressionError(f"unsupported expression node: {type(node).__name__}")

    def _eval_compare(self, node: ast.Compare, field_map: dict[str, str]) -> KernelValue:
        if len(node.ops) != 1 or len(node.comparators) != 1:
            raise UnsupportedExpressionError("chained comparisons are not supported")
        left = self._eval_node(node.left, field_map)
        right = self._eval_node(node.comparators[0], field_map)
        if not isinstance(left, KernelValue):
            left = KernelValue(self.market.select("datetime", "instrument", pl.lit(float(left)).alias("data")))
        if isinstance(right, KernelValue):
            frame = left.frame.join(right.frame, on=["datetime", "instrument"], suffix="_right")
            right_expr = pl.col("data_right")
        else:
            frame = left.frame
            right_expr = pl.lit(float(right))
        left_expr = pl.col("data")
        op = node.ops[0]
        if isinstance(op, ast.Gt):
            expr = left_expr > right_expr
        elif isinstance(op, ast.GtE):
            expr = left_expr >= right_expr
        elif isinstance(op, ast.Lt):
            expr = left_expr < right_expr
        elif isinstance(op, ast.LtE):
            expr = left_expr <= right_expr
        elif isinstance(op, ast.Eq):
            expr = left_expr == right_expr
        elif isinstance(op, ast.NotEq):
            expr = left_expr != right_expr
        else:
            raise UnsupportedExpressionError(f"unsupported comparison operator: {type(op).__name__}")
        return KernelValue(frame.select("datetime", "instrument", expr.fill_null(False).cast(pl.Float64).alias("data")))

    def _call(self, name: str, args: list[KernelValue | float | KernelSequence]) -> KernelValue | KernelSequence:
        if name == "DELAY" and len(args) == 2:
            return _delay(_expect_value(args[0]), int(_expect_number(args[1])))
        if name == "DELTA" and len(args) == 2:
            value = _expect_value(args[0])
            return value - _delay(value, int(_expect_number(args[1])))
        if name == "TS_MEAN" and len(args) == 2:
            return _rolling("mean", _expect_value(args[0]), int(_expect_number(args[1])))
        if name == "MEAN" and len(args) == 1:
            return _cs_aggregate(_expect_value(args[0]), "mean")
        if name == "TS_SUM" and len(args) == 2:
            return _rolling("sum", _expect_value(args[0]), int(_expect_number(args[1])))
        if name == "SUMAC" and len(args) == 2:
            return _rolling("sum", _expect_value(args[0]), int(_expect_number(args[1])))
        if name == "TS_PROD" and len(args) == 2:
            return _rolling_product_loose(_expect_value(args[0]), int(_expect_number(args[1])))
        if name == "TS_STD" and len(args) == 2:
            return _rolling("std", _expect_value(args[0]), int(_expect_number(args[1])))
        if name == "STD" and len(args) == 1:
            return _cs_aggregate(_expect_value(args[0]), "std")
        if name == "SKEW" and len(args) == 1:
            return _cs_aggregate(_expect_value(args[0]), "skew")
        if name == "KURT" and len(args) == 1:
            return _cs_kurt(_expect_value(args[0]))
        if name == "TS_VAR" and len(args) == 2:
            return _rolling("var", _expect_value(args[0]), int(_expect_number(args[1])))
        if name == "TS_SKEW" and len(args) == 2:
            return _rolling("skew", _expect_value(args[0]), int(_expect_number(args[1])))
        if name == "TS_MIN" and len(args) == 2:
            return _rolling("min", _expect_value(args[0]), int(_expect_number(args[1])))
        if name == "TS_MAX" and len(args) == 2:
            return _rolling("max", _expect_value(args[0]), int(_expect_number(args[1])))
        if name == "TS_MEDIAN" and len(args) == 2:
            return _rolling_quantile(_expect_value(args[0]), int(_expect_number(args[1])), 0.5)
        if name == "TS_MAD" and len(args) == 2:
            return _rolling_mad(_expect_value(args[0]), int(_expect_number(args[1])))
        if name == "TS_RANK" and len(args) == 2:
            return _ts_rank(_expect_value(args[0]), int(_expect_number(args[1])))
        if name == "RANK" and len(args) == 1:
            return _cs_rank(_expect_value(args[0]))
        if name == "ZSCORE" and len(args) == 1:
            return _cs_zscore(_expect_value(args[0]))
        if name == "TS_ZSCORE" and len(args) in {1, 2}:
            value = _expect_value(args[0])
            window = int(_expect_number(args[1])) if len(args) == 2 else 5
            return (_rolling("mean", value, window) * -1 + value) / _rolling("std", value, window)
        if name == "TS_PCTCHANGE" and len(args) == 2:
            value = _expect_value(args[0])
            period = int(_expect_number(args[1]))
            return value / _delay(value, period) - 1.0
        if name == "TS_QUANTILE" and len(args) == 3:
            return _rolling_quantile(_expect_value(args[0]), int(_expect_number(args[1])), float(_expect_number(args[2])))
        if name == "PERCENTILE" and len(args) == 2:
            return _full_instrument_quantile(_expect_value(args[0]), float(_expect_number(args[1])))
        if name == "PERCENTILE" and len(args) == 3:
            return _rolling_quantile(_expect_value(args[0]), int(_expect_number(args[2])), float(_expect_number(args[1])))
        if name == "TS_ARGMAX" and len(args) == 2:
            return _rolling_arg(_expect_value(args[0]), int(_expect_number(args[1])), "max")
        if name == "TS_ARGMIN" and len(args) == 2:
            return _rolling_arg(_expect_value(args[0]), int(_expect_number(args[1])), "min")
        if name == "TS_CORR" and len(args) == 3:
            return _rolling_corr(args[0], args[1], int(_expect_number(args[2])))
        if name == "TS_SLOPE" and len(args) == 2:
            return _rolling_regression(_expect_value(args[0]), int(_expect_number(args[1])), "slope")
        if name == "TS_RSQUARE" and len(args) == 2:
            return _rolling_regression(_expect_value(args[0]), int(_expect_number(args[1])), "rsquare")
        if name == "TS_RESI" and len(args) == 2:
            return _rolling_regression(_expect_value(args[0]), int(_expect_number(args[1])), "resi")
        if name == "SEQUENCE" and len(args) == 1:
            return KernelSequence(int(_expect_number(args[0])))
        if name == "REGBETA" and len(args) == 3:
            window = int(_expect_number(args[2]))
            if isinstance(args[1], KernelSequence):
                _expect_sequence(args[1], window)
                return _rolling_regression(_expect_value(args[0]), window, "slope", args[1].values())
            if not isinstance(args[1], KernelValue):
                return _rolling_regression(
                    _expect_value(args[0]),
                    window,
                    "slope",
                    np.full(window, float(_expect_number(args[1])), dtype=np.float32),
                )
            return _rolling_regression_xy(_expect_value(args[0]), _expect_value(args[1]), window, "slope")
        if name == "REGRESI" and len(args) == 3:
            window = int(_expect_number(args[2]))
            if isinstance(args[1], KernelSequence):
                _expect_sequence(args[1], window)
                return _rolling_regression(_expect_value(args[0]), window, "resi", args[1].values())
            if not isinstance(args[1], KernelValue):
                return _rolling_regression(
                    _expect_value(args[0]),
                    window,
                    "resi",
                    np.full(window, float(_expect_number(args[1])), dtype=np.float32),
                )
            return _rolling_regression_xy(_expect_value(args[0]), _expect_value(args[1]), window, "resi")
        if name == "IF" and len(args) == 3:
            return _where(_expect_value(args[0]), args[1], args[2])
        if name == "AND" and len(args) == 2:
            return _logical_binary(_expect_value(args[0]), args[1], "and")
        if name == "OR" and len(args) == 2:
            return _logical_binary(_expect_value(args[0]), args[1], "or")
        if name == "GREATER" and len(args) == 2:
            return _elementwise_extreme(_expect_value(args[0]), args[1], "max")
        if name == "LESS" and len(args) == 2:
            return _elementwise_extreme(_expect_value(args[0]), args[1], "min")
        if name == "MAX" and len(args) == 2:
            return _elementwise_extreme_args(args[0], args[1], "max")
        if name == "MIN" and len(args) == 2:
            return _elementwise_extreme_args(args[0], args[1], "min")
        if name == "MEDIAN" and len(args) == 1:
            return _cs_median(_expect_value(args[0]))
        if name == "COUNT" and len(args) == 2:
            return _rolling_count(_expect_value(args[0]), int(_expect_number(args[1])))
        if name == "SUMIF" and len(args) == 3:
            return _rolling_sumif(_expect_value(args[0]), int(_expect_number(args[1])), _expect_value(args[2]))
        if name == "FILTER" and len(args) == 2:
            return _expect_value(args[0]) * _expect_value(args[1])
        if name == "DECAYLINEAR" and len(args) == 2:
            return _decay_linear(_expect_value(args[0]), int(_expect_number(args[1])))
        if name == "EMA" and len(args) == 2:
            return _ewm_mean(_expect_value(args[0]), int(_expect_number(args[1])))
        if name == "SMA" and len(args) == 2:
            return _rolling_loose("mean", _expect_value(args[0]), int(_expect_number(args[1])))
        if name == "SMA" and len(args) == 3:
            return _ewm_alpha(_expect_value(args[0]), float(_expect_number(args[2])) / float(_expect_number(args[1])))
        if name == "WMA" and len(args) == 2:
            return _wma(_expect_value(args[0]), int(_expect_number(args[1])))
        if name == "MACD" and len(args) == 3:
            return _ewm_mean(_expect_value(args[0]), int(_expect_number(args[1]))) - _ewm_mean(
                _expect_value(args[0]), int(_expect_number(args[2]))
            )
        if name == "RSI" and len(args) == 2:
            return _rsi(_expect_value(args[0]), int(_expect_number(args[1])))
        if name == "BB_MIDDLE" and len(args) == 2:
            return _rolling_loose("mean", _expect_value(args[0]), int(_expect_number(args[1])))
        if name == "BB_UPPER" and len(args) == 2:
            value = _expect_value(args[0])
            window = int(_expect_number(args[1]))
            return _rolling_loose("mean", value, window) + _rolling_loose("std", value, window)
        if name == "BB_LOWER" and len(args) == 2:
            value = _expect_value(args[0])
            window = int(_expect_number(args[1]))
            return _rolling_loose("mean", value, window) - _rolling_loose("std", value, window)
        if name == "SIGN" and len(args) == 1:
            return _elementwise_math(_expect_value(args[0]), "sign") if isinstance(args[0], KernelValue) else float(np.sign(_expect_number(args[0])))
        if name == "INV" and len(args) == 1:
            return 1.0 / _expect_value(args[0]) if isinstance(args[0], KernelValue) else 1.0 / _expect_number(args[0])
        if name == "SQRT" and len(args) == 1:
            return _elementwise_math(_expect_value(args[0]), "sqrt") if isinstance(args[0], KernelValue) else float(np.sqrt(_expect_number(args[0])))
        if name == "POW" and len(args) == 2:
            return _elementwise_power(_expect_value(args[0]), float(_expect_number(args[1]))) if isinstance(args[0], KernelValue) else float(_expect_number(args[0]) ** _expect_number(args[1]))
        if name == "ABS" and len(args) == 1:
            return KernelValue(_expect_value(args[0]).frame.select("datetime", "instrument", pl.col("data").abs().alias("data"))) if isinstance(args[0], KernelValue) else abs(_expect_number(args[0]))
        if name == "LOG" and len(args) == 1:
            if isinstance(args[0], KernelSequence):
                return KernelSequence(args[0].length, log=True)
            return KernelValue(_expect_value(args[0]).frame.select("datetime", "instrument", pl.col("data").log().alias("data"))) if isinstance(args[0], KernelValue) else float(np.log(_expect_number(args[0])))
        raise UnsupportedExpressionError(f"unsupported function or arity: {name}/{len(args)}")


def _normalize_market(market_data: pd.DataFrame | pl.DataFrame) -> pl.DataFrame:
    if isinstance(market_data, pd.DataFrame):
        frame = market_data.reset_index() if isinstance(market_data.index, pd.MultiIndex) else market_data.copy()
        polars_frame = pl.from_pandas(frame)
    else:
        polars_frame = market_data.clone()
    rename_map = {
        "$open": "open",
        "$high": "high",
        "$low": "low",
        "$close": "close",
        "$volume": "volume",
        "$vwap": "vwap",
        "$return": "return",
        "vt_symbol": "instrument",
    }
    actual_rename = {old: new for old, new in rename_map.items() if old in polars_frame.columns and new not in polars_frame.columns}
    for column in polars_frame.columns:
        if column.startswith("$") and column[1:] not in polars_frame.columns:
            actual_rename[column] = column[1:]
    if actual_rename:
        polars_frame = polars_frame.rename(actual_rename)
    if "datetime" not in polars_frame.columns or "instrument" not in polars_frame.columns:
        raise ValueError("shared polars market data must contain datetime and instrument")
    return polars_frame.with_columns(pl.col("datetime").cast(pl.Datetime), pl.col("instrument").cast(pl.Utf8)).sort(["instrument", "datetime"])


def _prepare_for_ast(expression: str) -> tuple[str, dict[str, str]]:
    fields = sorted(set(re.findall(r"\$[A-Za-z_][A-Za-z0-9_]*", expression)), key=len, reverse=True)
    field_map = {f"field_{field[1:]}": field[1:] for field in fields}
    prepared = expression
    for name, field in field_map.items():
        prepared = prepared.replace(f"${field}", name)
    return prepared, field_map


def _prepare_expression_syntax(expression: str) -> str:
    expr = _convert_ternary_groups(expression)
    expr = _convert_ternary(expr)
    expr = _convert_logical_chains(expr)
    return expr


def _convert_ternary_groups(expression: str) -> str:
    expr = expression
    while True:
        pairs = _parenthesis_pairs(expr)
        replacement: tuple[int, int, str] | None = None
        for start, end in reversed(pairs):
            inner = expr[start + 1 : end]
            question = _find_top_level_char(inner, "?")
            if question < 0:
                continue
            colon = _find_matching_ternary_colon(inner, question)
            if colon < 0:
                continue
            replacement = (start, end, f"({_convert_ternary(inner)})")
            break
        if replacement is None:
            return expr
        start, end, converted = replacement
        expr = f"{expr[:start]}{converted}{expr[end + 1:]}"


def _parenthesis_pairs(expression: str) -> list[tuple[int, int]]:
    stack: list[int] = []
    pairs: list[tuple[int, int]] = []
    for index, char in enumerate(expression):
        if char == "(":
            stack.append(index)
        elif char == ")" and stack:
            pairs.append((stack.pop(), index))
    return pairs


def _convert_logical_chains(expression: str) -> str:
    return _convert_logical_operator(_convert_logical_operator(expression, "&&", "AND"), "||", "OR")


def _convert_logical_operator(expression: str, operator: str, function_name: str) -> str:
    expr = expression
    while operator in expr:
        index = expr.find(operator)
        left_start = _logical_operand_start(expr, index - 1)
        right_end = _logical_operand_end(expr, index + len(operator))
        left = expr[left_start:index].strip()
        right = expr[index + len(operator) : right_end].strip()
        expr = f"{expr[:left_start]}{function_name}({left}, {right}){expr[right_end:]}"
    return expr


def _logical_operand_start(expression: str, index: int) -> int:
    depth = 0
    while index >= 0:
        char = expression[index]
        if char == ")":
            depth += 1
        elif char == "(":
            if depth == 0:
                if index > 0 and (expression[index - 1].isalnum() or expression[index - 1] == "_"):
                    return index + 1
                return index
            depth -= 1
        elif depth == 0 and char == ",":
            return index + 1
        elif depth == 0 and index >= 1 and expression[index - 1 : index + 1] in {"&&", "||"}:
            return index + 1
        index -= 1
    return 0


def _logical_operand_end(expression: str, index: int) -> int:
    depth = 0
    while index < len(expression):
        char = expression[index]
        if char == "(":
            depth += 1
        elif char == ")":
            if depth == 0:
                return index
            depth -= 1
        elif depth == 0 and char == ",":
            return index
        elif depth == 0 and expression[index : index + 2] in {"&&", "||"}:
            return index
        index += 1
    return len(expression)


def _convert_ternary(expression: str) -> str:
    expression = expression.strip()
    question = _find_top_level_char(expression, "?")
    if question < 0:
        return expression
    colon = _find_matching_ternary_colon(expression, question)
    if colon < 0:
        raise UnsupportedExpressionError("malformed ternary expression")
    condition = _strip_outer_parens(expression[:question].strip())
    if_true = expression[question + 1 : colon].strip()
    if_false = expression[colon + 1 :].strip()
    return f"IF({_convert_logical_chains(_convert_ternary(condition))}, {_convert_ternary(if_true)}, {_convert_ternary(if_false)})"


def _find_top_level_char(expression: str, target: str) -> int:
    depth = 0
    for index, char in enumerate(expression):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif char == target and depth == 0:
            return index
    if expression.startswith("(") and expression.endswith(")"):
        inner = expression[1:-1]
        found = _find_top_level_char(inner, target)
        if found >= 0:
            return found + 1
    return -1


def _find_matching_ternary_colon(expression: str, question: int) -> int:
    depth = 0
    nested = 0
    for index in range(question + 1, len(expression)):
        char = expression[index]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        elif depth == 0 and char == "?":
            nested += 1
        elif depth == 0 and char == ":":
            if nested == 0:
                return index
            nested -= 1
    return -1


def _strip_outer_parens(expression: str) -> str:
    if not (expression.startswith("(") and expression.endswith(")")):
        return expression
    depth = 0
    for index, char in enumerate(expression):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0 and index != len(expression) - 1:
                return expression
    return expression[1:-1].strip()


def _expect_value(value: KernelValue | float | KernelSequence) -> KernelValue:
    if not isinstance(value, KernelValue):
        raise UnsupportedExpressionError("expected expression value, got scalar")
    return value


def _expect_number(value: KernelValue | float | KernelSequence) -> float:
    if isinstance(value, (KernelValue, KernelSequence)):
        raise UnsupportedExpressionError("expected scalar argument, got expression")
    return float(value)


def _expect_sequence(value: KernelValue | float | KernelSequence, window: int) -> KernelSequence:
    if not isinstance(value, KernelSequence):
        raise UnsupportedExpressionError("expected SEQUENCE(n) regression helper")
    if value.length != window:
        raise UnsupportedExpressionError(f"SEQUENCE length {value.length} differs from window {window}")
    return value


def _delay(value: KernelValue, period: int) -> KernelValue:
    return KernelValue(
        value.frame.select("datetime", "instrument", pl.col("data").shift(period).over("instrument").alias("data"))
    )


def _rolling(operation: str, value: KernelValue, window: int) -> KernelValue:
    expr = pl.col("data").fill_nan(None)
    if operation == "mean":
        data_expr = expr.rolling_mean(window, min_samples=window)
    elif operation == "sum":
        data_expr = expr.rolling_sum(window, min_samples=window)
    elif operation == "std":
        data_expr = expr.rolling_std(window, min_samples=window, ddof=1)
    elif operation == "var":
        data_expr = expr.rolling_var(window, min_samples=window, ddof=1)
    elif operation == "skew":
        data_expr = expr.rolling_skew(window_size=window, min_samples=window)
    elif operation == "min":
        data_expr = expr.rolling_min(window, min_samples=window)
    elif operation == "max":
        data_expr = expr.rolling_max(window, min_samples=window)
    else:
        raise UnsupportedExpressionError(f"unsupported rolling operation: {operation}")
    return KernelValue(value.frame.select("datetime", "instrument", data_expr.over("instrument").alias("data")))


def _rolling_loose(operation: str, value: KernelValue, window: int) -> KernelValue:
    expr = pl.col("data").fill_nan(None)
    if operation == "mean":
        data_expr = expr.rolling_mean(window, min_samples=1)
    elif operation == "std":
        data_expr = expr.rolling_std(window, min_samples=1, ddof=1)
    else:
        raise UnsupportedExpressionError(f"unsupported loose rolling operation: {operation}")
    return KernelValue(value.frame.select("datetime", "instrument", data_expr.over("instrument").alias("data")))


def _rolling_product_loose(value: KernelValue, window: int) -> KernelValue:
    def calc(values) -> float:
        arr = values.to_numpy()
        arr = arr[~np.isnan(arr)]
        return float(np.prod(arr)) if len(arr) else np.nan

    return KernelValue(
        value.frame.select(
            "datetime",
            "instrument",
            pl.col("data").fill_nan(None).rolling_map(calc, window_size=window, min_samples=1).over("instrument").alias("data"),
        )
    )


def _rolling_mad(value: KernelValue, window: int) -> KernelValue:
    def calc(values) -> float:
        arr = values.to_numpy()
        arr = arr[~np.isnan(arr)]
        if len(arr) == 0:
            return np.nan
        median = np.median(arr)
        return float(np.median(np.abs(arr - median)))

    return KernelValue(
        value.frame.select(
            "datetime",
            "instrument",
            pl.col("data").fill_nan(None).rolling_map(calc, window_size=window, min_samples=1).over("instrument").alias("data"),
        )
    )


def _cs_aggregate(value: KernelValue, operation: str) -> KernelValue:
    expr = pl.col("data")
    if operation == "mean":
        data_expr = expr.mean().over("datetime")
    elif operation == "std":
        data_expr = expr.std(ddof=1).over("datetime")
    elif operation == "skew":
        data_expr = ((expr - expr.mean().over("datetime")).pow(3).mean().over("datetime")) / expr.std(ddof=1).over("datetime").pow(3)
    else:
        raise UnsupportedExpressionError(f"unsupported cross-sectional aggregate: {operation}")
    return KernelValue(value.frame.select("datetime", "instrument", data_expr.alias("data")))


def _cs_kurt(value: KernelValue) -> KernelValue:
    pdf = value.frame.to_pandas().sort_values(["datetime", "instrument"])
    pdf["data"] = pdf.groupby("datetime", sort=False)["data"].transform(lambda series: series.kurt()).astype("float32")
    return KernelValue(pl.from_pandas(pdf))


def _rolling_quantile(value: KernelValue, window: int, quantile: float) -> KernelValue:
    data_expr = pl.col("data").fill_nan(None).rolling_quantile(
        quantile, interpolation="linear", window_size=window, min_samples=window
    )
    return KernelValue(value.frame.select("datetime", "instrument", data_expr.over("instrument").alias("data")))


def _full_instrument_quantile(value: KernelValue, quantile: float) -> KernelValue:
    return KernelValue(
        value.frame.select(
            "datetime",
            "instrument",
            pl.col("data").fill_nan(None).quantile(quantile, interpolation="linear").over("instrument").alias("data"),
        )
    )


def _rolling_count(value: KernelValue, window: int) -> KernelValue:
    data_expr = pl.col("data").fill_nan(None).is_not_null().cast(pl.Float64).rolling_sum(window, min_samples=window)
    return KernelValue(value.frame.select("datetime", "instrument", data_expr.over("instrument").alias("data")))


def _rolling_sumif(value: KernelValue, window: int, condition: KernelValue) -> KernelValue:
    frame = value.frame.join(condition.frame, on=["datetime", "instrument"], suffix="_condition")
    data_expr = (
        pl.when(pl.col("data_condition").fill_null(0.0) != 0.0)
        .then(pl.col("data").fill_nan(None))
        .otherwise(0.0)
        .rolling_sum(window, min_samples=window)
    )
    return KernelValue(frame.select("datetime", "instrument", data_expr.over("instrument").alias("data")))


def _decay_linear(value: KernelValue, window: int) -> KernelValue:
    weights = np.arange(1, window + 1, dtype=float)
    weights = weights / weights.sum()

    def calc(values) -> float:
        if len(values) < window or values.null_count() > 0:
            return None
        arr = values.to_numpy()
        return float((arr * weights).sum())

    return KernelValue(
        value.frame.select(
            "datetime",
            "instrument",
            pl.col("data").fill_nan(None).rolling_map(calc, window_size=window, min_samples=window).over("instrument").alias("data"),
        )
    )


def _rolling_arg(value: KernelValue, window: int, which: str) -> KernelValue:
    def arg(values) -> float:
        if len(values) < window or values.null_count() > 0:
            return None
        arr = values.to_numpy()
        if which == "max":
            return float(arr.argmax() + 1)
        return float(arr.argmin() + 1)

    return KernelValue(
        value.frame.select(
            "datetime",
            "instrument",
            pl.col("data").fill_nan(None).rolling_map(arg, window_size=window, min_samples=window).over("instrument").alias("data"),
        )
    )


def _ts_rank(value: KernelValue, window: int) -> KernelValue:
    current = pl.col("data").fill_nan(None)
    lags = [current.shift(i).over("instrument") for i in range(window)]
    less_count = pl.sum_horizontal([pl.when(lag.is_not_null() & (lag < current)).then(1.0).otherwise(0.0) for lag in lags])
    equal_count = pl.sum_horizontal([pl.when(lag.is_not_null() & (lag == current)).then(1.0).otherwise(0.0) for lag in lags])
    valid_count = pl.sum_horizontal([pl.when(lag.is_not_null()).then(1.0).otherwise(0.0) for lag in lags])
    rank_expr = (less_count + (equal_count + 1.0) / 2.0) / valid_count
    return KernelValue(
        value.frame.select(
            "datetime",
            "instrument",
            pl.when(current.is_null() | (valid_count < window)).then(None).otherwise(rank_expr).alias("data"),
        )
    )


def _cs_rank(value: KernelValue) -> KernelValue:
    return KernelValue(
        value.frame.select(
            "datetime",
            "instrument",
            pl.col("data").rank(method="average").over("datetime").alias("_rank"),
            pl.col("data").count().over("datetime").alias("_count"),
        ).select("datetime", "instrument", (pl.col("_rank") / pl.col("_count")).alias("data"))
    )


def _cs_zscore(value: KernelValue) -> KernelValue:
    frame = value.frame.with_columns(
        pl.col("data").mean().over("datetime").alias("_mean"),
        pl.col("data").std(ddof=1).over("datetime").alias("_std"),
    )
    return KernelValue(
        frame.select(
            "datetime",
            "instrument",
            pl.when(pl.col("_std") == 0).then(None).otherwise((pl.col("data") - pl.col("_mean")) / pl.col("_std")).alias("data"),
        )
    )


def _cs_median(value: KernelValue) -> KernelValue:
    return KernelValue(
        value.frame.select("datetime", "instrument", pl.col("data").median().over("datetime").alias("data"))
    )


def _rolling_corr(left: KernelValue | float | KernelSequence, right: KernelValue | float | KernelSequence, window: int) -> KernelValue:
    if isinstance(left, KernelSequence):
        _expect_sequence(left, window)
        return _rolling_corr_sequence(_expect_value(right), window)
    if isinstance(right, KernelSequence):
        _expect_sequence(right, window)
        return _rolling_corr_sequence(_expect_value(left), window)
    left = _expect_value(left)
    right = _expect_value(right)
    left_pdf = left.frame.to_pandas().set_index(["datetime", "instrument"])["data"].astype("float32")
    right_pdf = right.frame.to_pandas().set_index(["datetime", "instrument"])["data"].astype("float32")
    pieces = []
    for instrument, left_part in left_pdf.groupby(level="instrument", group_keys=False):
        try:
            right_part = right_pdf.xs(instrument, level="instrument")
        except KeyError:
            continue
        left_by_date = left_part.droplevel("instrument")
        corr = left_by_date.rolling(window, min_periods=window).corr(right_part)
        corr.index = pd.MultiIndex.from_arrays(
            [corr.index, [instrument] * len(corr)], names=["datetime", "instrument"]
        )
        pieces.append(corr)
    if not pieces:
        out = pd.Series(dtype="float32", index=left_pdf.index, name="data")
    else:
        out = pd.concat(pieces).sort_index().astype("float32").rename("data")
    return KernelValue(pl.from_pandas(out.reset_index()))


def _rolling_corr_sequence(value: KernelValue, window: int) -> KernelValue:
    series = value.frame.to_pandas().set_index(["datetime", "instrument"])["data"].astype("float32")
    x = np.linspace(1, window, window, dtype=np.float32)

    def calc(values) -> float:
        if len(values) < window or pd.isna(values).any():
            return np.nan
        if np.isclose(values.std(ddof=1), 0):
            return np.nan
        return float(pd.Series(values).corr(pd.Series(x)))

    result = (
        series.groupby(level="instrument", group_keys=False)
        .rolling(window, min_periods=window)
        .apply(calc, raw=True)
        .droplevel(0)
        .sort_index()
        .astype("float32")
        .rename("data")
    )
    return KernelValue(pl.from_pandas(result.reset_index()))


def _rolling_regression(value: KernelValue, window: int, stat: str, x_values: np.ndarray | None = None) -> KernelValue:
    if stat in {"rsquare", "resi"}:
        return _rolling_regression_pandas(value, window, stat, x_values)
    if x_values is not None:
        return _rolling_regression_pandas(value, window, stat, x_values)
    n = float(window)
    sum_x = n * (n + 1.0) / 2.0
    sum_x2 = n * (n + 1.0) * (2.0 * n + 1.0) / 6.0
    mean_x = (n + 1.0) / 2.0
    denom = n * sum_x2 - sum_x * sum_x
    y = pl.col("data").fill_nan(None)
    sum_xy = pl.sum_horizontal([(window - lag) * y.shift(lag) for lag in range(window)])
    frame = value.frame.with_columns(
        y.rolling_sum(window, min_samples=window).over("instrument").alias("_sum_y"),
        y.rolling_var(window, min_samples=window, ddof=0).over("instrument").alias("_var_y"),
        sum_xy.over("instrument").alias("_sum_xy"),
    )
    slope = (n * pl.col("_sum_xy") - sum_x * pl.col("_sum_y")) / denom
    if stat == "slope":
        return KernelValue(frame.select("datetime", "instrument", slope.alias("data")))
    mean_y = pl.col("_sum_y") / n
    if stat == "rsquare":
        var_x = sum_x2 / n - mean_x * mean_x
        cov_xy = pl.col("_sum_xy") / n - mean_x * mean_y
        rsquare = cov_xy.pow(2) / (var_x * pl.col("_var_y"))
        return KernelValue(
            frame.select(
                "datetime",
                "instrument",
                pl.when(rsquare.is_infinite() | rsquare.is_nan()).then(None).otherwise(rsquare).alias("data"),
            )
        )
    intercept = mean_y - slope * mean_x
    fitted_last = slope * n + intercept
    resi = y - fitted_last
    return KernelValue(frame.select("datetime", "instrument", resi.alias("data")))


def _rolling_regression_pandas(
    value: KernelValue,
    window: int,
    stat: str,
    x_values: np.ndarray | None = None,
) -> KernelValue:
    series = value.frame.to_pandas().set_index(["datetime", "instrument"])["data"].astype("float32")

    def calc(values) -> float:
        if pd.isna(values).any():
            return np.nan
        x = np.asarray(x_values, dtype=float) if x_values is not None else np.arange(1, len(values) + 1, dtype=float)
        x_mean = x.mean()
        y_mean = values.mean()
        denom = float(((x - x_mean) ** 2).sum())
        if denom <= 0:
            if stat in {"slope", "resi"}:
                design = np.vstack([x, np.ones(len(x))]).T
                slope, intercept = np.linalg.lstsq(design, values, rcond=None)[0]
                if stat == "slope":
                    return float(slope)
                return float(values[-1] - (slope * x[-1] + intercept))
            return np.nan
        slope = float(((x - x_mean) * (values - y_mean)).sum() / denom)
        intercept = y_mean - slope * x_mean
        fitted = slope * x + intercept
        residual = values - fitted
        if stat == "resi":
            return float(residual[-1])
        total = float(((values - y_mean) ** 2).sum())
        if total <= 0:
            return np.nan
        return float(1.0 - ((residual**2).sum() / total))

    result = (
        series.groupby(level="instrument", group_keys=False)
        .rolling(window, min_periods=window)
        .apply(calc, raw=True)
        .droplevel(0)
        .sort_index()
        .astype("float32")
        .rename("data")
    )
    if stat == "rsquare":
        rolling_std = (
            series.groupby(level="instrument", group_keys=False)
            .rolling(window, min_periods=window)
            .std()
            .droplevel(0)
            .sort_index()
        )
        result = result.mask(np.isclose(rolling_std, 0, atol=2e-05)).astype("float32").rename("data")
    return KernelValue(pl.from_pandas(result.reset_index()))


def _rolling_regression_xy(y_value: KernelValue, x_value: KernelValue, window: int, stat: str) -> KernelValue:
    y_series = y_value.frame.to_pandas().set_index(["datetime", "instrument"])["data"].astype("float32")
    x_series = x_value.frame.to_pandas().set_index(["datetime", "instrument"])["data"].astype("float32")
    joined = pd.concat([y_series.rename("y"), x_series.rename("x")], axis=1).sort_index()
    pieces = []
    for instrument, part in joined.groupby(level="instrument", group_keys=False):
        y = part["y"].droplevel("instrument")
        x = part["x"].droplevel("instrument")
        rows = []
        for end in range(len(part)):
            if end + 1 < window:
                rows.append(np.nan)
                continue
            y_win = y.iloc[end + 1 - window : end + 1].to_numpy(dtype=float)
            x_win = x.iloc[end + 1 - window : end + 1].to_numpy(dtype=float)
            if np.isnan(y_win).any() or np.isnan(x_win).any():
                rows.append(np.nan)
                continue
            x_mean = x_win.mean()
            y_mean = y_win.mean()
            denom = float(((x_win - x_mean) ** 2).sum())
            if denom <= 0:
                rows.append(np.nan)
                continue
            slope = float(((x_win - x_mean) * (y_win - y_mean)).sum() / denom)
            intercept = y_mean - slope * x_mean
            if stat == "slope":
                rows.append(slope)
            else:
                rows.append(float(y_win[-1] - (slope * x_win[-1] + intercept)))
        out = pd.Series(rows, index=y.index)
        out.index = pd.MultiIndex.from_arrays([out.index, [instrument] * len(out)], names=["datetime", "instrument"])
        pieces.append(out)
    result = pd.concat(pieces).sort_index().astype("float32").rename("data") if pieces else pd.Series(dtype="float32", index=y_series.index, name="data")
    return KernelValue(pl.from_pandas(result.reset_index()))


def _elementwise_extreme(left: KernelValue, right: KernelValue | float | KernelSequence, which: str) -> KernelValue:
    if isinstance(right, KernelValue):
        frame = left.frame.join(right.frame, on=["datetime", "instrument"], suffix="_right")
        values = [pl.col("data"), pl.col("data_right")]
    else:
        frame = left.frame
        values = [pl.col("data"), pl.lit(float(right))]
    expr = pl.max_horizontal(values) if which == "max" else pl.min_horizontal(values)
    return KernelValue(frame.select("datetime", "instrument", expr.alias("data")))


def _elementwise_extreme_args(left: KernelValue | float | KernelSequence, right: KernelValue | float | KernelSequence, which: str) -> KernelValue:
    if isinstance(left, KernelValue):
        return _elementwise_extreme(left, right, which)
    if isinstance(right, KernelValue):
        return _elementwise_extreme(right, left, which)
    raise UnsupportedExpressionError("scalar-only MAX/MIN expression cannot define output index")


def _elementwise_math(value: KernelValue, operation: str) -> KernelValue:
    expr = pl.col("data")
    if operation == "sign":
        data_expr = pl.when(expr > 0).then(1.0).when(expr < 0).then(-1.0).otherwise(0.0)
    elif operation == "sqrt":
        data_expr = expr.sqrt()
    elif operation == "abs":
        data_expr = expr.abs()
    else:
        raise UnsupportedExpressionError(f"unsupported element-wise math operation: {operation}")
    return KernelValue(value.frame.select("datetime", "instrument", data_expr.alias("data")))


def _elementwise_power(value: KernelValue, exponent: float) -> KernelValue:
    return KernelValue(value.frame.select("datetime", "instrument", pl.col("data").pow(exponent).alias("data")))


def _logical_binary(left: KernelValue, right: KernelValue | float | KernelSequence, operation: str) -> KernelValue:
    if isinstance(right, KernelValue):
        frame = left.frame.join(right.frame, on=["datetime", "instrument"], suffix="_right")
        lhs = pl.col("data").fill_null(0.0) != 0.0
        rhs = pl.col("data_right").fill_null(0.0) != 0.0
    else:
        frame = left.frame
        lhs = pl.col("data").fill_null(0.0) != 0.0
        rhs = pl.lit(bool(_expect_number(right)))
    expr = lhs & rhs if operation == "and" else lhs | rhs
    return KernelValue(frame.select("datetime", "instrument", expr.cast(pl.Float64).alias("data")))


def _value_compare(left: KernelValue, right: KernelValue | float | KernelSequence, operation: str) -> KernelValue:
    if isinstance(right, KernelValue):
        frame = left.frame.join(right.frame, on=["datetime", "instrument"], suffix="_right")
        right_expr = pl.col("data_right")
    else:
        frame = left.frame
        right_expr = pl.lit(float(_expect_number(right)))
    left_expr = pl.col("data")
    if operation == "gt":
        expr = left_expr > right_expr
    elif operation == "lt":
        expr = left_expr < right_expr
    else:
        raise UnsupportedExpressionError(f"unsupported value comparison: {operation}")
    return KernelValue(frame.select("datetime", "instrument", expr.fill_null(False).cast(pl.Float64).alias("data")))


def _where(condition: KernelValue, if_true: KernelValue | float | KernelSequence, if_false: KernelValue | float | KernelSequence) -> KernelValue:
    frame = condition.frame.rename({"data": "_condition"})
    if isinstance(if_true, KernelValue):
        frame = frame.join(if_true.frame, on=["datetime", "instrument"])
        true_expr = pl.col("data")
    else:
        true_expr = pl.lit(_expect_number(if_true))
    if isinstance(if_false, KernelValue):
        frame = frame.join(if_false.frame, on=["datetime", "instrument"], suffix="_false")
        false_expr = pl.col("data_false")
    else:
        false_expr = pl.lit(_expect_number(if_false))
    return KernelValue(
        frame.select(
            "datetime",
            "instrument",
            pl.when(pl.col("_condition").fill_null(0.0) != 0.0).then(true_expr).otherwise(false_expr).alias("data"),
        )
    )


def _wma(value: KernelValue, window: int) -> KernelValue:
    weights = np.array([0.9**i for i in range(window)][::-1], dtype=float)

    def calc(values) -> float:
        arr = values.to_numpy()
        arr = arr[~np.isnan(arr)]
        if len(arr) == 0:
            return np.nan
        active_weights = weights[: len(arr)]
        return float((arr * active_weights).sum() / active_weights.sum())

    return KernelValue(
        value.frame.select(
            "datetime",
            "instrument",
            pl.col("data").fill_nan(None).rolling_map(calc, window_size=window, min_samples=1).over("instrument").alias("data"),
        )
    )


def _rsi(value: KernelValue, window: int) -> KernelValue:
    delta = value - _delay(value, 1)
    up = _where(_value_compare(delta, 0.0, "gt"), delta, 0.0)
    down = _where(_value_compare(delta, 0.0, "lt"), _elementwise_math(delta, "abs"), 0.0)
    avg_up = _ewm_mean(up, window)
    avg_down = _ewm_mean(down, window)
    return 100.0 - (100.0 / (1.0 + (avg_up / avg_down)))


def _ewm_mean(value: KernelValue, window: int) -> KernelValue:
    pdf = value.frame.to_pandas().sort_values(["instrument", "datetime"])
    pdf["data"] = (
        pdf.groupby("instrument", sort=False)["data"]
        .transform(lambda series: series.ewm(span=window, min_periods=1).mean())
        .astype("float32")
    )
    return KernelValue(pl.from_pandas(pdf))


def _ewm_alpha(value: KernelValue, alpha: float) -> KernelValue:
    pdf = value.frame.to_pandas().sort_values(["instrument", "datetime"])
    pdf["data"] = (
        pdf.groupby("instrument", sort=False)["data"]
        .transform(lambda series: series.ewm(alpha=alpha, min_periods=1).mean())
        .astype("float32")
    )
    return KernelValue(pl.from_pandas(pdf))
