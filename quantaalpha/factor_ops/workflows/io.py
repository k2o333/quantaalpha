"""factor_ops 工作流 IO 边界。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import polars as pl


def load_registry_frame(path: str | Path) -> pl.DataFrame:
    """读取 JSON 或 Parquet 因子 registry 为 Polars DataFrame。"""
    source = Path(path)
    if source.is_dir():
        from quantaalpha.factors.factor_store_facade import FactorStoreFacade

        return pl.from_pandas(FactorStoreFacade(source).read_effective_factors())
    if source.suffix == ".parquet":
        return pl.read_parquet(source)
    data = json.loads(source.read_text(encoding="utf-8"))
    if isinstance(data, list):
        records = data
    else:
        factors = data.get("factors", {}) if isinstance(data, dict) else {}
        records = []
        for factor_id, entry in factors.items():
            record = dict(entry or {})
            record.setdefault("factor_id", factor_id)
            metadata = record.pop("metadata", record.get("metadata_json", {})) or {}
            if isinstance(metadata, str):
                metadata_json = metadata
            else:
                metadata_json = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
            record["metadata_json"] = metadata_json
            record.setdefault("factor_name", factor_id)
            record.setdefault("factor_expression", "")
            record.setdefault("evaluation_status", "")
            record.setdefault("sequence", 0)
            record.setdefault("op", "upsert")
            records.append(record)
    return pl.DataFrame(records) if records else pl.DataFrame()


def load_factor_values(path: str | Path) -> pl.DataFrame:
    """使用 Polars 读取因子值 Parquet。"""
    return pl.read_parquet(Path(path))


def load_returns(path: str | Path) -> pl.DataFrame:
    """使用 Polars 读取收益 Parquet。"""
    return pl.read_parquet(Path(path))


def load_regime_labels(path: str | Path) -> pl.DataFrame:
    """使用 Polars 读取 regime 标签 Parquet。"""
    return pl.read_parquet(Path(path))


def write_json_report(
    payload: dict[str, Any],
    output: str | Path | None,
    *,
    dry_run: bool = False,
    no_write: bool = False,
) -> dict[str, Any]:
    """写 JSON 报告；dry-run/no-write 时只返回 payload。"""
    result = dict(payload)
    if dry_run or no_write or output is None:
        result["written"] = False
        return result
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result["written"] = True
    result["output"] = str(target)
    return result


def write_markdown_report(
    payload: dict[str, Any],
    output: str | Path | None,
    *,
    dry_run: bool = False,
    no_write: bool = False,
) -> dict[str, Any]:
    """写 Markdown 报告；dry-run/no-write 时只返回 payload。"""
    result = dict(payload)
    if dry_run or no_write or output is None:
        result["written"] = False
        return result
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown_from_payload(payload), encoding="utf-8")
    result["written"] = True
    result["output"] = str(target)
    return result


def markdown_from_payload(payload: dict[str, Any]) -> str:
    """把结构化报告转换为简洁 Markdown。"""
    title = payload.get("title") or "Factor Ops Report"
    lines = [f"# {title}", ""]
    for key, value in payload.items():
        if key in {"title", "success", "written", "output"}:
            continue
        lines.append(f"## {key}")
        if isinstance(value, (dict, list)):
            lines.append("```json")
            lines.append(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))
            lines.append("```")
        else:
            lines.append(str(value))
        lines.append("")
    return "\n".join(lines)


def normalize_factor_values(df: pl.DataFrame, factor_id: str) -> pl.DataFrame:
    """把指定因子列标准化为 `factor_value`。"""
    if "factor_value" in df.columns:
        return df.select(["date", "stock_id", "factor_value"])
    if factor_id not in df.columns:
        raise ValueError(f"missing factor value column: {factor_id}")
    return df.select(["date", "stock_id", factor_id]).rename({factor_id: "factor_value"})


def factor_column_frame(df: pl.DataFrame, factor_id: str) -> pl.DataFrame:
    """返回包含指定因子列的 DataFrame。"""
    if factor_id in df.columns:
        return df.select(["date", "stock_id", factor_id])
    if "factor_value" in df.columns:
        return df.select(["date", "stock_id", "factor_value"]).rename({"factor_value": factor_id})
    raise ValueError(f"missing factor value column: {factor_id}")


def load_factor_records(path: str | Path) -> list[dict[str, Any]]:
    """读取 registry records。"""
    return load_registry_frame(path).to_dicts()
