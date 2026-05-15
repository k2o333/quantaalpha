"""Tests for capability-based provider routing."""

import pytest


class TestProviderConfigCapability:
    """Tests for ProviderConfig tags and tier fields."""

    def test_provider_config_has_tags_and_tier(self):
        """ProviderConfig accepts tags and tier."""
        from quantaalpha.llm.provider_pool import ProviderConfig

        config = ProviderConfig(
            name="openai-gpt4",
            api_keys=["key1"],
            tags=["tool_calling", "structured", "general"],
            tier=3,
        )
        assert config.tags == ["tool_calling", "structured", "general"]
        assert config.tier == 3

    def test_provider_config_defaults(self):
        """ProviderConfig defaults tags/extra_body to []/{} and tier to 2."""
        from quantaalpha.llm.provider_pool import ProviderConfig

        config = ProviderConfig(name="test", api_keys=["key"])
        assert config.tags == []
        assert config.extra_body == {}
        assert config.tier == 2

    def test_add_provider_accepts_tags_tier_and_extra_body(self):
        """ProviderPool.add_provider() accepts tags, tier, and extra_body."""
        from quantaalpha.llm.provider_pool import ProviderPool

        pool = ProviderPool()
        extra_body = {"chat_template_kwargs": {"enable_thinking": False}}
        pool.add_provider(
            "openai",
            api_keys=["key1"],
            extra_body=extra_body,
            tags=["tool_calling", "reasoning"],
            tier=3,
        )
        provider = pool.get_provider("openai")
        assert provider is not None
        assert provider.extra_body == extra_body
        assert provider.tags == ["tool_calling", "reasoning"]
        assert provider.tier == 3


class TestProviderPoolGetByCapability:
    """Tests for ProviderPool.get_by_capability() method."""

    def _make_pool(self):
        from quantaalpha.llm.provider_pool import ProviderPool

        pool = ProviderPool()
        pool.add_provider("gpt4", api_keys=["k1"], model="gpt-4-turbo", tags=["tool_calling", "structured", "general"], tier=3)
        pool.add_provider("gpt35", api_keys=["k2"], model="gpt-3.5-turbo", tags=["general"], tier=1)
        pool.add_provider("claude", api_keys=["k3"], model="claude-3-sonnet", tags=["tool_calling", "reasoning", "general"], tier=3)
        pool.add_provider("qwen", api_keys=["k4"], model="qwen-max", tags=["general"], tier=2)
        return pool

    def test_get_by_capability_single_tag(self):
        pool = self._make_pool()
        results = pool.get_by_capability(require_tags=["tool_calling"])
        assert len(results) == 2
        names = [p.name for p in results]
        assert "gpt4" in names
        assert "claude" in names

    def test_get_by_capability_multiple_tags(self):
        pool = self._make_pool()
        results = pool.get_by_capability(require_tags=["tool_calling", "reasoning"])
        assert len(results) == 1
        assert results[0].name == "claude"

    def test_get_by_capability_tier_filter(self):
        pool = self._make_pool()
        results = pool.get_by_capability(require_tags=["general"], max_tier=2)
        names = [p.name for p in results]
        assert "gpt35" in names
        assert "qwen" in names
        assert "gpt4" not in names

    def test_get_by_capability_exclude_tags(self):
        pool = self._make_pool()
        results = pool.get_by_capability(exclude_tags=["tool_calling"])
        names = [p.name for p in results]
        assert "gpt4" not in names
        assert "claude" not in names
        assert "gpt35" in names
        assert "qwen" in names

    def test_get_by_capability_sorted_by_tier(self):
        pool = self._make_pool()
        results = pool.get_by_capability(require_tags=["general"])
        tiers = [p.tier for p in results]
        assert tiers == sorted(tiers)

    def test_get_by_capability_no_match(self):
        pool = self._make_pool()
        results = pool.get_by_capability(require_tags=["nonexistent"])
        assert results == []

    def test_get_by_capability_no_filters(self):
        pool = self._make_pool()
        results = pool.get_by_capability()
        assert len(results) == 4
