"""Tests for thread-safe behavior of LLM client degradation state and SQLite cache."""

from concurrent.futures import ThreadPoolExecutor

import pytest


class TestDegradationStateThreadSafety:
    """Tests for thread-safe degradation-state bookkeeping."""

    def test_record_tool_call_capability_failure_is_thread_safe(self):
        """Concurrent calls to _record_tool_call_capability_failure must not lose updates."""
        from quantaalpha.llm import client as client_module

        client_module._MODEL_DEGRADATION_STATE.clear()

        def hit():
            client_module._record_tool_call_capability_failure("test-model")

        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(lambda _: hit(), range(8)))

        state = client_module._get_model_degradation_state("test-model")
        assert state["tool_call_failure_count"] >= 3
        assert state["force_text_json_fallback"] is True


class TestSQLiteCacheThreadSafety:
    """Tests for thread-safe SQLite prompt cache operations."""

    def test_sqlite_lazy_cache_supports_cross_thread_chat_get_and_set(self, tmp_path):
        """Cross-thread chat_set and chat_get must not corrupt or lose data."""
        from quantaalpha.llm.client import SQliteLazyCache

        # Reset singleton instance to avoid stale state from other tests
        SQliteLazyCache._instance = None

        cache = SQliteLazyCache(cache_location=str(tmp_path / "prompt_cache.db"))

        def write_value(i: int):
            cache.chat_set(f"k{i}", f"v{i}")
            return cache.chat_get(f"k{i}")

        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(write_value, range(4)))

        assert results == ["v0", "v1", "v2", "v3"]

        # Clean up singleton for subsequent tests
        SQliteLazyCache._instance = None
