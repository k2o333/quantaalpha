# S02: 因子库 Few-shot 导出与智能采样

**Triggered by:** D014 (ADR-001 因子知识库)

**Problem:** `library.py` has the base capability, but lacks an interface to export Active factors as LLM few-shot examples. Without this, historical good factors cannot guide new factor generation.

**After this:** Active factors can be exported by relatedness as LLM few-shot examples.

---

## Goal

Implement a new module `quantaalpha/factors/fewshot.py` that:
1. Queries `FactorLibraryManager` for Active factors filtered by stability score
2. Ranks factors by text-similarity relatedness to the current hypothesis/direction
3. Renders selected factors as `factor_experiment_output_format` JSON examples
4. Injects `fewshot_examples` into LLM prompts via `proposal.py` `prepare_context()`

**Demo:** Running `python -c "from quantaalpha.factors.fewshot import query_active_factors, render_fewshot_examples; ..."` produces formatted few-shot text that can be injected into prompts.

---

## Must-Haves

- `quantaalpha/factors/fewshot.py` module with `query_active_factors()` and `render_fewshot_examples()`
- Token budget control (default 2000 tokens, ~3-5 examples)
- Stability score filtering (default min_stability=0.5)
- Text-similarity relatedness scoring (hypothesis/description overlap + shared data fields)
- `{% raw %}` block in `prompts.yaml` for few-shot placeholder injection
- `prepare_context()` in `proposal.py` injects `fewshot_examples` with graceful fallback
- 24h JSON cache under `~/.cache/quantaalpha/`

---

## Proof Level

- **Contract verification:** Python syntax check, unit tests
- **Runtime required:** No — pure Python module, no external services
- **Human/UAT required:** No — automated verification sufficient

---

## Verification

```bash
# Syntax check
python -m py_compile third_party/quantaalpha/quantaalpha/factors/fewshot.py

# Unit test (mock FactorLibraryManager with sample factors)
python -m pytest tests/test_fewshot.py -v

# Manual verification — check prepare_context returns fewshot_examples key
python -c "
from quantaalpha.factors.proposal import QlibFactorHypothesis2Experiment
from quantaalpha.core.proposal import Hypothesis, Trace, Scenario
scen = Scenario()
exp = QlibFactorHypothesis2Experiment(scen)
h = Hypothesis('test', '', '', 'obs', 'just', 'know', 'spec')
t = Trace(scen)
ctx, ok = exp.prepare_context(h, t)
assert 'fewshot_examples' in ctx, f'fewshot_examples missing, got: {list(ctx.keys())}'
print('OK: fewshot_examples injected into context')
"

# Verify prompt template contains few-shot placeholder
grep -q "{% if fewshot_examples %}" third_party/quantaalpha/quantaalpha/factors/prompts/prompts.yaml && echo "OK: prompt template has fewshot placeholder"
```

---

## Observability / Diagnostics

- **Runtime signals:** None — synchronous pure-Python module, no async/stateful flows
- **Inspection surfaces:** `~/.cache/quantaalpha/fewshot_cache.json` — JSON cache of query results with timestamp and example count; `library.get_summary()` shows Active factor count
- **Failure visibility:** If `FactorLibraryManager` is unavailable or returns no factors, `render_fewshot_examples()` returns empty string — inspectable via cache file existence check
- **Redaction constraints:** Factor expressions and descriptions are written to cache; no PII expected in factor library entries

---

## Integration Closure

- **Upstream surfaces consumed:** `quantaalpha/factors/library.py` (FactorLibraryManager), `quantaalpha/factors/prompts/prompts.yaml`
- **New wiring introduced:** `proposal.py` `prepare_context()` imports `fewshot.render_fewshot_examples()` via try/except guard (S01 pattern)
- **What remains before end-to-end:** Prompt injection end-to-end requires actual factor library with Active entries; unit tests mock this entirely

---

## Tasks

- [x] **T01: Create `fewshot.py` module with core functions** `est:2h`
  - Why: The core module needs to exist before wiring into proposal.py and prompts.yaml
  - Files: `third_party/quantaalpha/quantaalpha/factors/fewshot.py`, `third_party/quantaalpha/quantaalpha/factors/library.py`
  - Do: Implement `query_active_factors()` (filter by status, score by relatedness) and `render_fewshot_examples()` (format as `factor_experiment_output_format` JSON). Add 24h TTL JSON cache under `~/.cache/quantaalpha/`. Follow S01's `data_capability.py` patterns.
  - Verify: `python -m py_compile third_party/quantaalpha/quantaalpha/factors/fewshot.py && python -m pytest tests/test_fewshot.py -v`
  - Done when: Module imports without error, unit tests pass with mock FactorLibraryManager

- [x] **T02: Wire fewshot into `prepare_context()` and `prompts.yaml`** `est:1h`
  - Why: The few-shot examples must be injected into LLM prompts to be useful
  - Files: `third_party/quantaalpha/quantaalpha/factors/proposal.py`, `third_party/quantaalpha/quantaalpha/factors/prompts/prompts.yaml`
  - Do: Add `{% raw %}`/`{% endraw %}` block for `{% if fewshot_examples %}` in prompts.yaml. Add `fewshot_examples` key to `prepare_context()` return dict via try/except guard (S01 pattern). Use `potential_direction` as the relatedness anchor.
  - Verify: `grep -q "{% if fewshot_examples %}" third_party/quantaalpha/quantaalpha/factors/prompts/prompts.yaml && python -c "from quantaalpha.factors.proposal import QlibFactorHypothesis2Experiment; ..."` (see full verification above)
  - Done when: `prepare_context()` returns `fewshot_examples` key, prompts.yaml has Jinja2 placeholder

---

## Files Likely Touched

- `third_party/quantaalpha/quantaalpha/factors/fewshot.py` — NEW
- `third_party/quantaalpha/quantaalpha/factors/library.py` — READ for FactorLibraryManager API
- `third_party/quantaalpha/quantaalpha/factors/proposal.py` — MODIFY prepare_context()
- `third_party/quantaalpha/quantaalpha/factors/prompts/prompts.yaml` — ADD few-shot placeholder template
- `tests/test_fewshot.py` — NEW (unit tests)

---
estimated_steps: 6
estimated_files: 5
skills_used:
  - test
  - best-practices
