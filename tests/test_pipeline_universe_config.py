from __future__ import annotations

from pathlib import Path

import yaml


def test_pipeline_noqlib_uses_hs300_instruments_file() -> None:
    project_root = Path(__file__).resolve().parents[3]
    config = yaml.safe_load((project_root / "config" / "pipeline.yaml").read_text(encoding="utf-8"))

    noqlib = config["factor"]["backtest_noqlib"]

    assert noqlib["instruments_path"] == "config/instruments/hs300.txt"
    assert (project_root / noqlib["instruments_path"]).exists()


def test_pipeline_noqlib_execution_periods_match_long_training_window() -> None:
    project_root = Path(__file__).resolve().parents[3]
    config = yaml.safe_load((project_root / "config" / "pipeline.yaml").read_text(encoding="utf-8"))

    execution = config["execution"]
    standard_frame = config["factor"]["backtest_noqlib"]["standard_frame"]

    assert execution["train"] == {"start": "2017-01-01", "end": "2023-12-31"}
    assert execution["valid"] == {"start": "2024-01-01", "end": "2024-12-31"}
    assert execution["test"] == {"start": "2025-01-01", "end": "2025-12-26"}
    assert standard_frame["start_date"] == "2016-01-01"
    assert standard_frame["start_date"] < execution["train"]["start"]
    assert standard_frame["lookback_days"] >= 3414


def test_pipeline_smoke_orchestration_is_explicit_linear_flow() -> None:
    project_root = Path(__file__).resolve().parents[3]
    config = yaml.safe_load((project_root / "config" / "pipeline.yaml").read_text(encoding="utf-8"))

    orchestration = config["mining"]["orchestration"]
    nodes = {node["id"]: node for node in orchestration["nodes"]}

    assert orchestration["conditions"] == []
    assert list(nodes) == ["original", "mutation", "crossover", "stop"]
    assert nodes["mutation"]["next"] == [{"goto": "crossover"}]
