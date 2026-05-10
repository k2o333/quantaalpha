"""No-qlib LightGBM 模型包装。"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .dataset import NoQlibDataset


class NoQlibModelRunner:
    """用原生 lightgbm 训练并输出 qlib 风格 prediction series。"""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def fit_predict(self, dataset: NoQlibDataset) -> pd.Series:
        """训练模型并预测所有可用样本。"""
        import lightgbm as lgb

        train = dataset.segment("train").dropna(subset=[dataset.label_column])
        valid = dataset.segment("valid").dropna(subset=[dataset.label_column]) if "valid" in dataset.segments else None
        model_cfg = self.config.get("model", {})
        raw_params = dict(model_cfg.get("params", {}))
        loss = raw_params.pop("loss", "mse")
        if loss not in {"mse", "binary"}:
            raise NotImplementedError(f"Unsupported LightGBM loss: {loss}")
        params = {"objective": loss, "verbosity": -1}
        params.update(raw_params)
        num_boost_round = int(params.pop("num_boost_round", 100))
        early_stopping_round = params.pop("early_stopping_rounds", params.pop("early_stopping_round", 50))
        train_set = lgb.Dataset(train[dataset.feature_columns].values, label=train[dataset.label_column].values)
        valid_sets = [train_set]
        valid_names = ["train"]
        callbacks = [lgb.early_stopping(int(early_stopping_round)), lgb.log_evaluation(period=20)]
        if valid is not None and not valid.empty:
            valid_sets.append(
                lgb.Dataset(
                    valid[dataset.feature_columns].values,
                    label=valid[dataset.label_column].values,
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
        values = model.predict(predict_frame[dataset.feature_columns].values)
        return pd.Series(values, index=predict_frame.index, name="score")
