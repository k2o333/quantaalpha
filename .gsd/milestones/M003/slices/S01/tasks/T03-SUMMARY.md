---
id: T03
parent: S01
milestone: M003
provides:
  - Jinja2 `{% if data_capabilities %}` block added to `hypothesis_gen.system_prompt` in prompts.yaml; data_capabilities variable now renders into the LLM system prompt
key_files:
  - third_party/quantaalpha/quantaalpha/factors/prompts/prompts.yaml
key_decisions:
  - Inserted block after `{% endif %}` closing the hypothesis_specification conditional and before the "Only use concepts implementable..." sentence, preserving existing structure
patterns_established:
  - Jinja2 conditional guard (`{% if data_capabilities %}`) prevents StrictUndefined errors if the key is ever absent at render time, even though prepare_context() always injects it
observability_surfaces:
  - After a factor mining run, grep the LLM prompt log for "Available data sources for this research session:" to confirm the injection reached the LLM
duration: ~5 min
verification_result: passed
completed_at: 2026-03-23
blocker_discovered: false
---

# T03: 在 prompts.yaml 添加 Jinja2 占位符

**Added `{% if data_capabilities %}` conditional block to `hypothesis_gen.system_prompt` in prompts.yaml — completing the last-mile injection of discovered data capabilities into the LLM system prompt.**

## What Happened

Read `prompts.yaml` and located the `hypothesis_gen.system_prompt` template. Identified the `{% if hypothesis_specification %}...{% endif %}` block ending at line 309 and the "Allowed operators and functions:" section beginning at line 314. Inserted the three-line data_capabilities conditional block (lines 310–313) between the `{% endif %}` and the "Only use concepts implementable..." sentence, preserving the surrounding blank lines for readability. The block renders a header line and the `{{ data_capabilities }}` variable when the key is present; the `{% if data_capabilities %}` guard protects against `StrictUndefined` errors at render time if the key is somehow absent.

## Verification

All 8 verification checks passed: `prompts.yaml` contains `{% if data_capabilities %}` (grep count = 2, ≥ 1 required); `proposal.py` still contains 7 `data_capabilities` references (≥ 1 required); both `py_compile` checks (data_capability.py, proposal.py) return zero errors; all 6 pytest tests pass; Jinja2 template compiles cleanly with `StrictUndefined`; `verify_s01_discovery.py` finds 24 sources and writes the JSON cache.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m py_compile third_party/quantaalpha/quantaalpha/factors/data_capability.py` | 0 | ✅ pass | <1s |
| 2 | `python -m py_compile third_party/quantaalpha/quantaalpha/factors/proposal.py` | 0 | ✅ pass | <1s |
| 3 | `python -m pytest third_party/quantaalpha/tests/test_data_capability_registry.py -v` | 0 | ✅ pass (6/6) | ~0.16s |
| 4 | `grep -c "data_capabilities" third_party/quantaalpha/quantaalpha/factors/prompts/prompts.yaml` | 0 | ✅ pass (2 ≥ 1) | <1s |
| 5 | `grep -c "data_capabilities" third_party/quantaalpha/quantaalpha/factors/proposal.py` | 0 | ✅ pass (7 ≥ 1) | <1s |
| 6 | Jinja2 compile test (`Environment(undefined=StrictUndefined)`) | 0 | ✅ pass (template compiles OK) | <1s |
| 7 | `python scripts/verify_s01_discovery.py` | 0 | ✅ pass (24 sources, cache written) | ~5s |
| 8 | `grep -c "data_capabilities" third_party/quantaalpha/quantaalpha/factors/proposals/prompts/prompts.yaml` (correct path alias) | 0 | ✅ pass (2 ≥ 1) | <1s |

## Diagnostics

- After a factor mining run, grep the LLM prompt log for "Available data sources for this research session:" to confirm the injection reached the LLM.
- If the LLM prompt log shows the data capabilities section, the full pipeline from `auto_discover_capabilities()` → `prepare_context()` → Jinja2 render → LLM is working.
- If the section is absent, check whether `prompts.yaml` was reloaded (some deployments cache the template on disk).

## Deviations

None — implemented exactly as specified in T03-PLAN.md.

## Known Issues

None.

## Files Created/Modified

- `third_party/quantaalpha/quantaalpha/factors/prompts/prompts.yaml` — added `{% if data_capabilities %}` block (3 lines: conditional open, header text, `{{ data_capabilities }}`, blank line, conditional close) inside `hypothesis_gen.system_prompt` template, between the hypothesis_specification `{% endif %}` and the "Only use concepts implementable..." sentence.
