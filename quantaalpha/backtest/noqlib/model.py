"""No-qlib LightGBM 模型包装。"""

from __future__ import annotations

from typing import Any

import polars as pl

from .dataset import NoQlibDataset


class TrainingDataError(ValueError):
    """训练数据不足或特征矩阵无效。"""


class NoQlibModelRunner:
    """用原生 lightgbm 训练并输出显式键列 prediction frame。"""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def fit_predict(self, dataset: NoQlibDataset) -> pl.DataFrame:
        """训练模型并预测所有可用样本。"""
        train = dataset.segment("train").drop_nulls([dataset.label_column])
        valid = dataset.segment("valid").drop_nulls([dataset.label_column]) if "valid" in dataset.segments else None
        _validate_training_frame(dataset, train)

        import lightgbm as lgb

        model_cfg = self.config.get("model", {})
        raw_params = dict(model_cfg.get("params", {}))
        loss = raw_params.pop("loss", "mse")
        if loss not in {"mse", "binary"}:
            raise NotImplementedError(f"Unsupported LightGBM loss: {loss}")
        params = {"objective": loss, "verbosity": -1}
        params.update(raw_params)
        num_boost_round = int(params.pop("num_boost_round", 100))
        early_stopping_round = params.pop("early_stopping_rounds", params.pop("early_stopping_round", 50))
        train_set = lgb.Dataset(
            train.select(dataset.feature_columns).to_numpy(),
            label=train.get_column(dataset.label_column).to_numpy(),
        )
        valid_sets = [train_set]
        valid_names = ["train"]
        callbacks = [lgb.early_stopping(int(early_stopping_round)), lgb.log_evaluation(period=20)]
        if valid is not None and not valid.is_empty():
            valid_sets.append(
                lgb.Dataset(
                    valid.select(dataset.feature_columns).to_numpy(),
                    label=valid.get_column(dataset.label_column).to_numpy(),
                    reference=train_set,
                )
            )
            valid_names.append("valid")
        model = lgb.train(
            params,
            train_set,
            num_boost_round=num_boost_round,
            valid_sets=valid_sets,
            valid_names=valid_names,
            callbacks=callbacks,
        )
        predict_frame = dataset.segment("test")
        values = model.predict(predict_frame.select(dataset.feature_columns).to_numpy())
        return predict_frame.select(["datetime", "instrument"]).with_columns(pl.Series(name="score", values=values))


def _validate_training_frame(dataset: NoQlibDataset, train: pl.DataFrame) -> None:
    if train.is_empty():
        raw_train = dataset.segment("train")
        raise TrainingDataError(
            "Training segment has 0 rows after dropping null labels. "
            f"raw train: {raw_train.height} rows, "
            f"train range: {dataset.segments.get('train')}, "
            f"combined total: {dataset.combined.height} rows, "
            f"features: {len(dataset.feature_columns)}"
        )
    if not dataset.feature_columns:
        raise TrainingDataError("No feature columns available for training.")
    missing_features = sorted(set(dataset.feature_columns) - set(train.columns))
    if missing_features:
        raise TrainingDataError(f"Feature columns missing from train segment: {missing_features}")
