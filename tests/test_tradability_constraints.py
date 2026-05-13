from __future__ import annotations

from datetime import date

import polars as pl


def test_build_tradability_mask_combines_calendar_suspension_and_st() -> None:
    from quantaalpha.backtest.tradability import build_tradability_mask

    universe = pl.DataFrame(
        {
            "datetime": [date(2024, 1, 2), date(2024, 1, 3), date(2024, 1, 3)],
            "instrument": ["000001.SZ", "000001.SZ", "000002.SZ"],
        }
    )
    trade_cal = pl.DataFrame({"cal_date": [date(2024, 1, 2), date(2024, 1, 3)], "is_open": [1, 1]})
    suspend = pl.DataFrame({"ts_code": ["000001.SZ"], "trade_date": [date(2024, 1, 3)]})
    st = pl.DataFrame({"ts_code": ["000002.SZ"], "trade_date": [date(2024, 1, 3)], "is_st": [1]})

    result = build_tradability_mask(universe, trade_cal=trade_cal, suspend_d=suspend, stock_st=st)

    assert result.select(["instrument", "datetime", "is_tradable"]).to_dicts() == [
        {"instrument": "000001.SZ", "datetime": date(2024, 1, 2), "is_tradable": True},
        {"instrument": "000001.SZ", "datetime": date(2024, 1, 3), "is_tradable": False},
        {"instrument": "000002.SZ", "datetime": date(2024, 1, 3), "is_tradable": False},
    ]
