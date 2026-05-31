from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

import numpy as np
import polars as pl

from quantaalpha.log import logger


DEFAULT_QUALITY_OVERLAY_CONFIG: dict[str, Any] = {
    "expression_static": {
        "lookahead_severity": "critical",
        "anti_pattern_severity": "major",
    },
    "pre_backtest": {
        "min_valid_ratio": 0.65,
        "max_nan_ratio": 0.35,
        "min_unique_values": 20,
        "min_active_days_ratio": 0.70,
        "max_constant_day_ratio": 0.20,
        "max_extreme_zscore_ratio": 0.03,
        "min_cross_section_coverage": 0.60,
    },
    "full_backtest": {},
    "oos": {},
}


def load_quality_overlay_config(config: dict[str, Any] | None) -> dict[str, Any]:
    source = dict(config or {})
    if "quality_overlay" in source and isinstance(source["quality_overlay"], dict):
        source = dict(source["quality_overlay"])
    return _deep_merge(DEFAULT_QUALITY_OVERLAY_CONFIG, source)


def filter_pre_backtest_survivors_polars(
    factor_df: pl.DataFrame,
    config: dict[str, Any] | None = None,
) -> tuple[pl.DataFrame, dict[str, dict[str, Any]]]:
    diagnostics = pre_backtest_screen_polars(factor_df, config)
    keep = [col for col in _value_columns(factor_df) if diagnostics.get(str(col), {}).get("passed")]
    if not keep:
        return factor_df.select(["datetime", "instrument"]).head(0), diagnostics
    cleaned = _clean_factor_frame(factor_df)
    return cleaned.select(["datetime", "instrument", *keep]).drop_nulls(subset=keep), diagnostics


def pre_backtest_screen_polars(factor_df: pl.DataFrame, config: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    cfg = load_quality_overlay_config({"pre_backtest": config or {}}).get("pre_backtest", {})
    cleaned = _clean_factor_frame(factor_df)
    results: dict[str, dict[str, Any]] = {}
    for col in _value_columns(cleaned):
        metrics = _pre_backtest_metrics(cleaned, col)
        reasons = _pre_backtest_failure_reasons(metrics, cfg)
        results[str(col)] = {
            "passed": not reasons,
            "failure_reasons": reasons,
            "metrics": metrics,
            **metrics,
        }
        _log_quality_overlay_event(
            "pre_backtest",
            "kept" if not reasons else "dropped",
            factor_name=str(col),
            metrics=metrics,
            reasons=reasons,
        )
    return results


def compute_tradability_metrics_polars(
    factor: pl.DataFrame,
    label: pl.DataFrame,
    *,
    cost_rate: float = 0.001,
    n_groups: int = 5,
) -> dict[str, float]:
    aligned = _align_signal_frames(factor, label).drop_nulls(["factor", "label"])
    if aligned.is_empty():
        return _empty_tradability_metrics()
    group_count = max(2, int(n_groups))
    daily_positions = _daily_long_short_positions(aligned, n_groups=group_count)
    turnover = _mean_turnover(daily_positions)
    group_means, long_short = _group_return_profile(aligned, n_groups=group_count)
    monotonicity = _monotonicity_score(group_means)
    daily_spread = _daily_long_short_spread(aligned, n_groups=group_count)
    gross_return = float(np.mean(daily_spread)) if daily_spread else 0.0
    cost_adjusted = gross_return - float(cost_rate) * turnover
    cost_adjusted_ir = _series_ir([value - float(cost_rate) * turnover for value in daily_spread])
    return {
        "turnover": turnover,
        "cost_adjusted_return": cost_adjusted,
        "cost_adjusted_information_ratio": cost_adjusted_ir,
        "cost_adjusted_ir": cost_adjusted_ir,
        "group_monotonicity_score": monotonicity,
        "long_short_spread": long_short,
        "rank_ic_after_cost": cost_adjusted_ir,
    }


def compute_oos_rank_ic_metrics_polars(
    factor: pl.DataFrame,
    label: pl.DataFrame,
    *,
    recent_trading_days: int = 250,
) -> dict[str, float]:
    daily = _daily_rank_ic_frame(factor, label)
    if daily.is_empty():
        return {
            "rank_ic_train": 0.0,
            "rank_ic_valid": 0.0,
            "rank_ic_test": 0.0,
            "rank_ic_recent": 0.0,
            "positive_year_ratio": 0.0,
            "worst_year_rank_ic": 0.0,
            "ic_std_by_year": 0.0,
            "ic_decay": 0.0,
        }
    values = [float(value) for value in daily.get_column("rank_ic").to_list()]
    n = len(values)
    train_end = max(1, int(n * 0.60))
    valid_end = max(train_end + 1, int(n * 0.80)) if n > 2 else n
    train = values[:train_end]
    valid = values[train_end:valid_end]
    test = values[valid_end:] if valid_end < n else values[-1:]
    recent = values[-int(recent_trading_days) :]
    yearly = daily.with_columns(pl.col("datetime").dt.year().alias("year")).group_by("year").agg(pl.col("rank_ic").mean().alias("rank_ic"))
    yearly_values = [float(value) for value in yearly.get_column("rank_ic").to_list()]
    rank_ic_train = _safe_mean(train)
    rank_ic_test = _safe_mean(test)
    return {
        "rank_ic_train": rank_ic_train,
        "rank_ic_valid": _safe_mean(valid),
        "rank_ic_test": rank_ic_test,
        "rank_ic_recent": _safe_mean(recent),
        "positive_year_ratio": float(np.mean([value > 0 for value in yearly_values])) if yearly_values else 0.0,
        "worst_year_rank_ic": float(min(yearly_values)) if yearly_values else 0.0,
        "ic_std_by_year": float(np.std(yearly_values)) if yearly_values else 0.0,
        "ic_decay": float(rank_ic_test / (abs(rank_ic_train) + 1e-12)),
    }


def _value_columns(frame: pl.DataFrame) -> list[str]:
    return [column for column in frame.columns if column not in {"datetime", "instrument"}]


def _clean_factor_frame(frame: pl.DataFrame) -> pl.DataFrame:
    return frame.with_columns(*[pl.when(pl.col(column).is_infinite() | pl.col(column).is_nan()).then(None).otherwise(pl.col(column).cast(pl.Float64, strict=False)).alias(column) for column in _value_columns(frame)])


def _pre_backtest_metrics(frame: pl.DataFrame, column: str) -> dict[str, float | int]:
    total = int(frame.height)
    if total == 0:
        return {
            "valid_ratio": 0.0,
            "nan_ratio": 1.0,
            "unique_values": 0,
            "active_days_ratio": 0.0,
            "constant_day_ratio": 1.0,
            "extreme_zscore_ratio": 0.0,
            "cross_section_coverage": 0.0,
        }
    stats = frame.select(
        pl.col(column).is_not_null().mean().alias("valid_ratio"),
        pl.col(column).is_null().mean().alias("nan_ratio"),
        pl.col(column).drop_nulls().n_unique().alias("unique_values"),
    ).row(0, named=True)
    active_days_ratio, constant_day_ratio, coverage = _cross_section_metrics(frame, column)
    non_null = frame.select(column).drop_nulls()
    extreme_ratio = 0.0
    if non_null.height > 1:
        mean_value = non_null.get_column(column).mean()
        std_value = non_null.get_column(column).std()
        if std_value is not None and float(std_value) > 1e-12 and mean_value is not None:
            extreme_ratio = float(non_null.select((((pl.col(column) - float(mean_value)) / float(std_value)).abs() > 8).mean()).item() or 0.0)
    return {
        "valid_ratio": float(stats["valid_ratio"] or 0.0),
        "nan_ratio": float(stats["nan_ratio"] or 0.0),
        "unique_values": int(stats["unique_values"] or 0),
        "active_days_ratio": active_days_ratio,
        "constant_day_ratio": constant_day_ratio,
        "extreme_zscore_ratio": extreme_ratio,
        "cross_section_coverage": coverage,
    }


def _cross_section_metrics(frame: pl.DataFrame, column: str) -> tuple[float, float, float]:
    daily = frame.group_by("datetime").agg(
        pl.len().alias("total"),
        pl.col(column).is_not_null().sum().alias("valid_count"),
        pl.col(column).drop_nulls().n_unique().alias("unique_count"),
    )
    if daily.is_empty():
        return 0.0, 1.0, 0.0
    daily = daily.with_columns(
        pl.when(pl.col("total") >= 2).then(pl.col("valid_count") >= 2).otherwise(pl.col("valid_count") > 0).cast(pl.Float64).alias("active"),
        (pl.col("unique_count") <= pl.when(pl.col("total") <= 2).then(1).otherwise(2)).cast(pl.Float64).alias("constant"),
        (pl.col("valid_count") / pl.col("total")).alias("coverage"),
    )
    row = daily.select(
        pl.col("active").mean().alias("active_days_ratio"),
        pl.col("constant").mean().alias("constant_day_ratio"),
        pl.col("coverage").mean().alias("cross_section_coverage"),
    ).row(0, named=True)
    return (
        float(row["active_days_ratio"] or 0.0),
        float(row["constant_day_ratio"] if row["constant_day_ratio"] is not None else 1.0),
        float(row["cross_section_coverage"] or 0.0),
    )


def _pre_backtest_failure_reasons(metrics: dict[str, float | int], cfg: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if float(metrics["valid_ratio"]) < float(cfg.get("min_valid_ratio", 0.65)):
        reasons.append("low_coverage")
    if float(metrics["nan_ratio"]) > float(cfg.get("max_nan_ratio", 0.35)):
        reasons.append("too_many_nan")
    if int(metrics["unique_values"]) < int(cfg.get("min_unique_values", 20)):
        reasons.append("constant_signal")
    if float(metrics["active_days_ratio"]) < float(cfg.get("min_active_days_ratio", 0.70)):
        reasons.append("low_active_days")
    if float(metrics["constant_day_ratio"]) > float(cfg.get("max_constant_day_ratio", 0.20)):
        reasons.append("constant_signal")
    if float(metrics["extreme_zscore_ratio"]) > float(cfg.get("max_extreme_zscore_ratio", 0.03)):
        reasons.append("extreme_values")
    if float(metrics["cross_section_coverage"]) < float(cfg.get("min_cross_section_coverage", 0.60)):
        reasons.append("low_cross_section_coverage")
    return sorted(set(reasons))


def _align_signal_frames(factor: pl.DataFrame, label: pl.DataFrame) -> pl.DataFrame:
    factor_frame = _normalize_signal_frame(factor, "factor")
    label_frame = _normalize_signal_frame(label, "label")
    return factor_frame.join(label_frame, on=["datetime", "instrument"], how="inner")


def _normalize_signal_frame(frame: pl.DataFrame, value_column: str) -> pl.DataFrame:
    if not isinstance(frame, pl.DataFrame):
        raise TypeError(f"{value_column} must be a polars DataFrame, got {type(frame).__name__}")
    required = {"datetime", "instrument"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{value_column} frame missing key columns: {sorted(missing)}")
    if value_column not in frame.columns:
        candidates = [column for column in frame.columns if column not in required]
        if len(candidates) != 1:
            raise ValueError(f"{value_column} frame must contain {value_column} or exactly one value column")
        frame = frame.rename({candidates[0]: value_column})
    datetime_expr = pl.col("datetime").str.strptime(pl.Datetime("ns"), strict=False) if frame.schema["datetime"] == pl.Utf8 else pl.col("datetime").cast(pl.Datetime("ns"), strict=False)
    return frame.select(["datetime", "instrument", value_column]).with_columns(
        datetime_expr.alias("datetime"),
        pl.col("instrument").cast(pl.Utf8),
        pl.col(value_column).cast(pl.Float64, strict=False),
    )


def _daily_long_short_positions(aligned: pl.DataFrame, n_groups: int) -> list[set[Any]]:
    positions: list[set[Any]] = []
    for _date, day_frame in aligned.partition_by("datetime", as_dict=True, maintain_order=True).items():
        ranked = day_frame.drop_nulls("factor").sort("factor", descending=True)
        if ranked.height < 2:
            positions.append(set())
            continue
        cutoff = max(1, math.ceil(ranked.height / n_groups))
        positions.append(set(str(value) for value in ranked.head(cutoff).get_column("instrument").to_list()))
    return positions


def _mean_turnover(positions: list[set[Any]]) -> float:
    if len(positions) < 2:
        return 0.0
    values = []
    for prev, cur in zip(positions[:-1], positions[1:]):
        if not prev and not cur:
            values.append(0.0)
            continue
        union = prev | cur
        values.append(1.0 - (len(prev & cur) / len(union) if union else 0.0))
    return float(np.mean(values)) if values else 0.0


def _group_return_profile(aligned: pl.DataFrame, n_groups: int) -> tuple[list[float], float]:
    buckets: dict[int, list[float]] = defaultdict(list)
    spreads: list[float] = []
    for _date, day_frame in aligned.partition_by("datetime", as_dict=True, maintain_order=True).items():
        rows = day_frame.drop_nulls(["factor", "label"]).sort("factor").to_dicts()
        if len(rows) < n_groups:
            continue
        group_values: dict[int, list[float]] = defaultdict(list)
        for idx, row in enumerate(rows):
            group_id = min(n_groups - 1, int(idx * n_groups / len(rows)))
            group_values[group_id].append(float(row["label"]))
        group_returns = {group_id: float(np.mean(values)) for group_id, values in group_values.items() if values}
        for group_id, value in group_returns.items():
            buckets[int(group_id)].append(float(value))
        if len(group_returns) >= 2:
            ordered = [group_returns[group_id] for group_id in sorted(group_returns)]
            spreads.append(float(ordered[-1] - ordered[0]))
    group_means = [float(np.mean(buckets[key])) for key in sorted(buckets)]
    return group_means, float(np.mean(spreads)) if spreads else 0.0


def _daily_long_short_spread(aligned: pl.DataFrame, n_groups: int) -> list[float]:
    spreads: list[float] = []
    for _date, day_frame in aligned.partition_by("datetime", as_dict=True, maintain_order=True).items():
        rows = day_frame.drop_nulls(["factor", "label"]).sort("factor").to_dicts()
        if len(rows) < 2:
            continue
        group_count = min(n_groups, len(rows))
        group_values: dict[int, list[float]] = defaultdict(list)
        for idx, row in enumerate(rows):
            group_id = min(group_count - 1, int(idx * group_count / len(rows)))
            group_values[group_id].append(float(row["label"]))
        ordered = [float(np.mean(group_values[group_id])) for group_id in sorted(group_values)]
        if len(ordered) >= 2:
            spreads.append(float(ordered[-1] - ordered[0]))
    return spreads


def _daily_rank_ic_frame(factor: pl.DataFrame, label: pl.DataFrame) -> pl.DataFrame:
    aligned = _align_signal_frames(factor, label).drop_nulls(["factor", "label"])
    if aligned.is_empty():
        return pl.DataFrame({"datetime": [], "rank_ic": []}, schema={"datetime": pl.Datetime("ns"), "rank_ic": pl.Float64})
    return (
        aligned.with_columns(
            pl.col("factor").rank(method="average").over("datetime").alias("factor_rank"),
            pl.col("label").rank(method="average").over("datetime").alias("label_rank"),
        )
        .group_by("datetime", maintain_order=True)
        .agg(
            pl.len().alias("rows"),
            pl.corr("factor_rank", "label_rank").alias("rank_ic"),
        )
        .filter(pl.col("rows") >= 2)
        .drop_nulls("rank_ic")
        .select(["datetime", "rank_ic"])
        .sort("datetime")
    )


def _monotonicity_score(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    ranks = np.arange(len(values), dtype=float)
    corr = np.corrcoef(ranks, np.asarray(values, dtype=float))[0, 1]
    if not np.isfinite(corr):
        return 0.0
    return float((corr + 1.0) / 2.0)


def _series_ir(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean = float(np.mean(values))
    std = float(np.std(values, ddof=1))
    return mean / std if std > 1e-12 else 0.0


def _safe_mean(values: list[float]) -> float:
    return float(np.mean(values)) if values else 0.0


def _empty_tradability_metrics() -> dict[str, float]:
    return {
        "turnover": 0.0,
        "cost_adjusted_return": 0.0,
        "cost_adjusted_information_ratio": 0.0,
        "cost_adjusted_ir": 0.0,
        "group_monotonicity_score": 0.0,
        "long_short_spread": 0.0,
        "rank_ic_after_cost": 0.0,
    }


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _log_quality_overlay_event(
    gate: str,
    decision: str,
    *,
    factor_name: str | None = None,
    metrics: dict[str, Any] | None = None,
    reasons: list[str] | None = None,
) -> None:
    metrics_payload = _json_ready_dict(metrics or {})
    reasons_payload = ",".join(str(reason) for reason in (reasons or [])) or "none"
    factor_payload = str(factor_name or "<batch>")
    logger.info(f"quality_overlay_event gate={gate} decision={decision} factor={factor_payload} reasons={reasons_payload} metrics={metrics_payload}")


def _json_ready_dict(payload: dict[str, Any]) -> dict[str, Any]:
    ready: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, (np.integer,)):
            ready[str(key)] = int(value)
        elif isinstance(value, (np.floating,)):
            ready[str(key)] = float(value)
        elif value is None or isinstance(value, (str, int, float, bool)):
            ready[str(key)] = value
        else:
            ready[str(key)] = str(value)
    return ready
