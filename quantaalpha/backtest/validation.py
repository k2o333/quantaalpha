from __future__ import annotations

from copy import deepcopy
from statistics import mean, pstdev
from typing import Any


SUMMARY_METRIC_KEYS = (
    ("IC", "ic_mean", "ic_std"),
    ("Rank IC", "rank_ic_mean", "rank_ic_std"),
    ("annualized_return", "annualized_return_mean", "annualized_return_std"),
    ("information_ratio", "information_ratio_mean", "information_ratio_std"),
)


def validate_multi_period_config(config: dict[str, Any] | None) -> dict[str, Any]:
    cfg = dict(config or {})
    periods = list(cfg.get("periods", []) or [])
    out = {
        "enabled": bool(cfg.get("enabled", False)),
        "fail_fast": bool(cfg.get("fail_fast", True)),
        "periods": [],
    }
    if not out["enabled"]:
        return out
    if not periods:
        raise ValueError("multi_period_validation.enabled=true requires at least one period")

    seen_names: set[str] = set()
    for period in periods:
        normalized = _normalize_period(period)
        if normalized["name"] in seen_names:
            raise ValueError(f"Duplicate multi-period validation name: {normalized['name']}")
        seen_names.add(normalized["name"])
        out["periods"].append(normalized)
    return out


def build_period_configs(base_config: dict[str, Any], multi_period_config: dict[str, Any]) -> list[dict[str, Any]]:
    mp_cfg = validate_multi_period_config(multi_period_config)
    if not mp_cfg.get("enabled"):
        return [deepcopy(base_config)]

    configs: list[dict[str, Any]] = []
    for period in mp_cfg["periods"]:
        cfg = deepcopy(base_config)
        cfg.setdefault("dataset", {}).setdefault("segments", {})
        cfg.setdefault("backtest", {}).setdefault("backtest", {})
        cfg["dataset"]["segments"] = {
            "train": period["train"],
            "valid": period["valid"],
            "test": period["test"],
        }
        cfg["backtest"]["backtest"]["start_time"] = period["test"][0]
        cfg["backtest"]["backtest"]["end_time"] = period["test"][1]
        cfg["_multi_period_context"] = {"name": period["name"], "segments": deepcopy(cfg["dataset"]["segments"])}
        configs.append(cfg)
    return configs


def aggregate_period_metrics(period_results: list[dict[str, Any]]) -> dict[str, Any]:
    successes = [item for item in period_results if item.get("status") == "success"]
    summary: dict[str, Any] = {
        "period_count": len(period_results),
        "success_count": len(successes),
        "failure_count": len(period_results) - len(successes),
    }
    for metric_name, mean_key, std_key in SUMMARY_METRIC_KEYS:
        values = [float(item["metrics"][metric_name]) for item in successes if item.get("metrics", {}).get(metric_name) is not None]
        if values:
            summary[mean_key] = mean(values)
            summary[std_key] = pstdev(values) if len(values) > 1 else 0.0
        else:
            summary[mean_key] = None
            summary[std_key] = None

    drawdowns = [float(item["metrics"]["max_drawdown"]) for item in successes if item.get("metrics", {}).get("max_drawdown") is not None]
    win_rates = [_success_win_rate(item.get("metrics", {})) for item in successes]
    win_rates = [rate for rate in win_rates if rate is not None]
    summary["max_drawdown_worst"] = min(drawdowns) if drawdowns else None
    summary["win_rate_mean"] = mean(win_rates) if win_rates else None
    summary["stability_score"] = compute_stability_score(summary)
    return summary


def compute_stability_score(summary: dict[str, Any]) -> float | None:
    if summary.get("success_count", 0) == 0:
        return None
    ic_mean = max(float(summary.get("ic_mean") or 0.0), 0.0)
    rank_ic_mean = max(float(summary.get("rank_ic_mean") or 0.0), 0.0)
    info_ratio_mean = max(float(summary.get("information_ratio_mean") or 0.0), 0.0)
    ic_std = float(summary.get("ic_std") or 0.0)
    rank_ic_std = float(summary.get("rank_ic_std") or 0.0)
    failure_penalty = min(float(summary.get("failure_count", 0)) * 0.15, 0.6)
    raw = 0.4 * ic_mean + 0.4 * rank_ic_mean + 0.2 * min(info_ratio_mean, 1.0)
    volatility_penalty = min(ic_std + rank_ic_std, 0.5)
    return round(max(min(raw - volatility_penalty - failure_penalty + 0.5, 1.0), 0.0), 4)


def _normalize_period(period: dict[str, Any]) -> dict[str, Any]:
    name = str(period.get("name") or "").strip()
    if not name:
        raise ValueError("Each multi-period validation period requires a non-empty name")
    normalized = {
        "name": name,
        "train": _normalize_segment(period, "train"),
        "valid": _normalize_segment(period, "valid"),
        "test": _normalize_segment(period, "test"),
    }
    return normalized


def _normalize_segment(period: dict[str, Any], key: str) -> list[str]:
    value = period.get(key)
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"Period '{period.get('name', '<unknown>')}' has invalid {key} segment")
    start, end = str(value[0]), str(value[1])
    if start > end:
        raise ValueError(f"Period '{period.get('name', '<unknown>')}' has invalid {key} date range")
    return [start, end]


def _success_win_rate(metrics: dict[str, Any]) -> float | None:
    positives = [metrics.get("IC"), metrics.get("Rank IC"), metrics.get("annualized_return")]
    values = [float(v) for v in positives if v is not None]
    if not values:
        return None
    return sum(v > 0 for v in values) / len(values)
