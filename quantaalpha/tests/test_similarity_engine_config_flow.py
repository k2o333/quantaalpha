from quantaalpha.continuous.orchestrator import MiningOrchestrator
from quantaalpha.continuous.scheduler import MiningConfig, PipelineConfig, SchedulerConfig


def test_pipeline_config_parses_similarity_engine_from_yaml_dict():
    config = PipelineConfig.from_yaml_dict(
        {
            "runtime": {
                "data_check_interval_seconds": 300,
                "cycle_budget_seconds": 7200,
            },
            "factor": {
                "library_path": "data/factorlib/all_factors_library.json",
            },
            "validation": {
                "min_ic": 0.02,
                "max_mining_per_run": 5,
            },
            "mining": {
                "pipeline_mode": True,
                "similarity_engine": {
                    "enabled": True,
                    "ensemble_mode": "weighted",
                    "metrics": {
                        "rag": {"enabled": False},
                        "ast": {"enabled": True},
                        "jaccard": {"enabled": True},
                    },
                },
            },
        }
    )

    assert config.mining.similarity_engine["enabled"] is True
    assert config.mining.similarity_engine["metrics"]["rag"]["enabled"] is False


def test_orchestrator_passes_similarity_engine_config():
    config = SchedulerConfig(
        mining=MiningConfig(
            pipeline_mode=True,
            similarity_engine={
                "enabled": True,
                "ensemble_mode": "weighted",
                "metrics": {
                    "rag": {"enabled": False},
                    "ast": {"enabled": True},
                    "jaccard": {"enabled": True},
                },
            },
        ),
    )

    orchestrator = MiningOrchestrator(config=config)
    scheduler = orchestrator.mining_scheduler

    assert scheduler._similarity_engine_cfg["enabled"] is True
    assert scheduler._similarity_engine_cfg["metrics"]["rag"]["enabled"] is False
