"""No-qlib TopK Dropout 组合回测。"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .risk import risk_metrics


class NoQlibTopkDropoutBacktester:
    """TopK Dropout 的 no-qlib 初版实现。"""

    def __init__(self, config: dict[str, Any], market_data: pd.DataFrame) -> None:
        self.config = config
        self.market_data = market_data

    def run(self, prediction: pd.Series) -> tuple[dict[str, float], pd.DataFrame, pd.DataFrame]:
        """返回 metrics、daily report、positions。"""
        bt_cfg = self.config.get("backtest", {}).get("backtest", {})
        st_cfg = self.config.get("backtest", {}).get("strategy", {}).get("kwargs", {})
        start = pd.Timestamp(bt_cfg.get("start_time"))
        end = pd.Timestamp(bt_cfg.get("end_time"))
        topk = int(st_cfg.get("topk", 50))
        n_drop = int(st_cfg.get("n_drop", 5))
        open_cost = float(bt_cfg.get("exchange_kwargs", {}).get("open_cost", 0.0))
        close_cost = float(bt_cfg.get("exchange_kwargs", {}).get("close_cost", 0.0))
        pred = prediction.loc[(prediction.index.get_level_values("datetime") >= start) & (prediction.index.get_level_values("datetime") <= end)]
        dates = sorted(pred.index.get_level_values("datetime").unique())
        holdings: list[str] = []
        report_rows = []
        position_rows = []
        close_returns = self.market_data["$return"]
        for dt in dates:
            day_pred = pred.xs(dt, level="datetime").dropna().sort_values(ascending=False)
            ranked = list(day_pred.index.astype(str))
            if not holdings:
                next_holdings = ranked[:topk]
            else:
                keep = [inst for inst in holdings if inst in ranked]
                rank_pos = {inst: i for i, inst in enumerate(ranked)}
                sells = sorted(keep, key=lambda inst: rank_pos.get(inst, 10**9), reverse=True)[:n_drop]
                keep = [inst for inst in keep if inst not in set(sells)]
                buys = [inst for inst in ranked if inst not in keep][: max(topk - len(keep), n_drop)]
                next_holdings = (keep + buys)[:topk]
            turnover = _turnover(holdings, next_holdings)
            day_returns = []
            for inst in next_holdings:
                try:
                    day_returns.append(float(close_returns.loc[(dt, inst)]))
                except KeyError:
                    day_returns.append(0.0)
            portfolio_return = float(np.mean(day_returns)) if day_returns else 0.0
            bench_return = _benchmark_return(self.market_data, dt)
            cost = turnover * (open_cost + close_cost)
            report_rows.append({"date": dt, "return": portfolio_return, "bench": bench_return, "cost": cost})
            weight = 1.0 / len(next_holdings) if next_holdings else 0.0
            for inst in next_holdings:
                position_rows.append({"date": dt, "instrument": inst, "weight": weight})
            holdings = next_holdings
        report = pd.DataFrame(report_rows).set_index("date") if report_rows else pd.DataFrame(columns=["return", "bench", "cost"])
        positions = pd.DataFrame(position_rows)
        if report.empty:
            return {}, report, positions
        excess = report["return"] - report["bench"] - report["cost"]
        metrics = risk_metrics(excess)
        return metrics, report, positions


def _turnover(old: list[str], new: list[str]) -> float:
    if not old and not new:
        return 0.0
    old_set = set(old)
    new_set = set(new)
    return len(old_set.symmetric_difference(new_set)) / max(len(old_set | new_set), 1)


def _benchmark_return(market_data: pd.DataFrame, dt: pd.Timestamp) -> float:
    try:
        values = market_data.xs(dt, level="datetime")["$return"]
    except KeyError:
        return 0.0
    return float(values.mean()) if len(values) else 0.0

