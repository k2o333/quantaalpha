from __future__ import annotations

import json

import numpy as np
import pandas as pd
import polars as pl
import pytest


def _factor_frame(values_by_factor: dict[str, list[float | None]]) -> pd.DataFrame:
    dates = pd.to_datetime(["2025-01-02", "2025-01-02", "2025-01-03", "2025-01-03", "2025-01-04", "2025-01-04"])
    instruments = ["A", "B", "A", "B", "A", "B"]
    index = pd.MultiIndex.from_arrays([dates, instruments], names=["datetime", "instrument"])
    return pd.DataFrame(values_by_factor, index=index)


def test_expression_static_diagnostics_blocks_lookahead_and_flags_antipatterns() -> None:
    from quantaalpha.factors.regulator.factor_regulator import FactorRegulator
    from quantaalpha.pipeline.quality_overlay import detect_expression_static_diagnostics

    lookahead = detect_expression_static_diagnostics("REF($close, -1)")
    assert lookahead["lookahead_risk"] == "critical"
    assert lookahead["severity"] == "critical"
    assert lookahead["failure_type"] == "lookahead_risk"

    anti = detect_expression_static_diagnostics("RANK(RANK($close)) + $open / $open")
    assert anti["lookahead_risk"] == "none"
    assert anti["severity"] == "major"
    assert "nested_rank" in anti["anti_pattern_flags"]
    assert "identity_open_ratio" in anti["anti_pattern_flags"]

    ok, error = FactorRegulator().parse_diagnostic("DELAY($close, -2)")
    assert ok is False
    assert "lookahead_risk" in str(error)


def test_pre_backtest_screen_records_reasons_and_runner_filters_survivors() -> None:
    from quantaalpha.factors.runner import QlibFactorRunner
    from quantaalpha.pipeline.quality_overlay import pre_backtest_screen

    frame = _factor_frame(
        {
            "good": [1, 2, 3, 4, 5, 6],
            "too_sparse": [1, None, None, None, None, 2],
            "constant": [7, 7, 7, 7, 7, 7],
        }
    )
    cfg = {
        "min_valid_ratio": 0.65,
        "max_nan_ratio": 0.35,
        "min_unique_values": 3,
        "min_active_days_ratio": 0.70,
        "max_constant_day_ratio": 0.20,
        "max_extreme_zscore_ratio": 0.50,
        "min_cross_section_coverage": 0.50,
    }

    diagnostics = pre_backtest_screen(frame, cfg)
    assert diagnostics["good"]["passed"] is True
    assert diagnostics["too_sparse"]["passed"] is False
    assert "too_many_nan" in diagnostics["too_sparse"]["failure_reasons"]
    assert diagnostics["constant"]["passed"] is False
    assert "constant_signal" in diagnostics["constant"]["failure_reasons"]

    runner = QlibFactorRunner(None)
    runner.set_quality_overlay_config({"pre_backtest": cfg})
    filtered = runner._apply_combined_quality_gate(frame)
    assert list(filtered.columns) == ["good"]
    assert runner._last_pre_backtest_diagnostics["too_sparse"]["passed"] is False


def test_tradability_oos_and_behavior_similarity_are_sampled_and_deterministic(tmp_path) -> None:
    from quantaalpha.pipeline.quality_overlay import (
        behavior_similarity,
        compute_oos_rank_ic_metrics,
        compute_tradability_metrics,
        load_historical_behavior_values,
    )

    frame = _factor_frame({"factor": [1, 2, 3, 4, 5, 6]})
    label = pd.Series([0.01, 0.02, 0.01, 0.03, 0.02, 0.04], index=frame.index, name="label")

    tradability = compute_tradability_metrics(frame["factor"], label, cost_rate=0.001, n_groups=2)
    assert tradability["turnover"] >= 0.0
    assert tradability["group_monotonicity_score"] > 0.0
    assert tradability["long_short_spread"] > 0.0
    assert "cost_adjusted_information_ratio" in tradability

    oos = compute_oos_rank_ic_metrics(frame["factor"], label, recent_trading_days=2)
    assert set(["rank_ic_train", "rank_ic_valid", "rank_ic_test", "rank_ic_recent", "positive_year_ratio"]).issubset(oos)

    similar = behavior_similarity(
        frame["factor"],
        {
            "active_clone": {"status": "active", "values": frame["factor"] * 10},
            "rejected_clone": {"status": "rejected", "values": frame["factor"] * 10},
        },
        compare_statuses=("active", "candidate"),
        max_sample_days=3,
    )
    assert similar["comparisons_made"] == 1
    assert similar["best_factor_id"] == "active_clone"
    assert similar["behavior_similarity_median"] == 1.0

    import polars as pl

    value_dir = tmp_path / "factor_values"
    value_dir.mkdir()
    for factor_id, scale in {"active_clone": 10.0, "rejected_clone": 10.0}.items():
        pl.DataFrame(
            {
                "trade_date": ["20250102", "20250102", "20250103", "20250103"],
                "instrument": ["A", "B", "A", "B"],
                "factor_id": [factor_id] * 4,
                "factor_value": [1.0 * scale, 2.0 * scale, 3.0 * scale, 4.0 * scale],
            }
        ).write_parquet(value_dir / f"{factor_id}.parquet")

    loaded = load_historical_behavior_values(
        value_dir,
        [
            {"factor_id": "active_clone", "evaluation_status": "active"},
            {"factor_id": "rejected_clone", "evaluation_status": "rejected"},
            {"factor_id": "missing_candidate", "evaluation_status": "candidate"},
        ],
    )
    assert list(loaded) == ["active_clone"]
    assert loaded["active_clone"]["status"] == "active"
    assert isinstance(loaded["active_clone"]["values"], pd.Series)


def test_quality_score_and_failure_attribution_drive_lifecycle() -> None:
    from quantaalpha.pipeline.quality_overlay import (
        infer_failure_attribution,
        quality_score_decision,
    )

    quarantine = quality_score_decision(
        {"rank_ic_test": 0.10, "Rank ICIR": 1.0},
        {"lookahead_risk": "critical"},
    )
    assert quarantine["status"] == "quarantine"
    assert quarantine["failure_type_primary"] == "lookahead_risk"

    rejected = infer_failure_attribution(
        metrics={"Rank IC": -0.01, "rank_ic_test": -0.02, "turnover": 1.5},
        diagnostics={"failure_reasons": ["high_similarity"]},
    )
    assert rejected["primary_failure_reason"] == "weak_oos_ic"
    assert "high_turnover" in rejected["secondary_failure_reasons"]
    assert rejected["next_action"]["action_type"] in {"discard", "simplify", "change_window"}


def test_persistence_extracts_overlay_metrics_and_metadata_json() -> None:
    from quantaalpha.pipeline.persistence import _extract_backtest_metric_payload, _quality_gate_status

    result = pd.DataFrame(
        {"value": [0.03, 0.31, 0.42, 0.7, 0.012, 0.018]},
        index=[
            "Rank IC",
            "information_ratio",
            "turnover",
            "group_monotonicity_score",
            "rank_ic_test",
            "rank_ic_recent",
        ],
    )
    metrics = _extract_backtest_metric_payload(result)
    assert metrics["turnover"] == 0.42
    assert metrics["group_monotonicity_score"] == 0.7
    assert metrics["rank_ic_test"] == 0.012

    status, decision = _quality_gate_status(
        metrics,
        {
            "promotion": {"min_rank_ic": 0.02, "min_information_ratio": 0.2},
            "quality_overlay": {
                "lifecycle": {
                    "use_quality_score": True,
                    "candidate": {"min_quality_score": 0.0, "min_rank_ic_test": 0.0},
                    "active": {"min_quality_score": 0.70, "min_rank_ic_test": 0.02},
                }
            },
        },
    )
    assert status == "candidate"
    assert decision["quality_score_decision"]["status"] == "candidate"
    json.dumps(decision)


def test_family_inventory_and_parent_selection_are_multi_objective() -> None:
    from quantaalpha.pipeline.quality_overlay import build_family_inventory, select_multi_objective_parents

    records = [
        {"factor_id": "perf", "factor_family": "momentum", "evaluation_status": "active", "backtest_results": {"rank_ic_test": 0.05, "information_ratio": 0.8}, "quality_score": 0.80, "novelty_score": 0.20, "symbol_length": 60},
        {"factor_id": "novel", "factor_family": "liquidity", "evaluation_status": "candidate", "backtest_results": {"rank_ic_test": 0.01, "information_ratio": 0.2}, "quality_score": 0.50, "novelty_score": 0.95, "symbol_length": 70},
        {"factor_id": "simple", "factor_family": "volatility", "evaluation_status": "candidate", "backtest_results": {"rank_ic_test": 0.02, "information_ratio": 0.3}, "quality_score": 0.45, "novelty_score": 0.40, "symbol_length": 20},
        {"factor_id": "bad", "factor_family": "momentum", "evaluation_status": "rejected", "backtest_results": {"rank_ic_test": -0.01}, "quality_score": 0.10, "novelty_score": 0.90, "symbol_length": 10},
    ]

    inventory = build_family_inventory(records)
    assert inventory["momentum"]["active"] == 1
    assert inventory["momentum"]["rejected"] == 1

    selected = select_multi_objective_parents(records, total=3)
    selected_ids = {item["factor_id"] for item in selected}
    assert {"perf", "novel", "simple"}.issubset(selected_ids)
    assert "bad" not in selected_ids


def test_high_value_heavy_analysis_is_guarded_and_reportable() -> None:
    from quantaalpha.pipeline.quality_overlay import (
        build_factor_research_report,
        heavy_analysis_plan,
    )

    rejected = heavy_analysis_plan(
        expression="TS_MEAN($close, 20) / TS_STD($close, 20)",
        lifecycle_status="rejected",
        quality_score=0.90,
    )
    assert rejected["enabled"] is False
    assert rejected["reason"] == "status_not_high_value"

    active = heavy_analysis_plan(
        expression="TS_MEAN($close, 20) * RANK($volume) / TS_STD($close, 20)",
        lifecycle_status="active",
        quality_score=0.72,
    )
    assert active["enabled"] is True
    assert active["window_candidates"][20] == [15, 20, 25]
    assert active["ablation_expressions"] == [
        "TS_MEAN($close, 20)",
        "RANK($volume)",
        "TS_MEAN($close, 20) * RANK($volume)",
        "TS_MEAN($close, 20) * RANK($volume) / TS_STD($close, 20)",
    ]

    report = build_factor_research_report(
        {
            "factor_name": "active_factor",
            "factor_expression": active["expression"],
            "factor_family": "momentum",
            "evaluation_status": "active",
            "quality_score": 0.72,
            "backtest_results": {"rank_ic_test": 0.03, "turnover": 0.42},
            "metadata": {"failure_type_primary": None, "behavior_similarity_median": 0.3},
        }
    )
    assert "# active_factor" in report
    assert "Quality Score: 0.7200" in report
    assert "rank_ic_test: 0.03" in report


def test_factor_mining_merges_quality_overlay_config() -> None:
    from quantaalpha.pipeline.factor_mining import _resolve_quality_gate_config

    cfg = _resolve_quality_gate_config(
        {
            "quality_gate": {"promotion": {"min_rank_ic": 0.03}},
            "quality_overlay": {"pre_backtest": {"min_unique_values": 7}},
        }
    )
    assert cfg["promotion"]["min_rank_ic"] == 0.03
    assert cfg["quality_overlay"]["pre_backtest"]["min_unique_values"] == 7
    assert cfg["quality_overlay"]["pre_backtest"]["min_valid_ratio"] == 0.65


def test_isolated_factor_metrics_use_each_factor_values() -> None:
    from quantaalpha.factors.runner import compute_isolated_factor_signal_metrics

    frame = _factor_frame(
        {
            "aligned": [1, 2, 1, 2, 1, 2],
            "opposite": [2, 1, 2, 1, 2, 1],
        }
    )
    label = pd.Series([1, 2, 1, 2, 1, 2], index=frame.index, name="label")

    isolated = compute_isolated_factor_signal_metrics(frame, label)

    assert isolated["aligned"]["Rank IC"] == pytest.approx(1.0)
    assert isolated["opposite"]["Rank IC"] == pytest.approx(-1.0)
    assert isolated["metric_unique_counts"]["Rank IC"] == 2


def test_isolated_factor_metrics_accept_explicit_polars_frames() -> None:
    from quantaalpha.factors.runner import compute_isolated_factor_signal_metrics

    features = pl.DataFrame(
        {
            "datetime": ["2025-01-02", "2025-01-02", "2025-01-03", "2025-01-03", "2025-01-04", "2025-01-04"],
            "instrument": ["A", "B", "A", "B", "A", "B"],
            "aligned": [1, 2, 1, 2, 1, 2],
            "opposite": [2, 1, 2, 1, 2, 1],
        }
    )
    labels = pl.DataFrame(
        {
            "datetime": ["2025-01-02", "2025-01-02", "2025-01-03", "2025-01-03", "2025-01-04", "2025-01-04"],
            "instrument": ["A", "B", "A", "B", "A", "B"],
            "label": [1, 2, 1, 2, 1, 2],
        }
    )

    isolated = compute_isolated_factor_signal_metrics(features, labels)

    assert isolated["aligned"]["Rank IC"] == pytest.approx(1.0)
    assert isolated["opposite"]["Rank IC"] == pytest.approx(-1.0)
    assert isolated["metric_unique_counts"]["Rank IC"] == 2


def test_isolated_factor_portfolio_metrics_use_each_factor_signal() -> None:
    from quantaalpha.factors.runner import compute_isolated_factor_portfolio_metrics

    index = pd.MultiIndex.from_product(
        [pd.to_datetime(["2024-01-01", "2024-01-02"]), ["000001.SZ", "000002.SZ"]],
        names=["datetime", "instrument"],
    )
    features = pd.DataFrame(
        {
            "strong": [1.0, 2.0, 3.0, 4.0],
            "weak": [4.0, 3.0, 2.0, 1.0],
        },
        index=index,
    )

    class FakeBacktester:
        def __init__(self, config, market):
            pass

        def run(self, prediction):
            if prediction.name == "strong":
                return {"information_ratio": 1.2, "annualized_return": 0.20}, pd.DataFrame(), pd.DataFrame()
            return {"information_ratio": -0.4, "annualized_return": -0.05}, pd.DataFrame(), pd.DataFrame()

    isolated = compute_isolated_factor_portfolio_metrics(
        features,
        market=pd.DataFrame(),
        config={},
        backtester_cls=FakeBacktester,
    )

    assert isolated["strong"]["information_ratio"] == pytest.approx(1.2)
    assert isolated["weak"]["information_ratio"] == pytest.approx(-0.4)


def test_quality_overlay_emits_structured_gate_event(monkeypatch) -> None:
    from quantaalpha.pipeline.quality_overlay import log_quality_overlay_event

    events = []
    monkeypatch.setattr("quantaalpha.pipeline.quality_overlay.logger.info", events.append)

    log_quality_overlay_event(
        "pre_backtest",
        "kept",
        factor_name="alpha_a",
        metrics={"valid_ratio": 1.0, "nan_ratio": 0.0},
        reasons=[],
    )

    assert events
    assert "quality_overlay_event" in events[0]
    assert "gate=pre_backtest" in events[0]
    assert "decision=kept" in events[0]
    assert "factor=alpha_a" in events[0]


def test_knowledge_graph_load_diagnostics_include_path_and_empty_reason(monkeypatch, tmp_path) -> None:
    from quantaalpha.coder.costeer import knowledge_management

    events = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(knowledge_management.logger, "info", events.append)

    knowledge_management.CoSTEERKnowledgeBaseV2()

    load_events = [event for event in events if "Knowledge Graph loaded" in event]
    assert load_events
    assert f"path={tmp_path / 'graph.pkl'}" in load_events[0]
    assert "exists=False" in load_events[0]
    assert "size=0" in load_events[0]
    assert "empty_reason=graph_file_missing" in load_events[0]
