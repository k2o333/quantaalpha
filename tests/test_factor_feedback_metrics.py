from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from quantaalpha.factors.feedback import AlphaAgentQlibFactorHypothesisExperiment2Feedback


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
