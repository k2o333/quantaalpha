from __future__ import annotations

import builtins
import sys
from datetime import date
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_noqlib_market_provider_filters_by_resolved_universe_path(tmp_path, monkeypatch):
    from quantaalpha.backtest.noqlib.data_provider import NoQlibMarketDataProvider

    market_path = tmp_path / "market.csv"
    pl.DataFrame(
        [
            {"trade_date": "20260101", "ts_code": "000001.SZ", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "vol": 100.0, "amount": 100.0},
            {"trade_date": "20260101", "ts_code": "000002.SZ", "open": 2.0, "high": 2.0, "low": 2.0, "close": 2.0, "vol": 100.0, "amount": 200.0},
        ]
    ).write_csv(market_path)
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
    ).load_market_frame()

    assert market.get_column("instrument").unique().to_list() == ["000001.SZ"]


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
    market = pl.DataFrame(
        {
            "datetime": ["2026-01-01", "2026-01-01", "2026-01-02", "2026-01-02", "2026-01-03", "2026-01-03"],
            "instrument": ["000001.SZ", "000002.SZ", "000001.SZ", "000002.SZ", "000001.SZ", "000002.SZ"],
            "$open": [1.0] * 6,
            "$high": [1.0] * 6,
            "$low": [1.0] * 6,
            "$close": [1.0] * 6,
            "$volume": [100.0] * 6,
            "$vwap": [1.0] * 6,
            "$return": [0.0] * 6,
        }
    )
    prediction = pl.DataFrame(
        {
            "datetime": ["2026-01-01", "2026-01-01", "2026-01-02", "2026-01-02"],
            "instrument": ["000001.SZ", "000002.SZ", "000001.SZ", "000002.SZ"],
            "score": [1.0, 2.0, 1.0, 2.0],
        }
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

    assert positions.select(["date", "instrument"]).to_dicts() == [
        {"date": date(2026, 1, 2), "instrument": "000001.SZ"},
        {"date": date(2026, 1, 3), "instrument": "000002.SZ"},
    ]
