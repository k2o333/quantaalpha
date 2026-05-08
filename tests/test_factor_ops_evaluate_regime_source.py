from __future__ import annotations

import polars as pl

from quantaalpha.factor_ops.workflows.evaluate import EvaluateWorkflowRunner


def test_evaluate_workflow_uses_optional_regime_labels(tmp_path) -> None:
    factor_values = tmp_path / "factor.parquet"
    returns = tmp_path / "returns.parquet"
    regime_labels = tmp_path / "regime.parquet"
    pl.DataFrame(
        {
            "date": ["2026-05-01", "2026-05-01", "2026-05-02", "2026-05-02"],
            "stock_id": ["A", "B", "A", "B"],
            "factor_001": [1.0, 2.0, 1.0, 2.0],
        }
    ).write_parquet(factor_values)
    pl.DataFrame(
        {
            "date": ["2026-05-01", "2026-05-01", "2026-05-02", "2026-05-02"],
            "stock_id": ["A", "B", "A", "B"],
            "return_t_plus_1": [0.01, 0.02, 0.02, 0.01],
        }
    ).write_parquet(returns)
    pl.DataFrame(
        {
            "date": ["2026-05-01", "2026-05-02"],
            "regime_label": ["bull", "bear"],
        }
    ).write_parquet(regime_labels)

    result = EvaluateWorkflowRunner().run(
        "factor_001",
        factor_values=factor_values,
        returns=returns,
        regime_labels=regime_labels,
        no_write=True,
    )

    assert result["success"] is True
    assert result["regime_source"] == str(regime_labels)
    assert result["regime_column"] == "regime_label"
    assert set(result["regime_ic"]) == {"bear", "bull"}
