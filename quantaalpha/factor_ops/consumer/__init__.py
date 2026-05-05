"""Consumer-side factor_ops contracts."""

from quantaalpha.factor_ops.consumer.portfolio import PortfolioWeightMapper
from quantaalpha.factor_ops.consumer.ts_gru import TSGRUFactorInputBuilder

__all__ = [
    "PortfolioWeightMapper",
    "TSGRUFactorInputBuilder",
]
