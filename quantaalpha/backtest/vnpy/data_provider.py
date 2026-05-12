"""Vnpy backend market data projection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd
import polars as pl


@dataclass(frozen=True)
class VnpySymbolMapping:
    """可逆的 instrument / vt_symbol 投影结果。"""

    instrument: str
    vt_symbol: str


class VnpyMarketDataProvider:
    """把 App5/no-qlib 标准 frame 显式投影为 vnpy schema。"""

    REQUIRED_COLUMNS = {"datetime", "instrument", "open", "high", "low", "close", "volume"}
    OPTIONAL_COLUMNS = {"vwap", "return"}
    DOLLAR_RENAME = {
        "$open": "open",
        "$high": "high",
        "$low": "low",
        "$close": "close",
        "$volume": "volume",
        "$vwap": "vwap",
        "$return": "return",
    }

    def __init__(self, market_frame: pd.DataFrame | pl.DataFrame) -> None:
        self.market_frame = market_frame
        self.mapping: dict[str, str] = {}

    def to_vnpy_frame(self) -> pl.DataFrame:
        """返回 `datetime, vt_symbol, ...` 的 vnpy long frame。"""
        frame = self._to_polars(self.market_frame)
        frame = self._normalize_columns(frame)
        missing = sorted(self.REQUIRED_COLUMNS - set(frame.columns))
        if missing:
            raise ValueError(f"vnpy market data missing columns: {missing}")
        if "vwap" not in frame.columns:
            frame = frame.with_columns(pl.col("close").cast(pl.Float64).alias("vwap"))
        if "return" not in frame.columns:
            frame = frame.sort(["instrument", "datetime"]).with_columns(
                (pl.col("close").cast(pl.Float64) / pl.col("close").cast(pl.Float64).shift(1).over("instrument") - 1.0)
                .fill_null(0.0)
                .alias("return")
            )
        instruments = sorted(str(value) for value in frame.get_column("instrument").unique().to_list())
        self.mapping = {instrument: self._to_vt_symbol(instrument) for instrument in instruments}
        return (
            frame.with_columns(
                pl.col("instrument").cast(pl.Utf8).replace(self.mapping).alias("vt_symbol"),
                pl.col("datetime").cast(pl.Datetime).alias("datetime"),
                pl.col("open").cast(pl.Float64),
                pl.col("high").cast(pl.Float64),
                pl.col("low").cast(pl.Float64),
                pl.col("close").cast(pl.Float64),
                pl.col("volume").cast(pl.Float64),
                pl.col("vwap").cast(pl.Float64),
                pl.col("return").cast(pl.Float64),
            )
            .select(["datetime", "vt_symbol", "open", "high", "low", "close", "volume", "vwap", "return"])
            .sort(["datetime", "vt_symbol"])
        )

    def restore_instrument(self, frame: pl.DataFrame) -> pl.DataFrame:
        """把 vnpy frame 的 `vt_symbol` 恢复为全仓 `instrument`。"""
        reverse = {vt_symbol: instrument for instrument, vt_symbol in self.mapping.items()}
        if "vt_symbol" not in frame.columns:
            raise ValueError("vnpy frame missing vt_symbol column")
        return frame.with_columns(pl.col("vt_symbol").cast(pl.Utf8).replace(reverse).alias("instrument"))

    def mapping_rows(self) -> list[VnpySymbolMapping]:
        """返回可审计的映射列表。"""
        return [VnpySymbolMapping(instrument=k, vt_symbol=v) for k, v in sorted(self.mapping.items())]

    def _to_polars(self, frame: pd.DataFrame | pl.DataFrame) -> pl.DataFrame:
        if isinstance(frame, pl.DataFrame):
            return frame.clone()
        if isinstance(frame.index, pd.MultiIndex):
            frame = frame.reset_index()
        return pl.from_pandas(frame)

    def _normalize_columns(self, frame: pl.DataFrame) -> pl.DataFrame:
        rename_map: dict[str, str] = {}
        for old, new in self.DOLLAR_RENAME.items():
            if old in frame.columns and new not in frame.columns:
                rename_map[old] = new
        if "trade_date" in frame.columns and "datetime" not in frame.columns:
            rename_map["trade_date"] = "datetime"
        if "date" in frame.columns and "datetime" not in frame.columns:
            rename_map["date"] = "datetime"
        if "ts_code" in frame.columns and "instrument" not in frame.columns:
            rename_map["ts_code"] = "instrument"
        if "vol" in frame.columns and "volume" not in frame.columns:
            rename_map["vol"] = "volume"
        return frame.rename(rename_map) if rename_map else frame

    def _to_vt_symbol(self, instrument: str) -> str:
        if "." in instrument:
            code, exchange = instrument.split(".", 1)
            return f"{code}.{exchange.upper()}"
        return f"{instrument}.LOCAL"
