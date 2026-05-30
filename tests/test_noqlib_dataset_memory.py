from __future__ import annotations

import polars as pl

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
