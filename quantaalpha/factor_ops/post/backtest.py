"""Training POST backtest adapter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from quantaalpha.factor_ops.eval.health_scorer import HealthScorer
from quantaalpha.factor_ops.utils._stats import is_finite


@dataclass(frozen=True)
class BacktestPostResult:
    """训练后回测接入结果。"""

    factor_id: str
    health_inputs: dict[str, dict[str, Any]]
    tradability_score: float
    eval_snapshot: dict[str, Any]
    manifest_stage_output: dict[str, Any]


class BacktestPostProcessor:
    """把回测指标转为 factor_ops eval/health 契约。"""

    def __init__(self, health_scorer: HealthScorer | None = None) -> None:
        """初始化处理器。"""
        self.health_scorer = health_scorer or HealthScorer()

    def process(
        self,
        *,
        factor_id: str,
        backtest_metrics: dict[str, Any],
        stage_output_path: str = "",
    ) -> BacktestPostResult:
        """规范化回测指标并计算可交易性得分。"""
        health_inputs = {"tradability": self._tradability_input(backtest_metrics)}
        health_result = self.health_scorer.compute(factor_id, **health_inputs)
        tradability_score = health_result.health_breakdown["tradability"]
        snapshot = {
            "factor_id": factor_id,
            "backtest_metrics": dict(backtest_metrics),
            "health_inputs": health_inputs,
            "tradability_score": tradability_score,
        }
        manifest = {
            "backtest_result_path": stage_output_path,
            "tradability_score": tradability_score,
        }
        return BacktestPostResult(
            factor_id=factor_id,
            health_inputs=health_inputs,
            tradability_score=tradability_score,
            eval_snapshot=snapshot,
            manifest_stage_output=manifest,
        )

    def _tradability_input(self, metrics: dict[str, Any]) -> dict[str, Any]:
        output: dict[str, Any] = {}
        turnover = _metric(metrics, "turnover_rate", "turnover")
        if turnover is not None:
            output["turnover"] = turnover
        max_drawdown = _metric(metrics, "max_drawdown", "MaxDrawdown")
        if max_drawdown is not None:
            output["max_drawdown"] = max_drawdown
        sharpe = _metric(metrics, "sharpe_after_cost", "after_cost_sharpe")
        if sharpe is not None:
            output["sharpe_after_cost"] = sharpe
        returns = _number_list(metrics.get("returns"))
        if returns:
            output["returns"] = returns
        turnover_series = _number_list(metrics.get("turnover"))
        if turnover_series:
            output["turnover"] = turnover_series
        return output


def _metric(metrics: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        value = metrics.get(key)
        if is_finite(value):
            return float(value)
    return None


def _number_list(value: Any) -> list[float]:
    if not isinstance(value, list):
        return []
    return [float(item) for item in value if is_finite(item)]
