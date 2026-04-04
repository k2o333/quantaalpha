"""
Provider Pool for multi-provider LLM routing.

Features:
- Multiple provider support (OpenAI, Azure, custom endpoints)
- Multiple API keys per provider (round-robin rotation)
- Routing strategies: round_robin, random, least_latency
- Latency tracking per provider/key for informed routing

Usage:
    pool = ProviderPool(routing="least_latency")
    pool.add_provider("openai", api_keys=["key1", "key2"], base_url="https://api.openai.com")
    result = await pool.call("generate", prompt="...")
"""

from __future__ import annotations

import random
import time
import threading
from dataclasses import dataclass, field
from typing import Any, Callable
from collections import defaultdict

from quantaalpha.log import logger

# =============================================================================
# Routing Strategies
# =============================================================================

ROUTING_STRATEGIES = ["round_robin", "random", "least_latency"]


def _round_robin_select(keys: list[str], counters: dict[str, int]) -> str:
    """Select next key in round-robin order."""
    if not keys:
        raise ValueError("No keys available")
    idx = counters["_current"] % len(keys)
    counters["_current"] += 1
    return keys[idx]


def _random_select(keys: list[str], counters: dict[str, int]) -> str:
    """Select a random key."""
    if not keys:
        raise ValueError("No keys available")
    return random.choice(keys)


def _least_latency_select(
    keys: list[str],
    counters: dict[str, int],
    latency_stats: dict[str, LatencyStats],
    min_samples: int = 3,
) -> str:
    """
    Select the key with lowest average latency.

    Falls back to round-robin if not enough samples.
    """
    if not keys:
        raise ValueError("No keys available")

    candidates = {}
    for key in keys:
        stats = latency_stats.get(key)
        if stats and stats.sample_count >= min_samples:
            candidates[key] = stats.avg_latency_ms

    if not candidates:
        # Not enough data, fall back to round-robin
        return _round_robin_select(keys, counters)

    # Pick the one with lowest latency
    return min(candidates, key=candidates.get)


SELECT_FUNCTIONS = {
    "round_robin": _round_robin_select,
    "random": _random_select,
    "least_latency": _least_latency_select,
}


# =============================================================================
# Latency Tracking
# =============================================================================


@dataclass
class LatencyStats:
    """Running statistics for latency tracking."""

    total_latency_ms: float = 0.0
    sample_count: int = 0
    min_latency_ms: float = float("inf")
    max_latency_ms: float = 0.0

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.sample_count if self.sample_count > 0 else 0.0

    @property
    def has_data(self) -> bool:
        return self.sample_count > 0

    def record(self, latency_ms: float) -> None:
        """Record a new latency sample."""
        self.total_latency_ms += latency_ms
        self.sample_count += 1
        self.min_latency_ms = min(self.min_latency_ms, latency_ms)
        self.max_latency_ms = max(self.max_latency_ms, latency_ms)


# =============================================================================
# Provider Definition
# =============================================================================


@dataclass
class ProviderConfig:
    """Configuration for a single LLM provider."""

    name: str
    api_keys: list[str]
    base_url: str | None = None
    model: str | None = None
    timeout: int = 60
    metadata: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    tier: int = 2  # 1=basic/low-cost, 2=standard, 3=premium/high-cost


# =============================================================================
# Provider Pool
# =============================================================================


class ProviderPool:
    """
    Multi-provider LLM routing pool with key rotation and latency tracking.

    Features:
    - Add/remove providers at runtime
    - Per-provider multiple API keys with automatic rotation
    - Routing strategies: round_robin, random, least_latency
    - Latency tracking per key for informed routing
    - Thread-safe operations

    Args:
        routing: Routing strategy. One of: round_robin, random, least_latency
        min_latency_samples: Min samples before least_latency uses a key

    Example:
        pool = ProviderPool(routing="least_latency")
        pool.add_provider("openai", api_keys=["key1", "key2"], base_url="...")
        pool.add_provider("azure", api_keys=["az_key1"], base_url="...")

        # Use with LLM client
        key, provider = pool.get_key_and_provider("generate")
        response = llm_client.chat(prompt, api_key=key, base_url=provider.base_url)
        pool.record_latency("openai", key, elapsed_ms)
    """

    def __init__(
        self,
        routing: str = "round_robin",
        min_latency_samples: int = 3,
    ):
        if routing not in ROUTING_STRATEGIES:
            raise ValueError(f"Unknown routing '{routing}'. Valid: {ROUTING_STRATEGIES}")
        self.routing = routing
        self.min_latency_samples = min_latency_samples
        self._providers: dict[str, ProviderConfig] = {}
        self._key_counters: dict[str, dict[str, int]] = defaultdict(lambda: {"_current": 0})
        self._latency_stats: dict[str, dict[str, LatencyStats]] = defaultdict(dict)
        self._lock = threading.RLock()

        logger.info(f"ProviderPool initialized with routing={routing}")

    def add_provider(
        self,
        name: str,
        api_keys: str | list[str],
        base_url: str | None = None,
        model: str | None = None,
        timeout: int = 60,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        tier: int = 2,
    ) -> None:
        """
        Add a provider to the pool.

        Args:
            name: Provider name (e.g., "openai", "azure", "custom")
            api_keys: Single API key (str) or list of keys
            base_url: API base URL
            model: Default model name
            timeout: Request timeout in seconds
            metadata: Additional provider metadata
            tags: Capability tags for declarative routing
            tier: Cost tier (1=basic, 2=standard, 3=premium)
        """
        if isinstance(api_keys, str):
            api_keys = [api_keys]

        with self._lock:
            self._providers[name] = ProviderConfig(
                name=name,
                api_keys=api_keys,
                base_url=base_url,
                model=model,
                timeout=timeout,
                metadata=metadata or {},
                tags=tags or [],
                tier=tier,
            )
            # Initialize latency stats for each key
            if name not in self._latency_stats:
                self._latency_stats[name] = {}
            for key in api_keys:
                if key not in self._latency_stats[name]:
                    self._latency_stats[name][key] = LatencyStats()

            logger.info(f"ProviderPool: added provider '{name}' with {len(api_keys)} key(s)")

    def remove_provider(self, name: str) -> bool:
        """Remove a provider from the pool. Returns True if removed."""
        with self._lock:
            if name not in self._providers:
                return False
            del self._providers[name]
            if name in self._latency_stats:
                del self._latency_stats[name]
            logger.info(f"ProviderPool: removed provider '{name}'")
            return True

    def get_providers(self) -> list[str]:
        """Return list of provider names."""
        with self._lock:
            return list(self._providers.keys())

    def get_provider(self, name: str) -> ProviderConfig | None:
        """Return provider config by name."""
        with self._lock:
            return self._providers.get(name)

    def get_by_capability(
        self,
        require_tags: list[str] | None = None,
        exclude_tags: list[str] | None = None,
        min_tier: int = 1,
        max_tier: int = 3,
    ) -> list[ProviderConfig]:
        """
        Declarative provider lookup by capability.

        Args:
            require_tags: All these tags must be present in provider.tags
            exclude_tags: Any of these tags disqualifies a provider
            min_tier: Minimum tier level (inclusive)
            max_tier: Maximum tier level (inclusive)

        Returns:
            Sorted list of matching ProviderConfig (by tier ascending).
            Empty list if no matches.
        """
        with self._lock:
            results = []
            required = set(require_tags) if require_tags else set()
            excluded = set(exclude_tags) if exclude_tags else set()

            for provider in self._providers.values():
                provider_tags = set(provider.tags)

                # Check tier bounds
                if not (min_tier <= provider.tier <= max_tier):
                    continue

                # Check exclusion
                if provider_tags & excluded:
                    continue

                # Check requirement
                if required and not required.issubset(provider_tags):
                    continue

                results.append(provider)

            # Sort by tier ascending (cheapest first)
            results.sort(key=lambda p: p.tier)
            return results

    def get_key_and_provider(
        self,
        provider_name: str | None = None,
    ) -> tuple[str, ProviderConfig] | tuple[None, None]:
        """
        Get the next API key and provider config based on routing strategy.

        If provider_name is provided, selects from that provider only.
        Otherwise, selects from all providers based on routing strategy.

        Returns:
            Tuple of (api_key, provider_config) or (None, None) if no providers

        Raises:
            ValueError: If specified provider has no keys
        """
        with self._lock:
            if provider_name:
                # Select from specific provider
                provider = self._providers.get(provider_name)
                if not provider or not provider.api_keys:
                    return None, None
                key = self._select_key(provider_name, provider.api_keys)
                return key, provider

            # Select from all providers based on routing
            if not self._providers:
                return None, None

            if self.routing == "random":
                provider = random.choice(list(self._providers.values()))
                key = _random_select(provider.api_keys, self._key_counters[provider.name])
                return key, provider

            # round_robin and least_latency need provider-level selection first
            if len(self._providers) == 1:
                provider = list(self._providers.values())[0]
                key = self._select_key(provider.name, provider.api_keys)
                return key, provider

            # Multiple providers: pick one then get key
            if self.routing == "least_latency":
                # Pick provider with lowest avg latency across all its keys
                provider_latencies = {}
                for pname, pconfig in self._providers.items():
                    if not pconfig.api_keys:
                        continue
                    key_latencies = []
                    for key in pconfig.api_keys:
                        stats = self._latency_stats.get(pname, {}).get(key)
                        if stats and stats.sample_count >= self.min_latency_samples:
                            key_latencies.append(stats.avg_latency_ms)
                    if key_latencies:
                        provider_latencies[pname] = sum(key_latencies) / len(key_latencies)

                if provider_latencies:
                    best_provider_name = min(provider_latencies, key=provider_latencies.get)
                else:
                    # Fall back to first available
                    best_provider_name = next(iter(self._providers))
            else:
                # round_robin across providers
                provider_names = list(self._providers.keys())
                idx = self._key_counters["_provider_rr"].get("_current", 0) % len(provider_names)
                self._key_counters["_provider_rr"]["_current"] = idx + 1
                best_provider_name = provider_names[idx]

            provider = self._providers[best_provider_name]
            key = self._select_key(provider.name, provider.api_keys)
            return key, provider

    def _select_key(
        self,
        provider_name: str,
        keys: list[str],
    ) -> str:
        """Select a key from a provider using the configured strategy."""
        counters = self._key_counters[provider_name]

        if self.routing == "least_latency":
            return _least_latency_select(
                keys,
                counters,
                self._latency_stats[provider_name],
                min_samples=self.min_latency_samples,
            )
        elif self.routing == "random":
            return _random_select(keys, counters)
        else:
            return _round_robin_select(keys, counters)

    def record_latency(
        self,
        provider_name: str,
        api_key: str,
        latency_ms: float,
    ) -> None:
        """
        Record latency for a provider/key pair.

        Call this after each request so least_latency routing can learn.
        """
        with self._lock:
            if provider_name not in self._latency_stats:
                self._latency_stats[provider_name] = {}
            if api_key not in self._latency_stats[provider_name]:
                self._latency_stats[provider_name][api_key] = LatencyStats()

            self._latency_stats[provider_name][api_key].record(latency_ms)
            # Latency recorded silently (debug-level info not available in RDAgentLog)

    def get_latency_stats(
        self,
        provider_name: str | None = None,
    ) -> dict[str, dict[str, LatencyStats]] | dict[str, LatencyStats] | None:
        """
        Get latency statistics.

        Args:
            provider_name: If provided, return stats for specific provider only

        Returns:
            Nested dict of {provider_name: {api_key: LatencyStats}}
        """
        with self._lock:
            if provider_name:
                return self._latency_stats.get(provider_name)
            return dict(self._latency_stats)

    def get_stats_summary(self) -> dict[str, Any]:
        """
        Get a summary of pool statistics.

        Returns:
            Dict with provider counts, key counts, and latency summaries
        """
        with self._lock:
            summary: dict[str, Any] = {
                "routing": self.routing,
                "num_providers": len(self._providers),
                "providers": {},
            }
            for pname, pconfig in self._providers.items():
                stats = self._latency_stats.get(pname, {})
                key_summaries = {}
                for key in pconfig.api_keys:
                    s = stats.get(key)
                    if s and s.has_data:
                        key_summaries[key[:8] + "..."] = {
                            "samples": s.sample_count,
                            "avg_ms": round(s.avg_latency_ms, 1),
                            "min_ms": round(s.min_latency_ms, 1),
                            "max_ms": round(s.max_latency_ms, 1),
                        }
                    else:
                        key_summaries[key[:8] + "..."] = {"samples": 0}
                summary["providers"][pname] = {
                    "num_keys": len(pconfig.api_keys),
                    "keys": key_summaries,
                }
            return summary

    def reset_latency_stats(self, provider_name: str | None = None) -> None:
        """Reset latency tracking. If provider_name provided, reset only that provider."""
        with self._lock:
            if provider_name:
                if provider_name in self._latency_stats:
                    # Reset stats in place, keeping the key entries
                    for key_stats in self._latency_stats[provider_name].values():
                        key_stats.total_latency_ms = 0.0
                        key_stats.sample_count = 0
                        key_stats.min_latency_ms = float("inf")
                        key_stats.max_latency_ms = 0.0
            else:
                for pstats in self._latency_stats.values():
                    for key_stats in pstats.values():
                        key_stats.total_latency_ms = 0.0
                        key_stats.sample_count = 0
                        key_stats.min_latency_ms = float("inf")
                        key_stats.max_latency_ms = 0.0

    def __len__(self) -> int:
        """Return number of providers."""
        with self._lock:
            return len(self._providers)
