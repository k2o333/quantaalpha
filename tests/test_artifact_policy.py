from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace


def test_pipeline_config_parses_minimal_artifact_policy(tmp_path):
    from quantaalpha.continuous.scheduler import PipelineConfig, SchedulerConfig

    yaml_path = tmp_path / "pipeline.yaml"
    yaml_path.write_text(
        """
artifact_policy:
  mode: minimal
  pickle_cache: disabled
  debug_artifacts: disabled
  parity_artifacts: disabled
  failed_workspace_retention: summary_only
  passed_workspace_retention: delete_after_publish
  publish_factor_values_on_pass: true
""",
        encoding="utf-8",
    )

    config = PipelineConfig.from_yaml(str(yaml_path))
    scheduler = SchedulerConfig.from_pipeline_config(config)

    assert config.artifact_policy.mode == "minimal"
    assert config.artifact_policy.pickle_cache == "disabled"
    assert config.artifact_policy.debug_artifacts == "disabled"
    assert config.artifact_policy.parity_artifacts == "disabled"
    assert config.artifact_policy.failed_workspace_retention == "summary_only"
    assert config.artifact_policy.passed_workspace_retention == "delete_after_publish"
    assert config.artifact_policy.publish_factor_values_on_pass is True
    assert scheduler.artifact_policy == config.artifact_policy


def test_minimal_artifact_policy_disables_pickle_cache_without_touching_workspace_path():
    from quantaalpha.continuous.artifact_policy import (
        ArtifactPolicyConfig,
        apply_artifact_policy_to_runtime,
    )

    settings = SimpleNamespace(
        cache_with_pickle=True,
        workspace_path="/tmp/workspace",
        pickle_cache_folder_path_str="/tmp/pickle_cache",
    )

    apply_artifact_policy_to_runtime(
        ArtifactPolicyConfig.from_dict({"mode": "minimal"}),
        settings=settings,
    )

    assert settings.cache_with_pickle is False
    assert settings.artifact_debug_artifacts_enabled is False
    assert settings.artifact_parity_artifacts_enabled is False
    assert settings.artifact_failed_workspace_retention == "summary_only"
    assert settings.artifact_passed_workspace_retention == "delete_after_publish"
    assert settings.artifact_publish_factor_values_on_pass is True
    assert settings.workspace_path == "/tmp/workspace"
    assert settings.pickle_cache_folder_path_str == "/tmp/pickle_cache"


def test_default_artifact_policy_preserves_runtime_cache_setting():
    from quantaalpha.continuous.artifact_policy import (
        ArtifactPolicyConfig,
        apply_artifact_policy_to_runtime,
    )

    settings = SimpleNamespace(cache_with_pickle=True)

    apply_artifact_policy_to_runtime(ArtifactPolicyConfig(), settings=settings)

    assert settings.cache_with_pickle is True


def test_runtime_parity_artifacts_enabled_defaults_to_true_and_honors_flag():
    from quantaalpha.continuous.artifact_policy import runtime_parity_artifacts_enabled

    assert runtime_parity_artifacts_enabled(settings=SimpleNamespace()) is True
    assert runtime_parity_artifacts_enabled(settings=SimpleNamespace(artifact_parity_artifacts_enabled=False)) is False


def test_runtime_publish_factor_values_on_pass_defaults_to_false_and_honors_flag():
    from quantaalpha.continuous.artifact_policy import runtime_publish_factor_values_on_pass

    assert runtime_publish_factor_values_on_pass(settings=SimpleNamespace()) is False
    assert (
        runtime_publish_factor_values_on_pass(
            settings=SimpleNamespace(artifact_publish_factor_values_on_pass=True)
        )
        is True
    )


def test_runtime_workspace_retention_helpers_default_and_honor_flags():
    from quantaalpha.continuous.artifact_policy import (
        runtime_failed_workspace_retention,
        runtime_passed_workspace_retention,
    )

    assert runtime_failed_workspace_retention(settings=SimpleNamespace()) == "full"
    assert runtime_passed_workspace_retention(settings=SimpleNamespace()) == "keep"
    settings = SimpleNamespace(
        artifact_failed_workspace_retention="summary_only",
        artifact_passed_workspace_retention="delete_after_publish",
    )
    assert runtime_failed_workspace_retention(settings=settings) == "summary_only"
    assert runtime_passed_workspace_retention(settings=settings) == "delete_after_publish"


def test_real_pipeline_yaml_enables_minimal_artifact_policy():
    from quantaalpha.continuous.scheduler import PipelineConfig

    repo_root = Path(__file__).resolve().parents[3]
    config = PipelineConfig.from_yaml(str(repo_root / "config" / "pipeline.yaml"))

    assert config.artifact_policy.mode == "minimal"
    assert config.artifact_policy.pickle_cache == "disabled"
    assert config.artifact_policy.debug_artifacts == "disabled"
    assert config.artifact_policy.parity_artifacts == "disabled"
    assert config.artifact_policy.failed_workspace_retention == "summary_only"
    assert config.artifact_policy.passed_workspace_retention == "delete_after_publish"
    assert config.artifact_policy.publish_factor_values_on_pass is True


def test_real_pipeline_yaml_retention_covers_minimal_mode_scratch_files():
    from quantaalpha.continuous.scheduler import PipelineConfig

    repo_root = Path(__file__).resolve().parents[3]
    config = PipelineConfig.from_yaml(str(repo_root / "config" / "pipeline.yaml"))
    workspace_root = next(
        root
        for root in config.workspace_retention.roots
        if str(root.root).endswith("third_party/workspace")
    )

    assert "*/result.parquet" in workspace_root.include_patterns
    assert "*/factor.py" in workspace_root.include_patterns
    assert "*/runtime_info.py" in workspace_root.include_patterns
    assert "*/factor_runtime*.json" in workspace_root.include_patterns
