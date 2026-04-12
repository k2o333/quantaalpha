"""
Unified path resolution - Single Source of Truth.

All paths from pipeline.yaml are resolved to absolute paths here.
"""

from pathlib import Path
from typing import Union


def resolve_path(
    raw: Union[str, Path],
    project_root: Union[str, Path, None] = None,
) -> Path:
    """
    Resolve a path value from pipeline.yaml to an absolute path.

    Rules:
    1. If raw is already absolute (starts with /), return as-is
    2. Otherwise, join with project_root and resolve
    3. If project_root not provided, resolve against cwd

    Args:
        raw: Raw path string or Path object from pipeline.yaml
        project_root: Project root directory (absolute path), str or Path

    Returns:
        Absolute Path object
    """
    p = Path(raw)
    if p.is_absolute():
        return p

    if project_root:
        return (Path(project_root) / p).resolve()

    return p.resolve()


def resolve_workspace_paths(config_dict: dict) -> dict:
    """
    Parse all paths from a complete pipeline.yaml dict.

    Returns a flat dict of resolved absolute path strings.
    Downstream modules get paths from this dict, no longer parse themselves.

    This function does NOT modify the input config_dict.

    Args:
        config_dict: Full dict from yaml.safe_load of pipeline.yaml

    Returns:
        {
            "project_root": "/abs/path",
            "log_root": "/abs/path/log",
            "mining_log_root": "/abs/path/log/continuous/mining",
            "runs_dir": "/abs/path/log/continuous/runs",
            "pool_save_path": "/abs/path/log/continuous/trajectory_pool.json",
            "factor_library_path": "/abs/path/data/factorlib/all_factors_library.json",
            "monitoring_output_path": "/abs/path/log/monitoring",
        }
    """
    workspace = config_dict.get("workspace", {})
    mining = config_dict.get("mining", {})
    factor = config_dict.get("factor", {})
    state = mining.get("state", {})

    # Step 1: Determine project_root (absolute path)
    project_root = workspace.get("project_root", "")
    if project_root:
        project_root = str(Path(project_root).resolve())
    else:
        project_root = str(Path.cwd().resolve())

    # Step 2: Determine log_root (relative to project_root)
    log_root_raw = workspace.get("log_root", "log")
    log_root = str(resolve_path(log_root_raw, project_root))

    # Step 3: Determine sub-paths (relative to log_root)
    mining_log_root_raw = mining.get("log_root", "continuous/mining")
    mining_log_root = str(resolve_path(mining_log_root_raw, log_root))

    runs_dir_raw = workspace.get("runs_dir", "continuous/runs")
    runs_dir = str(resolve_path(runs_dir_raw, log_root))

    pool_raw = state.get("pool_save_path", "continuous/trajectory_pool.json")
    pool_save_path = str(resolve_path(pool_raw, log_root))

    # Step 4: Non-log paths (relative to project_root)
    factor_lib_raw = factor.get(
        "library_path",
        "third_party/quantaalpha/data/factorlib/all_factors_library.json",
    )
    factor_library_path = str(resolve_path(factor_lib_raw, project_root))

    # Parquet library dir
    parquet_lib_raw = factor.get(
        "parquet_library_dir",
        "third_party/quantaalpha/data/factorlib/parquet_store",
    )
    parquet_library_dir = str(resolve_path(parquet_lib_raw, project_root))

    # monitoring_output_path: prefer workspace, fallback to factor
    monitoring_raw = workspace.get(
        "monitoring_output_path",
        factor.get("monitoring_output_path", "monitoring"),
    )
    # monitoring is log-relative output, resolve against log_root
    monitoring_output_path = str(resolve_path(monitoring_raw, log_root))

    # Step 5: Path conflict detection - prevent directory containment relationships
    named_paths = {
        "mining_log_root": mining_log_root,
        "runs_dir": runs_dir,
        "pool_save_path": pool_save_path,
    }
    for name_a, path_a in named_paths.items():
        for name_b, path_b in named_paths.items():
            if name_a >= name_b:
                continue
            # Skip file-type paths (ending with .json) from directory containment check
            if not path_a.endswith(".json") and not path_b.endswith(".json") and (path_a.startswith(path_b + "/") or path_b.startswith(path_a + "/")):
                raise ValueError(f"路径冲突：{name_a} ({path_a}) 与 {name_b} ({path_b}) 存在包含关系，请在 pipeline.yaml 中调整为互不包含的路径。")

    return {
        "project_root": project_root,
        "log_root": log_root,
        "mining_log_root": mining_log_root,
        "runs_dir": runs_dir,
        "pool_save_path": pool_save_path,
        "factor_library_path": factor_library_path,
        "parquet_library_dir": parquet_library_dir,
        "monitoring_output_path": monitoring_output_path,
    }
