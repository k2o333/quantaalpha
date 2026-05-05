"""Post-training factor_ops adapters."""

from quantaalpha.factor_ops.post.backtest import BacktestPostProcessor, BacktestPostResult
from quantaalpha.factor_ops.post.degradation import DegradationPostProcessor, DegradationPostResult
from quantaalpha.factor_ops.post.evaluation import EvaluationPostProcessor, EvaluationPostResult

__all__ = [
    "BacktestPostProcessor",
    "BacktestPostResult",
    "DegradationPostProcessor",
    "DegradationPostResult",
    "EvaluationPostProcessor",
    "EvaluationPostResult",
]
