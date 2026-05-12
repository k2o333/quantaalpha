"""Rolling regression helpers for the shared polars expression kernel."""

from __future__ import annotations

import numpy as np
import pandas as pd
import polars as pl


def rolling_regression_frame(
    frame: pl.DataFrame,
    window: int,
    stat: str,
    x_values: np.ndarray | None = None,
) -> pl.DataFrame:
    """Return `(datetime, instrument, data)` for rolling regression stats."""
    if x_values is not None:
        return _rolling_regression_pandas_frame(frame, window, stat, x_values)
    n = float(window)
    sum_x = n * (n + 1.0) / 2.0
    sum_x2 = n * (n + 1.0) * (2.0 * n + 1.0) / 6.0
    mean_x = (n + 1.0) / 2.0
    denom = n * sum_x2 - sum_x * sum_x
    y = pl.col("data").fill_nan(None)
    sum_xy = pl.sum_horizontal([(window - lag) * y.shift(lag) for lag in range(window)])
    work = frame.with_columns(
        y.rolling_sum(window, min_samples=window).over("instrument").alias("_sum_y"),
        y.pow(2).rolling_sum(window, min_samples=window).over("instrument").alias("_sum_y2"),
        y.rolling_var(window, min_samples=window, ddof=0).over("instrument").alias("_var_y"),
        sum_xy.over("instrument").alias("_sum_xy"),
    )
    slope = (n * pl.col("_sum_xy") - sum_x * pl.col("_sum_y")) / denom
    if stat == "slope":
        return work.select("datetime", "instrument", slope.alias("data"))
    mean_y = pl.col("_sum_y") / n
    if stat == "rsquare":
        var_x = sum_x2 / n - mean_x * mean_x
        centered_cov = (
            pl.sum_horizontal([(window - lag - mean_x) * (y.shift(lag) - mean_y) for lag in range(window)]).over(
                "instrument"
            )
            / n
        )
        centered_var_y = (
            pl.sum_horizontal([(y.shift(lag) - mean_y).pow(2) for lag in range(window)]).over("instrument") / n
        )
        rsquare = centered_cov.pow(2) / (var_x * centered_var_y)
        return work.select(
            "datetime",
            "instrument",
            pl.when(
                (centered_var_y <= (2e-05**2))
                | (pl.col("_var_y") <= (2e-05**2))
                | rsquare.is_infinite()
                | rsquare.is_nan()
            )
            .then(None)
            .otherwise(rsquare)
            .alias("data"),
        )
    intercept = mean_y - slope * mean_x
    fitted_last = slope * n + intercept
    resi = y - fitted_last
    return work.select("datetime", "instrument", resi.alias("data"))


def rolling_regression_xy_frame(y_frame: pl.DataFrame, x_frame: pl.DataFrame, window: int, stat: str) -> pl.DataFrame:
    """Compatibility implementation for rolling regression against dynamic x values."""
    y_series = y_frame.to_pandas().set_index(["datetime", "instrument"])["data"].astype("float32")
    x_series = x_frame.to_pandas().set_index(["datetime", "instrument"])["data"].astype("float32")
    joined = pd.concat([y_series.rename("y"), x_series.rename("x")], axis=1).sort_index()
    pieces = []
    for instrument, part in joined.groupby(level="instrument", group_keys=False):
        y = part["y"].droplevel("instrument")
        x = part["x"].droplevel("instrument")
        rows = []
        for end in range(len(part)):
            if end + 1 < window:
                rows.append(np.nan)
                continue
            y_win = y.iloc[end + 1 - window : end + 1].to_numpy(dtype=float)
            x_win = x.iloc[end + 1 - window : end + 1].to_numpy(dtype=float)
            if np.isnan(y_win).any() or np.isnan(x_win).any():
                rows.append(np.nan)
                continue
            x_mean = x_win.mean()
            y_mean = y_win.mean()
            denom = float(((x_win - x_mean) ** 2).sum())
            if denom <= 0:
                rows.append(np.nan)
                continue
            slope = float(((x_win - x_mean) * (y_win - y_mean)).sum() / denom)
            intercept = y_mean - slope * x_mean
            if stat == "slope":
                rows.append(slope)
            else:
                rows.append(float(y_win[-1] - (slope * x_win[-1] + intercept)))
        out = pd.Series(rows, index=y.index)
        out.index = pd.MultiIndex.from_arrays([out.index, [instrument] * len(out)], names=["datetime", "instrument"])
        pieces.append(out)
    result = (
        pd.concat(pieces).sort_index().astype("float32").rename("data")
        if pieces
        else pd.Series(dtype="float32", index=y_series.index, name="data")
    )
    return pl.from_pandas(result.reset_index())


def _rolling_regression_pandas_frame(
    frame: pl.DataFrame,
    window: int,
    stat: str,
    x_values: np.ndarray | None = None,
) -> pl.DataFrame:
    series = frame.to_pandas().set_index(["datetime", "instrument"])["data"].astype("float32")

    def calc(values) -> float:
        if pd.isna(values).any():
            return np.nan
        x = np.asarray(x_values, dtype=float) if x_values is not None else np.arange(1, len(values) + 1, dtype=float)
        x_mean = x.mean()
        y_mean = values.mean()
        denom = float(((x - x_mean) ** 2).sum())
        if denom <= 0:
            if stat in {"slope", "resi"}:
                design = np.vstack([x, np.ones(len(x))]).T
                slope, intercept = np.linalg.lstsq(design, values, rcond=None)[0]
                if stat == "slope":
                    return float(slope)
                return float(values[-1] - (slope * x[-1] + intercept))
            return np.nan
        slope = float(((x - x_mean) * (values - y_mean)).sum() / denom)
        intercept = y_mean - slope * x_mean
        fitted = slope * x + intercept
        residual = values - fitted
        if stat == "resi":
            return float(residual[-1])
        total = float(((values - y_mean) ** 2).sum())
        if total <= 0:
            return np.nan
        return float(1.0 - ((residual**2).sum() / total))

    result = (
        series.groupby(level="instrument", group_keys=False)
        .rolling(window, min_periods=window)
        .apply(calc, raw=True)
        .droplevel(0)
        .sort_index()
        .astype("float32")
        .rename("data")
    )
    if stat == "rsquare":
        rolling_std = (
            series.groupby(level="instrument", group_keys=False)
            .rolling(window, min_periods=window)
            .std()
            .droplevel(0)
            .sort_index()
        )
        result = result.mask(np.isclose(rolling_std, 0, atol=2e-05)).astype("float32").rename("data")
    return pl.from_pandas(result.reset_index())
