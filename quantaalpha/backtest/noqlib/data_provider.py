"""No-qlib 日频市场数据读取与标准化。"""

from __future__ import annotations

from pathlib import Path
import re
import sys
from typing import Any

import numpy as np
import pandas as pd
import polars as pl

from quantaalpha.backtest.contracts import validate_standard_frame_columns


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
        standard_frame_cfg = self.noqlib_config.get("standard_frame")
        if standard_frame_cfg:
            from quantaalpha.backtest.standard_frame import App5StandardFrameBuilder, request_from_mapping

            payload = dict(standard_frame_cfg)
            payload.setdefault("start_date", self.config.get("data", {}).get("start_time"))
            payload.setdefault("end_date", self.config.get("data", {}).get("end_time"))
            payload.setdefault("storage_root", self.noqlib_config.get("app5_storage_root", "data"))
            result = App5StandardFrameBuilder(storage_root=payload["storage_root"]).build(request_from_mapping(payload))
            return result.frame

        data_cfg = self.config.get("data", {})
        start_time = data_cfg.get("start_time")
        end_time = _app5_read_end_time(data_cfg.get("end_time"), self.config, self.noqlib_config)
        storage_root = self.noqlib_config.get("app5_storage_root", "data")
        interface_name = self.noqlib_config.get("daily_interface", "daily")
        _ensure_project_root_on_path(self.noqlib_config)
        try:
            from training.adapter.app5_parquet_adapter import App5ParquetAdapter
        except Exception as exc:  # pragma: no cover - environment guard
            raise RuntimeError("App5ParquetAdapter is required for noqlib app5 reads") from exc
        adapter = App5ParquetAdapter(storage_root=storage_root)
        frame = adapter.read(interface_name, start_date=start_time, end_date=end_time)
        benchmark_frame = self._read_qlib_bin_benchmark(start_time=start_time, end_time=end_time)
        if benchmark_frame is not None and not benchmark_frame.is_empty():
            frame = pl.concat([frame, benchmark_frame], how="diagonal_relaxed")
        return frame

    def _read_path(self, path: Path) -> pl.DataFrame:
        if not path.exists():
            raise FileNotFoundError(f"noqlib market_data_path not found: {path}")
        if path.suffix.lower() == ".csv":
            return pl.read_csv(path)
        return pl.read_parquet(path)

    def _normalize_frame(self, frame: pl.DataFrame) -> pl.DataFrame:
        if "ts_code" in frame.columns and "instrument" in frame.columns:
            frame = frame.with_columns(
                pl.coalesce([pl.col("instrument").cast(pl.Utf8), pl.col("ts_code").cast(pl.Utf8)]).alias("instrument")
            )
        if "trade_date" in frame.columns and "datetime" in frame.columns:
            frame = frame.with_columns(
                pl.coalesce([pl.col("datetime").cast(pl.Utf8), pl.col("trade_date").cast(pl.Utf8)]).alias("datetime")
            )
        if "vol" in frame.columns and "volume" in frame.columns:
            frame = frame.with_columns(
                pl.coalesce([pl.col("volume").cast(pl.Float64), pl.col("vol").cast(pl.Float64)]).alias("volume")
            )
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
        instruments = _resolve_config_instruments(self.noqlib_config)
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
        multiplier = self._amount_to_vwap_multiplier()
        vwap_fallback = (
            pl.when(pl.col("volume").cast(pl.Float64) > 0)
            .then(pl.col("amount").cast(pl.Float64) * multiplier / pl.col("volume").cast(pl.Float64))
            .otherwise(pl.col("close").cast(pl.Float64))
        )
        if "vwap" not in frame.columns:
            frame = frame.with_columns(
                vwap_fallback.alias("vwap")
            )
        else:
            frame = frame.with_columns(
                pl.coalesce([pl.col("vwap").cast(pl.Float64), vwap_fallback]).alias("vwap")
            )
        if "$return" in frame.columns and "pct_chg" in frame.columns:
            pct = pl.col("pct_chg").cast(pl.Float64)
            pct_ret = pl.when(pct.abs() > 1.0).then(pct / 100.0).otherwise(pct)
            ret_expr = pl.coalesce([pl.col("$return").cast(pl.Float64), pct_ret, pl.lit(0.0)])
        elif "pct_chg" in frame.columns:
            pct = pl.col("pct_chg").cast(pl.Float64).fill_null(0.0)
            ret_expr = pl.when(pct.abs() > 1.0).then(pct / 100.0).otherwise(pct)
        elif "$return" in frame.columns:
            ret_expr = pl.col("$return").cast(pl.Float64).fill_null(0.0)
        else:
            ret_expr = (
                pl.col("close").cast(pl.Float64) / pl.col("close").cast(pl.Float64).shift(1).over("instrument") - 1.0
            ).fill_null(0.0)
        datetime_expr = _datetime_expr(frame)
        normalized = (
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
        validate_standard_frame_columns(normalized.columns)
        return normalized

    def _amount_to_vwap_multiplier(self) -> float:
        if "amount_to_vwap_multiplier" in self.noqlib_config:
            return float(self.noqlib_config["amount_to_vwap_multiplier"])
        return 1.0 if self._explicit_market_path else 10.0

    def _read_qlib_bin_benchmark(self, *, start_time: str | None, end_time: str | None) -> pl.DataFrame | None:
        """Read benchmark rows from local qlib bin files without importing qlib."""
        provider_uri = self.noqlib_config.get("qlib_provider_uri")
        benchmark_instruments = [str(item) for item in self.noqlib_config.get("benchmark_instruments", [])]
        if not provider_uri or not benchmark_instruments:
            return None
        provider = Path(str(provider_uri)).expanduser()
        calendar_path = provider / "calendars" / "day.txt"
        features_root = provider / "features"
        if not calendar_path.exists() or not features_root.exists():
            raise FileNotFoundError(f"noqlib qlib_provider_uri is not a qlib bin directory: {provider}")
        calendar = [pd.Timestamp(line.strip()) for line in calendar_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        rows: list[dict[str, Any]] = []
        start_ts = pd.Timestamp(start_time) if start_time else None
        end_ts = pd.Timestamp(end_time) if end_time else None
        for instrument in benchmark_instruments:
            qlib_code = _qlib_bin_instrument_dir(instrument)
            inst_dir = features_root / qlib_code
            if not inst_dir.exists():
                continue
            series_by_field = {
                field: _read_qlib_bin_series(inst_dir / f"{field}.day.bin", calendar)
                for field in ("open", "high", "low", "close", "volume", "return")
            }
            if not series_by_field["close"]:
                continue
            for idx, dt in enumerate(calendar):
                if start_ts is not None and dt < start_ts:
                    continue
                if end_ts is not None and dt > end_ts:
                    continue
                close = series_by_field["close"].get(idx)
                if close is None or not np.isfinite(close):
                    continue
                rows.append(
                    {
                        "datetime": dt.date(),
                        "instrument": instrument,
                        "open": series_by_field["open"].get(idx, close),
                        "high": series_by_field["high"].get(idx, close),
                        "low": series_by_field["low"].get(idx, close),
                        "close": close,
                        "volume": series_by_field["volume"].get(idx, 0.0),
                        "$return": series_by_field["return"].get(idx, 0.0),
                        "vwap": close,
                    }
                )
        return pl.DataFrame(rows) if rows else None


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


def _resolve_config_instruments(noqlib_config: dict[str, Any]) -> list[str]:
    instruments = noqlib_config.get("instruments")
    if instruments:
        return [str(item) for item in instruments]
    instruments_path = noqlib_config.get("instruments_path")
    if instruments_path:
        path = Path(str(instruments_path)).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"noqlib instruments_path not found: {path}")
        values: list[str] = []
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            values.append(line.split()[0])
        return sorted(set(values))
    universe_path = noqlib_config.get("resolved_universe_path")
    if not universe_path:
        return []
    frame = pl.read_parquet(universe_path)
    if "selected" in frame.columns:
        frame = frame.filter(pl.col("selected"))
    elif "eligible" in frame.columns:
        frame = frame.filter(pl.col("eligible"))
    if "instrument" not in frame.columns:
        raise ValueError("resolved_universe_path must contain an instrument column")
    return sorted(str(value) for value in frame.get_column("instrument").unique().to_list())


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


def _app5_read_end_time(end_time: str | None, config: dict[str, Any], noqlib_config: dict[str, Any]) -> str | None:
    if not end_time:
        return end_time
    if "market_end_time" in noqlib_config:
        return str(noqlib_config["market_end_time"])
    calendar_days = noqlib_config.get("label_lookahead_calendar_days")
    if calendar_days is None:
        max_ref = _max_future_ref(config.get("dataset", {}).get("label", ""))
        calendar_days = max(10, max_ref * 4) if max_ref else 0
    calendar_days = int(calendar_days)
    if calendar_days <= 0:
        return end_time
    return (pd.Timestamp(end_time) + pd.Timedelta(days=calendar_days)).strftime("%Y-%m-%d")


def _max_future_ref(expression: str) -> int:
    values = [int(item) for item in re.findall(r"\bRef\s*\([^,]+,\s*-([0-9]+)\s*\)", str(expression))]
    return max(values) if values else 0


def _qlib_bin_instrument_dir(instrument: str) -> str:
    text = str(instrument)
    upper = text.upper()
    if upper.startswith("SH") and upper[2:].isdigit():
        return "sh" + upper[2:]
    if upper.startswith("SZ") and upper[2:].isdigit():
        return "sz" + upper[2:]
    if upper.endswith(".SH"):
        return upper[:-3].lower() + ".sh"
    if upper.endswith(".SZ"):
        return upper[:-3].lower() + ".sz"
    return text.lower()


def _read_qlib_bin_series(path: Path, calendar: list[pd.Timestamp]) -> dict[int, float]:
    if not path.exists():
        return {}
    values = np.fromfile(path, dtype="<f4")
    if len(values) == 0:
        return {}
    start_index = int(values[0])
    result = {}
    for offset, value in enumerate(values[1:]):
        idx = start_index + offset
        if idx >= len(calendar):
            break
        result[idx] = float(value)
    return result
