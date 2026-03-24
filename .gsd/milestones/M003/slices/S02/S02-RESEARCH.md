# S02: 因子库 Few-shot 导出 — Research

**Date:** 2026-03-23

## Summary

S02 implements the ability to export active factors from the factor library as LLM few-shot examples. Building on S01's data capability injection pattern, this slice adds a new query-and-render pipeline: `query_active_factors()` retrieves top-K factors by relatedness to the current hypothesis, and `render_fewshot_examples()` formats them as JSON examples matching the `factor_experiment_output_format` prompt template.

The implementation mirrors S01's architecture (dynamic discovery + Jinja2 rendering + LLM injection) but targets the existing `FactorLibraryManager` instead of Parquet files. Relatedness scoring uses text similarity on hypothesis/description fields and shared data field usage (e.g., both use `$close`).

## Recommendation

**Create a new module `quantaalpha/factors/fewshot.py`** with:
1. `query_active_factors()` — filters `FactorLibraryManager` by status, scores by relatedness
2. `render_fewshot_examples()` — formats selected factors as `factor_experiment_output_format` JSON
3. Jinja2 template section in `prompts.yaml` for few-shot injection placeholder
4. `prepare_context()` hook in `proposal.py` to inject `fewshot_examples` into LLM prompt

This follows the proven S01 pattern exactly. Start with text-similarity scoring (hypothesis/description overlap) before adding more complex metrics.

## Implementation Landscape

### Key Files

| File | Role |
|------|------|
| `quantaalpha/factors/library.py` | `FactorLibraryManager` — factor CRUD, status filtering, entry normalization |
| `quantaalpha/factors/prompts/prompts.yaml` | `factor_experiment_output_format` template — the target JSON schema for few-shot |
| `quantaalpha/factors/proposal.py` | `prepare_context()` methods — where few-shot injection happens |
| `quantaalpha/factors/data_capability.py` | S01 reference pattern — `auto_discover_capabilities()`, `render_data_capabilities()` |

### Factor Entry Schema (from library.py)

Each factor in the library has this structure:
```python
{
    "factor_id": str,
    "factor_name": str,
    "factor_expression": str,        # e.g., "RANK(TS_MEAN($close, 20))"
    "factor_description": str,
    "factor_formulation": str,        # LaTeX formula
    "factor_implementation_code": str,
    "metadata": {
        "hypothesis": str,           # ← primary relatedness anchor
        "evolution_phase": str,       # "original" | "refinement" | ...
        "experiment_id": str,
        ...
    },
    "backtest_results": {
        "IC": float,
        "1day.excess_return_without_cost.annualized_return": float,
        ...
    },
    "evaluation": {
        "status": str,               # "active" | "degraded" | "stale" | "pending_validation"
        "stability_score": float,
        ...
    },
    "data_requirements": {
        "fields": list[str],         # ["$close", "$volume"] — extracted from expression
        "dimensions": list[str],      # ["price_volume", "financial"]
    }
}
```

### Build Order

1. **Create `fewshot.py`** with minimal `query_active_factors()` and `render_fewshot_examples()`
2. **Add `{% raw %}` block to `prompts.yaml`** for few-shot placeholder template
3. **Wire into `proposal.py`** `prepare_context()` — follow S01's data_capability pattern exactly
4. **Add caching** (24h TTL, JSON cache under `~/.cache/quantaalpha/`)
5. **Verification** — unit tests + manual prompt inspection

### Verification Approach

```bash
# Syntax check
python -m py_compile third_party/quantaalpha/quantaalpha/factors/fewshot.py

# Unit test (mock FactorLibraryManager with sample factors)
python -m pytest tests/test_fewshot.py -v

# Manual verification — check LLM prompt contains few-shot block
grep -A 50 "fewshot_examples" ~/.cache/quantaalpha/llm_prompt_cache.json  # after a run
```

---

## Constraints

- **Worktree import path**: `third_party/quantaalpha` is the package root (not `third_party`). All imports must use `quantaalpha.factors.*` paths from within that root.
- **LLM context length**: Few-shot examples add token overhead. Limit to 3-5 examples per prompt to avoid hitting token limits.
- **FactorLibraryManager is file-based**: Queries require loading the JSON from disk each time. Cache results aggressively.
- **S01 pattern consistency**: Follow the same import guard pattern (`try/except ImportError`) for `render_fewshot_examples` in `proposal.py`.

---

## Common Pitfalls

- **Jinja2 escaping**: The few-shot JSON block contains `{{` and `}}` characters. Must wrap in `{% raw %}`/`{% endraw %}` in YAML or escape with `{% verbatim %}`.
- **Circular import**: `fewshot.py` imports `FactorLibraryManager` → `library.py` imports from `status_rules.py`. Avoid importing `fewshot` in `library.py`.
- **Empty factor library**: Handle gracefully when no active factors exist (return empty string, not error).

---

## Open Risks

- **Relatedness scoring granularity**: Text similarity on hypothesis/description is naive. May need TF-IDF or embedding-based similarity in future iteration.
- **Token budget**: 3-5 few-shot examples × ~500 chars each = ~2500 tokens overhead. Acceptable for now but monitor.

---

## Skills Discovered

| Technology | Skill | Status |
|------------|-------|--------|
| Jinja2 template escaping | N/A (standard library) | Available |
| JSON for LLM prompts | N/A (custom implementation) | N/A |
| Text similarity scoring | N/A (custom, simple overlap) | N/A |
