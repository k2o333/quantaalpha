from __future__ import annotations

import pandas as pd

from quantaalpha.backtest.noqlib.dataset import NoQlibDatasetBuilder


def test_noqlib_dataset_builder_uses_single_processed_frame() -> None:
    index = pd.MultiIndex.from_product(
        [[pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-02")], ["A", "B"]],
        names=["datetime", "instrument"],
    )
    features = pd.DataFrame({"factor": [1.0, 2.0, 3.0, float("inf")]}, index=index)
    labels = pd.DataFrame({"LABEL0": [0.1, 0.2, None, 0.4]}, index=index)

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
    assert dataset.segment("train").shape[0] == 2
    assert dataset.raw_labels is not None
    assert dataset.raw_labels.loc[(pd.Timestamp("2024-01-01"), "A")] == 0.1
