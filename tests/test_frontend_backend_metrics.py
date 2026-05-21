from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd
import polars as pl


def _load_backend_metrics_module():
    path = Path(__file__).resolve().parents[1] / "frontend-v2" / "backend" / "backend_metrics.py"
    spec = importlib.util.spec_from_file_location("backend_metrics_under_test", path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_config(project_root: Path, output_dir: Path) -> Path:
    config_path = project_root / "backtest.yaml"
    config_path.write_text(
        f"experiment:\n  output_dir: {output_dir}\n",
        encoding="utf-8",
    )
    return config_path


def _write_metrics(output_dir: Path, name: str = "demo") -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = output_dir / f"{name}_backtest_metrics.json"
    metrics_path.write_text(
        json.dumps({"experiment_name": name, "metrics": {"annualized_return": 0.1}}),
        encoding="utf-8",
    )
    return metrics_path


def test_load_backtest_results_prefers_cumulative_excess_parquet(tmp_path: Path) -> None:
    module = _load_backend_metrics_module()
    output_dir = tmp_path / "results"
    config_path = _write_config(tmp_path, output_dir)
    _write_metrics(output_dir)
    pl.DataFrame(
        {
            "date": ["2021-01-01", "2021-01-02"],
            "cumulative_excess_return": [0.01, 0.02],
        }
    ).write_parquet(output_dir / "demo_cumulative_excess.parquet")
    pd.DataFrame(
        {
            "date": ["legacy"],
            "cumulative_excess_return": [999.0],
        }
    ).to_csv(output_dir / "demo_cumulative_excess.csv", index=False)

    task = {"config": {"configPath": str(config_path)}}
    module.load_backtest_results(task, tmp_path)

    assert task["metrics"]["cumulative_curve"] == [
        {"date": "2021-01-01", "value": 0.01},
        {"date": "2021-01-02", "value": 0.02},
    ]


def test_load_backtest_results_falls_back_to_legacy_cumulative_excess_csv(tmp_path: Path) -> None:
    module = _load_backend_metrics_module()
    output_dir = tmp_path / "results"
    config_path = _write_config(tmp_path, output_dir)
    _write_metrics(output_dir)
    pd.DataFrame(
        {
            "date": ["2021-01-01"],
            "cumulative_excess_return": [0.03],
        }
    ).to_csv(output_dir / "demo_cumulative_excess.csv", index=False)

    task = {"config": {"configPath": str(config_path)}}
    module.load_backtest_results(task, tmp_path)

    assert task["metrics"]["cumulative_curve"] == [{"date": "2021-01-01", "value": 0.03}]
