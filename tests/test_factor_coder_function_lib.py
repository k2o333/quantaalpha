import numpy as np
import pandas as pd

from quantaalpha.factors.coder.function_lib import (
    DELTA,
    KURT,
    MAX,
    MIN,
    SKEW,
    TS_DELTA,
    TS_KURT,
    TS_SKEW,
)


def _panel(values):
    index = pd.MultiIndex.from_tuples(
        [
            ("2024-01-01", "a"),
            ("2024-01-02", "a"),
            ("2024-01-03", "a"),
            ("2024-01-04", "a"),
            ("2024-01-01", "b"),
            ("2024-01-02", "b"),
            ("2024-01-03", "b"),
            ("2024-01-04", "b"),
        ],
        names=["datetime", "instrument"],
    )
    return pd.DataFrame({"$return": values}, index=index)


def test_rolling_skew_and_kurt_use_vectorized_pandas_semantics():
    df = _panel([1.0, 2.0, 4.0, 8.0, 2.0, 3.0, 5.0, 9.0])

    skew = TS_SKEW(df, 3)
    kurt = TS_KURT(df, 4)

    expected_skew = df.groupby("instrument").transform(
        lambda x: x.rolling(3, min_periods=3).skew()
    )
    expected_kurt = df.groupby("instrument").transform(
        lambda x: x.rolling(4, min_periods=4).kurt()
    )
    pd.testing.assert_frame_equal(skew, expected_skew)
    pd.testing.assert_frame_equal(kurt, expected_kurt)


def test_cross_section_stats_and_min_max_single_arg_registration():
    df = _panel([1.0, 2.0, 4.0, 8.0, 2.0, 3.0, 5.0, 9.0])

    pd.testing.assert_frame_equal(SKEW(df), df.groupby("datetime").transform("skew"))
    pd.testing.assert_frame_equal(KURT(df), df.groupby("datetime").transform(lambda x: x.kurt()))
    pd.testing.assert_frame_equal(MIN(df), df.groupby("datetime").transform("min"))
    pd.testing.assert_frame_equal(MAX(df), df.groupby("datetime").transform("max"))


def test_ts_delta_alias_matches_delta():
    df = _panel([1.0, 2.0, 4.0, 8.0, 2.0, 3.0, 5.0, 9.0])

    pd.testing.assert_frame_equal(TS_DELTA(df, 2), DELTA(df, 2))


def test_min_max_pairwise_still_work_after_single_arg_support():
    left = _panel([1.0, 5.0, 3.0, 7.0, 2.0, 4.0, 6.0, 8.0])
    right = _panel([2.0, 4.0, 4.0, 6.0, 1.0, 5.0, 5.0, 9.0])

    np.testing.assert_allclose(MIN(left, right).to_numpy(), np.minimum(left, right).to_numpy())
    np.testing.assert_allclose(MAX(left, right).to_numpy(), np.maximum(left, right).to_numpy())
