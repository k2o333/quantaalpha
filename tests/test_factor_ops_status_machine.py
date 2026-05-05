from __future__ import annotations

from datetime import datetime, timedelta

from quantaalpha.factor_ops.lifecycle.status_machine import StatusMachine, TransitionResult


def test_status_machine_suggests_draft_to_testing_without_applying() -> None:
    """状态机第一版建议先行，不直接写回。"""
    result = StatusMachine().transition(
        "factor_001",
        current_status="draft",
        event="calculation_completed",
    )

    assert isinstance(result, TransitionResult)
    assert result.old_status == "draft"
    assert result.suggested_status == "testing"
    assert result.transition_valid
    assert not result.applied


def test_status_machine_gate_and_health_transitions() -> None:
    """Gate 和 health/tier 事件覆盖 testing/candidate 核心转换。"""
    machine = StatusMachine()

    assert machine.transition(
        "factor_002",
        current_status="testing",
        event="gate_passed",
        gate_result="pass",
        health_score=45,
    ).suggested_status == "candidate"
    assert machine.transition(
        "factor_002",
        current_status="candidate",
        event="tier_update",
        tier="A",
        health_score=85,
    ).suggested_status == "core"
    assert machine.transition(
        "factor_002",
        current_status="candidate",
        event="tier_update",
        tier="B",
        health_score=70,
    ).suggested_status == "satellite"
    assert machine.transition(
        "factor_002",
        current_status="candidate",
        event="tier_update",
        tier="C",
        health_score=45,
        health_confidence=0.4,
    ).suggested_status == "watchlist"


def test_status_machine_blacklists_hard_gate_failure_from_any_state() -> None:
    """硬 Gate 失败可从任意非终态进入 blacklist。"""
    result = StatusMachine().transition(
        "factor_003",
        current_status="core",
        event="gate_failed",
        gate_result="blacklist",
        reason="PIT validation failed",
    )

    assert result.suggested_status == "blacklist"
    assert result.legacy_status == ""
    assert result.model_eligible is False


def test_status_machine_degradation_and_timeout_rules() -> None:
    """健康分下降、复验失败和超时无改善输出建议状态。"""
    machine = StatusMachine()

    assert machine.transition(
        "factor_004",
        current_status="core",
        event="health_score_update",
        health_score=62,
        previous_health_score=85,
    ).suggested_status == "degraded"
    assert machine.transition(
        "factor_004",
        current_status="degraded",
        event="revalidation_failed",
        consecutive_failures=3,
    ).suggested_status == "retired"
    assert machine.transition(
        "factor_005",
        current_status="watchlist",
        event="timeout_check",
        status_entered_at=(datetime.now() - timedelta(days=61)).isoformat(),
    ).suggested_status == "retired"


def test_status_machine_rejects_invalid_transition() -> None:
    """不支持的事件返回无效结果，不静默改状态。"""
    result = StatusMachine().transition(
        "factor_006",
        current_status="core",
        event="unknown_event",
    )

    assert not result.transition_valid
    assert result.suggested_status == "core"
    assert result.error == "no transition rule matched"
