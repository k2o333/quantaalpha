---
id: T02
parent: S06
milestone: M004
status: completed
verification_result: passed
completed_at: 2026-03-24
blocker_discovered: false
observability_surfaces:
  - Singleton vector store: `get_vector_store()`
  - Jaccard similarity scores in query results
---

# T02: fewshot.py 集成 + 共性总结 prompt 模板

**Status:** Completed

## What Was Built

Integration of vector store with few-shot prompt generation pipeline.

### Key Components

1. **fewshot.py**: RAG-enhanced few-shot module
   - `query_active_factors_RAG()`: Vector similarity query with Jaccard fallback
   - `query_active_factors_jaccard()`: Pure Jaccard text matching
   - `build_fewshot_context()`: Format factors for prompts
   - `summarize_common_patterns()`: Extract shared characteristics
   - `enhance_prompt_with_RAG()`: Inject context into prompts

2. **prompts.yaml**: New templates for RAG-based synthesis
   - `common_patterns_summary`: Pattern analysis template
   - `factor_context_template`: Similar factors display

### API

```python
from quantaalpha.factors.fewshot import (
    query_active_factors_RAG,
    build_fewshot_context,
    summarize_common_patterns,
)

# Query similar factors
factors = query_active_factors_RAG(
    query="momentum reversal",
    top_k=5,
    library_path="data/results/factor_library.json"
)

# Build context for prompt
context = build_fewshot_context(factors)

# Summarize patterns
summary = summarize_common_patterns(factors, "momentum reversal")
```

## Verification Evidence

| Check | Command | Result |
|-------|---------|--------|
| Syntax | `python -m py_compile fewshot.py` | PASS |
| Import | `from quantaalpha.factors.fewshot import *` | PASS |
| Tests | `pytest tests/test_vector_store.py -v` | 34 passed |

## Key Decisions

1. **Singleton pattern**: `get_vector_store()` reuses instance
2. **Fallback chain**: Vector → Jaccard → empty result
3. **Pattern extraction**: Uses Counter for tag/operator frequency
