from __future__ import annotations

import polars as pl
import pytest

from quantaalpha.backtest.noqlib.dataset import NoQlibDatasetBuilder


def test_noqlib_dataset_builder_uses_single_processed_frame() -> None:
    features = pl.DataFrame(
        {
            "datetime": ["2024-01-01", "2024-01-01", "2024-01-02", "2024-01-02"],
            "instrument": ["A", "B", "A", "B"],
            "factor": [1.0, 2.0, 3.0, float("inf")],
        }
    )
    labels = pl.DataFrame(
        {
            "datetime": ["2024-01-01", "2024-01-01", "2024-01-02", "2024-01-02"],
            "instrument": ["A", "B", "A", "B"],
            "LABEL0": [0.1, 0.2, None, 0.4],
        }
    )

    dataset = NoQlibDatasetBuilder(
        {
            "dataset": {
                "segments": {
                    "train": ["2024-01-01", "2024-01-01"],
                    "test": ["2024-01-02", "2024-01-02"],
                }
            }
        }
    ).build(features, labels)

    assert dataset.learn_combined is None
    assert dataset.segment("train").height == 2
    assert dataset.raw_labels is not None
    assert dataset.raw_labels.filter((pl.col("datetime") == pl.datetime(2024, 1, 1)) & (pl.col("instrument") == "A")).get_column("LABEL0")[0] == 0.1


def test_noqlib_dataset_builder_rejects_uncovered_segment_with_actual_bounds() -> None:
    features, labels = _frames()

    with pytest.raises(ValueError, match="segment coverage validation failed") as exc_info:
        NoQlibDatasetBuilder(
            {
                "dataset": {
                    "segments": {
                        "train": ["2022-01-01", "2023-12-31"],
                        "valid": ["2024-01-01", "2024-01-01"],
                        "test": ["2024-01-02", "2024-01-02"],
                    }
                }
            }
        ).build(features, labels)

    message = str(exc_info.value)
    assert "requested train=('2022-01-01', '2023-12-31')" in message
    assert "feature bounds=('2024-01-01', '2024-01-02')" in message
    assert "label bounds=('2024-01-01', '2024-01-02')" in message
    assert "actual combined bounds=('2024-01-01', '2024-01-02')" in message


def test_noqlib_dataset_builder_rejects_overlapping_segments() -> None:
    features, labels = _frames()

    with pytest.raises(ValueError, match="segments must be ordered and mutually exclusive"):
        NoQlibDatasetBuilder(
            {
                "dataset": {
                    "segments": {
                        "train": ["2024-01-01", "2024-01-02"],
                        "valid": ["2024-01-02", "2024-01-02"],
                        "test": ["2024-01-02", "2024-01-02"],
                    }
                }
            }
        ).build(features, labels)


def _frames() -> tuple[pl.DataFrame, pl.DataFrame]:
    features = pl.DataFrame(
        {
            "datetime": ["2024-01-01", "2024-01-01", "2024-01-02", "2024-01-02"],
            "instrument": ["A", "B", "A", "B"],
            "factor": [1.0, 2.0, 3.0, 4.0],
        }
    )
    labels = pl.DataFrame(
        {
            "datetime": ["2024-01-01", "2024-01-01", "2024-01-02", "2024-01-02"],
            "instrument": ["A", "B", "A", "B"],
            "LABEL0": [0.1, 0.2, 0.3, 0.4],
        }
    )
    return features, labels
