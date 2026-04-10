"""
Few-shot prompt generation for factor mining with RAG enhancement.

This module provides methods to retrieve similar factors for few-shot prompting,
using either vector similarity (RAG) or fallback Jaccard text matching.
"""

import json
import logging
import os
from typing import Any, Optional

from quantaalpha.factors.vector_store import FactorVectorStore, FactorVectorEntry

logger = logging.getLogger(__name__)

# Default paths
DEFAULT_LIBRARY_PATH = os.environ.get(
    "FACTOR_LIBRARY_PATH",
    "third_party/quantaalpha/data/factorlib/all_factors_library.json"
)

# Singleton vector store instance
_vector_store: Optional[FactorVectorStore] = None


def get_vector_store(
    persist_dir: Optional[str] = None,
    library_path: Optional[str] = None,
    auto_sync: bool = True,
) -> FactorVectorStore:
    """
    Get or create the singleton vector store instance.
    
    Args:
        persist_dir: Directory for ChromaDB persistence
        library_path: Path to factor library for auto-sync
        auto_sync: Whether to sync from library on first access
        
    Returns:
        FactorVectorStore instance
    """
    global _vector_store
    
    if _vector_store is None:
        _vector_store = FactorVectorStore(
            persist_directory=persist_dir,
            collection_name="factors",
        )
        
        if auto_sync and library_path:
            try:
                _vector_store.sync_from_library(
                    library_path=library_path,
                    filter_status="active",
                )
                logger.info(f"Vector store synced from {library_path}")
            except Exception as e:
                logger.warning(f"Failed to sync vector store: {e}")
    
    return _vector_store


def reset_vector_store() -> None:
    """Reset the singleton vector store (useful for testing)."""
    global _vector_store
    _vector_store = None


def compute_jaccard_similarity(text1: str, text2: str) -> float:
    """
    Compute Jaccard similarity between two texts.
    
    Used as fallback when vector similarity is unavailable.
    Normalizes texts by removing special characters and lowercasing.
    """
    if not text1 or not text2:
        return 0.0
    
    def normalize(text: str) -> set[str]:
        """Normalize text: lowercase, remove special chars, split into words."""
        import re
        # Remove special characters but keep alphanumeric
        normalized = re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())
        # Split on whitespace and filter empty
        return set(w for w in normalized.split() if w)
    
    words1 = normalize(text1)
    words2 = normalize(text2)
    
    if not words1 or not words2:
        return 0.0
    
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    
    return intersection / union if union > 0 else 0.0


def query_active_factors_RAG(
    query: str,
    top_k: int = 5,
    min_score: float = 0.0,
    library_path: Optional[str] = None,
    use_vector: bool = True,
    fallback_to_jaccard: bool = True,
) -> list[dict[str, Any]]:
    """
    Query active factors using RAG (vector similarity) with Jaccard fallback.
    
    Args:
        query: Query text (e.g., "momentum reversal")
        top_k: Number of results to return
        min_score: Minimum similarity score threshold
        library_path: Path to factor library
        use_vector: Whether to use vector similarity (False = Jaccard only)
        fallback_to_jaccard: Whether to fall back to Jaccard if vector fails
        
    Returns:
        List of factor entries with similarity scores
    """
    # Try vector similarity first
    if use_vector:
        try:
            store = get_vector_store(
                library_path=library_path or DEFAULT_LIBRARY_PATH
            )
            
            results = store.query_similar(
                query_text=query,
                top_k=top_k * 2,  # Get more to allow filtering
                filter_metadata={"status": "active"},
            )
            
            # Filter by minimum score
            filtered = [r for r in results if r["score"] >= min_score]
            
            if filtered:
                logger.debug(f"RAG query '{query[:50]}' returned {len(filtered)} results")
                return filtered[:top_k]
            
        except Exception as e:
            logger.warning(f"Vector query failed, falling back to Jaccard: {e}")
    
    # Fallback to Jaccard similarity
    if fallback_to_jaccard:
        return query_active_factors_jaccard(
            query=query,
            top_k=top_k,
            min_score=min_score,
            library_path=library_path,
        )
    
    return []


def looks_like_factor_expression(query: str) -> bool:
    """Return True when the query resembles a factor expression."""
    if not query:
        return False

    markers = ["$", "(", ")", "+", "-", "*", "/"]
    if any(marker in query for marker in markers):
        return True

    upper_query = query.upper()
    function_markers = ["TS_", "MEAN(", "STD(", "MAX(", "MIN(", "RANK("]
    return any(marker in upper_query for marker in function_markers)


def query_active_factors_ast(
    query: str,
    top_k: int = 5,
    min_score: float = 0.0,
    library_path: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Query active factors using AST structural similarity when query is an expression."""
    if not looks_like_factor_expression(query):
        return []

    library_path = library_path or DEFAULT_LIBRARY_PATH

    if not os.path.exists(library_path):
        logger.warning(f"Factor library not found: {library_path}")
        return []

    try:
        with open(library_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load factor library: {e}")
        return []

    try:
        from quantaalpha.factors.ast_score import compute_ast_score
    except ImportError:
        try:
            from .ast_score import compute_ast_score
        except ImportError:
            logger.warning("AST score module not available for AST retrieval")
            return []

    factors = data.get("factors", {})
    results = []

    for factor_id, factor_entry in factors.items():
        status = factor_entry.get("evaluation", {}).get("status", "")
        if status != "active":
            continue

        expression = factor_entry.get("factor_expression", "")
        ast_result = compute_ast_score(query, expression)
        if ast_result.error is not None:
            continue

        if ast_result.score >= min_score:
            results.append({
                "factor_id": factor_id,
                "score": round(ast_result.score, 4),
                "factor_expression": expression,
                "factor_description": factor_entry.get("factor_description", ""),
                "factor_name": factor_entry.get("factor_name", ""),
                "tags": factor_entry.get("tags", {}),
                "metadata": {
                    "status": status,
                    "ic": factor_entry.get("backtest_results", {}).get("IC"),
                    "rank_ic": factor_entry.get("backtest_results", {}).get("Rank IC"),
                    "subtree_size": ast_result.subtree_size,
                    "nodes_a": ast_result.nodes_a,
                    "nodes_b": ast_result.nodes_b,
                },
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def query_active_factors_jaccard(
    query: str,
    top_k: int = 5,
    min_score: float = 0.1,
    library_path: Optional[str] = None,
) -> list[dict[str, Any]]:
    """
    Query active factors using Jaccard text similarity (fallback method).
    
    Args:
        query: Query text
        top_k: Number of results to return
        min_score: Minimum Jaccard score threshold
        library_path: Path to factor library
        
    Returns:
        List of factor entries with similarity scores
    """
    library_path = library_path or DEFAULT_LIBRARY_PATH
    
    if not os.path.exists(library_path):
        logger.warning(f"Factor library not found: {library_path}")
        return []
    
    try:
        with open(library_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load factor library: {e}")
        return []
    
    factors = data.get("factors", {})
    results = []
    
    for factor_id, factor_entry in factors.items():
        # Only active factors
        status = factor_entry.get("evaluation", {}).get("status", "")
        if status != "active":
            continue
        
        # Compute Jaccard similarity
        expression = factor_entry.get("factor_expression", "")
        description = factor_entry.get("factor_description", "")
        
        score1 = compute_jaccard_similarity(query, expression)
        score2 = compute_jaccard_similarity(query, description)
        score = max(score1, score2)
        
        if score >= min_score:
            results.append({
                "factor_id": factor_id,
                "score": round(score, 4),
                "factor_expression": expression,
                "factor_description": description,
                "factor_name": factor_entry.get("factor_name", ""),
                "tags": factor_entry.get("tags", {}),
                "metadata": {
                    "status": status,
                    "ic": factor_entry.get("backtest_results", {}).get("IC"),
                    "rank_ic": factor_entry.get("backtest_results", {}).get("Rank IC"),
                },
            })
    
    # Sort by score descending
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]


def build_fewshot_context(
    factors: list[dict[str, Any]],
    include_expression: bool = True,
    include_tags: bool = True,
    include_ic: bool = True,
) -> str:
    """
    Build a few-shot context string from factor entries.
    
    Args:
        factors: List of factor entries with scores
        include_expression: Include factor expression
        include_tags: Include classification tags
        include_ic: Include IC metrics
        
    Returns:
        Formatted context string for prompts
    """
    if not factors:
        return "No similar factors found."
    
    lines = ["Similar factors from the library:\n"]
    
    for i, factor in enumerate(factors, 1):
        lines.append(f"--- Factor {i} (similarity: {factor['score']:.2%}) ---")
        
        if factor.get("factor_name"):
            lines.append(f"Name: {factor['factor_name']}")
        
        if include_expression and factor.get("factor_expression"):
            lines.append(f"Expression: {factor['factor_expression']}")
        
        if include_tags and factor.get("tags"):
            tags = factor.get("tags", {})
            tag_parts = []
            for key, values in tags.items():
                if values:
                    tag_parts.append(f"{key}: {', '.join(values)}")
            if tag_parts:
                lines.append(f"Tags: {' | '.join(tag_parts)}")
        
        if include_ic:
            metadata = factor.get("metadata", {})
            ic = metadata.get("ic")
            rank_ic = metadata.get("rank_ic")
            if ic is not None:
                lines.append(f"IC: {ic:.4f}")
            if rank_ic is not None:
                lines.append(f"Rank IC: {rank_ic:.4f}")
        
        lines.append("")
    
    return "\n".join(lines)


def summarize_common_patterns(
    factors: list[dict[str, Any]],
    query: str,
) -> str:
    """
    Summarize common patterns from similar factors.
    
    This extracts shared characteristics that could guide new factor generation.
    
    Args:
        factors: List of similar factors
        query: Original query text
        
    Returns:
        Summary of common patterns
    """
    if not factors:
        return f"No existing factors match '{query}'. Consider exploring new patterns."
    
    # Aggregate tags
    all_tags = {"category": [], "data_dependency": [], "market_environment": [], "time_horizon": []}
    ic_values = []
    
    for factor in factors:
        tags = factor.get("tags", {})
        for key in all_tags:
            all_tags[key].extend(tags.get(key, []))
        
        metadata = factor.get("metadata", {})
        ic = metadata.get("ic")
        if ic is not None:
            ic_values.append(ic)
    
    # Count tag frequencies
    tag_summary = []
    for key, values in all_tags.items():
        if values:
            from collections import Counter
            counts = Counter(values).most_common(3)
            tag_summary.append(f"{key}: {', '.join(f'{v}({c})' for v, c in counts)}")
    
    # Compute average IC
    avg_ic = sum(ic_values) / len(ic_values) if ic_values else None
    
    # Build summary
    lines = [
        f"Analysis of {len(factors)} similar factors:",
        "",
    ]
    
    if tag_summary:
        lines.append("Common characteristics:")
        for ts in tag_summary:
            lines.append(f"  - {ts}")
        lines.append("")
    
    if avg_ic is not None:
        lines.append(f"Average IC: {avg_ic:.4f}")
        lines.append("")
    
    # Extract common expressions patterns
    expressions = [f.get("factor_expression", "") for f in factors if f.get("factor_expression")]
    if expressions:
        # Find common operators
        operators = []
        for expr in expressions:
            for op in ["RANK", "DELTA", "TS_MEAN", "ZSCORE", "/", "*", "-", "+"]:
                if op in expr.upper():
                    operators.append(op)
        
        if operators:
            from collections import Counter
            op_counts = Counter(operators).most_common(5)
            lines.append("Common operators:")
            for op, count in op_counts:
                lines.append(f"  - {op}: {count}/{len(expressions)} factors")
            lines.append("")
    
    return "\n".join(lines)


def enhance_prompt_with_RAG(
    prompt_template: str,
    query: str,
    top_k: int = 3,
    library_path: Optional[str] = None,
    include_pattern_summary: bool = True,
) -> str:
    """
    Enhance a prompt with RAG-retrieved factor context.
    
    Args:
        prompt_template: Base prompt template
        query: Query for finding similar factors
        top_k: Number of similar factors to include
        library_path: Path to factor library
        include_pattern_summary: Include summarized common patterns
        
    Returns:
        Enhanced prompt with factor context
    """
    # Get similar factors
    factors = query_active_factors_RAG(
        query=query,
        top_k=top_k,
        library_path=library_path,
        fallback_to_jaccard=True,
    )
    
    if not factors:
        return prompt_template
    
    # Build few-shot context
    context = build_fewshot_context(
        factors=factors,
        include_expression=True,
        include_tags=True,
        include_ic=True,
    )
    
    # Add pattern summary if requested
    if include_pattern_summary:
        pattern_summary = summarize_common_patterns(factors, query)
        context = f"{context}\n\n{pattern_summary}"
    
    # Insert into prompt (assuming placeholder)
    enhanced = prompt_template.replace(
        "{{FACTOR_CONTEXT}}",
        context
    )
    
    if "{{FACTOR_CONTEXT}}" not in enhanced:
        # Append if no placeholder found
        enhanced = f"{enhanced}\n\n## Similar Factors from Library\n\n{context}"
    
    return enhanced
