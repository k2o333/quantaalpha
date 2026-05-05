from __future__ import annotations

import json

import polars as pl
import pytest
from quantaalpha.factor_ops.gate.data_quality import DataQualityGate, DataQualityGateConfig
from quantaalpha.factor_ops.gate.log_writer import GateLogReader, GateLogWriter


def _base_gate() -> DataQualityGate:
    return DataQualityGate(
        DataQualityGateConfig(
            min_cross_section_count=2,
            min_cross_section_pass_ratio=0.9,
            extreme_value_ratio_threshold=0.20,
            single_day_jump_zscore_threshold=2.0,
            future_corr_threshold=0.5,
        )
    )


def test_data_quality_gate_rejects_high_missing_rate_without_short_circuit() -> None:
    """缺失率超过阈值时 reject，同时保留其他检查明细。"""
    df = pl.DataFrame(
        {
            "date": ["2026-05-05"] * 4,
            "stock_id": ["A", "B", "C", "D"],
            "factor_value": [1.0, None, None, None],
        }
    )

    result = _base_gate().run("factor_missing", df)

    assert result.gate_result == "reject"
    assert result.reason == "missing_rate failed"
    assert {detail["check_name"] for detail in result.check_details} >= {
        "missing_rate",
        "coverage_rate",
        "min_cross_section_count",
    }


def test_data_quality_gate_watchlists_low_coverage() -> None:
    """覆盖率低于阈值但缺失率未超 reject 阈值时进入 watchlist。"""
    df = pl.DataFrame(
        {
            "date": ["2026-05-05"] * 4,
            "stock_id": ["A", "B", "C", "D"],
            "factor_value": [1.0, 2.0, None, 4.0],
        }
    )
    gate = DataQualityGate(DataQualityGateConfig(min_cross_section_count=2, coverage_rate_threshold=0.80))

    result = gate.run("factor_coverage", df)

    assert result.gate_result == "watchlist"
    assert result.detail_by_name("coverage_rate")["passed"] is False


def test_data_quality_gate_flags_extreme_values_for_re_winsorize() -> None:
    """极端值比例超过阈值时返回 re_winsorize。"""
    df = pl.DataFrame(
        {
            "date": ["2026-05-05"] * 10,
            "stock_id": [f"S{i}" for i in range(10)],
            "factor_value": [1.0, 1.1, 0.9, 1.0, 1.2, 1.1, 0.8, 1.0, 100.0, -100.0],
        }
    )

    gate = DataQualityGate(
        DataQualityGateConfig(
            min_cross_section_count=2,
            extreme_value_ratio_threshold=0.19,
        )
    )

    result = gate.run("factor_extreme", df)

    assert result.gate_result == "re_winsorize"
    assert result.detail_by_name("extreme_value_ratio")["value"] >= 0.20


def test_data_quality_gate_blacklists_future_function_even_when_other_checks_fail() -> None:
    """未来收益高度相关是 blacklist，优先级高于 reject/watchlist。"""
    df = pl.DataFrame(
        {
            "date": ["2026-05-05"] * 4,
            "stock_id": ["A", "B", "C", "D"],
            "factor_value": [1.0, 2.0, 3.0, 4.0],
            "return_t_plus_1": [0.1, 0.2, 0.3, 0.4],
        }
    )

    result = _base_gate().run("factor_future", df)

    assert result.gate_result == "blacklist"
    assert result.detail_by_name("future_function")["passed"] is False


def test_data_quality_gate_writes_gate_log_when_writer_is_provided(tmp_path) -> None:
    """提供 GateLogWriter 时，Gate 结果写入 gate_log 并返回 gate_run_id。"""
    gate = DataQualityGate(
        DataQualityGateConfig(min_cross_section_count=2),
        gate_log_writer=GateLogWriter(tmp_path),
    )
    df = pl.DataFrame(
        {
            "date": ["2026-05-05"] * 2,
            "stock_id": ["A", "B"],
            "factor_value": [1.0, 2.0],
        }
    )

    result = gate.run("factor_logged", df, created_at="2026-05-05T11:00:00")

    assert result.gate_run_id is not None
    logs = GateLogReader(tmp_path).query(factor_id="factor_logged")
    assert logs.height == 1
    assert logs["gate_run_id"].item() == result.gate_run_id
    assert json.loads(logs["check_details"].item())[0]["check_name"] == "missing_rate"


def test_data_quality_gate_rejects_empty_input() -> None:
    """空数据无法表达请求语义，应直接报错。"""
    gate = _base_gate()

    with pytest.raises(ValueError, match="factor_values_df is empty"):
        gate.run("factor_empty", pl.DataFrame({"date": [], "stock_id": [], "factor_value": []}))
