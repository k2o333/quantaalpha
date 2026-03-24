"""Tests for Ensemble Aggregator and Provider Pool (S07)."""

import threading
import time

import pytest

from quantaalpha.llm.ensemble import (
    EnsembleAggregator,
    ModelResponse,
    AggregatedResult,
    _intersection_strategy,
    _union_dedup_strategy,
    _voting_strategy,
    _fusion_score_strategy,
)
from quantaalpha.llm.provider_pool import (
    ProviderPool,
    LatencyStats,
    ProviderConfig,
    ROUTING_STRATEGIES,
)


# =============================================================================
# EnsembleAggregator Tests
# =============================================================================


class TestEnsembleAggregatorConstruction:
    """Verify EnsembleAggregator construction and validation."""

    def test_valid_strategies(self):
        for strategy in ["intersection", "union_dedup", "voting", "fusion_score"]:
            agg = EnsembleAggregator(strategy=strategy)
            assert agg.strategy == strategy

    def test_invalid_strategy_raises(self):
        with pytest.raises(ValueError, match="Unknown strategy"):
            EnsembleAggregator(strategy="invalid")

    def test_voting_threshold_default(self):
        agg = EnsembleAggregator(strategy="voting")
        assert agg.voting_threshold is None  # defaults to majority

    def test_custom_voting_threshold(self):
        agg = EnsembleAggregator(strategy="voting", voting_threshold=3)
        assert agg.voting_threshold == 3

    def test_default_quality_score(self):
        agg = EnsembleAggregator()
        assert agg.default_quality_score == 0.5


class TestUnionDedupStrategy:
    """Test union_dedup aggregation strategy."""

    def test_empty_responses(self):
        result = _union_dedup_strategy([])
        assert result == []

    def test_two_models_no_overlap(self):
        responses = [
            ModelResponse("m1", ["factor1", "factor2"]),
            ModelResponse("m2", ["factor3", "factor4"]),
        ]
        result = _union_dedup_strategy(responses)
        assert len(result) == 4
        assert set(result) == {"factor1", "factor2", "factor3", "factor4"}

    def test_two_models_with_overlap(self):
        responses = [
            ModelResponse("m1", ["factor1", "factor2"]),
            ModelResponse("m2", ["factor2", "factor3"]),
        ]
        result = _union_dedup_strategy(responses)
        assert len(result) == 3
        assert "factor2" in result

    def test_three_models(self):
        responses = [
            ModelResponse("m1", ["a", "b"]),
            ModelResponse("m2", ["b", "c"]),
            ModelResponse("m3", ["c", "d"]),
        ]
        result = _union_dedup_strategy(responses)
        assert len(result) == 4
        assert set(result) == {"a", "b", "c", "d"}

    def test_string_output_not_list(self):
        responses = [
            ModelResponse("m1", "hello world"),
            ModelResponse("m2", "hello world"),
        ]
        result = _union_dedup_strategy(responses)
        assert "hello world" in result


class TestIntersectionStrategy:
    """Test intersection aggregation strategy."""

    def test_empty_responses(self):
        result = _intersection_strategy([])
        assert result == []

    def test_two_models_partial_overlap(self):
        responses = [
            ModelResponse("m1", ["factor1", "factor2"]),
            ModelResponse("m2", ["factor2", "factor3"]),
        ]
        result = _intersection_strategy(responses)
        assert result == ["factor2"]

    def test_two_models_no_overlap(self):
        responses = [
            ModelResponse("m1", ["factor1"]),
            ModelResponse("m2", ["factor2"]),
        ]
        result = _intersection_strategy(responses)
        assert result == []

    def test_three_models_common_element(self):
        responses = [
            ModelResponse("m1", ["a", "b", "c"]),
            ModelResponse("m2", ["b", "c", "d"]),
            ModelResponse("m3", ["b", "c", "e"]),
        ]
        result = _intersection_strategy(responses)
        assert set(result) == {"b", "c"}

    def test_all_same(self):
        responses = [
            ModelResponse("m1", ["x", "y"]),
            ModelResponse("m2", ["x", "y"]),
            ModelResponse("m3", ["x", "y"]),
        ]
        result = _intersection_strategy(responses)
        assert set(result) == {"x", "y"}


class TestVotingStrategy:
    """Test voting aggregation strategy."""

    def test_threshold_2_of_3(self):
        responses = [
            ModelResponse("m1", ["factor1", "factor2"]),
            ModelResponse("m2", ["factor2", "factor3"]),
            ModelResponse("m3", ["factor2", "factor1"]),
        ]
        result = _voting_strategy(responses, threshold=2)
        assert "factor2" in result
        # factor1 appears twice, factor2 appears 3 times
        assert "factor1" in result

    def test_threshold_3_of_3(self):
        responses = [
            ModelResponse("m1", ["factor1", "factor2"]),
            ModelResponse("m2", ["factor2", "factor3"]),
            ModelResponse("m3", ["factor2", "factor1"]),
        ]
        result = _voting_strategy(responses, threshold=3)
        assert "factor2" in result
        assert "factor1" not in result  # only 2 votes

    def test_majority_default(self):
        responses = [
            ModelResponse("m1", ["a", "b"]),
            ModelResponse("m2", ["a", "c"]),
            ModelResponse("m3", ["a", "d"]),
        ]
        # threshold defaults to ceil(3/2) = 2
        result = _voting_strategy(responses, threshold=None)
        assert "a" in result

    def test_empty_responses(self):
        result = _voting_strategy([])
        assert result == []

    def test_preserves_order_from_first_appearance(self):
        responses = [
            ModelResponse("m1", ["a", "b"]),
            ModelResponse("m2", ["b", "a"]),
        ]
        result = _voting_strategy(responses, threshold=2)
        # Order from first model that has the element
        assert result.index("a") < result.index("b")


class TestFusionScoreStrategy:
    """Test fusion_score aggregation strategy."""

    def test_weights_apply(self):
        responses = [
            ModelResponse("gpt4", ["factor1"], quality_score=0.9),
            ModelResponse("claude", ["factor1", "factor2"], quality_score=0.5),
        ]
        result = _fusion_score_strategy(responses)
        scores = dict(result)
        assert scores["factor1"] > scores["factor2"]

    def test_equal_weights(self):
        responses = [
            ModelResponse("m1", ["factor1"], quality_score=0.5),
            ModelResponse("m2", ["factor1", "factor2"], quality_score=0.5),
        ]
        result = _fusion_score_strategy(responses)
        scores = dict(result)
        # factor1 gets 2 votes at 0.5 each = 1.0 total; factor2 gets 1 vote = 0.5
        assert scores["factor1"] > scores["factor2"]

    def test_empty_responses(self):
        result = _fusion_score_strategy([])
        assert result == []


class TestEnsembleAggregatorInterface:
    """Test EnsembleAggregator high-level interface."""

    def test_dict_input_conversion(self):
        """Aggregator accepts dicts and converts to ModelResponse."""
        agg = EnsembleAggregator(strategy="union_dedup")
        result = agg.aggregate([
            {"model_name": "gpt4", "raw_output": ["factor1"]},
            {"model_name": "claude", "raw_output": ["factor2"]},
        ])
        assert len(result.output) == 2
        assert result.num_models == 2

    def test_accumulate_and_aggregate(self):
        agg = EnsembleAggregator(strategy="voting", voting_threshold=2)
        agg.accumulate(ModelResponse("m1", ["f1", "f2"]))
        agg.accumulate(ModelResponse("m2", ["f2", "f3"]))
        agg.accumulate(ModelResponse("m3", ["f2", "f1"]))
        result = agg.aggregate()
        assert result.num_models == 3
        assert "f2" in result.output

    def test_accumulate_from_dict(self):
        agg = EnsembleAggregator(strategy="union_dedup")
        agg.accumulate({"model_name": "m1", "raw_output": ["x"]})
        agg.accumulate({"model_name": "m2", "raw_output": ["y"]})
        result = agg.aggregate()
        assert result.num_models == 2

    def test_reset(self):
        agg = EnsembleAggregator(strategy="union_dedup")
        agg.accumulate(ModelResponse("m1", ["f1"]))
        agg.accumulate(ModelResponse("m2", ["f2"]))
        assert agg.get_accumulated_count() == 2
        agg.reset()
        assert agg.get_accumulated_count() == 0

    def test_empty_aggregate_returns_empty(self):
        agg = EnsembleAggregator(strategy="union_dedup")
        result = agg.aggregate([])
        assert result.output == []
        assert result.num_models == 0

    def test_source_counts_for_voting(self):
        agg = EnsembleAggregator(strategy="voting", voting_threshold=2)
        agg.accumulate(ModelResponse("m1", ["f1", "f2"]))
        agg.accumulate(ModelResponse("m2", ["f2", "f3"]))
        agg.accumulate(ModelResponse("m3", ["f2", "f1"]))
        result = agg.aggregate()
        assert result.source_counts["f2"] == 3
        assert result.source_counts["f1"] == 2
        assert result.source_counts["f3"] == 1

    def test_fusion_scores_populated(self):
        agg = EnsembleAggregator(strategy="fusion_score")
        result = agg.aggregate([
            ModelResponse("gpt4", ["a", "b"], quality_score=0.9),
            ModelResponse("claude", ["b", "c"], quality_score=0.5),
        ])
        assert result.fusion_scores is not None
        assert isinstance(result.fusion_scores, dict)


# =============================================================================
# ProviderPool Tests
# =============================================================================


class TestProviderPoolConstruction:
    """Verify ProviderPool construction and validation."""

    def test_valid_routing_strategies(self):
        for strategy in ROUTING_STRATEGIES:
            pool = ProviderPool(routing=strategy)
            assert pool.routing == strategy

    def test_invalid_routing_raises(self):
        with pytest.raises(ValueError, match="Unknown routing"):
            ProviderPool(routing="invalid")

    def test_min_latency_samples_default(self):
        pool = ProviderPool(routing="least_latency")
        assert pool.min_latency_samples == 3

    def test_custom_min_latency_samples(self):
        pool = ProviderPool(routing="least_latency", min_latency_samples=5)
        assert pool.min_latency_samples == 5


class TestProviderPoolBasicOperations:
    """Test basic add/remove/get operations."""

    def test_add_provider_single_key(self):
        pool = ProviderPool()
        pool.add_provider("openai", api_keys="sk-key1", base_url="https://api.openai.com")
        assert "openai" in pool.get_providers()
        provider = pool.get_provider("openai")
        assert provider is not None
        assert provider.api_keys == ["sk-key1"]
        assert provider.base_url == "https://api.openai.com"

    def test_add_provider_multiple_keys(self):
        pool = ProviderPool()
        pool.add_provider("openai", api_keys=["key1", "key2", "key3"])
        provider = pool.get_provider("openai")
        assert len(provider.api_keys) == 3

    def test_add_multiple_providers(self):
        pool = ProviderPool()
        pool.add_provider("openai", api_keys=["k1"])
        pool.add_provider("azure", api_keys=["k2"])
        pool.add_provider("anthropic", api_keys=["k3"])
        assert len(pool) == 3
        assert set(pool.get_providers()) == {"openai", "azure", "anthropic"}

    def test_remove_provider(self):
        pool = ProviderPool()
        pool.add_provider("openai", api_keys=["k1"])
        assert pool.remove_provider("openai") is True
        assert "openai" not in pool.get_providers()

    def test_remove_nonexistent_returns_false(self):
        pool = ProviderPool()
        assert pool.remove_provider("nonexistent") is False


class TestRoundRobinRouting:
    """Test round_robin routing with multiple keys."""

    def test_rr_cycles_through_keys(self):
        pool = ProviderPool(routing="round_robin")
        pool.add_provider("p1", api_keys=["k1", "k2", "k3"])
        keys = [pool.get_key_and_provider("p1")[0] for _ in range(9)]
        assert keys == ["k1", "k2", "k3", "k1", "k2", "k3", "k1", "k2", "k3"]

    def test_rr_across_providers(self):
        pool = ProviderPool(routing="round_robin")
        pool.add_provider("p1", api_keys=["p1k1"])
        pool.add_provider("p2", api_keys=["p2k1"])
        key1, prov1 = pool.get_key_and_provider()
        key2, prov2 = pool.get_key_and_provider()
        assert prov1.name != prov2.name


class TestRandomRouting:
    """Test random routing."""

    def test_random_returns_valid_key(self):
        pool = ProviderPool(routing="random")
        pool.add_provider("p1", api_keys=["k1", "k2"])
        for _ in range(20):
            key, _ = pool.get_key_and_provider("p1")
            assert key in ["k1", "k2"]


class TestLeastLatencyRouting:
    """Test least_latency routing strategy."""

    def test_least_latency_picks_fastest(self):
        pool = ProviderPool(routing="least_latency", min_latency_samples=1)
        pool.add_provider("fast", api_keys=["fast_key"])
        pool.add_provider("slow", api_keys=["slow_key"])

        # Record latency data
        for _ in range(5):
            pool.record_latency("slow", "slow_key", 500.0)
        for _ in range(5):
            pool.record_latency("fast", "fast_key", 30.0)

        # With enough samples, should pick fast
        key, prov = pool.get_key_and_provider()
        assert key == "fast_key"
        assert prov.name == "fast"

    def test_least_latency_falls_back_without_data(self):
        pool = ProviderPool(routing="least_latency", min_latency_samples=3)
        pool.add_provider("p1", api_keys=["k1"])
        pool.add_provider("p2", api_keys=["k2"])
        # Only 2 samples (below min=3), should fall back to round-robin
        pool.record_latency("p1", "k1", 100.0)
        pool.record_latency("p1", "k1", 100.0)
        key, prov = pool.get_key_and_provider("p1")
        assert key == "k1"  # Only one key available

    def test_least_latency_picks_best_key_in_single_provider(self):
        pool = ProviderPool(routing="least_latency", min_latency_samples=2)
        pool.add_provider("p1", api_keys=["fast_key", "slow_key"])

        pool.record_latency("p1", "slow_key", 300.0)
        pool.record_latency("p1", "slow_key", 300.0)
        pool.record_latency("p1", "fast_key", 50.0)
        pool.record_latency("p1", "fast_key", 50.0)

        key, _ = pool.get_key_and_provider("p1")
        assert key == "fast_key"


class TestLatencyTracking:
    """Test latency recording and statistics."""

    def test_record_latency_updates_stats(self):
        pool = ProviderPool()
        pool.add_provider("p1", api_keys=["k1"])
        pool.record_latency("p1", "k1", 100.0)
        pool.record_latency("p1", "k1", 200.0)
        pool.record_latency("p1", "k1", 300.0)

        stats = pool.get_latency_stats("p1")
        assert stats["k1"].sample_count == 3
        assert stats["k1"].avg_latency_ms == 200.0
        assert stats["k1"].min_latency_ms == 100.0
        assert stats["k1"].max_latency_ms == 300.0

    def test_get_latency_stats_nonexistent_provider(self):
        pool = ProviderPool()
        assert pool.get_latency_stats("nonexistent") is None

    def test_reset_latency_stats(self):
        pool = ProviderPool()
        pool.add_provider("p1", api_keys=["k1"])
        pool.record_latency("p1", "k1", 100.0)
        pool.reset_latency_stats("p1")
        stats = pool.get_latency_stats("p1")
        assert stats["k1"].sample_count == 0

    def test_reset_all_latency_stats(self):
        pool = ProviderPool()
        pool.add_provider("p1", api_keys=["k1"])
        pool.add_provider("p2", api_keys=["k2"])
        pool.record_latency("p1", "k1", 100.0)
        pool.record_latency("p2", "k2", 200.0)
        pool.reset_latency_stats()
        assert pool.get_latency_stats("p1")["k1"].sample_count == 0
        assert pool.get_latency_stats("p2")["k2"].sample_count == 0

    def test_get_stats_summary(self):
        pool = ProviderPool()
        pool.add_provider("openai", api_keys=["key1", "key2"])
        pool.record_latency("openai", "key1", 100.0)
        pool.record_latency("openai", "key1", 200.0)
        pool.record_latency("openai", "key2", 50.0)

        summary = pool.get_stats_summary()
        assert summary["num_providers"] == 1
        assert summary["providers"]["openai"]["num_keys"] == 2
        assert summary["providers"]["openai"]["keys"]["key1..."]["samples"] == 2
        assert summary["providers"]["openai"]["keys"]["key1..."]["avg_ms"] == 150.0


class TestProviderPoolThreadSafety:
    """Test thread-safe operations."""

    def test_concurrent_key_access(self):
        pool = ProviderPool(routing="round_robin")
        pool.add_provider("p1", api_keys=["k1", "k2", "k3", "k4"])
        results: list[str] = []
        errors: list[Exception] = []

        def get_keys():
            try:
                for _ in range(50):
                    key, _ = pool.get_key_and_provider("p1")
                    results.append(key)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=get_keys) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        assert len(results) == 200

    def test_concurrent_latency_recording(self):
        pool = ProviderPool()
        pool.add_provider("p1", api_keys=["k1"])
        errors: list[Exception] = []

        def record_latency():
            try:
                for i in range(100):
                    pool.record_latency("p1", "k1", float(i))
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=record_latency) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        stats = pool.get_latency_stats("p1")
        assert stats["k1"].sample_count == 400


class TestProviderConfigMetadata:
    """Test provider metadata and extended configuration."""

    def test_metadata_stored(self):
        pool = ProviderPool()
        pool.add_provider(
            "custom",
            api_keys=["key1"],
            base_url="https://custom.api.com",
            model="gpt-4",
            timeout=120,
            metadata={"region": "us-east", "tier": "premium"},
        )
        provider = pool.get_provider("custom")
        assert provider.metadata["region"] == "us-east"
        assert provider.metadata["tier"] == "premium"
        assert provider.timeout == 120
        assert provider.model == "gpt-4"

    def test_single_key_string(self):
        pool = ProviderPool()
        pool.add_provider("p1", api_keys="single_key_string")
        provider = pool.get_provider("p1")
        assert provider.api_keys == ["single_key_string"]
