from __future__ import annotations

from pathlib import Path

import pandas as pd
import polars as pl
import pytest


def test_write_cumulative_excess_parquet_uses_explicit_date_column(tmp_path: Path) -> None:
    from quantaalpha.backtest.artifacts import write_cumulative_excess_parquet

    frame = pd.DataFrame(
        {"daily_excess_return": [0.01, -0.02]},
        index=pd.Index(pd.to_datetime(["2021-01-01", "2021-01-02"]), name="trade_date"),
    )

    path = write_cumulative_excess_parquet(frame, tmp_path, "qlib_demo")

    assert path == tmp_path / "qlib_demo_cumulative_excess.parquet"
    assert path.exists()
    assert not (tmp_path / "qlib_demo_cumulative_excess.csv").exists()

    saved = pl.read_parquet(path)
    assert saved.columns == ["date", "daily_excess_return", "cumulative_excess_return"]
    assert saved["daily_excess_return"].to_list() == pytest.approx([0.01, -0.02])
    assert saved["cumulative_excess_return"].to_list() == pytest.approx([0.01, -0.01])
