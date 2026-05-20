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


def test_select_benchmark_universe_asof_accepts_yyyymmdd_trade_date() -> None:
    from quantaalpha.backtest.benchmark_universe import select_benchmark_universe_asof

    index_weight = pl.DataFrame(
        {
            "index_code": ["000300.SH", "000300.SH"],
            "con_code": ["000001.SZ", "000002.SZ"],
            "trade_date": ["20240430", "20240430"],
            "weight": [0.1, 0.2],
        }
    )

    result = select_benchmark_universe_asof(index_weight, index_code="000300.SH", as_of_date="2024-05-20")

    assert result.get_column("instrument").to_list() == ["000001.SZ", "000002.SZ"]


def test_write_benchmark_instruments_file_writes_one_ts_code_per_line(tmp_path) -> None:
    from quantaalpha.backtest.benchmark_universe import write_benchmark_instruments_file

    index_weight = pl.DataFrame(
        {
            "index_code": ["000852.SH", "000852.SH", "000852.SH", "000300.SH"],
            "con_code": ["430001.BJ", "000001.SZ", "000001.SZ", "600000.SH"],
            "trade_date": [date(2024, 4, 30), date(2024, 4, 30), date(2024, 3, 29), date(2024, 4, 30)],
            "weight": [0.1, 0.2, 0.3, 0.4],
        }
    )
    target = tmp_path / "zz1000.txt"

    written = write_benchmark_instruments_file(
        index_weight,
        index_code="000852.SH",
        as_of_date="2024-05-20",
        output_path=target,
        exclude_markets=("BJ",),
    )

    assert written == target
    assert target.read_text(encoding="utf-8").splitlines() == ["000001.SZ"]
