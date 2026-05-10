from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

from quantaalpha.continuous.workspace_retention import (
    RetentionRootConfig,
    WorkspaceRetentionCleaner,
)


def _touch(path: Path, mtime: datetime, content: bytes = b"x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    ts = mtime.timestamp()
    os.utime(path, (ts, ts))


def test_retention_plan_selects_old_scratch_without_touching_durable_roots(tmp_path):
    now = datetime(2026, 5, 9, 12, 0, 0)
    old = now - timedelta(hours=80)
    recent = now - timedelta(hours=2)

    workspace = tmp_path / "third_party" / "workspace"
    mining_log = tmp_path / "log" / "mining" / "continuous" / "mining"
    factorlib = tmp_path / "third_party" / "quantaalpha" / "data" / "factorlib"

    _touch(workspace / "old_exp" / "result.h5", old, b"old-h5")
    _touch(workspace / "old_exp" / "combined_factors_df.parquet", old, b"old-parquet")
    _touch(workspace / "old_exp" / "ret.pkl", old, b"old-pkl")
    _touch(workspace / "old_exp" / "mlruns" / "run" / "metrics" / "IC", old, b"old-metric")
    _touch(workspace / "new_exp" / "result.h5", recent, b"new-h5")
    _touch(mining_log / "init" / "debug_tpl" / "x.pkl", old, b"debug")
    _touch(factorlib / "performance_history" / "summary" / "year=2026" / "month=05" / "part.parquet", old, b"durable")
    _touch(factorlib / "parquet_store" / "delta" / "factor.parquet", old, b"registry")

    cleaner = WorkspaceRetentionCleaner(
        roots=[
            RetentionRootConfig(
                root=workspace,
                include_patterns=[
                    "*/combined_factors_df.parquet",
                    "*/result.h5",
                    "*.pkl",
                    "*/mlruns/**",
                ],
            ),
            RetentionRootConfig(
                root=mining_log,
                include_patterns=["**/*.pkl"],
            ),
        ],
        retention_hours=72,
        now=now,
        manifest_dir=tmp_path / "log" / "retention",
    )

    plan = cleaner.plan()
    selected = {item.path.relative_to(tmp_path).as_posix() for item in plan.items}

    assert selected == {
        "third_party/workspace/old_exp/result.h5",
        "third_party/workspace/old_exp/combined_factors_df.parquet",
        "third_party/workspace/old_exp/ret.pkl",
        "third_party/workspace/old_exp/mlruns/run/metrics/IC",
        "log/mining/continuous/mining/init/debug_tpl/x.pkl",
    }

    result = cleaner.apply()
    assert result.deleted_count == 5
    assert result.deleted_bytes == sum(item.bytes for item in plan.items)
    assert result.manifest_path.exists()

    assert not (workspace / "old_exp" / "result.h5").exists()
    assert (workspace / "new_exp" / "result.h5").exists()
    assert (factorlib / "performance_history" / "summary" / "year=2026" / "month=05" / "part.parquet").exists()
    assert (factorlib / "parquet_store" / "delta" / "factor.parquet").exists()
