from __future__ import annotations

import polars as pl
import pytest
from quantaalpha.factor_ops.eval.foundation_index import (
    FoundationHealthIndexComputer,
    FoundationHealthIndexResult,
)


def test_foundation_health_index_filters_dl_and_derived_factors() -> None:
    """FHI 只纳入 mined/manual/formula 一级因子，剥离 DL 和衍生因子。"""
    registry = pl.DataFrame(
        {
            "factor_id": ["f_mined", "f_manual", "f_formula", "f_dl", "f_composite"],
            "data_source_type": ["mined", "manual", "formula", "DL-Feature", "composite"],
            "health_score": [80.0, 60.0, 50.0, 100.0, 100.0],
            "health_confidence": [1.0, 0.5, 0.5, 1.0, 1.0],
        }
    )

    result = FoundationHealthIndexComputer().compute(registry)

    assert isinstance(result, FoundationHealthIndexResult)
    assert result.foundation_health_index == pytest.approx(67.5)
    assert result.included_factor_ids == ["f_formula", "f_manual", "f_mined"]
    assert result.excluded_factor_ids == ["f_composite", "f_dl"]
    assert result.to_metadata_ops() == {
        "foundation_health_index": 67.5,
        "foundation_factor_count": 3,
    }


def test_foundation_health_index_returns_zero_when_no_valid_foundation_factors() -> None:
    """没有可用基石因子或权重为 0 时返回低置信空结果。"""
    registry = pl.DataFrame(
        {
            "factor_id": ["f_dl"],
            "data_source_type": ["derived"],
            "health_score": [90.0],
            "health_confidence": [1.0],
        }
    )

    result = FoundationHealthIndexComputer().compute(registry)

    assert result.foundation_health_index == 0
    assert result.foundation_factor_count == 0
    assert result.included_factor_ids == []


def test_foundation_health_index_detects_absolute_and_cumulative_drop_triggers() -> None:
    """触发条件支持单日绝对下降和连续 5 日累计下降。"""
    computer = FoundationHealthIndexComputer()

    assert computer.detect_drop_trigger([82.0, 81.0, 70.5]) == {
        "triggered": True,
        "reason": "absolute_drop",
        "drop": 10.5,
    }
    assert computer.detect_drop_trigger([90.0, 88.0, 86.0, 83.0, 79.0, 74.0]) == {
        "triggered": True,
        "reason": "five_day_cumulative_drop",
        "drop": 16.0,
    }
    assert computer.detect_drop_trigger([80.0, 79.0, 78.5]) == {
        "triggered": False,
        "reason": "",
        "drop": 0.0,
    }
