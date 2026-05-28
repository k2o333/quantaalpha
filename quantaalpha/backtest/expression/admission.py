"""Polars 表达式准入检查。

本模块只做 direct parquet runtime 的前置语义检查，不替代
`SharedPolarsExpressionKernel` 的实际计算。准入分类优先来自 AST 和
算子签名提取，避免依赖 runtime 异常文案来区分 function/arity。
"""

from __future__ import annotations

import ast
from collections import defaultdict
from dataclasses import asdict, dataclass
import inspect
import re
import textwrap
from typing import Iterable

import pandas as pd
import polars as pl

from .canonical import QLIB_ALIAS_MAP, VNPY_ALIAS_MAP, canonicalize_expression
from .polars_kernel import (
    SharedPolarsExpressionKernel,
    UnsupportedExpressionError,
    _prepare_expression_syntax,
    _prepare_for_ast,
)

ADMISSION_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class OperatorSignature:
    """表达式算子签名。"""

    name: str
    arities: tuple[int, ...]
    aliases: tuple[str, ...] = ()


@dataclass(frozen=True)
class ExpressionAdmissionResult:
    """单个表达式准入结果。"""

    accepted: bool
    canonical: str
    reason_code: str | None = None
    message: str = ""
    missing_fields: tuple[str, ...] = ()
    function_name: str | None = None
    arity: int | None = None
    suggested_alternatives: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """返回可 JSON 序列化的 evidence 字典。"""

        return asdict(self)


def admit_expression(
    expression: str,
    *,
    available_fields: Iterable[str] | None = None,
) -> ExpressionAdmissionResult:
    """检查表达式是否落在 shared polars kernel 当前覆盖范围内。

    Args:
        expression: 原始因子表达式。
        available_fields: 可选的 standard-frame 字段集合。字段可带或不带 `$`。

    Returns:
        表达式准入结果。`accepted=False` 时 `reason_code` 用于 LLM 修正和 evidence 聚合。
    """

    source = str(expression or "").strip()
    if not source:
        return ExpressionAdmissionResult(
            accepted=False,
            canonical="",
            reason_code="parse_error",
            message="expression is empty",
        )

    try:
        canonical = canonicalize_expression(source).canonical
        prepared_expression = _prepare_expression_syntax(canonical)
        prepared, field_map = _prepare_for_ast(prepared_expression)
        tree = ast.parse(prepared, mode="eval")
    except SyntaxError as exc:
        return ExpressionAdmissionResult(
            accepted=False,
            canonical=canonical if "canonical" in locals() else source,
            reason_code="parse_error",
            message=str(exc),
        )
    except Exception as exc:
        return ExpressionAdmissionResult(
            accepted=False,
            canonical=canonical if "canonical" in locals() else source,
            reason_code="unsupported_syntax",
            message=str(exc),
        )

    if available_fields is not None:
        normalized_fields = _normalize_available_fields(available_fields)
        missing = tuple(sorted(field for field in set(field_map.values()) if field not in normalized_fields))
        if missing:
            return ExpressionAdmissionResult(
                accepted=False,
                canonical=canonical,
                reason_code="missing_field",
                message=f"missing standard-frame field(s): {', '.join('$' + field for field in missing)}",
                missing_fields=tuple(f"${field}" for field in missing),
            )

    signatures = extract_operator_signatures()
    syntax_error = _classify_syntax_and_calls(tree.body, signatures)
    if syntax_error is not None:
        return ExpressionAdmissionResult(canonical=canonical, **syntax_error)

    runtime_error = _classify_sample_evaluation(canonical, field_map.values())
    if runtime_error is not None:
        return ExpressionAdmissionResult(canonical=canonical, **runtime_error)

    return ExpressionAdmissionResult(accepted=True, canonical=canonical)


def extract_operator_signatures() -> dict[str, OperatorSignature]:
    """从 `SharedPolarsExpressionKernel._call()` 确定性提取算子签名。"""

    source = textwrap.dedent(inspect.getsource(SharedPolarsExpressionKernel._call))
    tree = ast.parse(source)
    arities_by_name: dict[str, set[int]] = defaultdict(set)
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        names, arities = _extract_if_signature(node.test)
        for name in names:
            for arity in arities:
                arities_by_name[name].add(arity)

    aliases_by_canonical: dict[str, set[str]] = defaultdict(set)
    for alias, canonical in {**QLIB_ALIAS_MAP, **VNPY_ALIAS_MAP}.items():
        aliases_by_canonical[canonical].add(alias)

    signatures: dict[str, OperatorSignature] = {}
    for name, arities in sorted(arities_by_name.items()):
        signatures[name] = OperatorSignature(
            name=name,
            arities=tuple(sorted(arities)),
            aliases=tuple(sorted(aliases_by_canonical.get(name, ()))),
        )
    return signatures


def _classify_syntax_and_calls(
    node: ast.AST,
    signatures: dict[str, OperatorSignature],
) -> dict[str, object] | None:
    if isinstance(node, ast.Expression):
        return _classify_syntax_and_calls(node.body, signatures)
    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
            return {
                "accepted": False,
                "reason_code": "unsupported_syntax",
                "message": f"unsupported binary operator: {type(node.op).__name__}",
            }
        return _first_error((_classify_syntax_and_calls(node.left, signatures), _classify_syntax_and_calls(node.right, signatures)))
    if isinstance(node, ast.UnaryOp):
        if not isinstance(node.op, ast.USub):
            return {
                "accepted": False,
                "reason_code": "unsupported_syntax",
                "message": f"unsupported unary operator: {type(node.op).__name__}",
            }
        return _classify_syntax_and_calls(node.operand, signatures)
    if isinstance(node, ast.Compare):
        if len(node.ops) != 1 or len(node.comparators) != 1:
            return {
                "accepted": False,
                "reason_code": "unsupported_syntax",
                "message": "chained comparisons are not supported",
            }
        allowed = (ast.Gt, ast.GtE, ast.Lt, ast.LtE, ast.Eq, ast.NotEq)
        if not isinstance(node.ops[0], allowed):
            return {
                "accepted": False,
                "reason_code": "unsupported_syntax",
                "message": f"unsupported comparison operator: {type(node.ops[0]).__name__}",
            }
        return _first_error(
            (
                _classify_syntax_and_calls(node.left, signatures),
                _classify_syntax_and_calls(node.comparators[0], signatures),
            )
        )
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            return None
        return {
            "accepted": False,
            "reason_code": "unsupported_syntax",
            "message": f"unsupported constant: {type(node.value).__name__}",
        }
    if isinstance(node, ast.Name):
        return None
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        name = node.func.id
        arity = len(node.args)
        if name not in signatures:
            return {
                "accepted": False,
                "reason_code": "unsupported_function",
                "message": f"unsupported function: {name}",
                "function_name": name,
                "arity": arity,
                "suggested_alternatives": _suggest_operator_alternatives(name, signatures),
            }
        if arity not in signatures[name].arities:
            return {
                "accepted": False,
                "reason_code": "unsupported_arity",
                "message": f"unsupported arity for {name}: {arity}; supported={signatures[name].arities}",
                "function_name": name,
                "arity": arity,
            }
        return _first_error(tuple(_classify_syntax_and_calls(arg, signatures) for arg in node.args))
    return {
        "accepted": False,
        "reason_code": "unsupported_syntax",
        "message": f"unsupported expression node: {type(node).__name__}",
    }


def _first_error(errors: Iterable[dict[str, object] | None]) -> dict[str, object] | None:
    for error in errors:
        if error is not None:
            return error
    return None


def _normalize_available_fields(fields: Iterable[str]) -> set[str]:
    normalized = set()
    for field in fields:
        value = str(field)
        if value in {"datetime", "instrument"}:
            continue
        normalized.add(value[1:] if value.startswith("$") else value)
    return normalized


def _classify_sample_evaluation(canonical: str, fields: Iterable[str]) -> dict[str, object] | None:
    try:
        SharedPolarsExpressionKernel(_sample_market(fields), compat_mode="h5_coder").compute_expression(canonical, "admission")
    except UnsupportedExpressionError as exc:
        message = str(exc)
        if "expected expression value" in message or "expected scalar argument" in message:
            return {
                "accepted": False,
                "reason_code": "scalar_value_mismatch",
                "message": message,
            }
        return {
            "accepted": False,
            "reason_code": "unsupported_syntax",
            "message": message,
        }
    except Exception as exc:
        return {
            "accepted": False,
            "reason_code": "unsupported_syntax",
            "message": str(exc),
        }
    return None


def _sample_market(fields: Iterable[str]) -> pl.DataFrame:
    data: dict[str, object] = {
        "datetime": [
            pd.Timestamp("2020-01-01"),
            pd.Timestamp("2020-01-01"),
            pd.Timestamp("2020-01-02"),
            pd.Timestamp("2020-01-02"),
        ],
        "instrument": ["A", "B", "A", "B"],
    }
    for field in sorted(set(fields)):
        data[field] = [1.0, 2.0, 3.0, 4.0]
    return pl.DataFrame(data)


def _extract_if_signature(test: ast.AST) -> tuple[tuple[str, ...], tuple[int, ...]]:
    parts = test.values if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And) else [test]
    names: set[str] = set()
    arities: set[int] = set()
    for part in parts:
        part_names = _extract_names(part)
        part_arities = _extract_arities(part)
        names.update(part_names)
        arities.update(part_arities)
    if not names or not arities:
        return (), ()
    return tuple(sorted(names)), tuple(sorted(arities))


def _extract_names(node: ast.AST) -> tuple[str, ...]:
    if not isinstance(node, ast.Compare) or len(node.ops) != 1 or len(node.comparators) != 1:
        return ()
    if not isinstance(node.left, ast.Name) or node.left.id != "name":
        return ()
    comparator = node.comparators[0]
    if isinstance(node.ops[0], ast.Eq) and isinstance(comparator, ast.Constant) and isinstance(comparator.value, str):
        return (comparator.value,)
    if isinstance(node.ops[0], ast.In) and isinstance(comparator, (ast.Set, ast.Tuple, ast.List)):
        values = []
        for item in comparator.elts:
            if isinstance(item, ast.Constant) and isinstance(item.value, str):
                values.append(item.value)
        return tuple(values)
    return ()


def _extract_arities(node: ast.AST) -> tuple[int, ...]:
    if not isinstance(node, ast.Compare) or len(node.ops) != 1 or len(node.comparators) != 1:
        return ()
    if not _is_len_args_call(node.left):
        return ()
    comparator = node.comparators[0]
    if isinstance(node.ops[0], ast.Eq) and isinstance(comparator, ast.Constant) and isinstance(comparator.value, int):
        return (comparator.value,)
    if isinstance(node.ops[0], ast.In) and isinstance(comparator, (ast.Set, ast.Tuple, ast.List)):
        values = []
        for item in comparator.elts:
            if isinstance(item, ast.Constant) and isinstance(item.value, int):
                values.append(item.value)
        return tuple(values)
    return ()


def _is_len_args_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "len"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Name)
        and node.args[0].id == "args"
    )


def _suggest_operator_alternatives(
    name: str,
    signatures: dict[str, OperatorSignature],
) -> tuple[str, ...]:
    upper = name.upper()
    if upper in signatures and upper != name:
        return (upper,)
    normalized = re.sub(r"[^A-Z]", "", upper)
    if not normalized:
        return ()
    prefix_matches = sorted(op for op in signatures if op.startswith(normalized[:3]))
    return tuple(prefix_matches[:3])
