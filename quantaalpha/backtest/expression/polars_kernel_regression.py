"""Rolling regression helpers for the shared polars expression kernel."""

from __future__ import annotations

import numpy as np
import polars as pl


def rolling_regression_frame(
    frame: pl.DataFrame,
    window: int,
    stat: str,
    x_values: np.ndarray | None = None,
) -> pl.DataFrame:
    """Return `(datetime, instrument, data)` for rolling regression stats."""
    if x_values is not None:
        return _rolling_regression_custom_sequence_frame(frame, window, stat, x_values)
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
    """Polars-backed rolling regression against dynamic x values."""
    joined = (
        y_frame.rename({"data": "y"})
        .join(x_frame.rename({"data": "x"}), on=["datetime", "instrument"], how="left")
        .sort(["instrument", "datetime"])
    )
    pieces: list[pl.DataFrame] = []
    for part in joined.partition_by("instrument", maintain_order=True):
        y = part.get_column("y").cast(pl.Float64).to_numpy()
        x = part.get_column("x").cast(pl.Float64).to_numpy()
        rows = []
        for end in range(part.height):
            if end + 1 < window:
                rows.append(None)
                continue
            y_win = y[end + 1 - window : end + 1]
            x_win = x[end + 1 - window : end + 1]
            if np.isnan(y_win).any() or np.isnan(x_win).any():
                rows.append(None)
                continue
            x_mean = x_win.mean()
            y_mean = y_win.mean()
            denom = float(((x_win - x_mean) ** 2).sum())
            if denom <= 0:
                rows.append(None)
                continue
            slope = float(((x_win - x_mean) * (y_win - y_mean)).sum() / denom)
            intercept = y_mean - slope * x_mean
            if stat == "slope":
                rows.append(slope)
            else:
                rows.append(float(y_win[-1] - (slope * x_win[-1] + intercept)))
        pieces.append(part.select("datetime", "instrument").with_columns(pl.Series("data", rows, dtype=pl.Float32)))
    if not pieces:
        return joined.select("datetime", "instrument").with_columns(pl.lit(None, dtype=pl.Float32).alias("data"))
    return pl.concat(pieces, how="vertical").sort(["datetime", "instrument"])


def _rolling_regression_custom_sequence_frame(
    frame: pl.DataFrame,
    window: int,
    stat: str,
    x_values: np.ndarray | None = None,
) -> pl.DataFrame:
    x = np.asarray(x_values, dtype=float) if x_values is not None else np.arange(1, window + 1, dtype=float)

    def calc(values) -> float:
        arr = values.to_numpy().astype(float)
        if np.isnan(arr).any():
            return None
        x_mean = x.mean()
        y_mean = arr.mean()
        denom = float(((x - x_mean) ** 2).sum())
        if denom <= 0:
            if stat in {"slope", "resi"}:
                design = np.vstack([x, np.ones(len(x))]).T
                slope, intercept = np.linalg.lstsq(design, arr, rcond=None)[0]
                if stat == "slope":
                    return float(slope)
                return float(arr[-1] - (slope * x[-1] + intercept))
            return None
        slope = float(((x - x_mean) * (arr - y_mean)).sum() / denom)
        intercept = y_mean - slope * x_mean
        fitted = slope * x + intercept
        residual = arr - fitted
        if stat == "resi":
            return float(residual[-1])
        total = float(((arr - y_mean) ** 2).sum())
        if total <= 0:
            return None
        return float(1.0 - ((residual**2).sum() / total))

    result = frame.select(
        "datetime",
        "instrument",
        pl.col("data")
        .fill_nan(None)
        .rolling_map(calc, window_size=window, min_samples=window)
        .over("instrument")
        .cast(pl.Float32)
        .alias("data"),
    )
    if stat == "rsquare":
        result = result.join(
            frame.select(
                "datetime",
                "instrument",
                pl.col("data").rolling_std(window, min_samples=window).over("instrument").alias("_rolling_std"),
            ),
            on=["datetime", "instrument"],
            how="left",
        ).select(
            "datetime",
            "instrument",
            pl.when(pl.col("_rolling_std").abs() <= 2e-05).then(None).otherwise(pl.col("data")).alias("data"),
        )
    return result
