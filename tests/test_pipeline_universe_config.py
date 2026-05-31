from __future__ import annotations

from pathlib import Path

import yaml


def test_pipeline_noqlib_uses_hs300_instruments_file() -> None:
    project_root = Path(__file__).resolve().parents[3]
    config = yaml.safe_load((project_root / "config" / "pipeline.yaml").read_text(encoding="utf-8"))

    noqlib = config["factor"]["backtest_noqlib"]

    assert noqlib["instruments_path"] == "config/instruments/hs300.txt"
    assert (project_root / noqlib["instruments_path"]).exists()


def test_pipeline_smoke_orchestration_is_explicit_linear_flow() -> None:
    project_root = Path(__file__).resolve().parents[3]
    config = yaml.safe_load((project_root / "config" / "pipeline.yaml").read_text(encoding="utf-8"))

    orchestration = config["mining"]["orchestration"]
    nodes = {node["id"]: node for node in orchestration["nodes"]}

    assert orchestration["conditions"] == []
    assert list(nodes) == ["original", "mutation", "crossover", "stop"]
    assert nodes["mutation"]["next"] == [{"goto": "crossover"}]
