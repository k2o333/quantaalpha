# T02: 在 proposal.py 的 prepare_context() 中注入 data_capabilities

**Slice:** S01 — 数据能力注入最后一公里 (S1)
**Milestone:** M003

## Description

修改 `AlphaAgentHypothesisGen.prepare_context()` 方法，在构建 `context_dict` 时调用 `render_data_capabilities()` 并将结果注入到 `context_dict["data_capabilities"]`，使 Jinja2 模板有机会将其渲染进 LLM 系统提示词。这是注入路径的关键断点修复。

## Steps

1. **Read the current `proposal.py`** around the `prepare_context()` method (lines ~240-270). Confirm the exact location of `context_dict = {...}` and the `return context_dict, True` line.
2. **Add import at the top of the relevant section** (near the existing `from quantaalpha.factors.data_capability import render_data_capabilities, get_data_capabilities` if present, or add it): `from quantaalpha.factors.data_capability import render_data_capabilities, get_data_capabilities, auto_discover_capabilities`. Wrap `auto_discover_capabilities` import in a try/except so the module still loads.
3. **Modify `prepare_context()`** to build `data_capabilities_text` before building `context_dict`:
   ```python
   try:
       capabilities = auto_discover_capabilities() if "auto_discover_capabilities" in dir() else None
       data_capabilities_text = render_data_capabilities(get_data_capabilities(capabilities))
   except Exception:
       data_capabilities_text = render_data_capabilities(None)  # fallback to hardcoded
   ```
   Place this just before the `context_dict = {...}` line.
4. **Add `"data_capabilities": data_capabilities_text` to `context_dict`**.
5. **Do NOT modify `prompts.yaml`** — that is T03's job.

## Must-Haves

- [ ] `proposal.py` imports `render_data_capabilities` and `get_data_capabilities` from `data_capability`.
- [ ] `prepare_context()` calls `render_data_capabilities()` and stores the result in `context_dict["data_capabilities"]`.
- [ ] If polars/discovery is unavailable, the fallback `render_data_capabilities(None)` uses the hardcoded `DATA_CAPABILITIES` dict — no crash.
- [ ] The module compiles without syntax error after the change.

## Verification

```bash
# Syntax check
python -m py_compile third_party/quantaalpha/quantaalpha/factors/proposal.py

# Verify the injection call exists
grep -c "data_capabilities" third_party/quantaalpha/quantaalpha/factors/proposal.py

# Verify render_data_capabilities import
grep "from quantaalpha.factors.data_capability import" third_party/quantaalpha/quantaalpha/factors/proposal.py | grep "render_data_capabilities"
```

## Observability Impact

- **Signals added/changed:** None — the injection adds a key to `context_dict`, which is passed to the Jinja2 renderer. No new logs or status surfaces.
- **How a future agent inspects:** Add a debug print of `context_dict.keys()` after `prepare_context()` returns — the `data_capabilities` key will be present.
- **Failure state exposed:** If the import or call fails, the fallback ensures `data_capabilities` key is still present (with the hardcoded content), so the LLM at least receives the original 2-source capability list.

## Inputs

- `third_party/quantaalpha/quantaalpha/factors/proposal.py` — modified to add the injection call
- `third_party/quantaalpha/quantaalpha/factors/data_capability.py` — the updated file from T01 (must exist and contain `render_data_capabilities`, `get_data_capabilities`, `auto_discover_capabilities`)

## Expected Output

- `third_party/quantaalpha/quantaalpha/factors/proposal.py` — modified: new import line for `render_data_capabilities`/`get_data_capabilities`, new `data_capabilities_text` variable in `prepare_context()`, `data_capabilities` added to `context_dict`
