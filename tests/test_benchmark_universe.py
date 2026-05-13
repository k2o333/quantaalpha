from __future__ import annotations

from datetime import date

import polars as pl


def test_select_benchmark_universe_asof_uses_latest_weight_date() -> None:
    from quantaalpha.backtest.benchmark_universe import select_benchmark_universe_asof

    index_weight = pl.DataFrame(
        {
            "index_code": ["000300.SH", "000300.SH", "000300.SH"],
            "con_code": ["000001.SZ", "000002.SZ", "000003.SZ"],
            "trade_date": [date(2024, 1, 1), date(2024, 1, 1), date(2024, 2, 1)],
            "weight": [0.1, 0.2, 0.3],
        }
    )

    result = select_benchmark_universe_asof(index_weight, index_code="000300.SH", as_of_date="2024-01-15")

    assert result.select(["instrument", "benchmark_weight"]).to_dicts() == [
        {"instrument": "000001.SZ", "benchmark_weight": 0.1},
        {"instrument": "000002.SZ", "benchmark_weight": 0.2},
    ]
