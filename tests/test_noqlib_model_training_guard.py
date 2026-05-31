from __future__ import annotations

from datetime import datetime

import polars as pl
import pytest

from quantaalpha.backtest.noqlib.dataset import NoQlibDataset
from quantaalpha.backtest.noqlib.model import NoQlibModelRunner, TrainingDataError


def test_fit_predict_rejects_empty_train_after_dropping_null_labels() -> None:
    dataset = _dataset(
        pl.DataFrame(
            {
                "datetime": [datetime(2020, 1, 2), datetime(2020, 1, 3)],
                "instrument": ["000001.SZ", "000001.SZ"],
                "factor": [0.1, 0.2],
                "LABEL0": [None, None],
            }
        ),
        feature_columns=["factor"],
    )

    with pytest.raises(TrainingDataError, match="0 rows after dropping null labels"):
        NoQlibModelRunner({}).fit_predict(dataset)


def test_fit_predict_rejects_empty_feature_columns() -> None:
    dataset = _dataset(
        pl.DataFrame(
            {
                "datetime": [datetime(2020, 1, 2), datetime(2020, 1, 3)],
                "instrument": ["000001.SZ", "000001.SZ"],
                "LABEL0": [0.1, 0.2],
            }
        ),
        feature_columns=[],
    )

    with pytest.raises(TrainingDataError, match="No feature columns"):
        NoQlibModelRunner({}).fit_predict(dataset)


def test_fit_predict_rejects_missing_feature_columns() -> None:
    dataset = _dataset(
        pl.DataFrame(
            {
                "datetime": [datetime(2020, 1, 2), datetime(2020, 1, 3)],
                "instrument": ["000001.SZ", "000001.SZ"],
                "factor": [0.1, 0.2],
                "LABEL0": [0.1, 0.2],
            }
        ),
        feature_columns=["factor", "missing_factor"],
    )

    with pytest.raises(TrainingDataError, match="missing_factor"):
        NoQlibModelRunner({}).fit_predict(dataset)


def _dataset(combined: pl.DataFrame, *, feature_columns: list[str]) -> NoQlibDataset:
    return NoQlibDataset(
        combined=combined,
        feature_columns=feature_columns,
        label_column="LABEL0",
        segments={
            "train": ("2020-01-01", "2020-01-31"),
            "valid": ("2020-02-01", "2020-02-29"),
            "test": ("2020-01-01", "2020-01-31"),
        },
    )
