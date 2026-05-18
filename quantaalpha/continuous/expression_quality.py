from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import Optional


def unsupported_translation_warning(translation_warnings: list[str]) -> Optional[str]:
    for warning in translation_warnings:
        if "不支持的功能" in warning or "unsupported" in warning.lower():
            return warning
    return None


def operator_arity_warning(translated_expression: str) -> Optional[str]:
    required_args = {
        "ts_corr": 3,
        "ts_cov": 3,
        "ts_regresi": 3,
        "ts_regbeta": 3,
        "ts_slope": 3,
        "ts_resi": 2,
        "ts_delay": 2,
        "ts_delta": 2,
        "ts_mean": 2,
        "ts_std": 2,
        "ts_var": 2,
        "ts_sum": 2,
        "ts_quantile": 3,
        "cs_mean": 1,
        "cs_std": 1,
        "cs_rank": 1,
        "cs_skew": 1,
        "cs_kurt": 1,
        "cs_median": 1,
        "cs_sum": 1,
        "cs_scale": 1,
    }
    for operator, expected in required_args.items():
        for args in iter_call_args(translated_expression, operator):
            if len(args) != expected:
                return f"{operator} expects {expected} arguments, got {len(args)}"

    integer_window_args = {
        "ts_corr": [2],
        "ts_cov": [2],
        "ts_regresi": [2],
        "ts_regbeta": [2],
        "ts_resi": [1],
        "ts_delay": [1],
        "ts_delta": [1],
        "ts_mean": [1],
        "ts_std": [1],
        "ts_var": [1],
        "ts_sum": [1],
        "ts_quantile": [1],
    }
    for operator, arg_positions in integer_window_args.items():
        for args in iter_call_args(translated_expression, operator):
            for arg_position in arg_positions:
                if len(args) <= arg_position:
                    continue
                value = args[arg_position].strip()
                if not re.fullmatch(r"-?\d+", value):
                    return (
                        f"{operator} expects integer window argument "
                        f"at position {arg_position + 1}, got {value}"
                    )
    return None


def iter_call_args(expression: str, operator: str) -> list[list[str]]:
    calls: list[list[str]] = []
    needle = f"{operator}("
    start = 0
    while True:
        idx = expression.find(needle, start)
        if idx < 0:
            break
        args_start = idx + len(needle)
        depth = 1
        pos = args_start
        while pos < len(expression) and depth > 0:
            char = expression[pos]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            pos += 1
        if depth != 0:
            calls.append([])
            start = args_start
            continue
        calls.append(split_top_level_args(expression[args_start : pos - 1]))
        start = pos
    return calls


def split_top_level_args(args_text: str) -> list[str]:
    args: list[str] = []
    depth = 0
    current: list[str] = []
    for char in args_text:
        if char == "(":
            depth += 1
            current.append(char)
        elif char == ")":
            depth -= 1
            current.append(char)
        elif char == "," and depth == 0:
            arg = "".join(current).strip()
            if arg:
                args.append(arg)
            current = []
        else:
            current.append(char)
    arg = "".join(current).strip()
    if arg:
        args.append(arg)
    return args


def build_factor_error(
    *,
    expression: str,
    error_type: str,
    error_message: str,
    source: str,
    factor_id: str | None = None,
    created_at: str | None = None,
) -> dict:
    error = {
        "expression": expression,
        "error_type": error_type,
        "error_message": error_message,
        "source": source,
        "created_at": created_at or datetime.now(UTC).isoformat(timespec="seconds"),
    }
    if factor_id:
        error["factor_id"] = factor_id
    return error
