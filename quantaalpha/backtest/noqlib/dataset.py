"""No-qlib dataset 构建和 qlib processor 等价子集。"""

from __future__ import annotations

import gc
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class NoQlibDataset:
    """训练、验证、测试切分后的矩阵。"""

    combined: pd.DataFrame
    feature_columns: list[str]
    label_column: str
    segments: dict[str, tuple[str, str]]
    learn_combined: pd.DataFrame | None = None
    raw_labels: pd.Series | None = None

    def segment(self, name: str) -> pd.DataFrame:
        source = self.learn_combined if name in {"train", "valid"} and self.learn_combined is not None else self.combined
        start, end = self.segments[name]
        dates = source.index.get_level_values("datetime")
        return source.loc[(dates >= pd.Timestamp(start)) & (dates <= pd.Timestamp(end))]


class NoQlibDatasetBuilder:
    """构建 feature/label combined frame。"""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def build(self, features: pd.DataFrame, labels: pd.DataFrame) -> NoQlibDataset:
        """对齐 index 并应用 Fillna/ProcessInf/DropnaLabel/CSRankNorm。"""
        features = _normalize_index(features)
        labels = _normalize_index(labels)
        common_index = features.index.intersection(labels.index)
        if len(common_index) == 0:
            raise ValueError("noqlib feature/label index intersection is empty")
        features = features.loc[common_index].copy()
        labels = labels.loc[common_index].copy()
        feature_columns = [str(c) for c in features.columns]
        label_column = "LABEL0"
        features.columns = feature_columns
        labels.columns = [label_column]
        raw_labels = labels[label_column].copy().sort_index()
        combined = pd.concat([features, labels], axis=1)
        del features, labels
        gc.collect()
        combined[feature_columns] = combined[feature_columns].replace([np.inf, -np.inf], np.nan).fillna(0.0)
        combined[feature_columns] = _cross_section_rank_norm(combined[feature_columns])
        combined[[label_column]] = _cross_section_rank_norm(combined[[label_column]])
        return NoQlibDataset(
            combined=combined.sort_index(),
            feature_columns=feature_columns,
            label_column=label_column,
            segments=_segments(self.config),
            learn_combined=None,
            raw_labels=raw_labels,
        )


def _normalize_index(frame: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(frame.index, pd.MultiIndex):
        raise ValueError("noqlib frame must use a MultiIndex")
    names = list(frame.index.names)
    if names == ["instrument", "datetime"]:
        frame = frame.swaplevel().sort_index()
    frame.index = frame.index.set_names(["datetime", "instrument"])
    return frame


def _cross_section_rank_norm(frame: pd.DataFrame) -> pd.DataFrame:
    return (frame.groupby(level="datetime").rank(pct=True) - 0.5) * 3.46


def _segments(config: dict[str, Any]) -> dict[str, tuple[str, str]]:
    raw_segments = config.get("dataset", {}).get("segments", {})
    return {name: (str(value[0]), str(value[1])) for name, value in raw_segments.items()}
