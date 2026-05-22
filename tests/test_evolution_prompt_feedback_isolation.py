from __future__ import annotations

from quantaalpha.pipeline.evolution.mutation import MutationOperator
from quantaalpha.pipeline.evolution.crossover import CrossoverOperator
from quantaalpha.pipeline.evolution.trajectory import RoundPhase, StrategyTrajectory


def _parent() -> StrategyTrajectory:
    return StrategyTrajectory(
        trajectory_id="parent_a",
        direction_id=0,
        round_idx=0,
        phase=RoundPhase.ORIGINAL,
        hypothesis="Momentum volatility hypothesis",
        factors=[{"name": "factor_a", "expression": "RANK($close)"}],
        backtest_metrics={"IC": 0.0567, "RankIC": 0.1234, "annualized_return": 0.7395, "information_ratio": 1.4567},
        feedback="Observed annualized_return=0.7395 and RankIC=0.1234 on the test window.",
    )


def test_mutation_generation_prompt_includes_parent_backtest_feedback(monkeypatch) -> None:
    captured: dict[str, str] = {}

    class FakeAPIBackend:
        def build_messages_and_create_chat_completion(self, *, user_prompt: str, system_prompt: str, **kwargs):
            del system_prompt, kwargs
            captured["user_prompt"] = user_prompt
            return '{"new_hypothesis":"x","exploration_direction":"y","orthogonality_reason":"z","expected_characteristics":"w"}'

    monkeypatch.setattr("quantaalpha.pipeline.evolution.mutation.APIBackend", FakeAPIBackend)

    MutationOperator().generate_mutation(_parent())

    prompt = captured["user_prompt"]
    assert "IC=0.0567" in prompt
    assert "Rank IC=0.1234" in prompt
    assert "Information Ratio=1.4567" in prompt
    assert "Annualized Return=0.7395" in prompt
    assert "Observed annualized_return=0.7395" in prompt


def test_crossover_generation_prompt_includes_parent_backtest_feedback(monkeypatch) -> None:
    captured: dict[str, str] = {}

    class FakeAPIBackend:
        def build_messages_and_create_chat_completion(self, *, user_prompt: str, system_prompt: str, **kwargs):
            del system_prompt, kwargs
            captured["user_prompt"] = user_prompt
            return '{"hybrid_hypothesis":"x","fusion_logic":"y","innovation_points":"z","expected_benefits":"w"}'

    monkeypatch.setattr("quantaalpha.pipeline.evolution.crossover.APIBackend", FakeAPIBackend)

    CrossoverOperator().generate_crossover([_parent(), _parent()])

    prompt = captured["user_prompt"]
    assert "Rank IC=0.1234" in prompt
    assert "Annualized Return=0.7395" in prompt
    assert "Observed annualized_return=0.7395" in prompt


def test_mutation_suffix_exploit_mode_preserves_parent_core_structure(monkeypatch) -> None:
    class FakeAPIBackend:
        def build_messages_and_create_chat_completion(self, **kwargs):
            return '{"new_hypothesis":"x","exploration_direction":"y","orthogonality_reason":"z","expected_characteristics":"w"}'

    monkeypatch.setattr("quantaalpha.pipeline.evolution.mutation.APIBackend", FakeAPIBackend)

    suffix = MutationOperator().generate_mutation_prompt_suffix(_parent(), mutation_mode="exploit")

    assert "Mutation Mode: exploit" in suffix
    assert "preserve the parent signal family" in suffix
    assert "IC=0.0567" in suffix
    assert "Rank IC=0.1234" in suffix
    assert "Information Ratio=1.4567" in suffix
    assert "Annualized Return=0.7395" in suffix


def test_mutation_suffix_explore_mode_requires_outperformance_hypothesis(monkeypatch) -> None:
    class FakeAPIBackend:
        def build_messages_and_create_chat_completion(self, **kwargs):
            return '{"new_hypothesis":"x","exploration_direction":"y","orthogonality_reason":"z","expected_characteristics":"w"}'

    monkeypatch.setattr("quantaalpha.pipeline.evolution.mutation.APIBackend", FakeAPIBackend)

    suffix = MutationOperator().generate_mutation_prompt_suffix(_parent(), mutation_mode="explore")

    assert "Mutation Mode: explore" in suffix
    assert "why the child should beat the parent Rank IC" in suffix
    assert "Rank IC=0.1234" in suffix
