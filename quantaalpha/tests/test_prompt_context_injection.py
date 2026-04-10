import os
import sys
import types
from unittest.mock import MagicMock, patch

_fake_factor_experiment = types.ModuleType("quantaalpha.factors.experiment")
_fake_factor_experiment.QlibFactorExperiment = type("QlibFactorExperiment", (), {})
sys.modules.setdefault("quantaalpha.factors.experiment", _fake_factor_experiment)

from quantaalpha.core.proposal import Trace
from quantaalpha.factors.proposal import (
    AlphaAgentHypothesis,
    AlphaAgentHypothesis2FactorExpression,
    AlphaAgentHypothesisGen,
    log_rendered_prompt_pair,
)


def _make_scenario():
    scen = MagicMock()
    scen.get_scenario_all_desc.return_value = "daily alpha research scenario"
    scen.background = "daily alpha research background"
    return scen


def test_hypothesis_prompt_includes_similarity_context():
    scen = _make_scenario()
    trace = Trace(scen=scen)
    generator = AlphaAgentHypothesisGen(
        scen,
        potential_direction="$close - $open",
        similarity_engine_cfg={"enabled": True, "metrics": {"rag": {"enabled": False}, "ast": {"enabled": True}, "jaccard": {"enabled": True}}},
        library_path="/tmp/library.json",
    )

    with patch("quantaalpha.factors.proposal.build_similarity_reference", return_value="SIMILAR FACTOR CONTEXT") as mock_build:
        system_prompt, user_prompt, _ = generator.render_generation_prompts(trace)

    assert "SIMILAR FACTOR CONTEXT" in user_prompt
    assert "daily alpha research scenario" in system_prompt
    mock_build.assert_called_once()


def test_experiment_context_includes_similarity_reference():
    scen = _make_scenario()
    trace = Trace(scen=scen)
    hypothesis = AlphaAgentHypothesis(
        hypothesis="Use close-open spread reversal",
        concise_observation="obs",
        concise_knowledge="knowledge",
        concise_justification="justification",
        concise_specification="spec",
    )
    constructor = AlphaAgentHypothesis2FactorExpression(
        similarity_engine_cfg={"enabled": True, "metrics": {"rag": {"enabled": False}, "ast": {"enabled": True}, "jaccard": {"enabled": True}}},
        library_path="/tmp/library.json",
    )

    with patch("quantaalpha.factors.proposal.build_similarity_reference", return_value="SIMILAR FACTOR CONTEXT") as mock_build:
        context, _ = constructor.prepare_context(hypothesis, trace)

    assert context["RAG"] == "SIMILAR FACTOR CONTEXT"
    mock_build.assert_called_once()


def test_log_rendered_prompt_pair_logs_full_prompt_when_enabled():
    with patch.dict(os.environ, {"QUANTAALPHA_LOG_PROMPTS": "1"}, clear=False):
        with patch("quantaalpha.factors.proposal.logger") as mock_logger:
            log_rendered_prompt_pair("hypothesis_gen", "SYSTEM BODY", "USER BODY")

    joined = "\n".join(str(call) for call in mock_logger.info.call_args_list)
    assert "[PROMPT] hypothesis_gen" in joined
    assert "SYSTEM BODY" in joined
    assert "USER BODY" in joined
