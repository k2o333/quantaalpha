"""
Adaptive direction planning for continuous mining.

Combines trajectory history, failure tracking, and diversity constraints
to select the next mining direction.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from quantaalpha.factors.failure_tracker import FactorFailureTracker
from quantaalpha.pipeline.evolution.trajectory import TrajectoryPool

logger = logging.getLogger(__name__)

# Direction category keywords
CATEGORY_KEYWORDS = {
    "price_volume": [
        "momentum",
        "reversal",
        "volatility",
        "liquidity",
        "volume",
        "price",
        "turnover",
        "spread",
        "range",
        "gap",
        "mean reversion",
    ],
    "fundamental": [
        "earnings",
        "dividend",
        "value",
        "growth",
        "quality",
        "profitability",
        "leverage",
        "fundamental",
    ],
    "alternative": [
        "sentiment",
        "news",
        "social",
        "satellite",
        "web",
        "alternative",
        "text",
        "nlp",
    ],
}


@dataclass
class DirectionPlanResult:
    """Result of direction planning."""

    direction: str
    category: str
    source: str  # "planner" | "fallback"


def detect_category(direction: str) -> str:
    """
    Detect the category of a direction string by keyword matching.

    Returns the first matching category, or "price_volume" as default.
    """
    text = direction.lower()
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(kw in text for kw in keywords):
            return category
    return "price_volume"


class ContinuousDirectionPlanner:
    """Plans the next mining direction with constraints."""

    def __init__(
        self,
        failure_tracker: FactorFailureTracker,
        trajectory_pool: TrajectoryPool,
        diversity_window: int = 3,
        last_failed_within_hours: int = 48,
    ):
        self._failure_tracker = failure_tracker
        self._trajectory_pool = trajectory_pool
        self._diversity_window = diversity_window
        self._last_failed_within_hours = last_failed_within_hours
        self._used_categories: list[str] = []

    def plan_next_direction(
        self,
        force_different_category: bool = False,
    ) -> DirectionPlanResult:
        """
        Plan the next mining direction.

        Args:
            force_different_category: If True, force a different category
                from recent ones (used in CB degraded mode).

        Returns:
            DirectionPlanResult with the planned direction.
        """
        # Get recently failed directions
        try:
            failed_directions = self._failure_tracker.get_recently_failed_directions()
        except Exception:
            failed_directions = []

        # Determine excluded categories
        excluded_categories = set()
        if force_different_category or len(self._used_categories) >= self._diversity_window:
            if self._used_categories:
                excluded_categories.add(self._used_categories[-1])

        # Get candidate directions
        candidates = self._get_candidates(use_llm=True)

        # Filter candidates
        for candidate in candidates:
            if candidate in failed_directions:
                continue
            category = detect_category(candidate)
            if category in excluded_categories:
                continue
            return DirectionPlanResult(
                direction=candidate,
                category=category,
                source="planner",
            )

        # Fallback: try without LLM
        fallback_candidates = self._get_candidates(use_llm=False)
        for candidate in fallback_candidates:
            if candidate in failed_directions:
                continue
            category = detect_category(candidate)
            if category in excluded_categories:
                continue
            return DirectionPlanResult(
                direction=candidate,
                category=category,
                source="fallback",
            )

        # Last resort
        return DirectionPlanResult(
            direction="price-volume factor exploration",
            category="price_volume",
            source="fallback",
        )

    def record_used_category(self, category: str) -> None:
        """Record that a category was used."""
        self._used_categories.append(category)
        if len(self._used_categories) > self._diversity_window:
            self._used_categories = self._used_categories[-self._diversity_window :]

    def _get_candidates(self, use_llm: bool = True) -> list[str]:
        """Get candidate directions from generate_parallel_directions."""
        try:
            from quantaalpha.pipeline.planning import generate_parallel_directions

            prompt_file = Path("config/prompts/direction_generation.yaml")
            return generate_parallel_directions(
                initial_direction=self._get_seed_direction(),
                n=5,
                prompt_file=prompt_file,
                use_llm=use_llm,
                allow_fallback=True,
            )
        except Exception as e:
            logger.warning(f"Direction generation failed: {e}")
            return []

    def _get_seed_direction(self) -> str:
        """Get seed direction from best trajectory or default."""
        if self._trajectory_pool.trajectories:
            best = max(
                self._trajectory_pool.trajectories,
                key=lambda t: t.get_primary_metric() or 0.0,
            )
            if best.hypothesis:
                return best.hypothesis[:200]
        return "general factor exploration"
