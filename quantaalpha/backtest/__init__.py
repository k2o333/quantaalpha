"""Backtest V2 public entry points."""

__version__ = "2.0.0"
__all__ = ["FactorLoader", "FactorCalculator", "BacktestRunner"]


def __getattr__(name: str):
    if name == "FactorLoader":
        from .factor_loader import FactorLoader

        return FactorLoader
    if name == "FactorCalculator":
        from .factor_calculator import FactorCalculator

        return FactorCalculator
    if name == "BacktestRunner":
        from .runner import BacktestRunner

        return BacktestRunner
    raise AttributeError(name)
