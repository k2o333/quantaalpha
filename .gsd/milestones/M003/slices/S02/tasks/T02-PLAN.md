# T02: Wire fewshot into `prepare_context()` and `prompts.yaml`

**Slice:** S02 — 因子库 Few-shot 导出与智能采样
**Milestone:** M003

## Description

Wire the `render_fewshot_examples()` function into the `prepare_context()` method in `proposal.py` and add the Jinja2 placeholder block in `prompts.yaml`. This follows S01's `data_capability` injection pattern exactly: try/except guard per symbol, graceful fallback on import error or empty result.

## Steps

1. Read the current `prepare_context()` method in `proposal.py` (around line 520) to find the insertion point. The method returns a `context_dict` that is then rendered via Jinja2. Add `fewshot_examples` to this dict.

2. Add the following import guard block near the top of `proposal.py` (after existing imports):
   ```python
   try:
       from quantaalpha.factors.fewshot import render_fewshot_examples
   except ImportError:
       render_fewshot_examples = None  # type: ignore
   ```

3. Find the `prepare_context()` method in `QlibFactorHypothesis2Experiment`. Add `fewshot_examples` injection:
   ```python
   # Inject few-shot examples from factor library
   fewshot_text = ""
   if render_fewshot_examples is not None:
       try:
           manager = FactorLibraryManager(str(library_path))
           fewshot_text = render_fewshot_examples(
               manager=manager,
               direction=self.potential_direction,
               max_examples=3,
               min_stability=0.5,
               max_token_budget=2000,
           )
       except Exception:
           logger.debug("fewshot injection failed, using empty examples")
   context_dict["fewshot_examples"] = fewshot_text
   ```

4. Add `library_path` variable if not already present in `prepare_context()`. It should be something like:
   ```python
   library_path = Path(os.environ.get("FACTOR_LIBRARY_PATH", "data/results/factor_library.json"))
   ```

5. Read `prompts.yaml` and find the `hypothesis_gen.system_prompt` section. Add the few-shot placeholder inside the `{% raw %}`/`{% endraw %}` block:
   ```yaml
   {% raw %}
   {% if fewshot_examples %}
   ## Reference: Active High-Quality Factors
   These factors have proven stable across multiple market periods.
   {{ fewshot_examples }}
   {% endif %}
   {% endraw %}
   ```

   **CRITICAL:** The `{% raw %}`/`{% endraw %}` block MUST wrap the `{{ fewshot_examples }}` template variable because the few-shot output contains Jinja2-like `{{` and `}}` characters from the JSON format.

6. Verify the Jinja2 template is syntactically valid:
   ```python
   from jinja2 import Environment, StrictUndefined
   env = Environment(undefined=StrictUndefined)
   template = env.from_string("""
   {% raw %}
   {% if fewshot_examples %}
   ## Reference
   {{ fewshot_examples }}
   {% endif %}
   {% endraw %}
   """)
   result = template.render(fewshot_examples="test")
   assert "Reference" in result
   ```

## Must-Haves

- [ ] `render_fewshot_examples` import wrapped in try/except guard in `proposal.py`
- [ ] `prepare_context()` returns `context_dict` containing `fewshot_examples` key
- [ ] Graceful fallback: if FactorLibraryManager unavailable or returns empty, `fewshot_examples = ""`
- [ ] `prompts.yaml` has `{% raw %}`/`{% endraw %}` block wrapping `{% if fewshot_examples %}` and `{{ fewshot_examples }}`
- [ ] Jinja2 template renders without error when `fewshot_examples` is empty or populated

## Verification

```bash
# Verify prompt template contains few-shot placeholder
grep -q "{% if fewshot_examples %}" third_party/quantaalpha/quantaalpha/factors/prompts/prompts.yaml && echo "OK: prompt template has fewshot placeholder"
grep -q "{% raw %}" third_party/quantaalpha/quantaalpha/factors/prompts/prompts.yaml && echo "OK: prompt template has raw block"

# Verify prepare_context injects fewshot_examples
python -c "
import os
os.environ['FACTOR_LIBRARY_PATH'] = 'data/results/factor_library.json'
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

# Jinja2 template validity
python -c "
from jinja2 import Environment, StrictUndefined
env = Environment(undefined=StrictUndefined)
import yaml
with open('third_party/quantaalpha/quantaalpha/factors/prompts/prompts.yaml') as f:
    prompts = yaml.safe_load(f)
template = env.from_string(prompts['hypothesis_gen']['system_prompt'])
result = template.render(fewshot_examples='test factor')
assert 'Reference' in result
print('OK: Jinja2 template renders correctly')
"
```

## Inputs

- `third_party/quantaalpha/quantaalpha/factors/proposal.py` — `prepare_context()` method to modify
- `third_party/quantaalpha/quantaalpha/factors/prompts/prompts.yaml` — Prompt template to add few-shot placeholder
- `third_party/quantaalpha/quantaalpha/factors/fewshot.py` — Output from T01 (render_fewshot_examples function)

## Expected Output

- `third_party/quantaalpha/quantaalpha/factors/proposal.py` — Modified with fewshot injection
- `third_party/quantaalpha/quantaalpha/factors/prompts/prompts.yaml` — Modified with Jinja2 few-shot placeholder
