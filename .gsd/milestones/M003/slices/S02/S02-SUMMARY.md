# S02: 因子库 Few-shot 导出 — Slice Summary

**Milestone:** M003 | **Slice:** S02 | **Completed:** 2026-03-23
**Triggered by:** D014 (ADR-001 因子知识库)
**Verification result:** ✅ All checks passed

---

## What This Slice Delivered

Implemented the query-and-render pipeline that exports Active factors from the factor library as LLM few-shot examples:

1. **`quantaalpha/factors/fewshot.py`** — new module (~340 lines) with:
   - `query_active_factors()` — filters `evaluation.status == "active"` and `stability_score >= min_stability`; scores by 70% Jaccard text-overlap + 30% shared data-field bonus; returns top `max_examples` sorted by (relatedness, stability) descending
   - `render_fewshot_examples()` — formats entries as `factor_experiment_output_format` JSON blocks; accumulates within `max_token_budget` chars; persists query results to `~/.cache/quantaalpha/fewshot_cache.json` (24h TTL)
   - `_compute_relatedness_score()` — composite anchor on `direction` (via `potential_direction`) + factor `metadata.hypothesis` + `factor_description`
   - `FactorLibraryManager` wrapped in `try/except ImportError` guard (S01 pattern); functions return `""` gracefully when library unavailable

2. **`proposal.py` T02 wiring** — `QlibFactorHypothesis2Experiment.prepare_context()` now injects `fewshot_examples` key (lines 176-199):
   - `getattr(self, 'potential_direction', None)` as anchor text (handles unset direction gracefully)
   - Defaults: `max_examples=3`, `min_stability=0.5`, `max_token_budget=2000`
   - Full try/except around `FactorLibraryManager` instantiation → `render_fewshot_examples()` → `fewshot_examples`; falls back to `""`
   - Result injected as `"fewshot_examples"` in returned context dict

3. **`prompts/prompts.yaml`** — `hypothesis_gen.system_prompt` now has:
   ```yaml
   {% if fewshot_examples %}
   ## Reference: Active High-Quality Factors
   These factors have proven stable across multiple market periods.
   {{ fewshot_examples }}
   {% endif %}
   ```
   **Deviation from plan:** `{% raw %}`/`{% endraw %}` was removed — the fewshot JSON output contains no Jinja2 syntax, so raw escaping would prevent variable substitution.

4. **`tests/test_fewshot.py`** — 27 unit tests covering all public functions and helpers; all pass.

---

## Verification Evidence

| # | Check | Command | Exit | Result |
|---|-------|---------|------|--------|
| 1 | `fewshot.py` syntax | `python -m py_compile .../fewshot.py` | 0 | ✅ pass |
| 2 | `proposal.py` syntax | `python -m py_compile .../proposal.py` | 0 | ✅ pass |
| 3 | Unit tests (27) | `python -m pytest tests/test_fewshot.py -v` | 0 | ✅ pass (0.46s) |
| 4 | Prompt template | `grep "{% if fewshot_examples %}" .../prompts.yaml` | 0 | ✅ pass |
| 5 | Injection in `prepare_context` | `grep "fewshot_examples" .../proposal.py` | 0 | ✅ pass (lines 26–199) |

---

## Patterns Established

1. **Try/except import guard for optional library** — `FactorLibraryManager` import wrapped in `try/except ImportError`, set to `None` on failure; every downstream call checks `is not None` before use. Matches S01's `data_capability.py` pattern exactly.

2. **Graceful empty-string fallback** — When library unavailable or no active factors qualify, `render_fewshot_examples()` returns `""` rather than raising. The Jinja2 `{% if fewshot_examples %}` guard in `prompts.yaml` skips the section silently.

3. **Per-block token budget with first-block safeguard** — Token budget guard fires on `len(blocks) > 0` to prevent the first (potentially oversized) block from being added, with an additional early-return guard for when the first block alone exceeds the budget.

4. **24h TTL JSON cache with mtime-based staleness** — `_cache_is_valid()` checks `st_mtime` against `CACHE_TTL_HOURS`; cache is written by `_save_cache()` only when no valid cache exists (avoids stamping over fresh cache with potentially stale in-memory data).

---

## Key Decisions

- **No `{% raw %}` block in Jinja2 template** — The fewshot content from `render_fewshot_examples()` is pure JSON; no Jinja2 template syntax appears in factor expressions/descriptions. Raw escaping would block `{{ fewshot_examples }}` interpolation. Plan was updated to reflect this.
- **Cache write after query, not after render** — Cache persists raw factor entry dicts (output of `query_active_factors`), not rendered JSON. This means `max_token_budget` is applied fresh each render call, allowing budget to be adjusted per-call without cache invalidation.
- **`potential_direction` via `getattr` guard** — `QlibFactorHypothesis2Experiment` does not guarantee `potential_direction` is set on every instance. `getattr(self, 'potential_direction', None)` avoids `AttributeError` and passes `None` to the scorer (which yields 0.0 relatedness but still returns factors sorted by stability).

---

## Observability Surfaces

| Surface | Location | Contents |
|---------|----------|----------|
| JSON cache | `~/.cache/quantaalpha/fewshot_cache.json` | `version`, `entries[]`, `generated_at` (ISO timestamp) |
| Module logger | via `logging.getLogger(__name__)` | `INFO` on cache miss, `WARNING` on read/write failure |
| `prepare_context` inspection | Return dict key `"fewshot_examples"` | Formatted JSON string or `""` |

Cache can be bypassed by setting `QUANTAALPHA_CACHE=""` env var or by calling `auto_discover_capabilities(use_cache=False)` equivalent.

---

## Boundary Map (S02 Outputs)

**Provides to downstream slices:**
- `fewshot.py` module with `query_active_factors()` / `render_fewshot_examples()`
- `prompts.yaml` `{% if fewshot_examples %}` placeholder in `hypothesis_gen.system_prompt`
- `prepare_context()` now returns `fewshot_examples` key

**Consumed by:**
- S04 (ProviderPool) — fewshot can provide factor examples for prompt augmentation
- S05 (JSON修复闭环) — fewshot examples may need JSON validation if factor expressions contain special chars
- S06 (Checkpoint) — fewshot cache is read at `prepare_context` call time; Checkpoint recovery must preserve cache file

---

## Known Limitations

- **Empty factor library**: If no Active factors exist with `stability_score >= 0.5`, `fewshot_examples` is `""` — the section is omitted from LLM prompts silently. This is by design (no noisy fallback) but means LLM may receive no historical guidance.
- **`rdagent` dependency in `proposal.py`**: The `prepare_context()` method cannot be imported in environments without the `rdagent` package (known conda env issue). The fewshot injection code path is wrapped in try/except, so the method itself compiles and the fewshot feature degrades gracefully when the module chain is broken.
- **No end-to-end test**: Real end-to-end verification requires a populated factor library with Active entries. Unit tests mock `FactorLibraryManager` entirely.

---

## Files Created / Modified

| File | Action | Lines |
|------|--------|-------|
| `third_party/quantaalpha/quantaalpha/factors/fewshot.py` | **CREATED** | ~340 |
| `tests/test_fewshot.py` | **CREATED** | ~370 |
| `third_party/quantaalpha/quantaalpha/factors/proposal.py` | MODIFIED (T02) | +25 lines (import guard + injection) |
| `third_party/quantaalpha/quantaalpha/factors/prompts/prompts.yaml` | MODIFIED (T02) | +5 lines (fewshot block) |
