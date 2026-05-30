"""No-qlib LightGBM 模型包装。"""

from __future__ import annotations

from typing import Any

import polars as pl

from .dataset import NoQlibDataset


class NoQlibModelRunner:
    """用原生 lightgbm 训练并输出显式键列 prediction frame。"""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def fit_predict(self, dataset: NoQlibDataset) -> pl.DataFrame:
        """训练模型并预测所有可用样本。"""
        import lightgbm as lgb

        train = dataset.segment("train").drop_nulls([dataset.label_column])
        valid = dataset.segment("valid").drop_nulls([dataset.label_column]) if "valid" in dataset.segments else None
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
