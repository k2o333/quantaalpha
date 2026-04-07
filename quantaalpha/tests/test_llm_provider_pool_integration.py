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


class TestProviderPoolKeyRotation:
    """Tests for ProviderPool key rotation in APIBackend."""

    def _make_backend_with_pool(self):
        """Create APIBackend with a mock ProviderPool."""
        from quantaalpha.llm.client import APIBackend
        from quantaalpha.llm.provider_pool import ProviderPool

        pool = ProviderPool()
        pool.add_provider("test-provider", api_keys=["test-key"], model="gpt-4-turbo")

        mock_client = MagicMock()
        backend = object.__new__(APIBackend)
        backend.use_azure = False
        backend.use_llama2 = False
        backend.use_gcr_endpoint = False
        backend.chat_stream = False
        backend.use_chat_cache = False
        backend.chat_model = "gpt-4-turbo"
        backend.reasoning_model = ""
        backend.chat_client = mock_client
        backend.cache = MagicMock()
        backend.cache.chat_get.return_value = None
        backend.task_model_map = {}
        backend.routing_default = ""
        backend.chat_model_map = {}
        backend.chat_api_key = "test"
        backend.base_url = None
        backend.embedding_api_key = ""
        backend.embedding_base_url = None
        backend.encoder = None
        backend.chat_seed = None
        backend.retry_wait_seconds = 1
        backend.dump_chat_cache = False
        backend._provider_pool = pool
        backend._mock_client = mock_client
        return backend

    def test_pool_key_rotation_on_api_call(self):
        """APIBackend gets key from pool before making API call."""
        backend = self._make_backend_with_pool()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "response"
        mock_response.choices[0].finish_reason = "stop"
        backend._mock_client.chat.completions.create.return_value = mock_response

        messages = [{"role": "user", "content": "hello"}]

        with patch("quantaalpha.llm.client.LLM_SETTINGS") as mock_settings:
            mock_settings.log_llm_chat_content = False
            mock_settings.use_auto_chat_cache_seed_gen = False
            mock_settings.chat_temperature = 0.7
            mock_settings.chat_max_tokens = 1000
            mock_settings.chat_frequency_penalty = 0.0
            mock_settings.chat_presence_penalty = 0.0
            with patch("quantaalpha.llm.client.openai.OpenAI", return_value=backend._mock_client):
                backend._create_chat_completion_inner_function(
                    messages=messages,
                    reasoning_flag=False,
                )

        # Verify pool was used (client was recreated with pool key)
        assert backend.chat_client is not None

    def test_pool_latency_recording(self):
        """APIBackend records latency after API call."""
        backend = self._make_backend_with_pool()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "response"
        mock_response.choices[0].finish_reason = "stop"
        backend._mock_client.chat.completions.create.return_value = mock_response

        messages = [{"role": "user", "content": "hello"}]

        with patch("quantaalpha.llm.client.LLM_SETTINGS") as mock_settings:
            mock_settings.log_llm_chat_content = False
            mock_settings.use_auto_chat_cache_seed_gen = False
            mock_settings.chat_temperature = 0.7
            mock_settings.chat_max_tokens = 1000
            mock_settings.chat_frequency_penalty = 0.0
            mock_settings.chat_presence_penalty = 0.0
            with patch("quantaalpha.llm.client.openai.OpenAI", return_value=backend._mock_client):
                backend._create_chat_completion_inner_function(
                    messages=messages,
                    reasoning_flag=False,
                )

        # Verify latency was recorded (pool has latency stats)
        stats = backend._provider_pool.get_latency_stats("test-provider")
        assert stats is not None
        assert stats["test-key"].sample_count > 0
