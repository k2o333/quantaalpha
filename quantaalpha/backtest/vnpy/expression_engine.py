"""Audited canonical-expression wrapper for the vnpy backend."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

import pandas as pd
import polars as pl

from .data_provider import VnpyMarketDataProvider
from quantaalpha.backtest.expression import (
    SharedPolarsExpressionKernel,
    UnsupportedExpressionError,
    canonicalize_expression,
)


ALLOWED_FUNCTIONS = {
    "ts_delay",
    "ts_mean",
    "ts_rank",
    "ts_sum",
    "ts_count",
    "ts_std",
    "ts_var",
    "ts_min",
    "ts_max",
    "ts_corr",
    "ts_delta",
    "cs_rank",
    "cs_mean",
    "cs_std",
    "log",
    "abs",
    "greater",
    "less",
    "quesval",
}
ALLOWED_NAMES = ALLOWED_FUNCTIONS | {"open", "high", "low", "close", "volume", "vwap", "return"}


@dataclass
class TranslationAudit:
    """单个表达式的翻译审计记录。"""

    factor_name: str
    original_expression: str
    canonical_expression: str
    vnpy_expression: str
    warnings: list[str]


class VnpyExpressionError(ValueError):
    """Vnpy expression lowering or execution failed."""

    def __init__(self, message: str, audit: TranslationAudit | None = None) -> None:
        super().__init__(message)
        self.audit = audit


class VnpyExpressionEngine:
    """把 canonical DSL 降低到 vnpy 表达式并恢复 `(datetime, instrument)` 输出。"""

    def __init__(self, market_frame: pd.DataFrame | pl.DataFrame, translation_mode: str = "shared_polars") -> None:
        if translation_mode not in {"shared_polars", "compat", "canonical_ast"}:
            raise ValueError(f"unsupported vnpy translation mode: {translation_mode}")
        self.translation_mode = translation_mode
        self.provider = VnpyMarketDataProvider(market_frame)
        self.vnpy_frame = self.provider.to_vnpy_frame()
        self.instrument_frame = self.provider.restore_instrument(self.vnpy_frame).drop("vt_symbol")
        self.kernel = SharedPolarsExpressionKernel(self.instrument_frame)
        self.audit: list[TranslationAudit] = []

    def compute(self, factor_defs: list[dict[str, Any]]) -> pd.DataFrame | pl.DataFrame:
        """计算多个因子，输出显式键列 DataFrame。"""
        if self.translation_mode == "shared_polars":
            frames: list[pl.DataFrame] = []
            for factor in factor_defs:
                name = str(factor.get("factor_name") or factor.get("factor_id"))
                expression = str(factor.get("factor_expression") or "")
                frames.append(self.compute_expression(expression, factor_name=name))
            if not frames:
                raise ValueError("vnpy factor_defs is empty")
            result = frames[0]
            for frame in frames[1:]:
                result = result.join(frame, on=["datetime", "instrument"], how="inner")
            return result.sort(["datetime", "instrument"])

        columns: list[pd.Series] = []
        for factor in factor_defs:
            name = str(factor.get("factor_name") or factor.get("factor_id"))
            expression = str(factor.get("factor_expression") or "")
            result = self.compute_expression(expression, factor_name=name)
            columns.append(result.iloc[:, 0].rename(name))
        if not columns:
            raise ValueError("vnpy factor_defs is empty")
        return pd.concat(columns, axis=1).sort_index()

    def compute_label(self, expression: str) -> pd.DataFrame | pl.DataFrame:
        """计算 label，返回 `LABEL0` 列。"""
        return self.compute_expression(expression, factor_name="LABEL0")

    def compute_expression(self, expression: str, factor_name: str) -> pd.DataFrame | pl.DataFrame:
        """计算单个 canonical 表达式。"""
        canonical = canonicalize_expression(expression)
        if self.translation_mode == "shared_polars":
            try:
                result = self.kernel.compute_expression_frame(canonical.canonical, factor_name)
            except UnsupportedExpressionError as exc:
                audit = TranslationAudit(
                    factor_name=factor_name,
                    original_expression=expression,
                    canonical_expression=canonical.canonical,
                    vnpy_expression="",
                    warnings=[*canonical.warnings, str(exc)],
                )
                self.audit.append(audit)
                raise VnpyExpressionError(f"unsupported shared polars expression for {factor_name}: {exc}", audit=audit) from exc
            audit = TranslationAudit(
                factor_name=factor_name,
                original_expression=expression,
                canonical_expression=canonical.canonical,
                vnpy_expression="",
                warnings=list(canonical.warnings),
            )
            self.audit.append(audit)
            return result

        vnpy_expression, warnings = self.translate(expression)
        audit = TranslationAudit(
            factor_name=factor_name,
            original_expression=expression,
            canonical_expression=canonical.canonical,
            vnpy_expression=vnpy_expression,
            warnings=warnings,
        )
        self.audit.append(audit)
        unsupported = [warning for warning in warnings if "不支持" in warning or "unsupported" in warning.lower()]
        if unsupported:
            raise VnpyExpressionError(f"unsupported vnpy expression for {factor_name}: {unsupported}", audit=audit)
        self._validate_expression(vnpy_expression, audit)
        _ensure_vnpy_on_path()
        from vnpy.alpha.dataset.utility import calculate_by_expression

        result = calculate_by_expression(self.vnpy_frame, vnpy_expression)
        restored = self.provider.restore_instrument(result)
        pdf = restored.select(["datetime", "instrument", "data"]).to_pandas().set_index(["datetime", "instrument"]).sort_index()
        pdf.columns = [factor_name]
        return pdf

    def translate(self, expression: str) -> tuple[str, list[str]]:
        """把 canonical/compat 表达式翻译为 vnpy 表达式。"""
        normalized = canonicalize_expression(expression).canonical
        if self.translation_mode == "canonical_ast":
            return normalized, []
        _ensure_glue_on_path()
        from expression_translator import ExpressionTranslator

        return ExpressionTranslator().translate(normalized)

    def _validate_expression(self, expression: str, audit: TranslationAudit) -> None:
        calls = set(re.findall(r"\b([A-Za-z_]\w*)\s*\(", expression))
        unsupported_calls = sorted(calls - ALLOWED_FUNCTIONS)
        names = set(re.findall(r"\b[A-Za-z_]\w*\b", expression))
        unsupported_names = sorted(name for name in names - ALLOWED_NAMES if not name.isupper())
        if unsupported_calls or unsupported_names:
            raise VnpyExpressionError(
                f"vnpy expression uses unsupported tokens: functions={unsupported_calls}, names={unsupported_names}",
                audit=audit,
            )


def _ensure_glue_on_path() -> None:
    from pathlib import Path
    import sys

    glue_root = Path(__file__).resolve().parents[4] / "glue"
    if str(glue_root) not in sys.path:
        sys.path.insert(0, str(glue_root))


def _ensure_vnpy_on_path() -> None:
    from pathlib import Path
    import sys

    vnpy_root = Path(__file__).resolve().parents[4] / "vnpy"
    if str(vnpy_root) not in sys.path:
        sys.path.insert(0, str(vnpy_root))
