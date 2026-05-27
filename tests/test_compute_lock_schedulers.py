from quantaalpha.continuous.mining_scheduler import DefaultMiningScheduler
from quantaalpha.continuous.revalidation_scheduler import DefaultRevalidationScheduler


class DenyingLock:
    def __init__(self, *args, **kwargs):
        self.released = False

    def acquire(self):
        return False

    def release(self):
        self.released = True


def test_mining_run_defers_when_global_compute_lock_is_held(tmp_path):
    scheduler = DefaultMiningScheduler(
        pipeline_mode=True,
        resource_governor_config={"enabled": True},
        continuous_lock_dir=str(tmp_path),
    )
    scheduler._resource_lock_factory = DenyingLock
    scheduler._run_pipeline_mining = lambda budget_seconds=None: (_ for _ in ()).throw(
        AssertionError("pipeline should not run without compute lock")
    )

    result = scheduler.run_mining(budget_seconds=1)

    assert result.factors_generated == 0
    assert result.errors == ["global compute lock held"]
    assert result.governance_events[0]["reason"] == "global_compute_lock_held"


def test_revalidation_defers_when_global_compute_lock_is_held(tmp_path):
    scheduler = DefaultRevalidationScheduler(
        resource_governor_config={"enabled": True},
        continuous_lock_dir=str(tmp_path),
    )
    scheduler._resource_lock_factory = DenyingLock
    scheduler._run_factor_backtest = lambda factor_id, factor_entry: (_ for _ in ()).throw(
        AssertionError("backtest should not run without compute lock")
    )

    result = scheduler.run_revalidation(candidates=[{"factor_id": "f1"}])

    assert result.total_candidates == 0
    assert result.errors == ["global compute lock held"]
    assert result.governance_events[0]["reason"] == "global_compute_lock_held"
