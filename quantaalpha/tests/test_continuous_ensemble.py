"""Tests for ensemble integration in AlphaAgentLoop."""

import sys
import threading
import types
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest


_fake_factor_experiment = types.ModuleType("quantaalpha.factors.experiment")
_fake_factor_experiment.QlibFactorExperiment = type("QlibFactorExperiment", (), {})
sys.modules.setdefault("quantaalpha.factors.experiment", _fake_factor_experiment)


@contextmanager
def mock_loop_dependencies():
    """Mock all dependencies needed to instantiate AlphaAgentLoop."""
    mock_logger = MagicMock()
    mock_logger.tag.return_value.__enter__ = MagicMock(return_value=None)
    mock_logger.tag.return_value.__exit__ = MagicMock(return_value=None)
    mock_logger.info = MagicMock()
    mock_logger.warning = MagicMock()
    mock_logger.error = MagicMock()
    mock_logger.log_object = MagicMock()

    with patch("quantaalpha.pipeline.loop.import_class", return_value=MagicMock()):
        with patch("quantaalpha.pipeline.loop.logger", mock_logger):
            with patch("quantaalpha.log.time.measure_time", lambda f: f):
                yield


class TestEnsembleIntegration:
    """Tests for ensemble_config in AlphaAgentLoop."""

    def test_alpha_agent_loop_accepts_ensemble_config(self):
        """AlphaAgentLoop accepts ensemble_config parameter."""
        from quantaalpha.pipeline.loop import AlphaAgentLoop
        from quantaalpha.pipeline.settings import ALPHA_AGENT_FACTOR_PROP_SETTING

        ensemble_cfg = {
            "enabled": True,
            "strategy": "voting",
            "models": [{"name": "gpt-4-turbo", "tier": 3}],
        }

        with mock_loop_dependencies():
            loop = AlphaAgentLoop(
                ALPHA_AGENT_FACTOR_PROP_SETTING,
                potential_direction="test direction",
                stop_event=threading.Event(),
                ensemble_config=ensemble_cfg,
            )
            assert loop._ensemble_config == ensemble_cfg

    def test_alpha_agent_loop_empty_ensemble_config(self):
        """AlphaAgentLoop defaults to empty ensemble_config."""
        from quantaalpha.pipeline.loop import AlphaAgentLoop
        from quantaalpha.pipeline.settings import ALPHA_AGENT_FACTOR_PROP_SETTING

        with mock_loop_dependencies():
            loop = AlphaAgentLoop(
                ALPHA_AGENT_FACTOR_PROP_SETTING,
                potential_direction="test direction",
                stop_event=threading.Event(),
            )
            assert loop._ensemble_config == {}


class TestEnsembleProposeStep:
    """Tests for ensemble in propose step."""

    def test_propose_with_ensemble_disabled(self):
        """When ensemble disabled, uses hypothesis_generator.gen()."""
        from quantaalpha.pipeline.loop import AlphaAgentLoop
        from quantaalpha.pipeline.settings import ALPHA_AGENT_FACTOR_PROP_SETTING
        from quantaalpha.factors.proposal import AlphaAgentHypothesis

        with mock_loop_dependencies():
            loop = AlphaAgentLoop(
                ALPHA_AGENT_FACTOR_PROP_SETTING,
                potential_direction="test direction",
                stop_event=threading.Event(),
                ensemble_config={"enabled": False},
            )
            loop.hypothesis_generator = MagicMock()
            loop.hypothesis_generator.gen.return_value = AlphaAgentHypothesis(
                hypothesis="test hypothesis",
                concise_observation="obs",
                concise_knowledge="knowledge",
                concise_justification="justification",
                concise_specification="spec",
            )
            loop.trace = MagicMock()

            result = loop.factor_propose({})
            loop.hypothesis_generator.gen.assert_called_once()
            assert isinstance(result, AlphaAgentHypothesis)

    def test_propose_with_ensemble_enabled_fallback(self):
        """When ensemble enabled but no models, falls back to single model."""
        from quantaalpha.pipeline.loop import AlphaAgentLoop
        from quantaalpha.pipeline.settings import ALPHA_AGENT_FACTOR_PROP_SETTING
        from quantaalpha.factors.proposal import AlphaAgentHypothesis

        with mock_loop_dependencies():
            loop = AlphaAgentLoop(
                ALPHA_AGENT_FACTOR_PROP_SETTING,
                potential_direction="test direction",
                stop_event=threading.Event(),
                ensemble_config={"enabled": True, "models": []},
            )
            loop.hypothesis_generator = MagicMock()
            loop.hypothesis_generator.gen.return_value = AlphaAgentHypothesis(
                hypothesis="fallback hypothesis",
                concise_observation="obs",
                concise_knowledge="knowledge",
                concise_justification="justification",
                concise_specification="spec",
            )
            loop.trace = MagicMock()

            result = loop.factor_propose({})
            loop.hypothesis_generator.gen.assert_called_once()
            assert isinstance(result, AlphaAgentHypothesis)

    def test_propose_normalizes_dict_output_to_alpha_agent_hypothesis(self):
        """factor_propose normalizes dict outputs before returning."""
        from quantaalpha.pipeline.loop import AlphaAgentLoop
        from quantaalpha.pipeline.settings import ALPHA_AGENT_FACTOR_PROP_SETTING
        from quantaalpha.factors.proposal import AlphaAgentHypothesis

        normalized = AlphaAgentHypothesis(
            hypothesis="normalized hypothesis",
            concise_observation="obs",
            concise_knowledge="knowledge",
            concise_justification="justification",
            concise_specification="spec",
        )

        with mock_loop_dependencies():
            loop = AlphaAgentLoop(
                ALPHA_AGENT_FACTOR_PROP_SETTING,
                potential_direction="test direction",
                stop_event=threading.Event(),
                ensemble_config={"enabled": True, "models": [{"name": "m1"}]},
            )
            loop.hypothesis_generator = MagicMock()
            loop.hypothesis_generator.convert_response.return_value = normalized
            loop.trace = MagicMock()
            loop._propose_with_ensemble = MagicMock(return_value={"hypothesis": "raw"})

            result = loop.factor_propose({})

            loop.hypothesis_generator.convert_response.assert_called_once()
            assert result is normalized

    def test_propose_with_ensemble_empty_output_falls_back_to_single_model(self):
        """_propose_with_ensemble falls back to single model when aggregation is empty."""
        from quantaalpha.pipeline.loop import AlphaAgentLoop
        from quantaalpha.pipeline.settings import ALPHA_AGENT_FACTOR_PROP_SETTING
        from quantaalpha.factors.proposal import AlphaAgentHypothesis

        fallback = AlphaAgentHypothesis(
            hypothesis="fallback hypothesis",
            concise_observation="obs",
            concise_knowledge="knowledge",
            concise_justification="justification",
            concise_specification="spec",
        )

        with mock_loop_dependencies():
            loop = AlphaAgentLoop(
                ALPHA_AGENT_FACTOR_PROP_SETTING,
                potential_direction="test direction",
                stop_event=threading.Event(),
                ensemble_config={"enabled": True, "models": [{"name": "m1"}]},
            )
            loop.hypothesis_generator = MagicMock()
            loop.hypothesis_generator.gen.return_value = fallback
            loop.trace = MagicMock()

            mock_result = MagicMock()
            mock_result.output = []

            with patch("quantaalpha.llm.client.APIBackend.build_messages_and_create_chat_completion", return_value="raw"), \
                 patch("quantaalpha.llm.ensemble.EnsembleAggregator.aggregate", return_value=mock_result):
                result = loop._propose_with_ensemble()

            loop.hypothesis_generator.gen.assert_called_once_with(loop.trace)
            assert result is fallback

    def test_propose_with_ensemble_uses_rendered_prompt_not_trace_repr(self):
        """Ensemble propose must use the hypothesis generator's rendered prompt."""
        from quantaalpha.pipeline.loop import AlphaAgentLoop
        from quantaalpha.pipeline.settings import ALPHA_AGENT_FACTOR_PROP_SETTING

        captured_prompts = {}

        class FakeBackend:
            def __init__(self, *args, **kwargs):
                pass

            def build_messages(self, user_prompt, system_prompt):
                captured_prompts["user_prompt"] = user_prompt
                captured_prompts["system_prompt"] = system_prompt
                return [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]

        with mock_loop_dependencies():
            loop = AlphaAgentLoop(
                ALPHA_AGENT_FACTOR_PROP_SETTING,
                potential_direction="price-volume divergence",
                stop_event=threading.Event(),
                ensemble_config={"enabled": True, "models": [{"name": "m1"}]},
            )
            loop._provider_name_to_model = {"m1": "glm-4.7-flash"}
            loop.hypothesis_generator = MagicMock()
            loop.hypothesis_generator.render_generation_prompts.return_value = (
                "system prompt",
                "rendered prompt with price-volume divergence",
                True,
            )

            mock_result = MagicMock()
            mock_result.output = [{"hypothesis": "h"}]

            with (
                patch("quantaalpha.pipeline.loop.APIBackend", FakeBackend),
                patch("quantaalpha.pipeline.loop.call_structured", return_value={"hypothesis": "h"}),
                patch("quantaalpha.llm.ensemble.EnsembleAggregator.aggregate", return_value=mock_result),
            ):
                loop._propose_with_ensemble()

        assert captured_prompts["user_prompt"], "Expected ensemble propose to render a non-empty user prompt"
        assert "Trace object" not in captured_prompts["user_prompt"]
        assert "<quantaalpha.core.proposal.Trace object" not in captured_prompts["user_prompt"]
        assert "price-volume divergence" in captured_prompts["user_prompt"]

    def test_propose_with_collect_all_returns_hypothesis_bundle(self):
        """collect_all must return a Hypothesis-compatible bundle, not a bare dict."""
        from quantaalpha.pipeline.loop import AlphaAgentLoop
        from quantaalpha.pipeline.settings import ALPHA_AGENT_FACTOR_PROP_SETTING
        from quantaalpha.factors.proposal import EnsembleHypothesisBundle

        with mock_loop_dependencies():
            loop = AlphaAgentLoop(
                ALPHA_AGENT_FACTOR_PROP_SETTING,
                potential_direction="test direction",
                stop_event=threading.Event(),
                ensemble_config={"enabled": True, "strategy": "collect_all", "models": [{"name": "m1"}, {"name": "m2"}]},
            )
            loop.hypothesis_generator = MagicMock()
            loop.trace = MagicMock()
            loop._propose_with_ensemble = MagicMock(
                return_value=EnsembleHypothesisBundle(
                    hypothesis="bundle summary",
                    concise_observation="obs",
                    concise_knowledge="knowledge",
                    concise_justification="justification",
                    concise_specification="spec",
                    hypotheses=[
                        {"model": "m1", "hypothesis": {"hypothesis": "alpha"}},
                        {"model": "m2", "hypothesis": {"hypothesis": "beta"}},
                    ],
                    ensemble_strategy="collect_all",
                    num_models=2,
                    primary_hypothesis_index=0,
                )
            )

            result = loop.factor_propose({})

            assert isinstance(result, EnsembleHypothesisBundle)
            assert result.hypotheses[0]["hypothesis"]["hypothesis"] == "alpha"
            loop.hypothesis_generator.convert_response.assert_not_called()

    def test_propose_with_collect_all_structured_aggregate_builds_bundle(self):
        """_propose_with_ensemble should wrap collect_all aggregate output into a bundle."""
        from quantaalpha.pipeline.loop import AlphaAgentLoop
        from quantaalpha.pipeline.settings import ALPHA_AGENT_FACTOR_PROP_SETTING
        from quantaalpha.factors.proposal import EnsembleHypothesisBundle

        class FakeBackend:
            def __init__(self, *args, **kwargs):
                pass

            def build_messages(self, user_prompt, system_prompt):
                return [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]

        with mock_loop_dependencies():
            loop = AlphaAgentLoop(
                ALPHA_AGENT_FACTOR_PROP_SETTING,
                potential_direction="test direction",
                stop_event=threading.Event(),
                ensemble_config={"enabled": True, "strategy": "collect_all", "models": [{"name": "m1"}, {"name": "m2"}]},
            )
            loop._provider_name_to_model = {"m1": "glm-4.7-flash", "m2": "mistral-small-latest"}
            loop.hypothesis_generator = MagicMock()
            loop.hypothesis_generator.render_generation_prompts.return_value = ("system", "user", True)
            loop.trace = MagicMock()

            aggregate_payload = {
                "hypotheses": [
                    {"model": "m1", "hypothesis": {"hypothesis": "alpha", "concise_observation": "obs1"}},
                    {"model": "m2", "hypothesis": {"hypothesis": "beta", "concise_observation": "obs2"}},
                ],
                "num_models": 2,
                "strategy": "collect_all",
            }
            mock_result = MagicMock()
            mock_result.output = [aggregate_payload]

            with (
                patch("quantaalpha.pipeline.loop.APIBackend", FakeBackend),
                patch("quantaalpha.pipeline.loop.call_structured", side_effect=[
                    {"hypothesis": "alpha", "concise_observation": "obs1"},
                    {"hypothesis": "beta", "concise_observation": "obs2"},
                ]),
                patch("quantaalpha.llm.ensemble.EnsembleAggregator.aggregate", return_value=mock_result),
            ):
                result = loop._propose_with_ensemble()

            assert isinstance(result, EnsembleHypothesisBundle)
            assert result.num_models == 2
            assert result.ensemble_strategy == "collect_all"
            assert result.hypotheses[1]["hypothesis"]["hypothesis"] == "beta"

    def test_factor_construct_routes_bundle_to_multi_hypothesis_converter(self):
        """factor_construct should use the multi-hypothesis path for ensemble bundles."""
        from quantaalpha.pipeline.loop import AlphaAgentLoop
        from quantaalpha.pipeline.settings import ALPHA_AGENT_FACTOR_PROP_SETTING
        from quantaalpha.factors.proposal import EnsembleHypothesisBundle

        fake_factor = MagicMock()
        fake_factor.sub_tasks = []

        with mock_loop_dependencies():
            loop = AlphaAgentLoop(
                ALPHA_AGENT_FACTOR_PROP_SETTING,
                potential_direction="test direction",
                stop_event=threading.Event(),
                ensemble_config={"enabled": True, "strategy": "collect_all"},
            )
            loop.trace = MagicMock()
            loop.factor_constructor = MagicMock()
            loop.factor_constructor.convert_multi_hypothesis.return_value = fake_factor
            loop._register_factors_from_experiment = MagicMock()

            bundle = EnsembleHypothesisBundle(
                hypothesis="bundle summary",
                concise_observation="obs",
                concise_knowledge="knowledge",
                concise_justification="justification",
                concise_specification="spec",
                hypotheses=[
                    {"model": "m1", "hypothesis": {"hypothesis": "alpha"}},
                    {"model": "m2", "hypothesis": {"hypothesis": "beta"}},
                ],
                ensemble_strategy="collect_all",
                num_models=2,
                primary_hypothesis_index=0,
            )

            result = loop.factor_construct({"factor_propose": bundle})

            loop.factor_constructor.convert_multi_hypothesis.assert_called_once_with(bundle, loop.trace)
            loop.factor_constructor.convert.assert_not_called()
            assert result is fake_factor
