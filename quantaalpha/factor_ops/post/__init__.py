"""Post-training factor_ops adapters."""

from quantaalpha.factor_ops.post.degradation import DegradationPostProcessor, DegradationPostResult
from quantaalpha.factor_ops.post.evaluation import EvaluationPostProcessor, EvaluationPostResult

__all__ = [
    "DegradationPostProcessor",
    "DegradationPostResult",
    "EvaluationPostProcessor",
    "EvaluationPostResult",
]
