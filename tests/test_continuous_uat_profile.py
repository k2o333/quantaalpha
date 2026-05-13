from __future__ import annotations

from types import SimpleNamespace

import pytest


def test_short_uat_profile_bounds_cycle_limits() -> None:
    from quantaalpha.continuous.main import _apply_uat_profile

    config = SimpleNamespace(
        cycle_budget_seconds=3600,
        validation=SimpleNamespace(max_revalidation_per_run=10, max_mining_per_run=5),
        mining=SimpleNamespace(
            evolution=SimpleNamespace(max_rounds=3),
            orchestration=SimpleNamespace(
                max_steps_per_cycle=6,
                nodes=[
                    SimpleNamespace(params={}),
                    SimpleNamespace(params={"max_tasks_per_run": 3}),
                ],
            ),
        ),
    )
    _apply_uat_profile(config, "short")
    assert config.cycle_budget_seconds == 900
    assert config.validation.max_revalidation_per_run == 1
    assert config.validation.max_mining_per_run == 1
    assert config.mining.evolution.max_rounds == 1
    assert config.mining.orchestration.max_steps_per_cycle == 1
    assert config.mining.orchestration.nodes[1].params["max_tasks_per_run"] == 1


def test_unknown_uat_profile_fails_fast() -> None:
    from quantaalpha.continuous.main import _apply_uat_profile

    config = SimpleNamespace(
        cycle_budget_seconds=3600,
        validation=SimpleNamespace(max_revalidation_per_run=10, max_mining_per_run=5),
    )
    with pytest.raises(ValueError, match="unsupported continuous UAT profile"):
        _apply_uat_profile(config, "nightly")


def test_mining_scheduler_uses_explicit_cycle_budget() -> None:
    from quantaalpha.continuous.mining_scheduler import DefaultMiningScheduler

    captured: dict[str, int | None] = {}
    scheduler = object.__new__(DefaultMiningScheduler)
    scheduler._pipeline_mode = True
    scheduler._state_cfg = {"cycle_budget_seconds": 999}
    scheduler._update_next_run = lambda: None

    def fake_pipeline_mining(*, budget_seconds: int | None = None) -> dict:
        captured["budget_seconds"] = budget_seconds
        return {
            "factors_generated": 0,
            "factors_validated": 0,
            "factors_added": 0,
            "factor_ids": [],
            "errors": [],
        }

    scheduler._run_pipeline_mining = fake_pipeline_mining

    result = scheduler.run_mining(budget_seconds=7)

    assert captured["budget_seconds"] == 7
    assert result.errors == []
