from __future__ import annotations

from types import SimpleNamespace

import pytest


def test_short_uat_profile_bounds_cycle_limits() -> None:
    from quantaalpha.continuous.main import _apply_uat_profile

    config = SimpleNamespace(
        cycle_budget_seconds=3600,
        validation=SimpleNamespace(max_revalidation_per_run=10, max_mining_per_run=5),
    )
    _apply_uat_profile(config, "short")
    assert config.cycle_budget_seconds == 900
    assert config.validation.max_revalidation_per_run == 1
    assert config.validation.max_mining_per_run == 1


def test_unknown_uat_profile_fails_fast() -> None:
    from quantaalpha.continuous.main import _apply_uat_profile

    config = SimpleNamespace(
        cycle_budget_seconds=3600,
        validation=SimpleNamespace(max_revalidation_per_run=10, max_mining_per_run=5),
    )
    with pytest.raises(ValueError, match="unsupported continuous UAT profile"):
        _apply_uat_profile(config, "nightly")
