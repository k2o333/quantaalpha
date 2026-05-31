from pathlib import Path

from quantaalpha.continuous.paths import resolve_workspace_paths
from quantaalpha.continuous.run_store import RunSummary
from quantaalpha.continuous.scheduler import PipelineConfig, SchedulerConfig


def test_pipeline_config_parses_resource_governor_block():
    config = PipelineConfig.from_yaml_dict(
        {
            "mining": {
                "resource_governor": {
                    "enabled": True,
                    "max_factor_workers": 6,
                    "max_memory_soft_limit_gb": 24.0,
                    "max_disk_usage_ratio": 0.88,
                }
            }
        }
    )

    assert config.mining.resource_governor.enabled is True
    assert config.mining.resource_governor.max_factor_workers == 6
    assert config.mining.resource_governor.max_memory_soft_limit_gb == 24.0
    assert config.mining.resource_governor.max_disk_usage_ratio == 0.88

    scheduler_config = SchedulerConfig.from_pipeline_config(config)
    assert scheduler_config.mining.resource_governor.enabled is True


def test_repository_pipeline_config_enables_resource_governor():
    config_path = Path(__file__).resolve().parents[3] / "config" / "pipeline.yaml"

    config = PipelineConfig.from_yaml(str(config_path))

    assert config.continuous_lock_dir == "log/continuous/locks"
    assert config.mining.resource_governor.enabled is True
    assert config.mining.resource_governor.max_concurrent_mining_jobs == 1
    assert config.mining.resource_governor.max_concurrent_revalidation_jobs == 1
    assert config.mining.resource_governor.max_memory_soft_limit_gb <= 19.2
    assert config.mining.resource_governor.pause_when_data_updating is True
    assert config.mining.resource_governor.pause_when_compaction_running is True


def test_resolve_workspace_paths_includes_default_lock_dir(tmp_path):
    resolved = resolve_workspace_paths({"workspace": {"project_root": str(tmp_path)}})

    assert resolved["continuous_lock_dir"] == str(
        Path(tmp_path) / "log" / "continuous" / "locks"
    )


def test_run_summary_persists_governance_events_round_trip():
    summary = RunSummary(
        cycle_type="mining",
        governance_events=[
            {
                "event": "resource_decision",
                "reason": "deferred_data_not_ready",
                "scheduler": "mining",
            }
        ],
    )

    payload = summary.to_dict()

    assert payload["governance_events"][0]["reason"] == "deferred_data_not_ready"
    restored = RunSummary.from_dict(payload)
    assert restored.governance_events[0]["scheduler"] == "mining"
