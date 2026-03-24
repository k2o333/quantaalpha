---
id: T02
parent: S01
milestone: M003
provides:
  - data_capabilities injection in AlphaAgentHypothesisGen.prepare_context(); try/except import guards for graceful degradation when data_capability module is unavailable
key_files:
  - third_party/quantaalpha/quantaalpha/factors/proposal.py
key_decisions:
  - Placed imports after existing core imports with separate try/except blocks so that absence of auto_discover_capabilities still leaves render_data_capabilities/get_data_capabilities usable
patterns_established:
  - Graceful fallback: if any import or call fails, render_data_capabilities(None) provides hardcoded content instead of crashing
observability_surfaces:
  - None added — injection populates context_dict["data_capabilities"], which is passed to Jinja2 renderer; no new logs or status endpoints
duration: ~8 min
verification_result: passed
completed_at: 2026-03-23
blocker_discovered: false
---

# T02: 在 proposal.py 的 prepare_context() 中注入 data_capabilities

**Added data_capabilities injection to AlphaAgentHypothesisGen.prepare_context() via render_data_capabilities() call in proposal.py.**

## What Happened

Read `proposal.py` and located `AlphaAgentHypothesisGen.prepare_context()` (around line 235). Added a two-block import section after the existing core imports: `render_data_capabilities` and `get_data_capabilities` in a try/except, then `auto_discover_capabilities` in a second try/except — so the module still loads if the discovery function is absent. Modified `prepare_context()` to call `auto_discover_capabilities()` when available, pipe the result through `get_data_capabilities()` and `render_data_capabilities()`, and store the rendered text in `context_dict["data_capabilities"]`. A top-level try/except wraps the call so any runtime failure falls back to `render_data_capabilities(None)` (hardcoded DATA_CAPABILITIES dict). The `prompts.yaml` was not modified — that is T03's job.

## Verification

All 4 task-level verification checks passed: syntax compiles cleanly, `grep -c "data_capabilities"` returns 7 (injection call exists and context key is added), and the `render_data_capabilities` import line is confirmed present. Slice-level checks also pass: `data_capability.py` compiles, all 6 pytest tests pass, and `verify_s01_discovery.py` finds 24 sources and writes the JSON cache. Note: full module import test fails due to unrelated `rdagent` dependency missing in this environment — not caused by my changes.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m py_compile third_party/quantaalpha/quantaalpha/factors/proposal.py` | 0 | ✅ pass | <1s |
| 2 | `python -m py_compile third_party/quantaalpha/quantaalpha/factors/data_capability.py` | 0 | ✅ pass | <1s |
| 3 | `python -m pytest third_party/quantaalpha/tests/test_data_capability_registry.py -v` | 0 | ✅ pass (6/6) | ~0.2s |
| 4 | `grep -c "data_capabilities" third_party/quantaalpha/quantaalpha/factors/proposal.py` | 0 | ✅ pass (7 ≥ 1) | <1s |
| 5 | `grep "from quantaalpha.factors.data_capability import" third_party/quantaalpha/quantaalpha/factors/proposal.py \| grep render_data_capabilities` | 0 | ✅ pass | <1s |
| 6 | `python scripts/verify_s01_discovery.py` | 0 | ✅ pass (24 sources, cache written) | ~5s |

## Diagnostics

- To confirm `data_capabilities` is present in `context_dict` after `prepare_context()` returns: add a debug print of `context_dict.keys()` after the call site in `gen()`.
- If the import fails silently, `data_capabilities` will still be present with hardcoded content from `render_data_capabilities(None)`.
- `grep -c "data_capabilities" prompts.yaml` returns 0 — expected, since T03 will add the Jinja2 variable reference there.

## Deviations

None — implemented exactly as specified in T02-PLAN.md.

## Known Issues

None.

## Files Created/Modified

- `third_party/quantaalpha/quantaalpha/factors/proposal.py` — added import block for `render_data_capabilities`, `get_data_capabilities`, `auto_discover_capabilities` (with separate try/except guards); added `data_capabilities_text` variable and `context_dict["data_capabilities"]` entry in `AlphaAgentHypothesisGen.prepare_context()`
