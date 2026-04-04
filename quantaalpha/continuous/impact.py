"""
Coarse Impact Classifier for 24H Continuous Factor MVP.

This module provides a heuristic classifier that:
1. Maps update interfaces to dependency groups (buckets)
2. Maps dependency groups to constrained factor candidate sets
3. Provides fallback strategies when metadata is sparse or unknown

Buckets:
- price_volume: price/volume based factors
- financial: financial statement based factors
- moneyflow: money flow based factors
- chip: chip/distribution based factors
- other: everything else

Fallback Behavior:
- If interface is unknown -> fallback to active/stale/degraded factors
- If factor metadata is missing -> fallback to active/stale/degraded factors
- If no matching candidates -> fallback to active/stale/degraded factors
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

if TYPE_CHECKING:
    from quantaalpha.factors.library import FactorLibraryManager

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Bucket definitions
# ----------------------------------------------------------------------
VALID_BUCKETS = ["price_volume", "financial", "moneyflow", "chip", "other"]

# Fallback statuses for bounded fallback candidate selection
FALLBACK_STATUSES = ["active", "stale", "degraded"]

# ----------------------------------------------------------------------
# Interface to bucket mapping (prefix-based and explicit rules)
# ----------------------------------------------------------------------
# Format: (pattern_type, pattern, bucket)
# pattern_type can be: "prefix", "exact", "contains"
INTERFACE_BUCKET_RULES: list[tuple[str, str, str]] = [
    # Price/Volume interfaces
    ("prefix", "daily", "price_volume"),
    ("prefix", "daily_basic", "price_volume"),
    ("prefix", "price", "price_volume"),
    ("prefix", "volume", "price_volume"),
    ("prefix", "quotation", "price_volume"),
    ("prefix", "bar", "price_volume"),
    ("prefix", "tick", "price_volume"),
    # Financial interfaces
    ("prefix", "financial", "financial"),
    ("prefix", "income", "financial"),
    ("prefix", "balance", "financial"),
    ("prefix", "cashflow", "financial"),
    ("prefix", "bank", "financial"),  # bank financial statement
    ("prefix", "insurance", "financial"),  # insurance financial statement
    ("prefix", "sec", "financial"),  # SEC filings
    # Moneyflow interfaces
    ("prefix", "moneyflow", "moneyflow"),
    ("prefix", "margin", "moneyflow"),  # margin trading
    ("prefix", "shuangxiang", "moneyflow"),  # bidirectional flow
    ("prefix", "north", "moneyflow"),  # northbound flow
    ("prefix", "south", "moneyflow"),  # southbound flow
    # Chip interfaces
    ("prefix", "chip", "chip"),
    ("prefix", "float", "chip"),  # float holder data
    ("prefix", "holder", "chip"),  # holder distribution
    ("prefix", "cyq_", "chip"),  # chip distribution pattern
    ("prefix", "position", "chip"),  # position distribution
    # Default: everything else
    ("default", "", "other"),
]


def _interface_matches_pattern(interface: str, pattern_type: str, pattern: str) -> bool:
    """Check if an interface name matches a pattern rule."""
    interface_lower = interface.lower()
    pattern_lower = pattern.lower()

    if pattern_type == "prefix":
        return interface_lower.startswith(pattern_lower)
    elif pattern_type == "exact":
        return interface_lower == pattern_lower
    elif pattern_type == "contains":
        return pattern_lower in interface_lower
    elif pattern_type == "default":
        return True  # Default rule always matches
    return False


def _classify_single_interface(interface: str) -> str:
    """Classify a single interface name into a dependency bucket."""
    for pattern_type, pattern, bucket in INTERFACE_BUCKET_RULES:
        if _interface_matches_pattern(interface, pattern_type, pattern):
            return bucket
    return "other"


# ----------------------------------------------------------------------
# Factor metadata tag to bucket mapping
# ----------------------------------------------------------------------
# These are the data_dependency tags from factor library
BUCKET_TAG_MAP = {
    "price_volume": ["price_volume", "alternative"],  # alternative can include price_volume
    "financial": ["financial"],
    "moneyflow": [],  # No specific tag, inferred from expression
    "chip": [],  # No specific tag, inferred from expression
    "other": [],  # Everything else
}

# Reverse index: tag value -> bucket key
# This fixes the bug where tag VALUES (like "alternative") were never matched
# because the old code only checked if dep was a BUCKET KEY
TAG_TO_BUCKET: dict[str, str] = {}
for bucket, tags in BUCKET_TAG_MAP.items():
    for tag in tags:
        TAG_TO_BUCKET[tag] = bucket
# Map the bucket keys themselves too
for bucket in BUCKET_TAG_MAP:
    TAG_TO_BUCKET.setdefault(bucket, bucket)

# Keywords in factor expressions that suggest a particular bucket
EXPRESSION_KEYWORDS = {
    "financial": [
        "roe", "roa", "roic", "gross_margin", "net_margin", "profit_margin",
        "revenue", "income", "ebit", "ebitda", "assets", "liabilities",
        "equity", "debt", "cash_flow", "operating profit", "net profit",
        "eps", "book_value", "financial_ratio",
    ],
    "moneyflow": [
        "moneyflow", "margin", "short", "borrow", "lend",
        "northbound", "southbound", "的主力", "净流入", "融资", "融券",
    ],
    "chip": [
        "chip", "float", "holder", "持股", "筹码", "cyq",
        "position", "distribution", "成本", "集中度",
    ],
}


def _extract_buckets_from_factor_entry(factor_entry: dict[str, Any]) -> list[str]:
    """Extract matching buckets from a factor entry based on its tags and expression."""
    buckets = set()

    # Check data_dependency tags
    tags = factor_entry.get("tags", {})
    data_deps = tags.get("data_dependency", [])

    if isinstance(data_deps, str):
        data_deps = [data_deps]

    for dep in data_deps:
        if dep in TAG_TO_BUCKET:
            buckets.add(TAG_TO_BUCKET[dep])

    # Check factor expression for keywords
    expression = str(factor_entry.get("factor_expression", "")).lower()

    for bucket, keywords in EXPRESSION_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in expression:
                buckets.add(bucket)
                break

    # If no tags or expression match, it could be price_volume (default)
    if not buckets:
        # Check if it uses price/volume fields
        price_volume_fields = ["$close", "$open", "$high", "$low", "$volume", "$amount"]
        for field in price_volume_fields:
            if field.lower() in expression:
                buckets.add("price_volume")
                break

    return list(buckets) if buckets else ["other"]


# ----------------------------------------------------------------------
# ImpactClassifier class
# ----------------------------------------------------------------------
class ImpactClassifier:
    """
    Coarse-grained impact classifier for continuous factor operations.

    Usage:
        classifier = ImpactClassifier()

        # Classify interfaces into dependency groups
        groups = classifier.classify_interfaces(["daily", "moneyflow", "unknown_interface"])
        # -> ["price_volume", "moneyflow", "other"]

        # Select factor candidates from a library based on groups
        candidates = classifier.select_factor_candidates(library_manager, groups, limit=50)
        # -> [{"factor_id": "...", "factor_name": "...", ...}, ...]
    """

    def __init__(
        self,
        default_limit: int = 50,
        fallback_limit: int = 100,
    ):
        """
        Initialize the classifier.

        Args:
            default_limit: Default maximum candidates to return per group.
            fallback_limit: Maximum candidates to return in fallback mode.
        """
        self.default_limit = default_limit
        self.fallback_limit = fallback_limit

    def classify_interfaces(self, interfaces: list[str]) -> list[str]:
        """
        Classify a list of interface names into dependency buckets.

        Args:
            interfaces: List of interface names (e.g., ["daily", "moneyflow", "cyq_chip"])

        Returns:
            List of unique bucket names (order preserved, deduplicated).
            Returns all valid buckets if interfaces is empty or all unknown.
        """
        if not interfaces:
            # Empty input -> return all buckets as a safe default
            return list(VALID_BUCKETS)

        buckets_seen = set()
        result = []

        for interface in interfaces:
            bucket = _classify_single_interface(interface)
            if bucket not in buckets_seen:
                buckets_seen.add(bucket)
                result.append(bucket)

        # If all interfaces were unknown (only "other"), still include all known buckets
        # to ensure some revalidation happens
        if result == ["other"] and len(interfaces) > 1:
            # Multiple unknown interfaces - use full fallback
            return list(VALID_BUCKETS)

        return result

    def select_factor_candidates(
        self,
        library_manager: "FactorLibraryManager",
        groups: list[str],
        limit: Optional[int] = None,
    ) -> list[dict[str, Any]]:
        """
        Select factor candidates from the library based on dependency groups.

        Args:
            library_manager: FactorLibraryManager instance to query.
            groups: List of dependency group buckets to filter by.
            limit: Maximum number of candidates to return.
                   If None, uses self.default_limit.
                   Fallback mode uses min(self.fallback_limit, limit or inf).

        Returns:
            List of factor entry dicts with at least:
            - factor_id
            - factor_name
            - factor_expression
            - tags (with data_dependency)
            - evaluation (with status)

            Returns fallback candidates if:
            - groups is empty
            - no factors match the given groups
            - library_manager is None or invalid
        """
        if limit is None:
            limit = self.default_limit

        # Fallback: if no groups specified, use all valid buckets
        if not groups:
            logger.debug("No groups specified, using all buckets for fallback")
            groups = list(VALID_BUCKETS)

        # Try to select from library
        candidates = []
        try:
            candidates = self._select_by_groups(library_manager, groups, limit)
        except Exception as e:
            logger.warning(f"Error selecting by groups, using fallback: {e}")

        # Fallback if no candidates found
        if not candidates:
            logger.debug(f"No candidates found for groups {groups}, using fallback")
            candidates = self._select_fallback_candidates(library_manager, limit)

        return candidates[:limit] if limit else candidates

    def _select_by_groups(
        self,
        library_manager: "FactorLibraryManager",
        groups: list[str],
        limit: int,
    ) -> list[dict[str, Any]]:
        """Select factors matching the given dependency groups."""
        if library_manager is None:
            return []

        all_factors = library_manager.data.get("factors", {})
        candidates = []

        for factor_id, factor_entry in all_factors.items():
            # Normalize entry
            if isinstance(factor_entry, dict):
                entry_buckets = _extract_buckets_from_factor_entry(factor_entry)

                # Check if any of the requested groups match
                for group in groups:
                    if group in entry_buckets:
                        normalized = self._normalize_factor_dict(factor_entry)
                        candidates.append(normalized)
                        break

        return candidates[:limit] if limit else candidates

    def _select_fallback_candidates(
        self,
        library_manager: "FactorLibraryManager",
        limit: int,
    ) -> list[dict[str, Any]]:
        """
        Select fallback candidates: all active, stale, and degraded factors.

        This is used when:
        - Interface is unknown
        - Factor metadata is missing
        - No factors match the given groups
        """
        effective_limit = min(self.fallback_limit, limit) if limit else self.fallback_limit

        if library_manager is None:
            logger.warning("No library manager provided, returning empty fallback")
            return []

        candidates = []
        all_factors = library_manager.data.get("factors", {})

        for factor_id, factor_entry in all_factors.items():
            if not isinstance(factor_entry, dict):
                continue

            status = factor_entry.get("evaluation", {}).get("status", "")

            if status in FALLBACK_STATUSES:
                normalized = self._normalize_factor_dict(factor_entry)
                candidates.append(normalized)

            if len(candidates) >= effective_limit:
                break

        return candidates

    @staticmethod
    def _normalize_factor_dict(factor_entry: dict[str, Any]) -> dict[str, Any]:
        """
        Normalize a factor entry to the standard candidate dict shape.

        Returns a dict with at least:
        - factor_id
        - factor_name
        - factor_expression
        - tags
        - evaluation
        """
        if not isinstance(factor_entry, dict):
            return {}

        return {
            "factor_id": factor_entry.get("factor_id", ""),
            "factor_name": factor_entry.get("factor_name", ""),
            "factor_expression": factor_entry.get("factor_expression", ""),
            "tags": factor_entry.get("tags", {}),
            "evaluation": factor_entry.get("evaluation", {}),
            "metadata": factor_entry.get("metadata", {}),
            "data_requirements": factor_entry.get("data_requirements", {}),
        }

    def get_valid_buckets(self) -> list[str]:
        """Return the list of valid bucket names."""
        return list(VALID_BUCKETS)

    def describe_bucket(self, bucket: str) -> str:
        """Return a human-readable description of a bucket."""
        descriptions = {
            "price_volume": "Price and volume based factors (close, open, high, low, volume, amount)",
            "financial": "Financial statement based factors (roe, roa, profit, margin, revenue)",
            "moneyflow": "Money flow based factors (margin, northbound,主力,净流入)",
            "chip": "Chip distribution based factors (chip, holder, float, cyq, position)",
            "other": "Factors that don't fit other categories or use mixed data sources",
        }
        return descriptions.get(bucket, f"Unknown bucket: {bucket}")
