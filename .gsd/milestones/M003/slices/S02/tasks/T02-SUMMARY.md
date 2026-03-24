---
id: T02
parent: S02
milestone: M003
provides:
  - "proposal.py: fewshot import guard + prepare_context injection (fewshot_examples key)"
  - "prompts.yaml: hypothesis_gen.system_prompt has {% if fewshot_examples %} block"
key_files:
  - "third_party/quantaalpha/quantaalpha/factors/proposal.py"
  - "third_party/quantaalpha/quantaalpha/factors/prompts/prompts.yaml"
patterns_established:
  - "Try/except import guard for optional render_fewshot_examples (same as S01 data_capability pattern)"
  - "Graceful fallback: if FactorLibraryManager unavailable or returns empty, fewshot_examples = \"\""
observability_surfaces:
  - "~/.cache/quantaalpha/fewshot_cache.json — written with generated_at timestamp and entries"
duration: ~10min
verification_result: passed
completed_at: 2026-03-23T19:16:04+08:00
blocker_discovered: false
---

# T02: Wire fewshot into `prepare_context()` and `prompts.yaml`

**Wired `render_fewshot_examples()` into `QlibFactorHypothesis2Experiment.prepare_context()` and added Jinja2 placeholder in `prompts.yaml`.**

## What Happened

Implemented the few-shot injection following the same patterns as S01's `data_capability`:

1. **Added import guard** in `proposal.py` (after data_capability imports):
   ```python
   try:
       from quantaalpha.factors.fewshot import render_fewshot_examples
       from quantaalpha.factors.library import FactorLibraryManager
   except ImportError:
       render_fewshot_examples = None
       FactorLibraryManager = None
   ```

2. **Added `fewshot_examples` injection** in `QlibFactorHypothesis2Experiment.prepare_context()`:
   - Uses `getattr(self, 'potential_direction', None)` for graceful handling (direction not always set on this class)
   - Calls `render_fewshot_examples()` with defaults: `max_examples=3`, `min_stability=0.5`, `max_token_budget=2000`
   - Wrapped in try/except for graceful failure if FactorLibraryManager is unavailable
   - Injects result as `fewshot_examples` key in the returned context dict

3. **Added Jinja2 placeholder** in `prompts.yaml` `hypothesis_gen.system_prompt`:
   ```yaml
   {% if fewshot_examples %}
   ## Reference: Active High-Quality Factors
   These factors have proven stable across multiple market periods.
   {{ fewshot_examples }}
   {% endif %}
   ```

   **Note:** Removed the `{% raw %}`/`{% endraw %}` block from the plan's approach. The raw block would prevent Jinja2 from interpolating `{{ fewshot_examples }}`. The fewshot content is JSON text without actual Jinja2 template syntax, so raw escaping is not needed.

## Verification

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `python -m py_compile third_party/quantaalpha/quantaalpha/factors/proposal.py` | 0 | ✅ pass | <1s |
| 2 | `grep -q "{% if fewshot_examples %}" .../prompts/prompts.yaml` | 0 | ✅ pass | <1s |
| 3 | Jinja2 template render test with populated fewshot_examples | 0 | ✅ pass | <1s |
| 4 | `python -m pytest tests/test_fewshot.py -v` (27 tests) | 0 | ✅ pass | 0.49s |

## Diagnostics

- **Cache file:** `~/.cache/quantaalpha/fewshot_cache.json` — written with `generated_at` timestamp and `entries` list; invalidate by deleting file or setting `QUANTAALPHA_CACHE` env var
- **Structured failure state:** `fewshot_examples = ""` when FactorLibraryManager unavailable or no active factors qualify
- **prepare_context inspection:** `ctx['fewshot_examples']` contains the formatted few-shot text or empty string

## Deviations

- **Removed `{% raw %}` block:** The plan specified `{% raw %}` around `{{ fewshot_examples }}`, but this prevents Jinja2 variable substitution. The fewshot content (JSON output from `render_fewshot_examples`) doesn't contain actual Jinja2 template syntax, so raw escaping is unnecessary. The template now correctly renders the fewshot content when present.

## Files Modified

- `third_party/quantaalpha/quantaalpha/factors/proposal.py` — Added import guard and `fewshot_examples` injection in `prepare_context()`
- `third_party/quantaalpha/quantaalpha/factors/prompts/prompts.yaml` — Added `{% if fewshot_examples %}` placeholder in `hypothesis_gen.system_prompt`
