"""No-qlib 日频市场数据读取与标准化。"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any

import pandas as pd
import polars as pl


class NoQlibMarketDataProvider:
    """从显式文件或 app5 adapter 读取日频价量数据。"""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        runtime = config.get("backtest_runtime", {})
        self.noqlib_config = runtime.get("noqlib", {})
        self._explicit_market_path = bool(self.noqlib_config.get("market_data_path"))

    def load_market_data(self) -> pd.DataFrame:
        """返回 qlib 风格 `(datetime, instrument)` MultiIndex DataFrame。"""
        frame = self._load_polars_frame()
        if frame.is_empty():
            raise ValueError("noqlib market data is empty")
        frame = self._normalize_frame(frame)
        return frame.to_pandas().set_index(["datetime", "instrument"]).sort_index()

    def _load_polars_frame(self) -> pl.DataFrame:
        path = self.noqlib_config.get("market_data_path")
        if path:
            return self._read_path(Path(path))

        data_cfg = self.config.get("data", {})
        start_time = data_cfg.get("start_time")
        end_time = data_cfg.get("end_time")
        storage_root = self.noqlib_config.get("app5_storage_root", "data")
        interface_name = self.noqlib_config.get("daily_interface", "daily")
        _ensure_project_root_on_path(self.noqlib_config)
        try:
            from training.adapter.app5_parquet_adapter import App5ParquetAdapter
        except Exception as exc:  # pragma: no cover - environment guard
            raise RuntimeError("App5ParquetAdapter is required for noqlib app5 reads") from exc
        adapter = App5ParquetAdapter(storage_root=storage_root)
        return adapter.read(interface_name, start_date=start_time, end_date=end_time)

    def _read_path(self, path: Path) -> pl.DataFrame:
        if not path.exists():
            raise FileNotFoundError(f"noqlib market_data_path not found: {path}")
        if path.suffix.lower() == ".csv":
            return pl.read_csv(path)
        return pl.read_parquet(path)

    def _normalize_frame(self, frame: pl.DataFrame) -> pl.DataFrame:
        rename_map = {
            "ts_code": "instrument",
            "trade_date": "datetime",
            "date": "datetime",
            "vol": "volume",
            "$open": "open",
            "$high": "high",
            "$low": "low",
            "$close": "close",
            "$volume": "volume",
            "$vwap": "vwap",
        }
        for old, new in rename_map.items():
            if old in frame.columns and new not in frame.columns:
                frame = frame.rename({old: new})
        instruments = self.noqlib_config.get("instruments")
        if instruments:
            keep = [str(item) for item in instruments]
            keep.extend(str(item) for item in self.noqlib_config.get("benchmark_instruments", []))
            frame = frame.filter(pl.col("instrument").cast(pl.Utf8).is_in(keep))
        required = {"datetime", "instrument", "open", "high", "low", "close"}
        missing = sorted(required - set(frame.columns))
        if missing:
            raise ValueError(f"noqlib market data missing columns: {missing}")
        if "volume" not in frame.columns:
            frame = frame.with_columns(pl.lit(0.0).alias("volume"))
        if "amount" not in frame.columns:
            frame = frame.with_columns(pl.lit(None).cast(pl.Float64).alias("amount"))
        if "vwap" not in frame.columns:
            multiplier = self._amount_to_vwap_multiplier()
            frame = frame.with_columns(
                pl.when(pl.col("volume").cast(pl.Float64) > 0)
                .then(pl.col("amount").cast(pl.Float64) * multiplier / pl.col("volume").cast(pl.Float64))
                .otherwise(pl.col("close").cast(pl.Float64))
                .alias("vwap")
            )
        if "pct_chg" in frame.columns:
            pct = pl.col("pct_chg").cast(pl.Float64).fill_null(0.0)
            ret_expr = pl.when(pct.abs() > 1.0).then(pct / 100.0).otherwise(pct)
        elif "$return" in frame.columns:
            ret_expr = pl.col("$return").cast(pl.Float64).fill_null(0.0)
        else:
            ret_expr = (
                pl.col("close").cast(pl.Float64) / pl.col("close").cast(pl.Float64).shift(1).over("instrument") - 1.0
            ).fill_null(0.0)
        datetime_expr = _datetime_expr(frame)
        return (
            frame.with_columns(
                pl.col("instrument").cast(pl.Utf8),
                ret_expr.alias("$return"),
            )
            .with_columns(
                datetime_expr.alias("datetime"),
                pl.col("open").cast(pl.Float64).alias("$open"),
                pl.col("high").cast(pl.Float64).alias("$high"),
                pl.col("low").cast(pl.Float64).alias("$low"),
                pl.col("close").cast(pl.Float64).alias("$close"),
                pl.col("volume").cast(pl.Float64).alias("$volume"),
                pl.col("vwap").cast(pl.Float64).alias("$vwap"),
            )
            .select(["datetime", "instrument", "$open", "$high", "$low", "$close", "$volume", "$vwap", "$return"])
            .sort(["datetime", "instrument"])
        )

    def _amount_to_vwap_multiplier(self) -> float:
        if "amount_to_vwap_multiplier" in self.noqlib_config:
            return float(self.noqlib_config["amount_to_vwap_multiplier"])
        return 1.0 if self._explicit_market_path else 10.0


def _ensure_project_root_on_path(noqlib_config: dict[str, Any]) -> None:
    configured = noqlib_config.get("project_root")
    candidates = []
    if configured:
        candidates.append(Path(configured))
    candidates.append(Path(__file__).resolve().parents[5])
    for candidate in candidates:
        if (candidate / "training").exists() and str(candidate) not in sys.path:
            sys.path.insert(0, str(candidate))
            return


def _datetime_expr(frame: pl.DataFrame) -> pl.Expr:
    dtype = frame.schema.get("datetime")
    if dtype in (pl.Date, pl.Datetime, pl.Datetime("ns"), pl.Datetime("us"), pl.Datetime("ms")):
        return pl.col("datetime").cast(pl.Date)
    return (
        pl.col("datetime")
        .cast(pl.Utf8)
        .str.replace_all(r"\D", "")
        .str.slice(0, 8)
        .str.strptime(pl.Date, "%Y%m%d", strict=False)
    )
