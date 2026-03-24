---
id: T01
parent: S02
milestone: M003
provides:
  - "fewshot.py module: query_active_factors() and render_fewshot_examples() with 24h JSON cache, text-similarity scoring, and token budget control"
key_files:
  - "third_party/quantaalpha/quantaalpha/factors/fewshot.py"
  - "tests/test_fewshot.py"
patterns_established:
  - "Try/except import guard for optional FactorLibraryManager (S01 data_capability.py pattern)"
  - "24h TTL JSON cache with timestamp-based staleness check"
observability_surfaces:
  - "~/.cache/quantaalpha/fewshot_cache.json — JSON cache with timestamp and entry count"
duration: ~15min
verification_result: passed
completed_at: 2026-03-23T19:16:00+08:00
blocker_discovered: false
---

# T01: Create `fewshot.py` module with core functions

**Created `quantaalpha/factors/fewshot.py` — the query-and-render pipeline for exporting Active factors as LLM few-shot examples, plus 27 passing unit tests.**

## What Happened

Implemented the core `fewshot.py` module following `data_capability.py` (S01) patterns exactly:

1. **`query_active_factors()`** — filters `FactorLibraryManager.data["factors"]` to entries where `evaluation.status == "active"` and `evaluation.stability_score >= min_stability`. Scores by composite relatedness: 70% Jaccard text-overlap on hypothesis/description fields + 30% shared data fields bonus (for factors whose `$close`/`$volume` etc. appear in the anchor direction text). Sorts by (relatedness, stability) descending, returns top `max_examples`.

2. **`render_fewshot_examples()`** — calls `query_active_factors()`, formats each entry as `factor_experiment_output_format` JSON (`{FactorName: {description, variables, formulation, expression}}`), accumulates blocks within `max_token_budget` chars. First-block budget enforcement added after test revealed the initial guard only fired on N>1 blocks. Persists query results to `~/.cache/quantaalpha/fewshot_cache.json` (24h TTL) using `_save_cache`/`_load_cache` helpers.

3. **FactorLibraryManager guard** — wrapped in `try/except ImportError` per S01 pattern; functions return empty/false gracefully when the library is unavailable.

4. **Unit tests (27 total)** — all pass: tokenize/overlap helpers (6), relatedness scoring (2), status filter (2), stability filter (2), max_examples and ranking (2), empty-library graceful return (2), JSON format and schema (2), token budget enforcement (2), exclude IDs (1), cache round-trip (2). Two tests required adding `patch("quantaalpha.factors.fewshot._cache_is_valid", return_value=False)` to avoid reading stale cache from prior test runs.

The pre-flight flagged that S02-PLAN.md's verification lacks a failure-path check and that T01-PLAN.md lacks an `## Observability Impact` section. Both are T02 concerns (proposal.py wiring) and will be addressed when T02 wires `prepare_context` to call `render_fewshot_examples()`.

## Verification

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m py_compile third_party/quantaalpha/quantaalpha/factors/fewshot.py` | 0 | ✅ pass | <1s |
| 2 | `python -m pytest tests/test_fewshot.py -v` (27 tests) | 0 | ✅ pass | 0.46s |
| 3 | `python -c "import sys; sys.path.insert(0,'third_party/quantaalpha'); from quantaalpha.factors.fewshot import query_active_factors, render_fewshot_examples; print('OK')"` | 0 | ✅ pass | <1s |

The `prepare_context` injection check (`grep -q "{% if fewshot_examples %}" ...`) belongs to T02 verification, not T01 — T02 wires `proposal.py` and `prompts.yaml`.

## Diagnostics

- **Cache file:** `~/.cache/quantaalpha/fewshot_cache.json` — written with `generated_at` timestamp and `entries` list; invalidate by deleting file or setting `QUANTAALPHA_CACHE` env var
- **Structured failure state:** `render_fewshot_examples()` returns `""` when no active factors qualify (visible as zero-length return, not an exception)
- **Module import:** `from quantaalpha.factors.fewshot import query_active_factors, render_fewshot_examples`

## Deviations

- **Token budget first-block fix:** Initial budget guard `if blocks and (current_len + block_len + 2) > max_token_budget` allowed the first block to be added even when it alone exceeded the budget. Fixed by adding an early-return guard before appending when `len(blocks) == 0`.
- **Cache mocking in tests:** Two empty-library tests required `patch(_cache_is_valid, return_value=False)` to prevent stale cache reads — added as a targeted fix rather than redesigning the cache layer.

## Files Created

- `third_party/quantaalpha/quantaalpha/factors/fewshot.py` — Core module (query + render + cache helpers, ~340 lines)
- `tests/test_fewshot.py` — 27 unit tests covering all public functions and helper logic (~370 lines)
