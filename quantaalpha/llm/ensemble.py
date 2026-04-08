"""
Ensemble Aggregator for multi-model factor generation.

Aggregates responses from multiple LLM models using configurable strategies:
- intersection: conservative, keeps only elements common to all models
- union_dedup: permissive, keeps all unique elements
- voting: keeps elements appearing in >= N responses
- fusion_score: weighted scoring based on model quality/certainty

Usage:
    aggregator = EnsembleAggregator(strategy="voting", threshold=2)
    result = aggregator.aggregate([model_a_response, model_b_response])
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from quantaalpha.log import logger

# =============================================================================
# Data Structures
# =============================================================================


@dataclass
class ModelResponse:
    """A single model response with its metadata."""

    model_name: str
    raw_output: str | dict | list
    latency_ms: float | None = None
    quality_score: float | None = None  # 0.0-1.0, used in fusion_score
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_structured(self) -> bool:
        """Check if response is a structured format (dict or list)."""
        return isinstance(self.raw_output, (dict, list))


@dataclass
class AggregatedResult:
    """Result from ensemble aggregation."""
    output: list[Any]
    strategy: str
    source_counts: dict[Any, int] = field(default_factory=dict)
    fusion_scores: dict[Any, float] | None = None
    num_models: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# Strategy Implementations
# =============================================================================


def _intersection_strategy(responses: list[ModelResponse]) -> list[Any]:
    """
    Take the intersection of all model outputs.

    For structured outputs (list of factors), returns factors appearing in every response.
    For string outputs, returns the shortest common response (conservative).
    """
    if not responses:
        return []

    if not all(r.is_structured for r in responses):
        # Fall back to shortest common response for non-structured
        non_empty = [r for r in responses if r.raw_output]
        if not non_empty:
            return []
        return [min(non_empty, key=lambda r: len(str(r.raw_output))).raw_output]

    # Convert all to sets for structured responses
    set_responses: list[set] = []
    for r in responses:
        val = r.raw_output
        if isinstance(val, list):
            # Normalize each item to a hashable representation
            normalized = [str(item) for item in val]
            set_responses.append(set(normalized))
        elif isinstance(val, dict):
            # For dict outputs, use sorted items as representation
            normalized = str(sorted(val.items()))
            set_responses.append({normalized})

    if not set_responses:
        return []

    intersection = set_responses[0]
    for s in set_responses[1:]:
        intersection &= s

    # Parse back from string representation
    result = []
    for item_str in intersection:
        try:
            import ast
            result.append(ast.literal_eval(item_str))
        except (ValueError, SyntaxError):
            result.append(item_str)
    return result


def _union_dedup_strategy(responses: list[ModelResponse]) -> list[Any]:
    """
    Take the union of all model outputs, deduplicating by string representation.
    """
    if not responses:
        return []

    seen: set[str] = set()
    result: list[Any] = []

    for r in responses:
        val = r.raw_output
        if isinstance(val, list):
            for item in val:
                key = str(item)
                if key not in seen:
                    seen.add(key)
                    result.append(item)
        elif val:
            key = str(val)
            if key not in seen:
                seen.add(key)
                result.append(val)

    return result


def _voting_strategy(
    responses: list[ModelResponse],
    threshold: int | None = None,
) -> list[Any]:
    """
    Keep elements appearing in at least `threshold` responses.

    Args:
        threshold: Minimum vote count. Defaults to majority (ceil(n/2)).
    """
    if not responses:
        return []

    if threshold is None:
        threshold = (len(responses) + 1) // 2  # majority

    # Count occurrences of each element across all responses
    counts: dict[str, tuple[int, Any]] = {}
    for r in responses:
        val = r.raw_output
        if isinstance(val, list):
            for item in val:
                key = str(item)
                if key in counts:
                    counts[key] = (counts[key][0] + 1, counts[key][1])
                else:
                    counts[key] = (1, item)
        elif val:
            key = str(val)
            if key in counts:
                counts[key] = (counts[key][0] + 1, counts[key][1])
            else:
                counts[key] = (1, val)

    # Filter by threshold and preserve order from first appearance
    result: list[Any] = []
    for r in responses:
        val = r.raw_output
        if isinstance(val, list):
            for item in val:
                key = str(item)
                if counts[key][0] >= threshold and item not in result:
                    result.append(item)
        elif val:
            key = str(val)
            if counts[key][0] >= threshold and val not in result:
                result.append(val)

    return result


def _fusion_score_strategy(
    responses: list[ModelResponse],
    weights: dict[str, float] | None = None,
) -> list[tuple[Any, float]]:
    """
    Fusion scoring: weight elements by model quality scores and vote strength.

    Returns list of (element, score) tuples sorted by score descending.

    Args:
        weights: Optional {model_name: weight} mapping. Defaults to equal weighting.
    """
    if not responses:
        return []

    if weights is None:
        weights = {r.model_name: r.quality_score or 0.5 for r in responses}
    else:
        # Fill in missing quality scores
        for r in responses:
            if r.model_name not in weights:
                weights[r.model_name] = r.quality_score or 0.5

    # Aggregate scores per element
    element_scores: dict[str, list[float]] = {}
    element_values: dict[str, Any] = {}

    for r in responses:
        weight = weights.get(r.model_name, 0.5)
        val = r.raw_output
        if isinstance(val, list):
            for item in val:
                key = str(item)
                if key not in element_scores:
                    element_scores[key] = []
                    element_values[key] = item
                element_scores[key].append(weight)
        elif val:
            key = str(val)
            if key not in element_scores:
                element_scores[key] = []
                element_values[key] = val
            element_scores[key].append(weight)

    # Compute fusion scores (sum of weights, normalized)
    fusion_scores: dict[str, float] = {}
    max_score = sum(weights.values())
    for key, score_list in element_scores.items():
        fusion_scores[key] = sum(score_list) / max_score if max_score > 0 else 0.0

    # Sort by score descending
    sorted_items = sorted(
        fusion_scores.items(),
        key=lambda x: x[1],
        reverse=True,
    )

    return [(element_values[key], score) for key, score in sorted_items]


def _collect_all_strategy(responses: list[ModelResponse]) -> list[Any]:
    """Preserve every model output in a single structured bundle."""
    if not responses:
        return []

    return [{
        "hypotheses": [
            {
                "model": r.model_name,
                "hypothesis": r.raw_output,
                "latency_ms": r.latency_ms,
                "quality_score": r.quality_score,
            }
            for r in responses
        ],
        "num_models": len(responses),
        "strategy": "collect_all",
    }]


# =============================================================================
# Main Aggregator
# =============================================================================


STRATEGY_FUNCTIONS = {
    "intersection": _intersection_strategy,
    "union_dedup": _union_dedup_strategy,
    "voting": _voting_strategy,
    "fusion_score": _fusion_score_strategy,
    "collect_all": _collect_all_strategy,
}


class EnsembleAggregator:
    """
    Aggregates multi-model responses using configurable strategies.

    Supports both stateless aggregation (single call) and stateful accumulation
    (multiple calls to build up a consensus).

    Args:
        strategy: Aggregation strategy. One of: intersection, union_dedup, voting, fusion_score
        voting_threshold: For voting strategy, minimum vote count (default: majority)
        default_quality_score: Default quality score for models without explicit scores

    Example:
        aggregator = EnsembleAggregator(strategy="voting", voting_threshold=2)
        results = aggregator.aggregate([
            ModelResponse("gpt4", ["factor1", "factor2"], quality_score=0.8),
            ModelResponse("claude", ["factor2", "factor3"], quality_score=0.7),
        ])
    """

    def __init__(
        self,
        strategy: str = "union_dedup",
        voting_threshold: int | None = None,
        default_quality_score: float = 0.5,
    ):
        if strategy not in STRATEGY_FUNCTIONS:
            raise ValueError(
                f"Unknown strategy '{strategy}'. "
                f"Valid: {list(STRATEGY_FUNCTIONS.keys())}"
            )
        self.strategy = strategy
        self.voting_threshold = voting_threshold
        self.default_quality_score = default_quality_score
        self._accumulated: list[ModelResponse] = []

    def aggregate(
        self,
        responses: list[ModelResponse] | list[dict] | None = None,
    ) -> AggregatedResult:
        """
        Aggregate model responses using the configured strategy.

        Args:
            responses: List of ModelResponse objects or dicts with keys:
                - model_name: str
                - raw_output: str | dict | list
                - latency_ms: float (optional)
                - quality_score: float (optional)

        Returns:
            AggregatedResult with output and metadata
        """
        # Merge accumulated + new responses
        all_responses = list(self._accumulated)
        if responses:
            for r in responses:
                if isinstance(r, ModelResponse):
                    all_responses.append(r)
                elif isinstance(r, dict):
                    all_responses.append(ModelResponse(
                        model_name=r.get("model_name", "unknown"),
                        raw_output=r.get("raw_output", r.get("output", "")),
                        latency_ms=r.get("latency_ms"),
                        quality_score=r.get("quality_score", self.default_quality_score),
                        metadata=r.get("metadata", {}),
                    ))
                else:
                    all_responses.append(ModelResponse(
                        model_name="unknown",
                        raw_output=r if isinstance(r, (str, dict, list)) else str(r),
                    ))

        if not all_responses:
            return AggregatedResult(
                output=[],
                strategy=self.strategy,
                num_models=0,
            )

        # Execute strategy
        strategy_fn = STRATEGY_FUNCTIONS[self.strategy]
        kwargs = {}
        if self.strategy == "voting":
            kwargs["threshold"] = self.voting_threshold

        raw_output = strategy_fn(all_responses, **kwargs)

        # Build result
        result = AggregatedResult(
            output=raw_output if self.strategy != "fusion_score" else [x[0] for x in raw_output],
            strategy=self.strategy,
            num_models=len(all_responses),
            metadata={"strategy": self.strategy},
        )

        if self.strategy == "voting":
            # Compute source counts for voting
            source_counts: dict[Any, int] = {}
            for r in all_responses:
                val = r.raw_output
                if isinstance(val, list):
                    for item in val:
                        key = str(item)
                        source_counts[key] = source_counts.get(key, 0) + 1
                elif val:
                    key = str(val)
                    source_counts[key] = source_counts.get(key, 0) + 1
            result.source_counts = source_counts

        elif self.strategy == "fusion_score":
            result.fusion_scores = {str(x[0]): x[1] for x in raw_output}

        return result

    def accumulate(self, response: ModelResponse | dict) -> None:
        """
        Accumulate a response for later aggregation.

        Use this for streaming scenarios where models respond at different times.
        """
        if isinstance(response, dict):
            response = ModelResponse(
                model_name=response.get("model_name", "unknown"),
                raw_output=response.get("raw_output", response.get("output", "")),
                latency_ms=response.get("latency_ms"),
                quality_score=response.get("quality_score", self.default_quality_score),
                metadata=response.get("metadata", {}),
            )
        self._accumulated.append(response)

    def reset(self) -> None:
        """Clear accumulated responses."""
        self._accumulated.clear()

    def get_accumulated_count(self) -> int:
        """Return number of accumulated responses."""
        return len(self._accumulated)
