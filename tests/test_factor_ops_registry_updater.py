from __future__ import annotations

import json

from quantaalpha.factor_ops.lifecycle.log_writer import LifecycleLogReader
from quantaalpha.factor_ops.registry.updater import RegistryUpdater, RegistryUpdateResult


class _FakeStore:
    def __init__(self) -> None:
        self.records = [
            {
                "factor_id": "factor_001",
                "factor_name": "value",
                "factor_expression": "close / open",
                "factor_expression_normalized": "close/open",
                "expression_hash": "abc",
                "evaluation_status": "active",
                "created_at": "2026-05-01T00:00:00",
                "updated_at": "2026-05-01T00:00:00",
                "sequence": 10,
                "op": "upsert",
                "tags_json": "{}",
                "metadata_json": json.dumps({"ops": {"status": "candidate", "tier": "C", "version": 3}}),
                "backtest_results_json": "{}",
            }
        ]
        self.writes: list[dict] = []

    def read_effective_factor_records(self) -> list[dict]:
        return self.records

    def write_factor(self, event: dict) -> None:
        self.writes.append(event)


def test_registry_updater_updates_ops_fields_and_writes_lifecycle_log(tmp_path) -> None:
    """RegistryUpdater 成功追加 registry 事件后写 lifecycle_log。"""
    store = _FakeStore()
    updater = RegistryUpdater(store, lifecycle_storage_root=tmp_path)

    result = updater.update_ops(
        "factor_001",
        ops_update={"status": "core", "tier": "A", "health_score": 86.0},
        expected_version=3,
        reason="tier promoted",
        timestamp="2026-05-05T12:00:00",
    )

    assert isinstance(result, RegistryUpdateResult)
    assert result.success
    assert result.old_status == "candidate"
    assert result.new_status == "core"
    assert result.new_version == 4
    assert len(store.writes) == 1
    written_metadata = json.loads(store.writes[0]["metadata_json"])
    assert written_metadata["ops"]["status"] == "core"
    assert written_metadata["ops"]["tier"] == "A"
    assert written_metadata["ops"]["version"] == 4

    log_row = LifecycleLogReader(tmp_path).query(factor_id="factor_001").row(0, named=True)
    assert log_row["old_status"] == "candidate"
    assert log_row["new_status"] == "core"
    assert log_row["old_tier"] == "C"
    assert log_row["new_tier"] == "A"


def test_registry_updater_rejects_stale_expected_version_without_writing(tmp_path) -> None:
    """expected_version 不匹配时不写 registry，也不写 lifecycle_log。"""
    store = _FakeStore()
    result = RegistryUpdater(store, lifecycle_storage_root=tmp_path).update_ops(
        "factor_001",
        ops_update={"status": "degraded"},
        expected_version=2,
        reason="stale update",
        timestamp="2026-05-05T12:00:00",
    )

    assert not result.success
    assert result.error == "version conflict"
    assert store.writes == []
    assert LifecycleLogReader(tmp_path).query(factor_id="factor_001").is_empty()


def test_registry_updater_bulk_update_returns_per_factor_results(tmp_path) -> None:
    """批量更新逐因子返回结果，不隐藏局部失败。"""
    store = _FakeStore()
    updater = RegistryUpdater(store, lifecycle_storage_root=tmp_path)

    results = updater.bulk_update(
        [
            {"factor_id": "factor_001", "ops_update": {"status": "satellite", "tier": "B"}, "expected_version": 3},
            {"factor_id": "missing", "ops_update": {"status": "core"}, "expected_version": 1},
        ],
        timestamp="2026-05-05T12:00:00",
    )

    assert [result.success for result in results] == [True, False]
    assert results[1].error == "factor not found"
