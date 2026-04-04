"""
Factor Vector Store using ChromaDB for semantic similarity search.

This module provides vector-based retrieval for factors, replacing Jaccard
text overlap with semantic embedding similarity.

Usage:
    from quantaalpha.factors.vector_store import FactorVectorStore
    
    # Initialize store (in-memory mode for development)
    store = FactorVectorStore()
    
    # Add a factor
    store.add_factor(factor_id="factor_001", factor_expression="close / open",
                     tags={"category": ["momentum"], "data_dependency": ["price_volume"]},
                     metadata={"status": "active", "ic": 0.05})
    
    # Query similar factors
    results = store.query_similar("momentum reversal", top_k=5)
"""

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Try to import ChromaDB - make it optional
try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    logger.warning("ChromaDB not available. Vector store will use fallback mode.")


@dataclass
class FactorVectorEntry:
    """Represents a factor with its embedding metadata."""
    factor_id: str
    factor_expression: str
    tags: dict[str, list[str]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class FactorVectorStore:
    """
    Vector store for factor expressions using ChromaDB.
    
    Supports:
    - Add/remove/query factors with semantic embeddings
    - Sync from FactorLibraryManager
    - Fallback mode when ChromaDB unavailable
    """
    
    DEFAULT_COLLECTION_NAME = "factors"
    DEFAULT_EMBEDDING_MODEL = "all-MiniLM-L6-v2"  # Default sentence-transformers model
    
    def __init__(
        self,
        persist_directory: Optional[str] = None,
        collection_name: str = DEFAULT_COLLECTION_NAME,
        embedding_model: Optional[str] = None,
    ):
        """
        Initialize the vector store.
        
        Args:
            persist_directory: Directory for ChromaDB persistence. 
                              If None, uses in-memory mode.
            collection_name: Name of the ChromaDB collection
            embedding_model: HuggingFace model name for embeddings.
                           If None, uses DEFAULT_EMBEDDING_MODEL.
        """
        self.collection_name = collection_name
        self.embedding_model = embedding_model or self.DEFAULT_EMBEDDING_MODEL
        self._client = None
        self._collection = None
        self._embedding_function = None
        
        # Fallback storage when ChromaDB unavailable
        self._fallback_storage: dict[str, dict] = {}
        
        if CHROMADB_AVAILABLE:
            self._init_chromadb(persist_directory)
        else:
            logger.info("Vector store running in fallback mode (ChromaDB not installed)")
    
    def _init_chromadb(self, persist_directory: Optional[str]) -> None:
        """Initialize ChromaDB client and collection."""
        try:
            if persist_directory:
                self._client = chromadb.PersistentClient(
                    path=str(persist_directory),
                    settings=Settings(anonymized_telemetry=False)
                )
            else:
                self._client = chromadb.Client(
                    Settings(anonymized_telemetry=False)
                )
            
            # Get or create collection with cosine distance
            self._collection = self._client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            
            # Initialize embedding function
            self._embedding_function = self._get_embedding_function()
            
            logger.info(f"Vector store initialized: collection={self.collection_name}, "
                       f"model={self.embedding_model}, persist={persist_directory}")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            self._client = None
            self._collection = None
    
    def _get_embedding_function(self):
        """Get embedding function for text."""
        if not CHROMADB_AVAILABLE:
            return None
            
        try:
            from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
            return SentenceTransformerEmbeddingFunction(model_name=self.embedding_model)
        except ImportError:
            logger.warning("sentence-transformers not available for ChromaDB embeddings")
            return None
    
    def _compute_text_representation(self, entry: FactorVectorEntry) -> str:
        """
        Compute a text representation for embedding.
        
        Combines factor expression with tags for richer semantic representation.
        """
        parts = [entry.factor_expression]
        
        # Add tag context
        if entry.tags:
            tag_parts = []
            for key, values in entry.tags.items():
                if values:
                    tag_parts.append(f"{key}: {', '.join(values)}")
            if tag_parts:
                parts.append(" | ".join(tag_parts))
        
        # Add metadata context
        if entry.metadata:
            meta_parts = []
            if entry.metadata.get("status"):
                meta_parts.append(f"status: {entry.metadata['status']}")
            if entry.metadata.get("ic") is not None:
                meta_parts.append(f"IC: {entry.metadata['ic']:.4f}")
            if entry.metadata.get("factor_name"):
                meta_parts.append(f"name: {entry.metadata['factor_name']}")
            if meta_parts:
                parts.append(" | ".join(meta_parts))
        
        return " | ".join(parts)
    
    def add_factor(
        self,
        factor_id: str,
        factor_expression: str,
        tags: Optional[dict[str, list[str]]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """
        Add a factor to the vector store.
        
        Args:
            factor_id: Unique identifier for the factor
            factor_expression: The factor formula/expression
            tags: Factor classification tags (category, data_dependency, etc.)
            metadata: Additional metadata (status, ic, factor_name, etc.)
            
        Returns:
            True if added successfully, False otherwise
        """
        if not factor_id or not factor_expression:
            logger.warning(f"Invalid factor: id={factor_id}, expr={factor_expression[:50] if factor_expression else 'empty'}")
            return False
        
        entry = FactorVectorEntry(
            factor_id=factor_id,
            factor_expression=factor_expression,
            tags=tags or {},
            metadata=metadata or {},
        )
        
        # Remove existing if re-adding
        self.remove_factor(factor_id)
        
        if CHROMADB_AVAILABLE and self._collection is not None:
            return self._add_to_chromadb(entry)
        else:
            return self._add_to_fallback(entry)
    
    def _add_to_chromadb(self, entry: FactorVectorEntry) -> bool:
        """Add entry to ChromaDB."""
        try:
            text_repr = self._compute_text_representation(entry)
            
            # Prepare metadata for ChromaDB
            chroma_metadata = {
                "factor_id": entry.factor_id,
                "factor_expression": entry.factor_expression,
                "tags": json.dumps(entry.tags, ensure_ascii=False),
                "metadata": json.dumps(entry.metadata, ensure_ascii=False),
                "created_at": entry.created_at,
            }
            
            self._collection.add(
                documents=[text_repr],
                metadatas=[chroma_metadata],
                ids=[entry.factor_id],
            )
            
            logger.debug(f"Added factor to ChromaDB: {entry.factor_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to add factor to ChromaDB: {e}")
            return False
    
    def _add_to_fallback(self, entry: FactorVectorEntry) -> bool:
        """Add entry to fallback storage (simple text matching)."""
        self._fallback_storage[entry.factor_id] = {
            "factor_expression": entry.factor_expression,
            "tags": entry.tags,
            "metadata": entry.metadata,
            "text_repr": self._compute_text_representation(entry),
            "created_at": entry.created_at,
        }
        logger.debug(f"Added factor to fallback storage: {entry.factor_id}")
        return True
    
    def query_similar(
        self,
        query_text: str,
        top_k: int = 5,
        filter_metadata: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """
        Query for similar factors using vector similarity.
        
        Args:
            query_text: Text to find similar factors for
            top_k: Number of results to return
            filter_metadata: Optional metadata filters
            
        Returns:
            List of dicts with factor_id, score, and metadata
        """
        if CHROMADB_AVAILABLE and self._collection is not None:
            return self._query_chromadb(query_text, top_k, filter_metadata)
        else:
            return self._query_fallback(query_text, top_k, filter_metadata)
    
    def _query_chromadb(
        self,
        query_text: str,
        top_k: int,
        filter_metadata: Optional[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Query ChromaDB for similar factors."""
        try:
            # Build where clause for filtering
            where_clause = None
            if filter_metadata:
                where_clause = {}
                for key, value in filter_metadata.items():
                    if key in ["status"]:
                        where_clause[key] = value
            
            results = self._collection.query(
                query_texts=[query_text],
                n_results=min(top_k, self._collection.count()),
                where=where_clause,
            )
            
            if not results or not results.get("ids"):
                return []
            
            # Format results
            formatted = []
            for i, factor_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i]
                distance = results["distances"][0][i] if results.get("distances") else 1.0
                
                # Convert cosine distance to similarity score (0-1, higher = more similar)
                similarity = max(0.0, 1.0 - distance)
                
                formatted.append({
                    "factor_id": factor_id,
                    "score": round(similarity, 4),
                    "factor_expression": metadata.get("factor_expression", ""),
                    "tags": json.loads(metadata.get("tags", "{}")),
                    "metadata": json.loads(metadata.get("metadata", "{}")),
                    "created_at": metadata.get("created_at", ""),
                })
            
            return formatted
        except Exception as e:
            logger.error(f"ChromaDB query failed: {e}")
            return self._query_fallback(query_text, top_k, filter_metadata)
    
    def _query_fallback(
        self,
        query_text: str,
        top_k: int,
        filter_metadata: Optional[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Fallback query using simple text matching with normalization."""
        import re
        
        def normalize(text: str) -> set[str]:
            """Normalize text: lowercase, remove special chars, split into words."""
            normalized = re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())
            return set(w for w in normalized.split() if w)
        
        query_words = normalize(query_text)
        
        results = []
        for factor_id, data in self._fallback_storage.items():
            # Apply metadata filters
            if filter_metadata:
                skip = False
                for key, value in filter_metadata.items():
                    stored_value = data.get("metadata", {}).get(key)
                    if stored_value != value:
                        skip = True
                        break
                if skip:
                    continue
            
            # Normalized word overlap scoring
            text_repr = data["text_repr"]
            text_words = normalize(text_repr)
            
            # Jaccard-like score
            if query_words and text_words:
                overlap = len(query_words & text_words)
                union = len(query_words | text_words)
                score = overlap / union if union > 0 else 0.0
            else:
                score = 0.0
            
            # Boost if query appears in text (after normalization)
            query_lower = query_text.lower()
            text_lower = text_repr.lower()
            if query_lower in text_lower or any(q in text_lower for q in query_lower.split()):
                score = max(score, 0.3)
            
            if score > 0:
                results.append({
                    "factor_id": factor_id,
                    "score": round(score, 4),
                    "factor_expression": data["factor_expression"],
                    "tags": data.get("tags", {}),
                    "metadata": data.get("metadata", {}),
                    "created_at": data.get("created_at", ""),
                })
        
        # Sort by score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]
    
    def remove_factor(self, factor_id: str) -> bool:
        """
        Remove a factor from the vector store.
        
        Args:
            factor_id: ID of the factor to remove
            
        Returns:
            True if removed successfully
        """
        if CHROMADB_AVAILABLE and self._collection is not None:
            try:
                self._collection.delete(ids=[factor_id])
                logger.debug(f"Removed factor from ChromaDB: {factor_id}")
                return True
            except Exception as e:
                logger.debug(f"Factor {factor_id} not in ChromaDB: {e}")
        
        # Also remove from fallback
        if factor_id in self._fallback_storage:
            del self._fallback_storage[factor_id]
            logger.debug(f"Removed factor from fallback: {factor_id}")
        
        return True
    
    def sync_from_library(
        self,
        library_path: str,
        filter_status: Optional[str] = None,
        filter_tags: Optional[dict[str, list[str]]] = None,
    ) -> int:
        """
        Sync factors from FactorLibraryManager JSON file.
        
        Args:
            library_path: Path to the factor library JSON file
            filter_status: Only sync factors with this status
            filter_tags: Only sync factors with these tags (any match)
            
        Returns:
            Number of factors synced
        """
        try:
            with open(library_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Failed to load library from {library_path}: {e}")
            return 0
        
        factors = data.get("factors", {})
        synced = 0
        
        for factor_id, factor_entry in factors.items():
            # Apply status filter
            if filter_status:
                status = factor_entry.get("evaluation", {}).get("status", "")
                if status != filter_status:
                    continue
            
            # Apply tag filter
            if filter_tags:
                tags = factor_entry.get("tags", {})
                has_match = False
                for key, values in filter_tags.items():
                    factor_values = tags.get(key, [])
                    if any(v in factor_values for v in values):
                        has_match = True
                        break
                if not has_match:
                    continue
            
            # Add to vector store
            success = self.add_factor(
                factor_id=factor_id,
                factor_expression=factor_entry.get("factor_expression", ""),
                tags=factor_entry.get("tags", {}),
                metadata={
                    "status": factor_entry.get("evaluation", {}).get("status", ""),
                    "ic": factor_entry.get("backtest_results", {}).get("IC"),
                    "rank_ic": factor_entry.get("backtest_results", {}).get("Rank IC"),
                    "factor_name": factor_entry.get("factor_name", ""),
                    "stability_score": factor_entry.get("evaluation", {}).get("stability_score"),
                },
            )
            if success:
                synced += 1
        
        logger.info(f"Synced {synced} factors from {library_path}")
        return synced
    
    def count(self) -> int:
        """Get the number of factors in the store."""
        if CHROMADB_AVAILABLE and self._collection is not None:
            return self._collection.count()
        return len(self._fallback_storage)
    
    def clear(self) -> None:
        """Clear all factors from the store."""
        if CHROMADB_AVAILABLE and self._collection is not None:
            try:
                self._collection.delete(where={})
            except Exception as e:
                logger.error(f"Failed to clear ChromaDB collection: {e}")
        
        self._fallback_storage.clear()
        logger.info("Vector store cleared")


def create_vector_store(
    persist_dir: Optional[str] = None,
    collection: str = "factors",
) -> FactorVectorStore:
    """
    Factory function to create a FactorVectorStore instance.
    
    Args:
        persist_dir: Directory for persistence (None for in-memory)
        collection: Collection name
        
    Returns:
        FactorVectorStore instance
    """
    return FactorVectorStore(
        persist_directory=persist_dir,
        collection_name=collection,
    )
