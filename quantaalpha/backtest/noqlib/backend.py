"""No-qlib 回测 backend 编排。"""

from __future__ import annotations

import gc
import json
import time
from pathlib import Path
from typing import Any

from quantaalpha.backtest.contracts import build_metric_namespaces
from quantaalpha.backtest.factor_loader import FactorLoader

from .data_provider import NoQlibMarketDataProvider
from .dataset import NoQlibDatasetBuilder
from .expression_engine import NoQlibExpressionEngine
from .model import NoQlibModelRunner
from .portfolio import NoQlibTopkDropoutBacktester
from .result_writer import save_results
from .signal_analysis import signal_metrics


class NoQlibBacktestBackend:
    """完全不依赖 qlib import 的回测 backend。"""

    def __init__(self, config_path: str, config: dict[str, Any]) -> None:
        self.config_path = Path(config_path)
        self.config = config

    def run(
        self,
        factor_source: str | None = None,
        factor_json: list[str] | None = None,
        experiment_name: str | None = None,
        output_name: str | None = None,
        skip_uncached: bool = False,
    ) -> dict:
        """运行 no-qlib 回测。"""
        del skip_uncached
        started = time.time()
        if factor_source:
            self.config.setdefault("factor_source", {})["type"] = factor_source
        if factor_json:
            self.config.setdefault("factor_source", {}).setdefault("custom", {})["json_files"] = factor_json
        if output_name is None and factor_json:
            output_name = Path(factor_json[0]).stem
        exp_name = experiment_name or output_name or self.config.get("experiment", {}).get("name", "noqlib_backtest")
        qlib_factors, custom_factors = FactorLoader(self.config).load_factors()
        factor_defs = [
            {"factor_id": name, "factor_name": name, "factor_expression": expr}
            for name, expr in qlib_factors.items()
        ]
        factor_defs.extend(custom_factors)
        if not factor_defs:
            raise ValueError("no factors available for noqlib backtest")
        market = NoQlibMarketDataProvider(self.config).load_market_data()
        feature_market = _filter_feature_market(market, self.config)
        expression_engine = NoQlibExpressionEngine(feature_market)
        features = expression_engine.compute(factor_defs)
        labels = expression_engine.compute_label(self.config.get("dataset", {}).get("label", "Ref($close, -2) / Ref($close, -1) - 1"))
        # Free expression engine after feature/label computation
        del expression_engine, feature_market
        gc.collect()
        dataset = NoQlibDatasetBuilder(self.config).build(features, labels)
        del features, labels
        gc.collect()
        prediction = NoQlibModelRunner(self.config).fit_predict(dataset)
        label_for_signal = dataset.raw_labels if dataset.raw_labels is not None else dataset.combined[dataset.label_column]
        signal_metric_values = signal_metrics(prediction, label_for_signal)
        metrics = dict(signal_metric_values)
        portfolio_metrics, daily_report, positions = NoQlibTopkDropoutBacktester(self.config, market).run(prediction)
        del prediction, dataset, market
        gc.collect()
        metrics.update(portfolio_metrics)
        metrics["metric_namespaces"] = build_metric_namespaces(
            signal_metrics=signal_metric_values,
            portfolio_metrics=portfolio_metrics,
            daily_report_columns=daily_report.columns,
        )
        save_results(
            config=self.config,
            metrics=metrics,
            exp_name=exp_name,
            factor_source=self.config.get("factor_source", {}).get("type", "unknown"),
            num_factors=len(factor_defs),
            elapsed=time.time() - started,
            output_name=output_name,
            daily_report=daily_report,
            positions=positions,
        )
        return metrics

    def run_from_library(
        self,
        library_path: str,
        factor_ids: list[str] | None = None,
        status_filter: str | None = None,
        output_name: str | None = None,
        skip_uncached: bool = False,
    ) -> dict:
        """从旧 JSON 因子库运行 no-qlib 回测。"""
        with Path(library_path).open("r", encoding="utf-8") as fh:
            lib_data = json.load(fh)
        factors_raw = lib_data.get("factors", {})
        selected = []
        for fid, finfo in factors_raw.items():
            if factor_ids and fid not in factor_ids:
                continue
            status = finfo.get("evaluation", {}).get("status", "pending_validation")
            if status_filter and status != status_filter:
                continue
            expr = finfo.get("factor_expression", "")
            if not expr:
                continue
            selected.append({"factor_id": fid, "factor_name": finfo.get("factor_name", fid), "factor_expression": expr})
        if not selected:
            return {"error": "no_matching_factors", "factors_checked": list(factors_raw.keys())}
        tmp_path = Path(library_path).parent / f".{Path(library_path).name}.noqlib_tmp_factors.json"
        try:
            tmp_path.write_text(json.dumps({"factors": {f["factor_id"]: f for f in selected}}, ensure_ascii=False), encoding="utf-8")
            metrics = self.run(
                factor_source="custom",
                factor_json=[str(tmp_path)],
                output_name=output_name or "library_backtest",
                skip_uncached=skip_uncached,
            )
            return {"metrics": metrics, "factors_backtested": [f["factor_id"] for f in selected], "library_path": library_path}
        finally:
            if tmp_path.exists():
                tmp_path.unlink()


def _filter_feature_market(market, config: dict[str, Any]):
    noqlib_cfg = config.get("backtest_runtime", {}).get("noqlib", {})
    instruments = noqlib_cfg.get("instruments")
    if not instruments:
        return market
    keep = {str(item) for item in instruments}
    mask = market.index.get_level_values("instrument").astype(str).isin(keep)
    return market.loc[mask]
