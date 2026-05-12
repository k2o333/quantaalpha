"""Vnpy dataset contract adapter."""

from __future__ import annotations

from quantaalpha.backtest.noqlib.dataset import NoQlibDataset, NoQlibDatasetBuilder


class VnpyDatasetBuilder(NoQlibDatasetBuilder):
    """Vnpy feature/label output uses the shared no-qlib dataset contract."""


__all__ = ["NoQlibDataset", "VnpyDatasetBuilder"]
