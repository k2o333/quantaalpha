from __future__ import annotations

import pandas as pd


def test_h5_oracle_contract_shape_and_sorting(tmp_path) -> None:
    from quantaalpha.factors.coder.runtime_data import read_h5_oracle_result

    index = pd.MultiIndex.from_tuples(
        [
            (pd.Timestamp("2020-01-02"), "000001.SZ"),
            (pd.Timestamp("2020-01-01"), "000001.SZ"),
        ],
        names=["datetime", "instrument"],
    )
    pd.Series([2.0, 1.0], index=index, name="alpha").to_hdf(tmp_path / "result.h5", key="data")

    result = read_h5_oracle_result(tmp_path / "result.h5", factor_name="alpha")

    assert result.index.names == ["datetime", "instrument"]
    assert list(result.columns) == ["alpha"]
    assert result.index.tolist() == [
        (pd.Timestamp("2020-01-01"), "000001.SZ"),
        (pd.Timestamp("2020-01-02"), "000001.SZ"),
    ]

