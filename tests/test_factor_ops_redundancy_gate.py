from __future__ import annotations

import json

import polars as pl
from quantaalpha.factor_ops.gate.log_writer import GateLogReader, GateLogWriter
from quantaalpha.factor_ops.gate.redundancy import RedundancyGate, RedundancyGateConfig


def test_redundancy_gate_blacklists_high_factor_value_correlation() -> None:
    """候选因子与池内因子值高度相关时 blacklist。"""
    candidate = pl.DataFrame(
        {
            "date": ["2026-05-05", "2026-05-05", "2026-05-05"],
            "stock_id": ["A", "B", "C"],
            "candidate": [1.0, 2.0, 3.0],
        }
    )
    pool = pl.DataFrame(
        {
            "date": ["2026-05-05", "2026-05-05", "2026-05-05"],
            "stock_id": ["A", "B", "C"],
            "pool_a": [1.0, 2.0, 3.0],
            "pool_b": [3.0, 1.0, 2.0],
        }
    )

    result = RedundancyGate(RedundancyGateConfig(correlation_threshold=0.85)).run(
        "factor_candidate",
        candidate,
        pool,
    )

    assert result.gate_result == "blacklist"
    assert result.reason == "factor_value_correlation failed"
    assert result.detail_by_name("factor_value_correlation")["details"]["nearest_factor_id"] == "pool_a"


def test_redundancy_gate_passes_when_expression_and_values_are_distinct() -> None:
    """表达式和因子值相关性均未超过阈值时 pass。"""
    candidate = pl.DataFrame(
        {
            "date": ["2026-05-05", "2026-05-05", "2026-05-05"],
            "stock_id": ["A", "B", "C"],
            "candidate": [1.0, 2.0, 3.0],
        }
    )
    pool = pl.DataFrame(
        {
            "date": ["2026-05-05", "2026-05-05", "2026-05-05"],
            "stock_id": ["A", "B", "C"],
            "pool_a": [2.0, 3.0, 1.0],
        }
    )

    result = RedundancyGate(RedundancyGateConfig(correlation_threshold=0.99)).run(
        "factor_candidate",
        candidate,
        pool,
        expression_similarity_score=0.20,
    )

    assert result.gate_result == "pass"
    assert result.detail_by_name("expression_similarity")["passed"] is True
    assert result.detail_by_name("factor_value_correlation")["passed"] is True


def test_redundancy_gate_blacklists_expression_similarity_without_value_pool() -> None:
    """表达式相似分超过阈值时，即使没有值池也 blacklist。"""
    candidate = pl.DataFrame(
        {
            "date": ["2026-05-05", "2026-05-05"],
            "stock_id": ["A", "B"],
            "candidate": [1.0, 2.0],
        }
    )

    result = RedundancyGate(RedundancyGateConfig(expression_similarity_threshold=0.85)).run(
        "factor_expr",
        candidate,
        pool_df=None,
        expression_similarity_score=0.91,
    )

    assert result.gate_result == "blacklist"
    assert result.detail_by_name("expression_similarity")["passed"] is False


def test_redundancy_gate_writes_gate_log_when_writer_is_provided(tmp_path) -> None:
    """提供 GateLogWriter 时，冗余 Gate 写入 gate_log。"""
    gate = RedundancyGate(gate_log_writer=GateLogWriter(tmp_path))
    candidate = pl.DataFrame(
        {
            "date": ["2026-05-05", "2026-05-05"],
            "stock_id": ["A", "B"],
            "candidate": [1.0, 2.0],
        }
    )
    pool = pl.DataFrame(
        {
            "date": ["2026-05-05", "2026-05-05"],
            "stock_id": ["A", "B"],
            "pool_a": [1.0, 2.0],
        }
    )

    result = gate.run("factor_logged", candidate, pool, created_at="2026-05-05T12:00:00")

    assert result.gate_run_id is not None
    logs = GateLogReader(tmp_path).query(factor_id="factor_logged", gate_name="redundancy")
    assert logs.height == 1
    assert json.loads(logs["check_details"].item())[0]["check_name"] == "expression_similarity"
