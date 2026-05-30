"""No-qlib TopK Dropout 组合回测。"""

from __future__ import annotations

from datetime import date, datetime
import math
from pathlib import Path
from typing import Any

import polars as pl

from .risk import risk_metrics, risk_metrics_by_year


class NoQlibTopkDropoutBacktester:
    """TopK Dropout 的 no-qlib 初版实现。"""

    def __init__(self, config: dict[str, Any], market_data: pl.DataFrame) -> None:
        self.config = config
        self.market_data = market_data
        self.universe_mask = _load_resolved_universe_mask(config)
        self._polars_price_rows = _build_polars_price_rows(market_data)

    def run(self, prediction: pl.DataFrame) -> tuple[dict[str, Any], pl.DataFrame, pl.DataFrame]:
        """返回 metrics、daily report、positions。"""
        bt_cfg = self.config.get("backtest", {}).get("backtest", {})
        st_cfg = self.config.get("backtest", {}).get("strategy", {}).get("kwargs", {})
        start = _date_key(bt_cfg.get("start_time"))
        end = _date_key(bt_cfg.get("end_time"))
        topk = int(st_cfg.get("topk", 50))
        n_drop = int(st_cfg.get("n_drop", 5))
        account = float(bt_cfg.get("account", 100000000))
        risk_degree = float(st_cfg.get("risk_degree", 0.95))
        open_cost = float(bt_cfg.get("exchange_kwargs", {}).get("open_cost", 0.0))
        close_cost = float(bt_cfg.get("exchange_kwargs", {}).get("close_cost", 0.0))
        min_cost = float(bt_cfg.get("exchange_kwargs", {}).get("min_cost", 0.0))
        benchmark = bt_cfg.get("benchmark")
        pred = _prediction_by_date(prediction)
        dates = _market_dates(self.market_data, start, end)
        pred_dates = sorted(pred)
        holdings: list[str] = []
        amounts: dict[str, float] = {}
        cash = account
        previous_account_value = account
        report_rows = []
        position_rows = []
        last_close_prices: dict[str, float] = {}
        missing_price_examples: list[dict[str, str]] = []
        missing_close_valuation_count = 0
        missing_open_buy_skip_count = 0
        missing_open_sell_skip_count = 0
        for dt in dates:
            previous_holdings = list(holdings)
            signal_dt = _previous_signal_date(pred_dates, dt)
            if signal_dt is None:
                next_holdings = _filter_holdings_by_universe(holdings, self.universe_mask, dt)
            else:
                day_pred = pred.get(signal_dt, {})
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
            total_trade_value = 0.0
            skipped_sells: set[str] = set()
            for inst in list(sell_set):
                amount = amounts.get(inst, 0.0)
                if amount <= 0:
                    amounts.pop(inst, None)
                    continue
                open_price = _price(self.market_data, dt, inst, "$open", self._polars_price_rows)
                if not math.isfinite(open_price) or open_price <= 0:
                    missing_open_sell_skip_count += 1
                    _record_missing_price(
                        missing_price_examples,
                        market_data=self.market_data,
                        dt=dt,
                        instrument=inst,
                        field="$open",
                        action="skip_sell_keep_position",
                    )
                    skipped_sells.add(inst)
                    continue
                amounts.pop(inst, None)
                trade_value = amount * open_price
                trade_cost = _trade_cost(trade_value, close_cost, min_cost)
                cash += trade_value - trade_cost
                total_cost_value += trade_cost
                total_trade_value += trade_value
            if skipped_sells:
                buy_list = []
            buy_budget = cash * risk_degree / len(buy_list) if buy_list else 0.0
            for inst in buy_list:
                open_price = _price(self.market_data, dt, inst, "$open", self._polars_price_rows)
                if open_price <= 0 or not math.isfinite(open_price):
                    missing_open_buy_skip_count += 1
                    _record_missing_price(
                        missing_price_examples,
                        market_data=self.market_data,
                        dt=dt,
                        instrument=inst,
                        field="$open",
                        action="skip_buy",
                    )
                    continue
                trade_value = buy_budget
                if trade_value <= 0:
                    continue
                trade_cost = _trade_cost(trade_value, open_cost, min_cost)
                if trade_value + trade_cost > cash:
                    trade_value = max(cash / (1.0 + open_cost), 0.0)
                    trade_cost = _trade_cost(trade_value, open_cost, min_cost)
                amount = trade_value / open_price
                amounts[inst] = amounts.get(inst, 0.0) + amount
                cash -= trade_value + trade_cost
                total_cost_value += trade_cost
                total_trade_value += trade_value
            holdings = [stock for stock in next_holdings if stock in amounts]
            holdings.extend(stock for stock in previous_holdings if stock in skipped_sells and stock in amounts and stock not in holdings)
            stock_value = {}
            for inst, amount in amounts.items():
                close_price = _price(self.market_data, dt, inst, "$close", self._polars_price_rows)
                if math.isfinite(close_price) and close_price > 0:
                    last_close_prices[inst] = close_price
                elif inst in last_close_prices:
                    close_price = last_close_prices[inst]
                    missing_close_valuation_count += 1
                    _record_missing_price(
                        missing_price_examples,
                        market_data=self.market_data,
                        dt=dt,
                        instrument=inst,
                        field="$close",
                        action="carry_forward_last_close",
                    )
                else:
                    raise ValueError(f"missing close price with no carry-forward price: date={dt} instrument={inst}")
                stock_value[inst] = amount * close_price
            account_value = cash + float(sum(stock_value.values()))
            pre_cost_account_value = account_value + total_cost_value
            portfolio_return = pre_cost_account_value / previous_account_value - 1.0 if previous_account_value else 0.0
            bench_return = _benchmark_return(self.market_data, dt, benchmark=benchmark)
            cost = total_cost_value / previous_account_value if previous_account_value else 0.0
            turnover = _turnover(total_trade_value, previous_account_value)
            report_rows.append(
                {
                    "date": dt,
                    "return": portfolio_return,
                    "bench": bench_return,
                    "cost": cost,
                    "turnover": turnover,
                    "cash": cash,
                    "equity": account_value,
                }
            )
            for inst in holdings:
                weight = stock_value.get(inst, 0.0) / account_value if account_value else 0.0
                position_rows.append(
                    {
                        "date": dt,
                        "instrument": inst,
                        "weight": weight,
                        "amount": amounts.get(inst, 0.0),
                        "value": stock_value.get(inst, 0.0),
                    }
                )
            previous_account_value = account_value
        report = pl.DataFrame(report_rows) if report_rows else _empty_report_frame()
        positions = pl.DataFrame(position_rows) if position_rows else _empty_positions_frame()
        if report.is_empty():
            return {}, report, positions
        report = report.with_columns((pl.col("return") - pl.col("bench") - pl.col("cost")).alias("excess_return"))
        excess = report.get_column("excess_return")
        metrics = risk_metrics(excess)
        metrics["yearly_excess_return"] = risk_metrics_by_year(report.select(["date", "excess_return"]))
        metrics["missing_close_valuation_count"] = float(missing_close_valuation_count)
        metrics["missing_open_buy_skip_count"] = float(missing_open_buy_skip_count)
        metrics["missing_open_sell_skip_count"] = float(missing_open_sell_skip_count)
        metrics["missing_price_example_count"] = float(len(missing_price_examples))
        metrics["missing_price_examples"] = missing_price_examples
        return metrics, report, positions


def _previous_signal_date(pred_dates: list[date], trade_date: date) -> date | None:
    previous = [dt for dt in pred_dates if dt < trade_date]
    if not previous:
        return None
    return previous[-1]


def _load_resolved_universe_mask(config: dict[str, Any]) -> dict[date, set[str]]:
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
    mask: dict[date, set[str]] = {}
    for row in rows:
        trade_date = _date_key(row["trade_date"])
        mask.setdefault(trade_date, set()).add(str(row["instrument"]))
    return mask


def _filter_prediction_by_universe(
    pred_score: dict[str, float],
    universe_mask: dict[date, set[str]],
    trade_date: date,
) -> dict[str, float]:
    if not universe_mask:
        return pred_score
    allowed = universe_mask.get(_date_key(trade_date), set())
    if not allowed:
        return {}
    return {instrument: score for instrument, score in pred_score.items() if instrument in allowed}


def _filter_holdings_by_universe(
    holdings: list[str],
    universe_mask: dict[date, set[str]],
    trade_date: date,
) -> list[str]:
    if not universe_mask:
        return list(holdings)
    allowed = universe_mask.get(_date_key(trade_date), set())
    return [stock for stock in holdings if stock in allowed]


def _next_topk_dropout_holdings(
    *,
    holdings: list[str],
    pred_score: dict[str, float],
    topk: int,
    n_drop: int,
) -> list[str]:
    """Match qlib TopkDropoutStrategy's deterministic buy/sell selection."""
    current = [stock for stock in holdings if stock in pred_score]
    last = sorted(current, key=lambda stock: pred_score[stock], reverse=True)
    today = [
        stock
        for stock, _score in sorted(
            ((stock, score) for stock, score in pred_score.items() if stock not in set(last)),
            key=lambda item: item[1],
            reverse=True,
        )[: n_drop + topk - len(last)]
    ]
    combined = sorted(set(last) | set(today), key=lambda stock: pred_score[stock], reverse=True)
    sell = set(last[-n_drop:]) & set(combined[-n_drop:]) if n_drop > 0 else set()
    buy = today[: len(sell) + topk - len(last)]
    next_holdings = [stock for stock in holdings if stock not in set(sell)]
    next_holdings.extend([str(stock) for stock in buy if stock not in next_holdings])
    return next_holdings[:topk]


def _prediction_by_date(prediction: pl.DataFrame) -> dict[date, dict[str, float]]:
    if not isinstance(prediction, pl.DataFrame):
        raise TypeError(f"noqlib prediction must be a polars DataFrame, got {type(prediction).__name__}")
    rows = prediction.drop_nulls(["score"]).select(["datetime", "instrument", "score"]).to_dicts()
    by_date: dict[date, dict[str, float]] = {}
    for row in rows:
        by_date.setdefault(_date_key(row["datetime"]), {})[str(row["instrument"])] = float(row["score"])
    return by_date


def _benchmark_return(market_data: pl.DataFrame, dt: date, benchmark: str | None = None) -> float:
    day = market_data.filter(_date_filter_expr(dt))
    if benchmark and str(benchmark).lower() != "mean":
        candidates = {str(benchmark), str(benchmark).lower()}
        row = day.filter(pl.col("instrument").cast(pl.Utf8).is_in(candidates))
        if row.is_empty():
            raise KeyError(f"benchmark {benchmark} is missing from noqlib market data at {dt}")
        return float(row.get_column("$return")[0])
    return float(day.get_column("$return").mean() or 0.0) if not day.is_empty() else 0.0


def _price(
    market_data: pl.DataFrame,
    dt: date,
    instrument: str,
    field: str,
    polars_price_rows: dict[tuple[date, str], dict[str, float]] | None = None,
) -> float:
    rows = polars_price_rows or _build_polars_price_rows(market_data)
    return float(rows.get((_date_key(dt), str(instrument)), {}).get(field, float("nan")))


def _market_dates(market_data: pl.DataFrame, start: date, end: date) -> list[date]:
    return [
        _date_key(value)
        for value in market_data.select(pl.col("datetime")).unique().sort("datetime").get_column("datetime").to_list()
        if start <= _date_key(value) <= end
    ]


def _build_polars_price_rows(market_data: Any) -> dict[tuple[date, str], dict[str, float]]:
    if not isinstance(market_data, pl.DataFrame):
        return {}
    rows = market_data.select(["datetime", "instrument", "$open", "$close", "$return"]).to_dicts()
    return {
        (_date_key(row["datetime"]), str(row["instrument"])): {
            "$open": float(row["$open"]) if row["$open"] is not None else float("nan"),
            "$close": float(row["$close"]) if row["$close"] is not None else float("nan"),
            "$return": float(row["$return"]) if row["$return"] is not None else float("nan"),
        }
        for row in rows
    }


def _record_missing_price(
    examples: list[dict[str, str]],
    *,
    market_data: pl.DataFrame,
    dt: date,
    instrument: str,
    field: str,
    action: str,
) -> None:
    if len(examples) >= 20:
        return
    examples.append(
        {
            "date": _date_key(dt).strftime("%Y-%m-%d"),
            "instrument": str(instrument),
            "field": field,
            "action": action,
            "reason": _missing_price_reason(market_data, dt, instrument, field),
        }
    )


def _missing_price_reason(market_data: pl.DataFrame, dt: date, instrument: str, field: str) -> str:
    row = market_data.filter(_date_filter_expr(dt) & (pl.col("instrument").cast(pl.Utf8) == str(instrument)))
    if row.is_empty():
        return "no_price_row"
    if field not in row.columns:
        return "missing_price_field"
    try:
        value = float(row.get_column(field)[0])
    except (TypeError, ValueError):
        return "non_numeric_price"
    if not math.isfinite(value) or value <= 0:
        return "non_finite_or_non_positive_price"
    return "unknown"


def _trade_cost(trade_value: float, rate: float, min_cost: float) -> float:
    if trade_value <= 0 or rate <= 0:
        return 0.0
    return max(trade_value * rate, min_cost)


def _turnover(total_trade_value: float, previous_account_value: float) -> float:
    """Match qlib turnover: executed trade value over previous account value."""
    if previous_account_value <= 0:
        return 0.0
    return float(total_trade_value / previous_account_value)


def _date_key(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value)
    digits = "".join(char for char in text if char.isdigit())
    if len(digits) >= 8:
        return datetime.strptime(digits[:8], "%Y%m%d").date()
    return date.fromisoformat(text[:10])


def _date_filter_expr(value: date) -> pl.Expr:
    return pl.col("datetime").cast(pl.Date) == pl.lit(_date_key(value))


def _empty_report_frame() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "date": pl.Date,
            "return": pl.Float64,
            "bench": pl.Float64,
            "cost": pl.Float64,
            "turnover": pl.Float64,
            "cash": pl.Float64,
            "equity": pl.Float64,
        }
    )


def _empty_positions_frame() -> pl.DataFrame:
    return pl.DataFrame(
        schema={
            "date": pl.Date,
            "instrument": pl.Utf8,
            "weight": pl.Float64,
            "amount": pl.Float64,
            "value": pl.Float64,
        }
    )
