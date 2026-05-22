from __future__ import annotations


def test_llm_advisor_provider_name_falls_back_without_error() -> None:
    from quantaalpha.continuous.mining_orchestration import MiningOrchestrationMixin

    class Harness(MiningOrchestrationMixin):
        pass

    harness = Harness()
    result = harness._execute_llm_advisor(
        {
            "allowed_next": ["crossover", "stop"],
            "fallback_next": "crossover",
            "llm_provider": "litellm_modelbig",
            "cycle_id": "cycle-1",
            "step_index": 3,
        },
        "llm_decide",
    )

    assert result.action == "llm_advisor"
    assert result.status == "fallback"
    assert result.error is None
    assert result.metadata["selected_next"] == "crossover"
    assert result.metadata["fallback_reason"] == "provider_name_unbound"
    assert result.metadata["llm_provider"] == "litellm_modelbig"
