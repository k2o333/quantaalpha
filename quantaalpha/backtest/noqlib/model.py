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

        train = dataset.segment("train")
        valid = dataset.segment("valid") if "valid" in dataset.segments else None
        model_cfg = self.config.get("model", {})
        params = dict(model_cfg.get("params", {}))
        num_boost_round = int(params.pop("num_boost_round", 100))
        early_stopping_round = params.pop("early_stopping_round", None)
        params.setdefault("objective", "regression")
        params.setdefault("metric", "l2")
        params.setdefault("verbose", -1)
        train_set = lgb.Dataset(train[dataset.feature_columns], label=train[dataset.label_column])
        valid_sets = None
        callbacks = None
        if valid is not None and not valid.empty:
            valid_sets = [lgb.Dataset(valid[dataset.feature_columns], label=valid[dataset.label_column], reference=train_set)]
            if early_stopping_round:
                callbacks = [lgb.early_stopping(int(early_stopping_round), verbose=False)]
        model = lgb.train(params, train_set, num_boost_round=num_boost_round, valid_sets=valid_sets, callbacks=callbacks)
        values = model.predict(dataset.combined[dataset.feature_columns])
        return pd.Series(values, index=dataset.combined.index, name="score")

