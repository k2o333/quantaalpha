# S01: 数据能力注入最后一公里 (S1) — Slice Summary

**Milestone:** M003 | **Slices:** S01 | **Status:** ✅ Complete
**Executed:** 2026-03-23 | **Duration:** ~25 min (T01: ~10m, T02: ~8m, T03: ~5m)

---

## What This Slice Delivered

S01 closes the "last-mile" gap in LLM data awareness by wiring three previously disconnected components:

1. **`auto_discover_capabilities()`** — a new function in `data_capability.py` that dynamically scans all 24 Parquet subdirectories under `/home/quan/testdata/aspipe_v4/data/*/`, reads the first `.parquet` schema via Polars, infers `freq` (quarterly vs daily) and `lag_days` (45 vs 0) from the presence of `ann_date`, excludes `_update_time`-family metadata fields, maps directory names to domain `factor_hints`, and writes a 24-hour JSON cache to `~/.cache/quantaalpha/data_capability_registry.json`.

2. **`prepare_context()` injection** — `AlphaAgentHypothesisGen.prepare_context()` now calls `auto_discover_capabilities()` → `get_data_capabilities()` → `render_data_capabilities()` and inserts the result as `context_dict["data_capabilities"]` before the Jinja2 template is rendered. All imports are wrapped in separate `try/except` blocks so the absence of any single function falls back to the hardcoded `DATA_CAPABILITIES` dict.

3. **`prompts.yaml` Jinja2 placeholder** — the `hypothesis_gen.system_prompt` template now contains a `{% if data_capabilities %}` conditional block between the hypothesis specification section and the operator constraints section, so the LLM receives the full 24-source registry at inference time.

---

## Verification Results

| Check | Result |
|---|---|
| `py_compile data_capability.py` | ✅ pass |
| `py_compile proposal.py` | ✅ pass |
| `pytest test_data_capability_registry.py -v` | ✅ 6/6 pass |
| `scripts/verify_s01_discovery.py` | ✅ 24 sources discovered, 15 589-char render, cache written |
| `grep "data_capabilities" prompts.yaml` | ✅ ≥ 1 (found 2) |
| `grep "data_capabilities" proposal.py` | ✅ ≥ 1 (found 7) |

---

## Key Design Decisions

- **Package root is `third_party/quantaalpha`** — the worktree root is the parent of the quantaalpha submodule; `sys.path` must extend to `third_party/quantaalpha` for direct `from quantaalpha.factors.data_capability import …` imports. Using the bare package name was a recurring source of `ImportError` in the worktree environment.
- **Polars import is wrapped in `try/except` within `_scan_dir_schema`** — `data_capability.py` still loads and compiles when Polars is absent; only dynamic discovery fails, leaving the hardcoded fallback intact.
- **Separate `try/except` import blocks for each symbol** — ensures that `render_data_capabilities` / `get_data_capabilities` remain usable even if `auto_discover_capabilities` fails to import. Import failure cascades are the most common failure mode in this codebase (per M001/M002 lessons).
- **24-hour JSON cache validity window** — chosen to match the likely update frequency of the data directory without requiring frequent rescans. The cache file preserves the last successful scan even after failures.
- **Jinja2 `{% if data_capabilities %}` guard in `prompts.yaml`** — prevents `StrictUndefined` errors if the key is ever absent at render time. This defensive pattern is consistent with the template's existing `{% if hypothesis_specification %}` guard.

---

## Patterns Established

1. **Graceful degradation at every boundary** — `auto_discover_capabilities()` → `get_data_capabilities()` → `render_data_capabilities()` each has an independent fallback, forming a three-layer fallback chain.
2. **Polars-optional module loading** — wrapped inside `_scan_dir_schema()` rather than at the top level, so the module compiles even when Polars is absent.
3. **Defensive isinstance check** — future code that consumes `render_data_capabilities()` output should treat it as a string; dict-type inputs are handled by the fallback chain but the output is always a string.
4. **Per-symbol try/except import blocks** — each imported symbol has its own try/except, preventing a missing function from cascading into unrelated imports.

---

## Files Modified

| File | Change |
|---|---|
| `third_party/quantaalpha/quantaalpha/factors/data_capability.py` | Added `auto_discover_capabilities()`, 4 helper functions, module constants, polars import, JSON cache logic, updated `__all__` |
| `third_party/quantaalpha/quantaalpha/factors/proposal.py` | Added import block with try/except guards; injected `data_capabilities` into `context_dict` in `prepare_context()` |
| `third_party/quantaalpha/quantaalpha/factors/prompts/prompts.yaml` | Added `{% if data_capabilities %}` Jinja2 conditional block to `hypothesis_gen.system_prompt` |
| `scripts/verify_s01_discovery.py` | New standalone verification script |

---

## Downstream Dependencies (Boundary Map)

- **S04 (ProviderPool)** — consumes the data capability registry for config validation
- **S07 (PIT Alignment)** — uses the `ann_date` lag inference to align financial data by announcement date

---

## Open Items

- No blockers. All must-have criteria in the slice plan are satisfied.
- Observability surface confirmed: `~/.cache/quantaalpha/data_capability_registry.json` contains all 24 sources with schema field counts after any invocation of `auto_discover_capabilities()`.
