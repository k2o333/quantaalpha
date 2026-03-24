# T01: Create `fewshot.py` module with core functions

**Slice:** S02 — 因子库 Few-shot 导出与智能采样
**Milestone:** M003

## Description

Create the core `fewshot.py` module implementing the query-and-render pipeline for exporting Active factors as LLM few-shot examples. This task implements:
- `query_active_factors()` — filter FactorLibraryManager by Active status + min_stability, score by relatedness (text overlap + shared data fields)
- `render_fewshot_examples()` — format selected factors as `factor_experiment_output_format` JSON
- 24h TTL JSON cache under `~/.cache/quantaalpha/fewshot_cache.json`

Follow S01's `data_capability.py` patterns exactly: dynamic import of FactorLibraryManager, try/except guards, Polars optional dependency wrapped in function.

## Steps

1. Create `third_party/quantaalpha/quantaalpha/factors/fewshot.py` with:
   - Imports: `json`, `os`, `hashlib`, `logging`, `Path` from pathlib, `datetime`
   - `CACHE_DIR = Path(os.environ.get("QUANTAALPHA_CACHE", str(Path.home() / ".cache" / "quantaalpha")))`
   - `CACHE_TTL_HOURS = 24`
   - `_load_cache()` and `_save_cache()` helper functions for JSON caching with TTL

2. Implement `query_active_factors()`:
   ```python
   def query_active_factors(
       manager: FactorLibraryManager,
       direction: str | None = None,
       max_examples: int = 3,
       min_stability: float = 0.5,
   ) -> list[dict]:
   ```
   - Filter: `evaluation.status == "active"` AND `stability_score >= min_stability`
   - Score by relatedness: text overlap on `hypothesis` + `factor_description` fields (case-insensitive token intersection), plus shared data fields from `data_requirements.fields` (e.g., both use `$close`)
   - Sort by (relatedness_score, stability_score) descending
   - Return top `max_examples`

3. Implement `render_fewshot_examples()`:
   ```python
   def render_fewshot_examples(
       manager: FactorLibraryManager,
       direction: str | None = None,
       max_examples: int = 3,
       min_stability: float = 0.5,
       max_token_budget: int = 2000,
       exclude_factor_ids: set[str] | None = None,
   ) -> str:
   ```
   - Call `query_active_factors()` to get factors
   - Format each as `factor_experiment_output_format` JSON block:
     ```json
     {
         "FactorName": {
             "description": "...",
             "variables": {"$close": "Close price", ...},
             "formulation": "LaTeX formula",
             "expression": "RANK(TS_MEAN($close, 20))"
         }
     }
     ```
   - Accumulate within token budget (rough estimate: count characters)
   - Return formatted string or empty string if no active factors

4. Wrap FactorLibraryManager import in try/except:
   ```python
   try:
       from quantaalpha.factors.library import FactorLibraryManager
   except ImportError:
       FactorLibraryManager = None  # type: ignore
   ```

5. Create `tests/test_fewshot.py` with:
   - Mock FactorLibraryManager returning sample factors with various statuses
   - Test: `test_query_active_factors_filters_status`
   - Test: `test_query_active_factors_filters_stability`
   - Test: `test_query_active_factors_scores_relatedness`
   - Test: `test_render_fewshot_examples_empty_library`
   - Test: `test_render_fewshot_examples_formats_json`
   - Test: `test_render_fewshot_examples_respects_token_budget`
   - Use pytest fixtures for mock manager

## Must-Haves

- [ ] `fewshot.py` module created with `query_active_factors()` and `render_fewshot_examples()` functions
- [ ] FactorLibraryManager import wrapped in try/except
- [ ] Text-similarity scoring implemented (hypothesis/description token overlap + shared data fields)
- [ ] Token budget control (default 2000 chars)
- [ ] 24h TTL JSON cache implemented
- [ ] Graceful empty result (returns empty string, not error)
- [ ] Unit tests pass with mock FactorLibraryManager

## Verification

```bash
# Syntax check
python -m py_compile third_party/quantaalpha/quantaalpha/factors/fewshot.py

# Run unit tests
python -m pytest tests/test_fewshot.py -v

# Verify module imports
python -c "from quantaalpha.factors.fewshot import query_active_factors, render_fewshot_examples; print('OK')"
```

## Inputs

- `third_party/quantaalpha/quantaalpha/factors/library.py` — FactorLibraryManager API for filtering/querying factors
- `third_party/quantaalpha/quantaalpha/factors/data_capability.py` — S01 reference pattern for try/except import guards and caching

## Expected Output

- `third_party/quantaalpha/quantaalpha/factors/fewshot.py` — New module with query+render pipeline
- `tests/test_fewshot.py` — Unit tests with mock FactorLibraryManager
