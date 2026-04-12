"""Tests for quantaalpha.continuous.paths - unified path resolution."""

from pathlib import Path
import copy
import pytest
from quantaalpha.continuous.paths import resolve_path, resolve_workspace_paths


# --- resolve_path basic tests ---


def test_relative_path_resolved():
    p = resolve_path("log/continuous/mining", "/home/quan/testdata/aspipe_v4")
    assert str(p) == "/home/quan/testdata/aspipe_v4/log/continuous/mining"
    assert p.is_absolute()


def test_absolute_path_unchanged():
    p = resolve_path("/custom/log/dir", "/home/quan/testdata/aspipe_v4")
    assert str(p) == "/custom/log/dir"


def test_no_project_root_uses_cwd():
    p = resolve_path("log/test")
    assert p.is_absolute()  # resolve() uses cwd


def test_path_object_input():
    """resolve_path should accept both str and Path."""
    p = resolve_path(Path("log/test"), Path("/home/quan"))
    assert str(p) == "/home/quan/log/test"


# --- resolve_workspace_paths full tests ---


def test_full_workspace_resolution():
    raw = {
        "workspace": {
            "project_root": "/home/quan/testdata/aspipe_v4",
            "log_root": "log",
            "runs_dir": "continuous/runs",
        },
        "mining": {
            "log_root": "continuous/mining",
            "state": {
                "pool_save_path": "continuous/trajectory_pool.json",
            },
        },
        "factor": {
            "library_path": "data/factorlib/all_factors_library.json",
        },
    }
    resolved = resolve_workspace_paths(raw)
    assert resolved["mining_log_root"] == "/home/quan/testdata/aspipe_v4/log/continuous/mining"
    assert resolved["runs_dir"] == "/home/quan/testdata/aspipe_v4/log/continuous/runs"
    assert resolved["pool_save_path"] == "/home/quan/testdata/aspipe_v4/log/continuous/trajectory_pool.json"


def test_empty_config_uses_defaults():
    """Empty config should use all defaults, all results should be absolute paths."""
    resolved = resolve_workspace_paths({})
    assert Path(resolved["log_root"]).is_absolute()
    assert "log" in resolved["log_root"]
    assert Path(resolved["mining_log_root"]).is_absolute()
    assert Path(resolved["runs_dir"]).is_absolute()


def test_nested_relative_paths():
    """project_root as relative path should resolve correctly."""
    resolved = resolve_workspace_paths({"workspace": {"project_root": ".", "log_root": "my_logs"}})
    assert Path(resolved["log_root"]).is_absolute()
    assert resolved["log_root"].endswith("my_logs")


def test_path_conflict_detection():
    """runs_dir nested under mining_log_root should raise ValueError."""
    with pytest.raises(ValueError, match="路径冲突"):
        resolve_workspace_paths(
            {
                "workspace": {
                    "project_root": "/test",
                    "log_root": "log",
                    "runs_dir": "continuous/mining/runs",  # nested under mining_log_root
                },
                "mining": {
                    "log_root": "continuous/mining",
                },
            }
        )


def test_original_dict_not_mutated():
    """resolve_workspace_paths should NOT mutate the input dict."""
    raw = {"workspace": {"project_root": "/test"}}
    original = copy.deepcopy(raw)
    resolve_workspace_paths(raw)
    assert raw == original


def test_monitoring_output_from_workspace():
    """workspace.monitoring_output_path takes priority over factor.monitoring_output_path."""
    resolved = resolve_workspace_paths(
        {
            "workspace": {
                "project_root": "/test",
                "log_root": "log",
                "monitoring_output_path": "custom_monitor",
            },
            "factor": {
                "monitoring_output_path": "old_monitor",
            },
        }
    )
    assert resolved["monitoring_output_path"] == "/test/log/custom_monitor"


def test_monitoring_output_fallback_to_factor():
    """Fallback to factor.monitoring_output_path when workspace doesn't have it."""
    resolved = resolve_workspace_paths(
        {
            "workspace": {"project_root": "/test", "log_root": "log"},
            "factor": {"monitoring_output_path": "old_monitor"},
        }
    )
    assert resolved["monitoring_output_path"] == "/test/log/old_monitor"


def test_parquet_library_dir_resolved_relative_to_project_root():
    """resolve_workspace_paths() returns a parquet_library_dir absolute path
    resolved relative to workspace.project_root."""
    resolved = resolve_workspace_paths(
        {
            "workspace": {"project_root": "/home/quan/testdata/aspipe_v4"},
            "factor": {
                "library_path": "third_party/quantaalpha/data/factorlib/all_factors_library.json",
                "parquet_library_dir": "third_party/quantaalpha/data/factorlib/parquet_store",
            },
        }
    )
    assert "parquet_library_dir" in resolved
    assert resolved["parquet_library_dir"] == "/home/quan/testdata/aspipe_v4/third_party/quantaalpha/data/factorlib/parquet_store"
    assert Path(resolved["parquet_library_dir"]).is_absolute()
