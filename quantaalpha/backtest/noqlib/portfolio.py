"""No-qlib TopK Dropout 组合回测。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import polars as pl

from .risk import risk_metrics


class NoQlibTopkDropoutBacktester:
    """TopK Dropout 的 no-qlib 初版实现。"""

    def __init__(self, config: dict[str, Any], market_data: pd.DataFrame) -> None:
        self.config = config
        self.market_data = market_data
        self.universe_mask = _load_resolved_universe_mask(config)

    def run(self, prediction: pd.Series) -> tuple[dict[str, float], pd.DataFrame, pd.DataFrame]:
        """返回 metrics、daily report、positions。"""
        bt_cfg = self.config.get("backtest", {}).get("backtest", {})
        st_cfg = self.config.get("backtest", {}).get("strategy", {}).get("kwargs", {})
        start = pd.Timestamp(bt_cfg.get("start_time"))
        end = pd.Timestamp(bt_cfg.get("end_time"))
        topk = int(st_cfg.get("topk", 50))
        n_drop = int(st_cfg.get("n_drop", 5))
        account = float(bt_cfg.get("account", 100000000))
        risk_degree = float(st_cfg.get("risk_degree", 0.95))
        open_cost = float(bt_cfg.get("exchange_kwargs", {}).get("open_cost", 0.0))
        close_cost = float(bt_cfg.get("exchange_kwargs", {}).get("close_cost", 0.0))
        min_cost = float(bt_cfg.get("exchange_kwargs", {}).get("min_cost", 0.0))
        benchmark = bt_cfg.get("benchmark")
        pred = prediction.sort_index()
        dates = sorted(
            dt
            for dt in self.market_data.index.get_level_values("datetime").unique()
            if start <= dt <= end
        )
        pred_dates = sorted(pred.index.get_level_values("datetime").unique())
        holdings: list[str] = []
        amounts: dict[str, float] = {}
        cash = account
        previous_account_value = account
        report_rows = []
        position_rows = []
        for dt in dates:
            signal_dt = _previous_signal_date(pred_dates, dt)
            if signal_dt is None:
                next_holdings = _filter_holdings_by_universe(holdings, self.universe_mask, dt)
            else:
                day_pred = pred.xs(signal_dt, level="datetime").dropna()
                day_pred = _filter_prediction_by_universe(day_pred, self.universe_mask, dt)
                next_holdings = _next_topk_dropout_holdings(
                    holdings=_filter_holdings_by_universe(holdings, self.universe_mask, dt),
                    pred_score=day_pred,
                    topk=topk,
                    n_drop=n_drop,
                )
            sell_set = set(holdings) - set(next_holdings)
            buy_list = [stock for stock in next_holdings if stock not in set(holdings)]
            total_cost_value = 0.0
            for inst in list(sell_set):
                amount = amounts.pop(inst, 0.0)
                if amount <= 0:
                    continue
                trade_value = amount * _price(self.market_data, dt, inst, "$open")
                trade_cost = _trade_cost(trade_value, close_cost, min_cost)
                cash += trade_value - trade_cost
                total_cost_value += trade_cost
            buy_budget = cash * risk_degree / len(buy_list) if buy_list else 0.0
            for inst in buy_list:
                open_price = _price(self.market_data, dt, inst, "$open")
                if open_price <= 0 or not np.isfinite(open_price):
                    continue
                trade_value = buy_budget
                trade_cost = _trade_cost(trade_value, open_cost, min_cost)
                if trade_value + trade_cost > cash:
                    trade_value = max(cash / (1.0 + open_cost), 0.0)
                    trade_cost = _trade_cost(trade_value, open_cost, min_cost)
                amount = trade_value / open_price
                amounts[inst] = amounts.get(inst, 0.0) + amount
                cash -= trade_value + trade_cost
                total_cost_value += trade_cost
            holdings = [stock for stock in next_holdings if stock in amounts]
            stock_value = {
                inst: amount * _price(self.market_data, dt, inst, "$close")
                for inst, amount in amounts.items()
            }
            account_value = cash + float(sum(stock_value.values()))
            pre_cost_account_value = account_value + total_cost_value
            portfolio_return = pre_cost_account_value / previous_account_value - 1.0 if previous_account_value else 0.0
            bench_return = _benchmark_return(self.market_data, dt, benchmark=benchmark)
            cost = total_cost_value / previous_account_value if previous_account_value else 0.0
            report_rows.append({"date": dt, "return": portfolio_return, "bench": bench_return, "cost": cost})
            for inst in holdings:
                weight = stock_value.get(inst, 0.0) / account_value if account_value else 0.0
                position_rows.append({"date": dt, "instrument": inst, "weight": weight})
            previous_account_value = account_value
        report = pd.DataFrame(report_rows).set_index("date") if report_rows else pd.DataFrame(columns=["return", "bench", "cost"])
        positions = pd.DataFrame(position_rows)
        if report.empty:
            return {}, report, positions
        excess = report["return"] - report["bench"] - report["cost"]
        metrics = risk_metrics(excess)
        return metrics, report, positions


def _previous_signal_date(pred_dates: list[pd.Timestamp], trade_date: pd.Timestamp) -> pd.Timestamp | None:
    previous = [dt for dt in pred_dates if dt < trade_date]
    if not previous:
        return None
    return previous[-1]


def _load_resolved_universe_mask(config: dict[str, Any]) -> dict[pd.Timestamp, set[str]]:
    noqlib_config = config.get("backtest_runtime", {}).get("noqlib", {})
    universe_path = noqlib_config.get("resolved_universe_path")
    if not universe_path:
        return {}
    path = Path(str(universe_path))
    if not path.exists():
        raise FileNotFoundError(f"resolved_universe_path not found: {path}")
    frame = pl.read_parquet(path)
    if "trade_date" not in frame.columns or "instrument" not in frame.columns:
        raise ValueError("resolved_universe_path must contain trade_date and instrument columns")
    mask_col = "eligible" if "eligible" in frame.columns else "selected"
    if mask_col not in frame.columns:
        raise ValueError("resolved_universe_path must contain eligible or selected column")
    rows = (
        frame.filter(pl.col(mask_col).cast(pl.Boolean, strict=False).fill_null(False))
        .select(
            pl.col("trade_date").cast(pl.Utf8),
            pl.col("instrument").cast(pl.Utf8),
        )
        .to_dicts()
    )
    mask: dict[pd.Timestamp, set[str]] = {}
    for row in rows:
        trade_date = pd.Timestamp(str(row["trade_date"])).normalize()
        mask.setdefault(trade_date, set()).add(str(row["instrument"]))
    return mask


def _filter_prediction_by_universe(
    pred_score: pd.Series,
    universe_mask: dict[pd.Timestamp, set[str]],
    trade_date: pd.Timestamp,
) -> pd.Series:
    if not universe_mask:
        return pred_score
    allowed = universe_mask.get(pd.Timestamp(trade_date).normalize(), set())
    if not allowed:
        return pred_score.iloc[0:0]
    return pred_score[pred_score.index.isin(allowed)]


def _filter_holdings_by_universe(
    holdings: list[str],
    universe_mask: dict[pd.Timestamp, set[str]],
    trade_date: pd.Timestamp,
) -> list[str]:
    if not universe_mask:
        return list(holdings)
    allowed = universe_mask.get(pd.Timestamp(trade_date).normalize(), set())
    return [stock for stock in holdings if stock in allowed]


def _next_topk_dropout_holdings(
    *,
    holdings: list[str],
    pred_score: pd.Series,
    topk: int,
    n_drop: int,
) -> list[str]:
    """Match qlib TopkDropoutStrategy's deterministic buy/sell selection."""
    current = pd.Index([stock for stock in holdings if stock in pred_score.index])
    last = pred_score.reindex(current).sort_values(ascending=False).index
    today = pred_score[~pred_score.index.isin(last)].sort_values(ascending=False).index[
        : n_drop + topk - len(last)
    ]
    comb = pred_score.reindex(last.union(pd.Index(today))).sort_values(ascending=False).index
    sell = last[last.isin(list(comb[-n_drop:]))] if n_drop > 0 else pd.Index([])
    buy = today[: len(sell) + topk - len(last)]
    next_holdings = [stock for stock in holdings if stock not in set(sell)]
    next_holdings.extend([str(stock) for stock in buy if stock not in next_holdings])
    return next_holdings[:topk]


def _benchmark_return(market_data: pd.DataFrame, dt: pd.Timestamp, benchmark: str | None = None) -> float:
    if benchmark and str(benchmark).lower() != "mean":
        for candidate in {str(benchmark), str(benchmark).lower()}:
            try:
                return float(market_data.loc[(dt, candidate), "$return"])
            except KeyError:
                continue
        raise KeyError(f"benchmark {benchmark} is missing from noqlib market data at {dt}")
    try:
        values = market_data.xs(dt, level="datetime")["$return"]
    except KeyError:
        return 0.0
    return float(values.mean()) if len(values) else 0.0


def _price(market_data: pd.DataFrame, dt: pd.Timestamp, instrument: str, field: str) -> float:
    try:
        return float(market_data.loc[(dt, instrument), field])
    except KeyError:
        return float("nan")


def _trade_cost(trade_value: float, rate: float, min_cost: float) -> float:
    if trade_value <= 0 or rate <= 0:
        return 0.0
    return max(trade_value * rate, min_cost)
