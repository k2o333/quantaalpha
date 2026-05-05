from __future__ import annotations

from quantaalpha.factor_ops.post.backtest import BacktestPostProcessor, BacktestPostResult


def test_backtest_post_processor_builds_tradability_snapshot_and_manifest() -> None:
    """回测结果转换为 eval_snapshot、HealthScorer 可交易性输入和 manifest 输出。"""
    result = BacktestPostProcessor().process(
        factor_id="factor_001",
        backtest_metrics={
            "annualized_return": 0.18,
            "max_drawdown": 0.08,
            "turnover_rate": 0.20,
            "sharpe_after_cost": 1.3,
            "cost_rate": 0.0015,
        },
        stage_output_path="eval_snapshot/year=2026/month=05/factor_001_backtest.parquet",
    )

    assert isinstance(result, BacktestPostResult)
    assert result.health_inputs == {
        "tradability": {
            "turnover": 0.2,
            "max_drawdown": 0.08,
            "sharpe_after_cost": 1.3,
        }
    }
    assert result.eval_snapshot["factor_id"] == "factor_001"
    assert result.eval_snapshot["backtest_metrics"]["annualized_return"] == 0.18
    assert result.manifest_stage_output == {
        "backtest_result_path": "eval_snapshot/year=2026/month=05/factor_001_backtest.parquet",
        "tradability_score": result.tradability_score,
    }


def test_backtest_post_processor_can_compute_after_cost_returns_input() -> None:
    """没有 sharpe_after_cost 时，保留 returns/turnover 给 HealthScorer 计算。"""
    result = BacktestPostProcessor().process(
        factor_id="factor_002",
        backtest_metrics={
            "returns": [0.01, 0.012, 0.008],
            "turnover": [0.10, 0.20, 0.10],
        },
    )

    assert result.health_inputs["tradability"] == {
        "returns": [0.01, 0.012, 0.008],
        "turnover": [0.1, 0.2, 0.1],
    }
    assert result.tradability_score > 0
