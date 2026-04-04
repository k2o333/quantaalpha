"""Tests for ProviderPool integration in APIBackend."""

from unittest.mock import MagicMock, patch

import pytest


class TestProviderPoolIntegration:
    """Tests for ProviderPool injection into APIBackend."""

    def test_api_backend_accepts_provider_pool(self):
        """APIBackend accepts provider_pool parameter."""
        from quantaalpha.llm.client import APIBackend
        from quantaalpha.llm.provider_pool import ProviderPool

        pool = ProviderPool()
        with patch("quantaalpha.llm.client.openai.OpenAI", return_value=MagicMock()):
            backend = APIBackend(provider_pool=pool)
            assert backend._provider_pool is pool

    def test_api_backend_without_pool(self):
        """APIBackend works without provider_pool (backward compat)."""
        from quantaalpha.llm.client import APIBackend

        with patch("quantaalpha.llm.client.openai.OpenAI", return_value=MagicMock()):
            backend = APIBackend()
            assert backend._provider_pool is None
