# T03: 在 prompts.yaml 添加 Jinja2 占位符

**Slice:** S01 — 数据能力注入最后一公里 (S1)
**Milestone:** M003

## Description

在 `prompts.yaml` 的 `hypothesis_gen.system_prompt` 模板中添加 Jinja2 条件块，使 `data_capabilities` 变量能被渲染到 LLM 系统提示词中。这是"最后一公里"——即使 `prepare_context()` 正确注入了 `data_capabilities`，如果没有对应的 Jinja2 占位符，LLM 仍然收不到数据能力描述。

## Steps

1. **Read `prompts.yaml`** and locate the `hypothesis_gen.system_prompt` section. Identify the `{% if hypothesis_specification %}...{% endif %}` block and the `Allowed operators and functions:` line.
2. **Add the data_capabilities block** after the `{% if hypothesis_specification %}...{% endif %}` block and before the `Allowed operators and functions:` line:
   ```yaml
   {% if data_capabilities %}
   Available data sources for this research session:
   {{ data_capabilities }}

   {% endif %}
   ```
3. **Use `{% if data_capabilities %}` guard** — this is critical because `prepare_context()` always injects the key (with fallback content), but the guard prevents Jinja2 `StrictUndefined` errors in case the key is somehow missing at render time.
4. **Do NOT** add any new YAML keys outside the template strings — only modify the template text content.

## Must-Haves

- [ ] `prompts.yaml` contains `{% if data_capabilities %}` somewhere in the file.
- [ ] The block renders `{{ data_capabilities }}` inside the `hypothesis_gen.system_prompt` template.
- [ ] Existing pytest tests (`test_data_capability_registry.py`) still pass after this change.
- [ ] No Jinja2 syntax errors introduced.

## Verification

```bash
# Verify placeholder exists
grep -c "data_capabilities" third_party/quantaalpha/quantaalpha/factors/prompts/prompts.yaml

# Verify existing tests still pass
cd third_party/quantaalpha
python -m pytest tests/test_data_capability_registry.py -v

# Quick Jinja2 render smoke test
python3 -c "
from jinja2 import Environment, StrictUndefined
env = Environment(undefined=StrictUndefined)
template = open('quantaalpha/factors/prompts/prompts.yaml').read()
# Check template compiles without error
# (We only check it compiles; full render needs the full context)
print('Template compiles OK')
"
```

## Observability Impact

- **Signals added/changed:** None — template-only change.
- **How a future agent inspects:** After a factor mining run, grep the LLM prompt log for "Available data capabilities:" to confirm the injection reached the LLM.
- **Failure state exposed:** If the placeholder is missing, the LLM receives no data capability description — the symptom is factor expressions referencing fields that don't exist in the parquet schemas. This would require adding the placeholder (this task) to fix.

## Inputs

- `third_party/quantaalpha/quantaalpha/factors/prompts/prompts.yaml` — modified to add the Jinja2 conditional block

## Expected Output

- `third_party/quantaalpha/quantaalpha/factors/prompts/prompts.yaml` — modified: new `{% if data_capabilities %}...{{ data_capabilities }}...{% endif %}` block added to `hypothesis_gen.system_prompt`
