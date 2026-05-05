from __future__ import annotations

from datetime import datetime, timedelta

from quantaalpha.factor_ops.orchestration import (
    DataMonitorRouter,
    RevalidationPlanner,
    TriggerConditionEvaluator,
)


def test_data_monitor_router_maps_data_updates_to_factor_ops_workflows() -> None:
    """数据更新事件按数据类型触发 revalidation / health / training 工作流。"""
    event = {
        "dataset": "daily_price",
        "change_type": "append",
        "rows_changed": 1200,
        "major_update": True,
    }

    result = DataMonitorRouter().route_update(event)

    assert result["trigger_type"] == "data_update"
    assert result["workflows"] == ["revalidation", "health_recompute", "fhi_recompute", "training_evaluation"]
    assert result["dedupe_key"] == "daily_price:append"


def test_revalidation_planner_filters_by_ops_status_and_maps_failures() -> None:
    """复验优先 core/satellite/degraded/candidate，并将失败转为状态机事件。"""
    records = [
        {"factor_id": "f1", "metadata_json": {"ops": {"status": "core"}}},
        {"factor_id": "f2", "metadata_json": {"ops": {"status": "retired"}}},
        {"factor_id": "f3", "metadata_json": {"ops": {"status": "satellite"}}},
    ]

    planner = RevalidationPlanner()
    assert planner.select_candidates(records) == ["f1", "f3"]
    result = planner.map_result(
        factor_id="f1",
        current_status="core",
        passed=False,
        consecutive_failures=3,
    )

    assert result.suggested_status == "degraded"
    assert result.transition_valid
    assert result.health_recompute_required


def test_trigger_condition_evaluator_prioritizes_manual_and_respects_cooldown() -> None:
    """统一触发条件支持优先级、FHI 下降、数据/复验/挖掘联动和冷却期。"""
    evaluator = TriggerConditionEvaluator(cooldown_minutes=60)
    now = datetime(2026, 5, 5, 14, 0, 0)

    result = evaluator.evaluate(
        now=now,
        manual_requested=True,
        fhi_history=[90.0, 88.0, 79.0],
        data_update={"workflows": ["training_evaluation"]},
        revalidation_decay_count=2,
        new_factor_count=5,
    )

    assert result["triggered"]
    assert result["reason"] == "manual"
    assert result["priority"] == 1

    cooled = evaluator.evaluate(
        now=now + timedelta(minutes=30),
        last_triggered_at=now,
        fhi_history=[90.0, 88.0, 79.0],
    )

    assert not cooled["triggered"]
    assert cooled["reason"] == "cooldown"


def test_trigger_condition_evaluator_detects_fhi_and_revalidation_without_manual() -> None:
    evaluator = TriggerConditionEvaluator()

    assert evaluator.evaluate(fhi_history=[90.0, 89.0, 79.0])["reason"] == "fhi_drop"
    assert evaluator.evaluate(revalidation_decay_count=1)["reason"] == "revalidation_decay"
    assert evaluator.evaluate(new_factor_count=10, mining_new_factor_threshold=5)["reason"] == "new_factor_threshold"
