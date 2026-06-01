"""Standard-frame 上游 App5 数据契约校验。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import polars as pl


def validate_open_market_source_coverage(
    frame: pl.DataFrame,
    calendar: pl.DataFrame,
    *,
    interface: str,
) -> None:
    """拒绝被误解释为全市场停牌的开放交易日缺口。"""
    if calendar.is_empty():
        return
    source_dates = frame.select("datetime").drop_nulls().unique()
    missing = calendar.join(source_dates, on="datetime", how="anti").sort("datetime")
    if missing.height:
        sample = [str(item) for item in missing.get_column("datetime").head(10).to_list()]
        raise ValueError(
            f"open-market dates missing from standard frame source: "
            f"interface={interface} missing_dates={missing.height} sample={sample}"
        )


def validate_tradable_core_prices(
    frame: pl.DataFrame,
    *,
    interface: str,
    adjustment: str,
) -> None:
    """拒绝有成交量但核心价格为空或非有限值的源记录。"""
    core_columns = ("$open", "$high", "$low", "$close")
    invalid_core = pl.any_horizontal(
        [
            pl.col(column).cast(pl.Float64, strict=False).fill_nan(None).is_null()
            | ~pl.col(column).cast(pl.Float64, strict=False).fill_nan(None).is_finite()
            for column in core_columns
        ]
    )
    tradable = pl.col("$volume").cast(pl.Float64, strict=False).fill_nan(None).fill_null(0.0) > 0.0
    invalid_rows = frame.filter(tradable & invalid_core)
    if invalid_rows.height:
        sample = invalid_rows.select("datetime", "instrument", "$volume", *core_columns).head(5).to_dicts()
        raise ValueError(
            f"tradable standard frame source rows have missing core prices: "
            f"interface={interface} adjustment={adjustment} invalid_rows={invalid_rows.height} sample={sample}"
        )


def source_interfaces_for_request(request: Any) -> tuple[str, ...]:
    """列出标准帧物化依赖的 App5 接口。"""
    interfaces = [str(request.daily_interface), "trade_cal"]
    interfaces.extend(str(field.source_interface) for field in request.optional_fields)
    interfaces.extend(str(field.source_interface) for field in request.admitted_fields)
    return tuple(dict.fromkeys(interfaces))


def source_manifest_fingerprints(storage_root: str | Path, interfaces: Iterable[str]) -> dict[str, dict[str, str]]:
    """计算 App5 active manifest 指纹，供缓存身份和审计使用。"""
    root = Path(storage_root)
    result: dict[str, dict[str, str]] = {}
    for interface in dict.fromkeys(str(item) for item in interfaces):
        path = root / interface / "manifest" / "current.json"
        if not path.exists():
            result[interface] = {"status": "missing"}
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        result[interface] = {
            "status": "active",
            "sha256": "sha256:" + hashlib.sha256(encoded).hexdigest(),
        }
    return result


def source_bound_cache_identity(request_hash: str, fingerprints: dict[str, dict[str, str]]) -> str:
    """将请求身份与 active source manifest 共同绑定为物化缓存身份。"""
    payload = {"request_hash": request_hash, "source_manifest_fingerprints": fingerprints}
    encoded = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
