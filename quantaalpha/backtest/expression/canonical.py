"""Canonical factor expression normalization.

Canonical storage/audit form uses uppercase QuantaAlpha operators with `$field`
references, for example `TS_MEAN($close, 20)`.
"""

from __future__ import annotations

from dataclasses import dataclass
import re

from quantaalpha.factors.expression_syntax import normalize_expression_syntax


@dataclass(frozen=True)
class CanonicalExpression:
    """Canonicalization result."""

    source: str
    canonical: str
    warnings: tuple[str, ...] = ()


QLIB_ALIAS_MAP = {
    "Ref": "DELAY",
    "Mean": "TS_MEAN",
    "Std": "TS_STD",
    "Sum": "TS_SUM",
    "Rank": "TS_RANK",
    "Min": "TS_MIN",
    "Max": "TS_MAX",
    "Corr": "TS_CORR",
    "Quantile": "TS_QUANTILE",
    "IdxMax": "TS_ARGMAX",
    "IdxMin": "TS_ARGMIN",
    "Slope": "TS_SLOPE",
    "Rsquare": "TS_RSQUARE",
    "Resi": "TS_RESI",
    "Delta": "DELTA",
    "Abs": "ABS",
    "Log": "LOG",
    "Greater": "GREATER",
    "Less": "LESS",
}
VNPY_ALIAS_MAP = {
    "ts_delay": "DELAY",
    "ts_mean": "TS_MEAN",
    "ts_std": "TS_STD",
    "ts_sum": "TS_SUM",
    "ts_rank": "TS_RANK",
    "ts_min": "TS_MIN",
    "ts_max": "TS_MAX",
    "ts_corr": "TS_CORR",
    "ts_quantile": "TS_QUANTILE",
    "ts_argmax": "TS_ARGMAX",
    "ts_argmin": "TS_ARGMIN",
    "ts_slope": "TS_SLOPE",
    "ts_rsquare": "TS_RSQUARE",
    "ts_resi": "TS_RESI",
    "ts_delta": "DELTA",
    "ts_var": "TS_VAR",
    "ts_zscore": "TS_ZSCORE",
    "ts_pctchange": "TS_PCTCHANGE",
    "ts_median": "TS_MEDIAN",
    "ts_count": "COUNT",
    "greater": "GREATER",
    "less": "LESS",
    "abs": "ABS",
    "log": "LOG",
    "sign": "SIGN",
    "inv": "INV",
    "sqrt": "SQRT",
    "pow1": "POW",
}
CANONICAL_FIELDS = {"open", "high", "low", "close", "volume", "vwap", "return"}


def canonicalize_expression(expression: str) -> CanonicalExpression:
    """Normalize supported aliases into uppercase canonical DSL."""
    source = str(expression).strip()
    canonical = normalize_expression_syntax(source)
    warnings: list[str] = []
    for old, new in QLIB_ALIAS_MAP.items():
        canonical = re.sub(rf"\b{old}\s*\(", f"{new}(", canonical)
    for old, new in VNPY_ALIAS_MAP.items():
        if re.search(rf"\b{old}\s*\(", canonical):
            warnings.append(f"legacy vnpy local operator normalized: {old} -> {new}")
        canonical = re.sub(rf"\b{old}\s*\(", f"{new}(", canonical)
    for field in CANONICAL_FIELDS:
        canonical = re.sub(rf"(?<![\w$]){field}(?!\w)", f"${field}", canonical)
    canonical = re.sub(r"\s+", " ", canonical).strip()
    return CanonicalExpression(source=source, canonical=canonical, warnings=tuple(warnings))
