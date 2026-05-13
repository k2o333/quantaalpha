"""Small expression-syntax normalizations shared by mining and backtest."""

from __future__ import annotations


def normalize_neg_function(expression: str) -> str:
    """Normalize ``NEG(x)`` to ``-(x)`` without changing return semantics."""
    text = str(expression)
    needle = "NEG("
    while True:
        start = text.find(needle)
        if start < 0:
            return text
        arg_start = start + len(needle)
        depth = 1
        index = arg_start
        while index < len(text) and depth:
            char = text[index]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            index += 1
        if depth:
            return text
        inner = text[arg_start : index - 1]
        text = f"{text[:start]}-({inner}){text[index:]}"


def normalize_ts_autocorrelation(expression: str) -> str:
    """Normalize ``TS_AUTOCORRELATION(x, n)`` to explicit lag-1 rolling correlation."""
    text = str(expression)
    for name in ("TS_AUTOCORRELATION", "TS_AUTOCORR"):
        text = _normalize_autocorr_name(text, name)
    return text


def normalize_expression_syntax(expression: str) -> str:
    """Apply shared syntax normalizations that preserve factor semantics."""
    return normalize_ts_autocorrelation(normalize_neg_function(expression))


def _normalize_autocorr_name(text: str, name: str) -> str:
    needle = f"{name}("
    while True:
        start = text.find(needle)
        if start < 0:
            return text
        arg_start = start + len(needle)
        depth = 1
        index = arg_start
        comma_index = -1
        while index < len(text) and depth:
            char = text[index]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            elif char == "," and depth == 1 and comma_index < 0:
                comma_index = index
            index += 1
        if depth or comma_index < 0:
            return text
        value = text[arg_start:comma_index].strip()
        window = text[comma_index + 1 : index - 1].strip()
        replacement = f"TS_CORR({value}, DELAY({value}, 1), {window})"
        text = f"{text[:start]}{replacement}{text[index:]}"
