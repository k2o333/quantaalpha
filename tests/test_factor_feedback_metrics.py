from __future__ import annotations

import json
from types import SimpleNamespace

import pandas as pd

from quantaalpha.factors.feedback import AlphaAgentQlibFactorHypothesisExperiment2Feedback
from quantaalpha.pipeline.persistence import get_cross_run_historical_best_reference


class FakeScenario:
    config: dict = {}

    def get_scenario_all_desc(self) -> str:
        return "daily alpha factor mining"


class FakeTask:
    def get_task_information_and_implementation_result(self) -> dict[str, object]:
        return {
            "factor_name": "factor_a",
            "factor_description": "test factor",
            "factor_formulation": "RANK(close)",
            "variables": {"$close": "close"},
            "factor_implementation": "True",
            "factor_expression": "RANK($close)",
        }


def test_alpha_agent_feedback_prompt_includes_backtest_metrics(monkeypatch) -> None:
    captured: dict[str, str] = {}

    class FakeAPIBackend:
        def build_messages(self, *, user_prompt: str, system_prompt: str):
            del system_prompt
            captured["user_prompt"] = user_prompt
            return []

    monkeypatch.setattr("quantaalpha.factors.feedback._new_feedback_api_backend", FakeAPIBackend)
    monkeypatch.setattr(
        "quantaalpha.factors.feedback.call_structured",
        lambda *args, **kwargs: {
            "Observations": "observed",
            "Feedback for Hypothesis": "feedback",
            "New Hypothesis": "new",
            "Reasoning": "reason",
            "Replace Best Result": "no",
        },
    )

    result = pd.DataFrame(
        {"0": [0.012345, 0.045678, 1.2345, 0.0789]},
        index=[
            "IC",
            "Rank IC",
            "1day.excess_return_without_cost.information_ratio",
            "1day.excess_return_without_cost.annualized_return",
        ],
    )
    exp = SimpleNamespace(
        result=result,
        sub_tasks=[FakeTask()],
        based_experiments=[],
    )

    AlphaAgentQlibFactorHypothesisExperiment2Feedback(FakeScenario()).generate_feedback(
        exp,
        SimpleNamespace(hypothesis="hypothesis text"),
        SimpleNamespace(),
    )

    prompt = captured["user_prompt"]
    assert "Backtest Metrics" in prompt
    assert "IC=0.0123" in prompt
    assert "Rank IC=0.0457" in prompt
    assert "Information Ratio=1.2345" in prompt
    assert "Annualized Return=0.0789" in prompt


def test_cross_run_historical_best_uses_only_active_records(tmp_path) -> None:
    from quantaalpha.factors.factor_store_facade import FactorStoreFacade

    store = FactorStoreFacade(str(tmp_path / "parquet_store"))
    _write_factor_record(
        store,
        factor_id="candidate_high",
        status="candidate",
        rank_ic=0.99,
        information_ratio=9.9,
    )
    _write_factor_record(
        store,
        factor_id="active_best_rank",
        status="active",
        rank_ic="0.047",
        information_ratio=0.4,
    )
    _write_factor_record(
        store,
        factor_id="active_best_ir",
        status="active",
        rank_ic=0.02,
        information_ratio="1.25",
    )

    reference = get_cross_run_historical_best_reference(str(tmp_path / "parquet_store"))

    assert reference["available"] is True
    assert reference["total_active"] == 2
    assert reference["best_rank_ic"] == 0.047
    assert reference["best_rank_ic_factor_name"] == "active_best_rank"
    assert reference["best_information_ratio"] == 1.25
    assert reference["best_information_ratio_factor_name"] == "active_best_ir"


def test_alpha_agent_feedback_prompt_includes_cross_run_reference(monkeypatch) -> None:
    captured: dict[str, str] = {}

    class FakeAPIBackend:
        def build_messages(self, *, user_prompt: str, system_prompt: str):
            del system_prompt
            captured["user_prompt"] = user_prompt
            return []

    monkeypatch.setattr("quantaalpha.factors.feedback._new_feedback_api_backend", FakeAPIBackend)
    monkeypatch.setattr(
        "quantaalpha.factors.feedback.call_structured",
        lambda *args, **kwargs: {
            "Observations": "observed",
            "Feedback for Hypothesis": "feedback",
            "New Hypothesis": "new",
            "Reasoning": "reason",
            "Replace Best Result": "no",
        },
    )

    result = pd.DataFrame(
        {"0": [0.012345, 0.045678]},
        index=["IC", "Rank IC"],
    )
    exp = SimpleNamespace(
        result=result,
        sub_tasks=[FakeTask()],
        based_experiments=[],
    )

    AlphaAgentQlibFactorHypothesisExperiment2Feedback(FakeScenario()).generate_feedback(
        exp,
        SimpleNamespace(hypothesis="hypothesis text"),
        SimpleNamespace(),
        cross_run_best={
            "available": True,
            "total_active": 2,
            "best_rank_ic": 0.047,
            "best_information_ratio": 1.25,
            "best_rank_ic_factor_name": "active_best_rank",
            "best_information_ratio_factor_name": "active_best_ir",
        },
    )

    prompt = captured["user_prompt"]
    assert "Cross-Run Historical Best (2 active factors)" in prompt
    assert "Best Rank IC: 0.0470" in prompt
    assert "active_best_rank" in prompt
    assert "Best Information Ratio: 1.2500" in prompt
    assert "active_best_ir" in prompt


def _write_factor_record(
    store,
    *,
    factor_id: str,
    status: str,
    rank_ic,
    information_ratio,
) -> None:
    store.write_factor(
        {
            "factor_id": factor_id,
            "factor_name": factor_id,
            "factor_expression": "RANK($close)",
            "factor_expression_normalized": "RANK($close)",
            "expression_hash": factor_id,
            "evaluation_status": status,
            "created_at": "2026-05-23T00:00:00",
            "updated_at": "2026-05-23T00:00:00",
            "sequence": 1,
            "op": "upsert",
            "tags_json": json.dumps([]),
            "metadata_json": json.dumps({}),
            "backtest_results_json": json.dumps(
                {
                    "Rank IC": rank_ic,
                    "information_ratio": information_ratio,
                }
            ),
        }
    )
