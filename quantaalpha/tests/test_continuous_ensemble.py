"""Tests for ensemble integration in AlphaAgentLoop."""

import threading
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest


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
