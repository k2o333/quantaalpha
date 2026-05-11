from __future__ import annotations

import builtins
import sys
from pathlib import Path

import pandas as pd
import polars as pl

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_noqlib_market_provider_filters_by_resolved_universe_path(tmp_path, monkeypatch):
    from quantaalpha.backtest.noqlib.data_provider import NoQlibMarketDataProvider

    market_path = tmp_path / "market.csv"
    pd.DataFrame(
        [
            {"trade_date": "20260101", "ts_code": "000001.SZ", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "vol": 100.0, "amount": 100.0},
            {"trade_date": "20260101", "ts_code": "000002.SZ", "open": 2.0, "high": 2.0, "low": 2.0, "close": 2.0, "vol": 100.0, "amount": 200.0},
        ]
    ).to_csv(market_path, index=False)
    universe_path = tmp_path / "universe.parquet"
    pl.DataFrame(
        [
            {"trade_date": "2026-01-01", "instrument": "000001.SZ", "selected": True, "eligible": True},
            {"trade_date": "2026-01-01", "instrument": "000002.SZ", "selected": False, "eligible": False},
        ]
    ).write_parquet(universe_path)
    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "qlib" or name.startswith("qlib."):
            raise AssertionError(f"noqlib provider imported qlib: {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    market = NoQlibMarketDataProvider(
        {
            "backtest_runtime": {
                "noqlib": {
                    "market_data_path": str(market_path),
                    "resolved_universe_path": str(universe_path),
                }
            }
        }
    ).load_market_data()

    assert market.index.get_level_values("instrument").unique().tolist() == ["000001.SZ"]


def test_noqlib_portfolio_filters_daily_candidates_by_resolved_universe_path(tmp_path):
    from quantaalpha.backtest.noqlib.portfolio import NoQlibTopkDropoutBacktester

    universe_path = tmp_path / "universe.parquet"
    pl.DataFrame(
        [
            {"trade_date": "2026-01-02", "instrument": "000001.SZ", "selected": True, "eligible": True},
            {"trade_date": "2026-01-02", "instrument": "000002.SZ", "selected": True, "eligible": False},
            {"trade_date": "2026-01-03", "instrument": "000001.SZ", "selected": True, "eligible": False},
            {"trade_date": "2026-01-03", "instrument": "000002.SZ", "selected": True, "eligible": True},
        ]
    ).write_parquet(universe_path)
    dates = pd.to_datetime(["2026-01-01", "2026-01-02", "2026-01-03"])
    market_index = pd.MultiIndex.from_product([dates, ["000001.SZ", "000002.SZ"]], names=["datetime", "instrument"])
    market = pd.DataFrame(
        {
            "$open": 1.0,
            "$high": 1.0,
            "$low": 1.0,
            "$close": 1.0,
            "$volume": 100.0,
            "$vwap": 1.0,
            "$return": 0.0,
        },
        index=market_index,
    )
    prediction = pd.Series(
        [1.0, 2.0, 1.0, 2.0],
        index=pd.MultiIndex.from_tuples(
            [
                (pd.Timestamp("2026-01-01"), "000001.SZ"),
                (pd.Timestamp("2026-01-01"), "000002.SZ"),
                (pd.Timestamp("2026-01-02"), "000001.SZ"),
                (pd.Timestamp("2026-01-02"), "000002.SZ"),
            ],
            names=["datetime", "instrument"],
        ),
    )
    config = {
        "backtest_runtime": {"noqlib": {"resolved_universe_path": str(universe_path)}},
        "backtest": {
            "strategy": {"kwargs": {"topk": 1, "n_drop": 1, "risk_degree": 1.0}},
            "backtest": {
                "start_time": "2026-01-02",
                "end_time": "2026-01-03",
                "account": 1000.0,
                "benchmark": "mean",
                "exchange_kwargs": {},
            },
        },
    }

    _metrics, _report, positions = NoQlibTopkDropoutBacktester(config, market).run(prediction)

    assert positions[["date", "instrument"]].to_dict("records") == [
        {"date": pd.Timestamp("2026-01-02"), "instrument": "000001.SZ"},
        {"date": pd.Timestamp("2026-01-03"), "instrument": "000002.SZ"},
    ]
