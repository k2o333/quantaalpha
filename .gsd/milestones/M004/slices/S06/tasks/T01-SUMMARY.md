---
id: T01
parent: S06
milestone: M004
status: completed
verification_result: passed
completed_at: 2026-03-24
blocker_discovered: false
observability_surfaces:
  - ChromaDB availability: `CHROMADB_AVAILABLE` constant
  - Vector store count: `store.count()`
  - ChromaDB collection metadata via chromadb client
---

# T01: vector_store.py 核心模块

**Status:** Completed

## What Was Built

FactorVectorStore class with ChromaDB integration for semantic similarity search.

### Key Components

- **Vector Store**: ChromaDB-backed with in-memory and persistent modes
- **Fallback Mode**: When ChromaDB unavailable, uses normalized Jaccard similarity
- **Text Normalization**: Removes special characters (`$`, `()`, etc.) for matching
- **CRUD Operations**: `add_factor()`, `query_similar()`, `remove_factor()`, `sync_from_library()`
- **Embedding Format**: Combines factor_expression + tags + metadata for rich representation

### API

```python
from quantaalpha.factors.vector_store import FactorVectorStore

# In-memory mode
store = FactorVectorStore()

# Persistent mode
store = FactorVectorStore(persist_directory="/path/to/dir")

# Add factor
store.add_factor(
    factor_id="f001",
    factor_expression="RANK(TS_MEAN($close, 20))",
    tags={"category": ["momentum"]},
    metadata={"status": "active", "ic": 0.05}
)

# Query similar factors
results = store.query_similar("momentum reversal", top_k=5)

# Sync from library
store.sync_from_library("data/results/factor_library.json", filter_status="active")
```

## Verification Evidence

| Check | Command | Result |
|-------|---------|--------|
| Syntax | `python -m py_compile vector_store.py` | PASS |
| Import | `from quantaalpha.factors.vector_store import FactorVectorStore` | PASS |
| Tests | `pytest tests/test_vector_store.py -v` | 34 passed |

## Key Decisions

1. **ChromaDB optional**: Falls back to Jaccard when ChromaDB unavailable
2. **Cosine distance**: ChromaDB collection uses `hnsw:space: cosine`
3. **Text normalization**: `re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())` for matching

## Diagnostics

```bash
# Check ChromaDB availability
python -c "from quantaalpha.factors.vector_store import CHROMADB_AVAILABLE; print(CHROMADB_AVAILABLE)"

# Count factors in store
python -c "from quantaalpha.factors.vector_store import FactorVectorStore; print(FactorVectorStore().count())"
```
