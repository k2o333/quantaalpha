from __future__ import annotations

import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd


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
    "similarity": {
        "compare_statuses": ("active", "candidate"),
        "sample_recent_trading_days": 250,
        "sample_days_per_month": 5,
        "max_behavior_rank_corr_median": 0.80,
        "max_behavior_rank_corr_p90": 0.90,
    },
    "lifecycle": {
        "use_quality_score": False,
        "active": {"min_quality_score": 0.70, "min_rank_ic_test": 0.02},
        "candidate": {"min_quality_score": 0.45, "min_rank_ic_test": 0.00},
        "quarantine": {"lookahead_risk": "critical"},
    },
}


LOOKAHEAD_PATTERNS: tuple[tuple[str, str], ...] = (
    ("negative_shift", r"\bshift\s*\(\s*-\d+"),
    ("negative_ref", r"\bREF\s*\([^,]+,\s*-\d+"),
    ("negative_delay", r"\bDELAY\s*\([^,]+,\s*-\d+"),
    ("future_prefix", r"\bfuture_"),
    ("next_prefix", r"\bNEXT_"),
    ("forward_prefix", r"\bFORWARD_"),
    ("lead_function", r"\bLEAD\s*\("),
)


ANTI_PATTERNS: tuple[tuple[str, str], ...] = (
    ("identity_close_ratio", r"\$close\s*/\s*\$close"),
    ("identity_open_ratio", r"\$open\s*/\s*\$open"),
    ("nested_rank", r"\bRANK\s*\(\s*RANK\s*\("),
    ("nested_ts_mean", r"\bTS_MEAN\s*\(\s*TS_MEAN\s*\("),
    ("nested_abs", r"\bABS\s*\(\s*ABS\s*\("),
    ("std_window_one", r"\bSTD\s*\([^)]*,\s*1\s*\)"),
    ("ts_std_window_one", r"\bTS_STD\s*\([^)]*,\s*1\s*\)"),
)


def load_quality_overlay_config(config: dict[str, Any] | None) -> dict[str, Any]:
    """Return quality overlay config with documented defaults applied."""
    source = dict(config or {})
    if "quality_overlay" in source and isinstance(source["quality_overlay"], dict):
        source = dict(source["quality_overlay"])
    merged = _deep_merge(DEFAULT_QUALITY_OVERLAY_CONFIG, source)
    return merged


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def detect_expression_static_diagnostics(expression: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Detect lookahead and low-value expression patterns before factor calculation."""
    cfg = load_quality_overlay_config(config).get("expression_static", {})
    text = str(expression or "")
    lookahead_flags = [
        flag
        for flag, pattern in LOOKAHEAD_PATTERNS
        if re.search(pattern, text, flags=re.IGNORECASE)
    ]
    anti_pattern_flags = [
        flag
        for flag, pattern in ANTI_PATTERNS
        if re.search(pattern, text, flags=re.IGNORECASE)
    ]
    if lookahead_flags:
        severity = str(cfg.get("lookahead_severity") or "critical")
        failure_type = "lookahead_risk"
        lookahead_risk = "critical"
    elif anti_pattern_flags:
        severity = str(cfg.get("anti_pattern_severity") or "major")
        failure_type = "too_complex" if severity == "minor" else "expression_anti_pattern"
        lookahead_risk = "none"
    else:
        severity = "none"
        failure_type = None
        lookahead_risk = "none"
    return {
        "severity": severity,
        "lookahead_risk": lookahead_risk,
        "lookahead_flags": lookahead_flags,
        "anti_pattern_flags": anti_pattern_flags,
        "failure_type": failure_type,
        "message": _expression_diagnostic_message(lookahead_flags, anti_pattern_flags),
    }


def _expression_diagnostic_message(lookahead_flags: list[str], anti_pattern_flags: list[str]) -> str:
    if lookahead_flags:
        return f"lookahead_risk detected: {', '.join(lookahead_flags)}"
    if anti_pattern_flags:
        return f"expression anti-pattern detected: {', '.join(anti_pattern_flags)}"
    return ""


def pre_backtest_screen(factor_df: pd.DataFrame, config: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    """Screen factor-value columns before expensive full backtest."""
    cfg = load_quality_overlay_config({"pre_backtest": config or {}}).get("pre_backtest", {})
    cleaned = factor_df.replace([np.inf, -np.inf], np.nan)
    results: dict[str, dict[str, Any]] = {}
    for col in cleaned.columns:
        series = cleaned[col]
        metrics = _pre_backtest_metrics(series)
        reasons = _pre_backtest_failure_reasons(metrics, cfg)
        results[str(col)] = {
            "passed": not reasons,
            "failure_reasons": reasons,
            "metrics": metrics,
            **metrics,
        }
    return results


def filter_pre_backtest_survivors(
    factor_df: pd.DataFrame,
    config: dict[str, Any] | None = None,
) -> tuple[pd.DataFrame, dict[str, dict[str, Any]]]:
    """Return columns that passed cheap gate and their diagnostics."""
    diagnostics = pre_backtest_screen(factor_df, config)
    keep = [col for col in factor_df.columns if diagnostics.get(str(col), {}).get("passed")]
    return factor_df.loc[:, keep].replace([np.inf, -np.inf], np.nan).dropna(how="any"), diagnostics


def _pre_backtest_metrics(series: pd.Series) -> dict[str, float | int]:
    total = int(len(series))
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
    clean = series.replace([np.inf, -np.inf], np.nan)
    valid_ratio = float(clean.notna().mean())
    nan_ratio = float(clean.isna().mean())
    unique_values = int(clean.nunique(dropna=True))
    active_days_ratio, constant_day_ratio, coverage = _cross_section_metrics(clean)
    non_null = clean.dropna().astype(float) if not clean.dropna().empty else pd.Series(dtype=float)
    if len(non_null) > 1:
        std = float(non_null.std())
        if std > 1e-12:
            z = ((non_null - float(non_null.mean())) / std).abs()
            extreme_ratio = float((z > 8).mean())
        else:
            extreme_ratio = 0.0
    else:
        extreme_ratio = 0.0
    return {
        "valid_ratio": valid_ratio,
        "nan_ratio": nan_ratio,
        "unique_values": unique_values,
        "active_days_ratio": active_days_ratio,
        "constant_day_ratio": constant_day_ratio,
        "extreme_zscore_ratio": extreme_ratio,
        "cross_section_coverage": coverage,
    }


def _cross_section_metrics(series: pd.Series) -> tuple[float, float, float]:
    if not isinstance(series.index, pd.MultiIndex) or "datetime" not in series.index.names:
        valid = float(series.notna().mean())
        constant = 1.0 if series.nunique(dropna=True) <= 2 else 0.0
        return valid, constant, valid
    by_date = series.groupby(level="datetime")
    active_flags = []
    constant_flags = []
    coverage_values = []
    for _date, values in by_date:
        total = int(len(values))
        valid_count = int(values.notna().sum())
        active_flags.append(valid_count >= 2 if total >= 2 else valid_count > 0)
        unique_count = values.nunique(dropna=True)
        constant_flags.append(unique_count <= (1 if total <= 2 else 2))
        coverage_values.append(valid_count / total if total else 0.0)
    return (
        float(np.mean(active_flags)) if active_flags else 0.0,
        float(np.mean(constant_flags)) if constant_flags else 1.0,
        float(np.mean(coverage_values)) if coverage_values else 0.0,
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


def compute_tradability_metrics(
    factor: pd.Series,
    label: pd.Series,
    *,
    cost_rate: float = 0.001,
    n_groups: int = 5,
) -> dict[str, float]:
    """Compute lightweight tradability metrics from factor values and forward returns."""
    aligned = pd.concat([factor.rename("factor"), label.rename("label")], axis=1).dropna()
    if aligned.empty:
        return _empty_tradability_metrics()
    daily_positions = _daily_long_short_positions(aligned["factor"], n_groups=max(2, int(n_groups)))
    turnover = _mean_turnover(daily_positions)
    group_means, long_short = _group_return_profile(aligned, n_groups=max(2, int(n_groups)))
    monotonicity = _monotonicity_score(group_means)
    daily_spread = _daily_long_short_spread(aligned, n_groups=max(2, int(n_groups)))
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


def _daily_long_short_positions(factor: pd.Series, n_groups: int) -> list[set[Any]]:
    if not isinstance(factor.index, pd.MultiIndex) or "datetime" not in factor.index.names:
        return []
    positions: list[set[Any]] = []
    instrument_level = factor.index.names.index("instrument") if "instrument" in factor.index.names else -1
    for _date, values in factor.groupby(level="datetime"):
        ranked = values.dropna().rank(method="first")
        if len(ranked) < 2:
            positions.append(set())
            continue
        cutoff = max(1, math.ceil(len(ranked) / n_groups))
        top_index = ranked.sort_values(ascending=False).head(cutoff).index
        positions.append(set(idx[instrument_level] if isinstance(idx, tuple) else idx for idx in top_index))
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


def _group_return_profile(aligned: pd.DataFrame, n_groups: int) -> tuple[list[float], float]:
    buckets: dict[int, list[float]] = defaultdict(list)
    if isinstance(aligned.index, pd.MultiIndex) and "datetime" in aligned.index.names:
        groups = aligned.groupby(level="datetime")
    else:
        groups = [(None, aligned)]
    spreads: list[float] = []
    for _date, frame in groups:
        frame = frame.dropna()
        if len(frame) < n_groups:
            continue
        ranks = frame["factor"].rank(method="first")
        labels = pd.qcut(ranks, q=n_groups, labels=False, duplicates="drop")
        tmp = frame.assign(_group=labels)
        group_returns = tmp.groupby("_group")["label"].mean()
        for group_id, value in group_returns.items():
            buckets[int(group_id)].append(float(value))
        if len(group_returns) >= 2:
            spreads.append(float(group_returns.iloc[-1] - group_returns.iloc[0]))
    group_means = [float(np.mean(buckets[key])) for key in sorted(buckets)]
    return group_means, float(np.mean(spreads)) if spreads else 0.0


def _daily_long_short_spread(aligned: pd.DataFrame, n_groups: int) -> list[float]:
    spreads: list[float] = []
    if not isinstance(aligned.index, pd.MultiIndex) or "datetime" not in aligned.index.names:
        return spreads
    for _date, frame in aligned.groupby(level="datetime"):
        frame = frame.dropna()
        if len(frame) < 2:
            continue
        ranks = frame["factor"].rank(method="first")
        buckets = pd.qcut(ranks, q=min(n_groups, len(frame)), labels=False, duplicates="drop")
        tmp = frame.assign(_group=buckets)
        group_returns = tmp.groupby("_group")["label"].mean()
        if len(group_returns) >= 2:
            spreads.append(float(group_returns.iloc[-1] - group_returns.iloc[0]))
    return spreads


def _monotonicity_score(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    corr = pd.Series(range(len(values))).corr(pd.Series(values), method="spearman")
    if pd.isna(corr):
        return 0.0
    return float((corr + 1.0) / 2.0)


def compute_oos_rank_ic_metrics(
    factor: pd.Series,
    label: pd.Series,
    *,
    recent_trading_days: int = 250,
) -> dict[str, float]:
    """Compute cheap chronological OOS Rank IC metrics from factor values."""
    daily = _daily_rank_ic_series(factor, label)
    if daily.empty:
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
    n = len(daily)
    train_end = max(1, int(n * 0.60))
    valid_end = max(train_end + 1, int(n * 0.80)) if n > 2 else n
    train = daily.iloc[:train_end]
    valid = daily.iloc[train_end:valid_end]
    test = daily.iloc[valid_end:] if valid_end < n else daily.iloc[-1:]
    recent = daily.iloc[-int(recent_trading_days) :]
    yearly = daily.groupby(daily.index.year).mean()
    rank_ic_train = _safe_mean(train)
    rank_ic_test = _safe_mean(test)
    return {
        "rank_ic_train": rank_ic_train,
        "rank_ic_valid": _safe_mean(valid),
        "rank_ic_test": rank_ic_test,
        "rank_ic_recent": _safe_mean(recent),
        "positive_year_ratio": float((yearly > 0).mean()) if len(yearly) else 0.0,
        "worst_year_rank_ic": float(yearly.min()) if len(yearly) else 0.0,
        "ic_std_by_year": float(yearly.std(ddof=0)) if len(yearly) else 0.0,
        "ic_decay": float(rank_ic_test / (abs(rank_ic_train) + 1e-12)),
    }


def _daily_rank_ic_series(factor: pd.Series, label: pd.Series) -> pd.Series:
    aligned = pd.concat([factor.rename("factor"), label.rename("label")], axis=1).dropna()
    if aligned.empty:
        return pd.Series(dtype=float)
    if not isinstance(aligned.index, pd.MultiIndex) or "datetime" not in aligned.index.names:
        value = aligned["factor"].rank().corr(aligned["label"].rank())
        return pd.Series([0.0 if pd.isna(value) else float(value)], index=pd.to_datetime(["1970-01-01"]))
    values = {}
    for date, frame in aligned.groupby(level="datetime"):
        if len(frame) < 2:
            continue
        value = frame["factor"].rank().corr(frame["label"].rank())
        if not pd.isna(value):
            values[pd.Timestamp(date)] = float(value)
    return pd.Series(values).sort_index()


def _safe_mean(values: pd.Series | list[float]) -> float:
    if len(values) == 0:
        return 0.0
    return float(np.mean(values))


def behavior_similarity(
    new_values: pd.Series,
    historical_factors: dict[str, dict[str, Any]],
    *,
    compare_statuses: Iterable[str] = ("active", "candidate"),
    max_sample_days: int = 250,
) -> dict[str, Any]:
    """Compare a factor with sampled active/candidate historical factor values."""
    allowed = {str(status) for status in compare_statuses}
    sampled_new = _sample_recent_days(new_values, max_sample_days=max_sample_days)
    best_factor_id = None
    best_median = 0.0
    best_p90 = 0.0
    comparisons = 0
    for factor_id, payload in historical_factors.items():
        if str(payload.get("status") or payload.get("evaluation_status") or "") not in allowed:
            continue
        other = payload.get("values")
        if not isinstance(other, pd.Series):
            continue
        sampled_other = _sample_recent_days(other, max_sample_days=max_sample_days)
        daily_corrs = _daily_cross_section_rank_corr(sampled_new, sampled_other)
        if not daily_corrs:
            continue
        comparisons += 1
        median = float(round(float(np.median(daily_corrs)), 12))
        p90 = float(round(float(np.percentile(daily_corrs, 90)), 12))
        if median > best_median or (median == best_median and p90 > best_p90):
            best_factor_id = factor_id
            best_median = median
            best_p90 = p90
    return {
        "comparisons_made": comparisons,
        "best_factor_id": best_factor_id,
        "behavior_similarity_median": best_median,
        "behavior_similarity_p90": best_p90,
    }


def load_historical_behavior_values(
    factor_value_dir: str | Path,
    records: Iterable[dict[str, Any]],
    *,
    compare_statuses: Iterable[str] = ("active", "candidate"),
) -> dict[str, dict[str, Any]]:
    """Load sampled-comparison inputs from published long-format factor-value parquet files."""
    import polars as pl

    root = Path(factor_value_dir)
    allowed = {str(status) for status in compare_statuses}
    loaded: dict[str, dict[str, Any]] = {}
    if not root.exists():
        return loaded
    for record in records:
        status = str(record.get("evaluation_status") or record.get("status") or "")
        if status not in allowed:
            continue
        factor_id = str(record.get("factor_id") or "")
        if not factor_id:
            continue
        path = root / f"{factor_id}.parquet"
        if not path.exists():
            continue
        try:
            frame = pl.read_parquet(path, columns=["trade_date", "instrument", "factor_value"])
        except Exception:
            continue
        if frame.is_empty():
            continue
        pdf = (
            frame.with_columns(
                pl.col("trade_date").cast(pl.Utf8),
                pl.col("instrument").cast(pl.Utf8),
                pl.col("factor_value").cast(pl.Float64, strict=False),
            )
            .drop_nulls(["trade_date", "instrument", "factor_value"])
            .to_pandas()
        )
        if pdf.empty:
            continue
        index = pd.MultiIndex.from_arrays(
            [pd.to_datetime(pdf["trade_date"], format="%Y%m%d", errors="coerce"), pdf["instrument"]],
            names=["datetime", "instrument"],
        )
        series = pd.Series(pdf["factor_value"].to_numpy(dtype=float), index=index, name=factor_id).dropna()
        if series.empty:
            continue
        loaded[factor_id] = {"status": status, "values": series.sort_index()}
    return loaded


def _sample_recent_days(series: pd.Series, max_sample_days: int) -> pd.Series:
    if not isinstance(series.index, pd.MultiIndex) or "datetime" not in series.index.names:
        return series
    dates = pd.Index(series.index.get_level_values("datetime")).drop_duplicates().sort_values()
    sampled_dates = set(dates[-int(max_sample_days) :])
    mask = series.index.get_level_values("datetime").isin(sampled_dates)
    return series.loc[mask]


def _daily_cross_section_rank_corr(left: pd.Series, right: pd.Series) -> list[float]:
    aligned = pd.concat([left.rename("left"), right.rename("right")], axis=1).dropna()
    if aligned.empty:
        return []
    if not isinstance(aligned.index, pd.MultiIndex) or "datetime" not in aligned.index.names:
        corr = aligned["left"].rank().corr(aligned["right"].rank())
        return [] if pd.isna(corr) else [float(corr)]
    values: list[float] = []
    for _date, frame in aligned.groupby(level="datetime"):
        if len(frame) < 2:
            continue
        corr = frame["left"].rank().corr(frame["right"].rank())
        if not pd.isna(corr):
            values.append(float(corr))
    return values


def infer_failure_attribution(
    *,
    metrics: dict[str, Any],
    diagnostics: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build deterministic failure attribution when LLM feedback is unavailable."""
    diagnostics = diagnostics or {}
    reasons = list(diagnostics.get("failure_reasons") or [])
    rank_ic_test = _metric_value(metrics, "rank_ic_test", "Rank IC")
    turnover = _metric_value(metrics, "turnover")
    lookahead = diagnostics.get("lookahead_risk") or metrics.get("lookahead_risk")
    if lookahead == "critical":
        primary = "lookahead_risk"
    elif rank_ic_test is not None and rank_ic_test <= 0:
        primary = "weak_oos_ic"
    elif "too_many_nan" in reasons:
        primary = "too_many_nan"
    elif "constant_signal" in reasons:
        primary = "constant_signal"
    elif "high_similarity" in reasons:
        primary = "high_similarity"
    else:
        primary = "weak_ic"
    secondary = []
    if turnover is not None and turnover > 0.8:
        secondary.append("high_turnover")
    for reason in reasons:
        if reason != primary and reason not in secondary:
            secondary.append(reason)
    next_action = {
        "action_type": _next_action_for_failure(primary),
        "specific_instruction": _instruction_for_failure(primary),
        "do_not_repeat": [f"Do not repeat factors with primary failure `{primary}` without addressing it."],
    }
    return {
        "decision": "quarantine" if primary == "lookahead_risk" else "rejected",
        "primary_failure_reason": primary,
        "secondary_failure_reasons": secondary,
        "diagnostics": {
            "predictive_power": "weak" if primary in {"weak_ic", "weak_oos_ic"} else "acceptable",
            "stability": "unstable" if primary in {"weak_oos_ic", "ic_decay"} else "acceptable",
            "novelty": "redundant" if primary == "high_similarity" else "novel",
            "tradability": "poor" if "high_turnover" in secondary else "acceptable",
            "complexity": "too_complex" if primary == "too_complex" else "acceptable",
            "lookahead_risk": "critical" if primary == "lookahead_risk" else "none",
        },
        "next_action": next_action,
    }


def quality_score_decision(
    metrics: dict[str, Any],
    diagnostics: dict[str, Any] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compute interpretable QualityScore and lifecycle suggestion."""
    diagnostics = diagnostics or {}
    cfg = load_quality_overlay_config(config).get("lifecycle", {})
    lookahead_risk = diagnostics.get("lookahead_risk") or metrics.get("lookahead_risk") or "none"
    rank_ic_test = _metric_value(metrics, "rank_ic_test", "Rank IC", default=0.0) or 0.0
    rank_icir = _metric_value(metrics, "rank_icir_test", "Rank ICIR", "RankICIR", default=0.0) or 0.0
    monotonicity = _metric_value(metrics, "group_monotonicity_score", default=0.0) or 0.0
    max_similarity = _metric_value(metrics, "behavior_similarity_median", "expression_similarity_max", default=0.0) or 0.0
    stability = _metric_value(metrics, "positive_year_ratio", default=0.0) or 0.0
    turnover = _metric_value(metrics, "turnover", default=0.0) or 0.0
    symbol_length = _metric_value(metrics, "symbol_length", default=20.0) or 20.0
    components = {
        "rank_ic_test_score": _clip_score(rank_ic_test, 0.0, 0.05),
        "rank_icir_test_score": _clip_score(rank_icir, 0.0, 0.80),
        "monotonicity_score": float(max(0.0, min(1.0, monotonicity))),
        "novelty_score": float(max(0.0, min(1.0, 1.0 - max_similarity))),
        "stability_score": float(max(0.0, min(1.0, stability))),
        "turnover_penalty": _clip_score(turnover, 0.30, 1.20),
        "similarity_penalty": float(max(0.0, min(1.0, max_similarity))),
        "complexity_penalty": _clip_score(symbol_length, 20.0, 80.0),
        "lookahead_penalty": 1.0 if lookahead_risk == "critical" else 0.0,
    }
    score = (
        1.50 * components["rank_ic_test_score"]
        + 1.00 * components["rank_icir_test_score"]
        + 0.80 * components["monotonicity_score"]
        + 0.60 * components["novelty_score"]
        + 0.50 * components["stability_score"]
        - 0.80 * components["turnover_penalty"]
        - 0.80 * components["similarity_penalty"]
        - 0.50 * components["complexity_penalty"]
        - 1.00 * components["lookahead_penalty"]
    ) / 3.60
    score = float(max(0.0, min(1.0, score)))
    if lookahead_risk == "critical":
        status = "quarantine"
        failure_type = "lookahead_risk"
    elif score >= float(cfg.get("active", {}).get("min_quality_score", 0.70)) and rank_ic_test > float(
        cfg.get("active", {}).get("min_rank_ic_test", 0.02)
    ):
        status = "active"
        failure_type = None
    elif score >= float(cfg.get("candidate", {}).get("min_quality_score", 0.45)) and rank_ic_test > float(
        cfg.get("candidate", {}).get("min_rank_ic_test", 0.0)
    ):
        status = "candidate"
        failure_type = None
    else:
        attribution = infer_failure_attribution(metrics=metrics, diagnostics=diagnostics)
        status = "rejected"
        failure_type = attribution["primary_failure_reason"]
    return {
        "status": status,
        "quality_score": score,
        "components": components,
        "failure_type_primary": failure_type,
    }


def _clip_score(value: float, lo: float, hi: float) -> float:
    if hi <= lo:
        return 0.0
    return float(max(0.0, min(1.0, (float(value) - lo) / (hi - lo))))


def _metric_value(metrics: dict[str, Any], *keys: str, default: float | None = None) -> float | None:
    for key in keys:
        value = metrics.get(key)
        try:
            if value is None or pd.isna(value):
                continue
            return float(value)
        except (TypeError, ValueError):
            continue
    return default


def _next_action_for_failure(primary: str) -> str:
    if primary in {"lookahead_risk", "high_similarity", "weak_oos_ic"}:
        return "discard"
    if primary in {"high_turnover", "cost_sensitive"}:
        return "change_window"
    if primary in {"too_complex", "constant_signal"}:
        return "simplify"
    return "change_window"


def _instruction_for_failure(primary: str) -> str:
    mapping = {
        "lookahead_risk": "Remove all forward-looking operators and rebuild from lagged daily fields only.",
        "weak_oos_ic": "Change horizon or factor family; do not optimize only in-sample IC.",
        "high_similarity": "Switch to an orthogonal factor family or add a genuinely different normalizer.",
        "high_turnover": "Smooth the signal or lengthen the horizon before retrying.",
        "constant_signal": "Use a continuous cross-sectional transformation with enough unique values.",
    }
    return mapping.get(primary, "Revise the signal based on the primary failure reason.")


def build_family_inventory(records: Iterable[dict[str, Any]]) -> dict[str, dict[str, float | int]]:
    """Summarize lifecycle counts and hit rate by factor family."""
    inventory: dict[str, dict[str, float | int]] = {}
    for rec in records:
        family = str(rec.get("factor_family") or rec.get("family") or "other")
        status = str(rec.get("evaluation_status") or rec.get("status") or "candidate")
        bucket = inventory.setdefault(
            family,
            {"active": 0, "candidate": 0, "rejected": 0, "quarantine": 0, "total": 0, "recent_hit_rate": 0.0},
        )
        bucket["total"] = int(bucket["total"]) + 1
        if status in bucket:
            bucket[status] = int(bucket[status]) + 1
    for bucket in inventory.values():
        total = int(bucket.get("total") or 0)
        bucket["recent_hit_rate"] = float(bucket.get("active") or 0) / total if total else 0.0
    return inventory


def select_multi_objective_parents(records: list[dict[str, Any]], total: int = 8) -> list[dict[str, Any]]:
    """Select parent records from performance, novelty and low-complexity buckets."""
    eligible = [rec for rec in records if str(rec.get("evaluation_status") or rec.get("status")) in {"active", "candidate"}]
    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    bucket_specs = (
        (max(1, round(total * 0.50)), _performance_key),
        (max(1, round(total * 0.30)), lambda rec: float(rec.get("novelty_score") or 0.0)),
        (max(1, total - max(1, round(total * 0.50)) - max(1, round(total * 0.30))), _simplicity_key),
    )
    for count, key_func in bucket_specs:
        for rec in sorted(eligible, key=key_func, reverse=True):
            factor_id = str(rec.get("factor_id") or rec.get("factor_name") or id(rec))
            if factor_id in selected_ids:
                continue
            selected.append(rec)
            selected_ids.add(factor_id)
            if len([item for item in selected if item in selected]) >= total:
                return selected[:total]
            count -= 1
            if count <= 0:
                break
    for rec in sorted(eligible, key=_performance_key, reverse=True):
        if len(selected) >= total:
            break
        factor_id = str(rec.get("factor_id") or rec.get("factor_name") or id(rec))
        if factor_id not in selected_ids:
            selected.append(rec)
            selected_ids.add(factor_id)
    return selected[:total]


def heavy_analysis_plan(
    *,
    expression: str,
    lifecycle_status: str,
    quality_score: float | None = None,
    quality_score_threshold: float = 0.45,
) -> dict[str, Any]:
    """Build the bounded P3 analysis plan for candidate/active factors only."""
    status = str(lifecycle_status or "")
    score = 0.0 if quality_score is None else float(quality_score)
    if status not in {"candidate", "active"}:
        return {
            "enabled": False,
            "reason": "status_not_high_value",
            "expression": str(expression or ""),
            "window_candidates": {},
            "ablation_expressions": [],
        }
    if score < float(quality_score_threshold):
        return {
            "enabled": False,
            "reason": "quality_score_below_threshold",
            "expression": str(expression or ""),
            "window_candidates": {},
            "ablation_expressions": [],
        }
    expr = str(expression or "").strip()
    return {
        "enabled": True,
        "reason": "high_value_candidate",
        "expression": expr,
        "window_candidates": window_robustness_candidates(expr),
        "ablation_expressions": limited_ablation_expressions(expr),
    }


def window_robustness_candidates(expression: str) -> dict[int, list[int]]:
    """Return n*0.75, n, n*1.25 candidates for integer DSL windows in an expression."""
    windows: set[int] = set()
    for match in re.finditer(r"\b[A-Z][A-Z_]*\s*\([^)]*,\s*(\d+)\s*\)", str(expression or "")):
        value = int(match.group(1))
        if value > 1:
            windows.add(value)
    return {
        window: sorted(
            {
                max(2, int(round(window * 0.75))),
                window,
                max(2, int(round(window * 1.25))),
            }
        )
        for window in sorted(windows)
    }


def limited_ablation_expressions(expression: str) -> list[str]:
    """Return bounded A, B, A*B, A*B/C style ablation expressions without AST explosion."""
    expr = str(expression or "").strip()
    if not expr:
        return []
    numerator, denominator = _split_top_level(expr, "/")
    left, right = _split_top_level(numerator, "*")
    pieces: list[str] = []
    if left and right:
        pieces.extend([left.strip(), right.strip(), f"{left.strip()} * {right.strip()}"])
    elif numerator.strip():
        pieces.append(numerator.strip())
    if denominator:
        full = f"{numerator.strip()} / {denominator.strip()}"
        if full not in pieces:
            pieces.append(full)
    elif expr not in pieces:
        pieces.append(expr)
    return pieces[:4]


def _split_top_level(expression: str, operator: str) -> tuple[str, str | None]:
    depth = 0
    for idx, char in enumerate(expression):
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        elif char == operator and depth == 0:
            return expression[:idx], expression[idx + 1 :]
    return expression, None


def build_factor_research_report(record: dict[str, Any]) -> str:
    """Build a short human-readable report for active/manual-review candidates."""
    metrics = record.get("backtest_results") or record.get("metrics") or {}
    if not isinstance(metrics, dict):
        metrics = {}
    metadata = record.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    name = str(record.get("factor_name") or record.get("factor_id") or "factor")
    expression = str(record.get("factor_expression") or record.get("expression") or "")
    quality_score = record.get("quality_score")
    quality_text = "unavailable" if quality_score is None else f"{float(quality_score):.4f}"
    metric_lines = [
        f"- {key}: {value}"
        for key, value in sorted(metrics.items())
        if key
        in {
            "rank_ic_train",
            "rank_ic_valid",
            "rank_ic_test",
            "rank_ic_recent",
            "positive_year_ratio",
            "turnover",
            "cost_adjusted_information_ratio",
            "group_monotonicity_score",
            "long_short_spread",
        }
    ]
    if not metric_lines:
        metric_lines = ["- metric_unavailable: true"]
    risk = metadata.get("failure_type_primary") or record.get("failure_type_primary") or "none"
    similarity = metadata.get("behavior_similarity_median") or record.get("behavior_similarity_median")
    return "\n".join(
        [
            f"# {name}",
            "",
            f"- Status: {record.get('evaluation_status') or record.get('status') or 'unknown'}",
            f"- Family: {record.get('factor_family') or record.get('family') or 'unknown'}",
            f"- Quality Score: {quality_text}",
            f"- Expression: `{expression}`",
            "",
            "## Metrics",
            *metric_lines,
            "",
            "## Risk",
            f"- Primary failure risk: {risk}",
            f"- Behavior similarity median: {similarity if similarity is not None else 'unavailable'}",
            "",
        ]
    )


def _performance_key(rec: dict[str, Any]) -> float:
    metrics = rec.get("backtest_results") or rec.get("metrics") or {}
    if isinstance(metrics, str):
        return 0.0
    return float(rec.get("quality_score") or 0.0) + float(metrics.get("rank_ic_test") or metrics.get("Rank IC") or 0.0)


def _simplicity_key(rec: dict[str, Any]) -> float:
    metrics = rec.get("backtest_results") or rec.get("metrics") or {}
    rank_ic_test = float(metrics.get("rank_ic_test") or metrics.get("Rank IC") or 0.0) if isinstance(metrics, dict) else 0.0
    if rank_ic_test <= 0:
        return -1.0
    symbol_length = float(rec.get("symbol_length") or 80.0)
    return rank_ic_test + max(0.0, 1.0 - symbol_length / 100.0)


def _series_ir(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    std = float(np.std(values, ddof=1))
    return float(np.mean(values) / std) if std > 1e-12 else 0.0
