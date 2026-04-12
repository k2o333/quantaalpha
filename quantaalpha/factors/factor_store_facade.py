"""
FactorStoreFacade - 统一因子存储入口

职责:
- 封装 ParquetFactorLibrary 的读写操作
- 提供稳定的业务 API
- 不做业务逻辑（如 check_redundancy、select_revalidation_candidates）

设计原则:
- append-only 事件模型，不修改老记录
- compact 只合并文件，不承担"修改老记录"语义
"""

from pathlib import Path
from datetime import datetime, timezone
import json
from typing import Any, List

import pandas as pd

from quantaalpha.factors.parquet_library import ParquetFactorLibrary, REQUIRED_COLUMNS
from quantaalpha.factors.status_rules import update_factor_status


class FactorStoreFacade:
    """统一因子存储入口，向业务层提供稳定 API"""

    def __init__(self, store_path: str | Path):
        """初始化 FactorStoreFacade

        Args:
            store_path: Parquet store 根目录的绝对或相对路径
        """
        self.store_path = Path(store_path)
        self._parquet = ParquetFactorLibrary(str(self.store_path))

    def write_factor(self, entry: dict) -> None:
        """写入单个因子到 delta 目录

        Args:
            entry: 因子 entry dict，包含 required schema 的所有字段
        """
        self._parquet.write_factor_delta(entry)

    def write_status_update(
        self,
        factor_entry: dict[str, Any],
        validation_result: dict[str, Any],
        *,
        sequence: int | None = None,
    ) -> dict[str, Any]:
        """Append a validation status update event for one factor.

        Returns the legacy-shaped updated entry so callers can keep existing status logic.
        """
        legacy_entry = self._legacy_entry_from_record(factor_entry)
        updated = update_factor_status(legacy_entry, validation_result)
        event = self._parquet_event_from_legacy_entry(
            updated,
            source_record=factor_entry,
            op="upsert",
            sequence=sequence,
            backtest_results=validation_result,
        )
        self.write_factor(event)
        return updated

    def delete_factor(self, factor_id: str, *, sequence: int | None = None) -> None:
        """Append a tombstone event for a factor by factor_id."""
        records = self.read_effective_factor_records()
        record = next((r for r in records if r.get("factor_id") == factor_id), None)
        if record is None:
            raise KeyError(f"factor_id not found: {factor_id}")
        legacy_entry = self._legacy_entry_from_record(record)
        event = self._parquet_event_from_legacy_entry(
            legacy_entry,
            source_record=record,
            op="delete",
            sequence=sequence,
        )
        self.write_factor(event)

    def read_effective_factors(self) -> pd.DataFrame:
        """读取有效因子列表（compacted + delta，已去重）

        Returns:
            pandas DataFrame，包含所有有效因子记录
        """
        df = self._parquet.read_factor_library()
        if df is None or df.is_empty():
            return pd.DataFrame(columns=REQUIRED_COLUMNS)
        return df.to_pandas()

    def read_effective_factor_records(self) -> list[dict]:
        """读取有效因子记录列表

        Returns:
            list of dict，每个 dict 代表一条因子记录
        """
        return self.read_effective_factors().to_dict("records")

    def as_legacy_library(self) -> dict[str, Any]:
        """Return effective Parquet factors in the legacy JSON-library shape."""
        factors = {}
        for record in self.read_effective_factor_records():
            legacy = self._legacy_entry_from_record(record)
            factors[legacy["factor_id"]] = legacy
        return {"metadata": {"version": "parquet-facade"}, "factors": factors}

    def to_factor_zoo_frame(self) -> pd.DataFrame:
        """返回因子动物园视图（factor_name, factor_expression）

        Returns:
            pandas DataFrame，仅包含 factor_name 和 factor_expression 列
        """
        df = self.read_effective_factors()
        if "factor_name" not in df.columns or "factor_expression" not in df.columns:
            return pd.DataFrame(columns=["factor_name", "factor_expression"])
        return df[["factor_name", "factor_expression"]].copy()

    def delta_file_count(self) -> int:
        """返回 delta 目录中的 parquet 文件数量

        Returns:
            delta 目录中的 .parquet 文件数
        """
        delta_dir = self.store_path / "delta"
        if not delta_dir.exists():
            return 0
        return len(list(delta_dir.glob("*.parquet")))

    def compact(self, *, archive_retention: int | None = None) -> None:
        """执行 compact 操作，合并 delta 到 compacted"""
        before_count = self.delta_file_count()
        if before_count == 0:
            return
        self._parquet.compact(archive_retention=archive_retention)

    @staticmethod
    def _next_sequence() -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1_000_000)

    @staticmethod
    def _loads_json(value: Any, default: Any) -> Any:
        if isinstance(value, (dict, list)):
            return value
        if not value:
            return default
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return default

    def _legacy_entry_from_record(self, record: dict[str, Any]) -> dict[str, Any]:
        """Convert a Parquet row/event into the legacy nested factor entry shape."""
        if "evaluation" in record:
            return dict(record)

        metadata = self._loads_json(record.get("metadata_json"), {})
        backtest_results = self._loads_json(record.get("backtest_results_json"), {})
        tags = self._loads_json(record.get("tags_json"), {})
        if isinstance(tags, list):
            tags = {}
        status = record.get("evaluation_status") or "pending_validation"

        return {
            "factor_id": record.get("factor_id", ""),
            "factor_name": record.get("factor_name", ""),
            "factor_expression": record.get("factor_expression", ""),
            "factor_expression_normalized": record.get("factor_expression_normalized", record.get("factor_expression", "")),
            "factor_description": metadata.get("factor_description", ""),
            "metadata": metadata,
            "tags": tags,
            "backtest_results": backtest_results,
            "evaluation": {
                "status": status,
                "last_validated": metadata.get("last_validated"),
                "stability_score": metadata.get("stability_score"),
                "period_results": metadata.get("period_results", []),
                "validation_summary": metadata.get("validation_summary", ""),
                "consecutive_failures": metadata.get("consecutive_failures", 0),
            },
        }

    def _parquet_event_from_legacy_entry(
        self,
        legacy_entry: dict[str, Any],
        *,
        source_record: dict[str, Any],
        op: str,
        sequence: int | None = None,
        backtest_results: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now_iso = datetime.now().isoformat()
        metadata = dict(source_record.get("metadata", {}) or {})
        metadata.update(self._loads_json(source_record.get("metadata_json"), {}))
        metadata.update(legacy_entry.get("metadata", {}) or {})
        evaluation = legacy_entry.get("evaluation", {}) or {}
        metadata.update(
            {
                "last_validated": evaluation.get("last_validated"),
                "stability_score": evaluation.get("stability_score"),
                "period_results": evaluation.get("period_results", []),
                "validation_summary": evaluation.get("validation_summary", ""),
                "consecutive_failures": evaluation.get("consecutive_failures", 0),
            }
        )

        tags = legacy_entry.get("tags", self._loads_json(source_record.get("tags_json"), {}))
        results = backtest_results if backtest_results is not None else legacy_entry.get("backtest_results", {})
        factor_expression = legacy_entry.get("factor_expression", source_record.get("factor_expression", ""))

        return {
            "factor_id": legacy_entry.get("factor_id", source_record.get("factor_id", "")),
            "factor_name": legacy_entry.get("factor_name", source_record.get("factor_name", "")),
            "factor_expression": factor_expression,
            "factor_expression_normalized": legacy_entry.get(
                "factor_expression_normalized",
                source_record.get("factor_expression_normalized", factor_expression),
            ),
            "expression_hash": source_record.get("expression_hash") or legacy_entry.get("expression_hash", ""),
            "evaluation_status": evaluation.get("status", source_record.get("evaluation_status", "pending_validation")),
            "created_at": source_record.get("created_at") or now_iso,
            "updated_at": now_iso,
            "sequence": int(sequence if sequence is not None else max(int(source_record.get("sequence", 0) or 0) + 1, self._next_sequence())),
            "op": op,
            "tags_json": json.dumps(tags or {}, ensure_ascii=False),
            "metadata_json": json.dumps(metadata or {}, ensure_ascii=False),
            "backtest_results_json": json.dumps(results or {}, ensure_ascii=False),
        }
