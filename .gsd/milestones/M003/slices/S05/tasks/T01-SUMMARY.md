# T01: 实现核心逻辑

**Slice:** S05 | **Milestone:** M003 | **Status:** Complete

## Goal
在 `robust_json_parse()` 中实现 Strategy 5（Coding 模型 JSON 修复闭环），遵守 D019 约束。

## Implementation

### File modified
`third_party/quantaalpha/quantaalpha/llm/client.py`

### Changes

**1. 常量添加 (行 154-161)**
```python
JSON_REPAIR_SYSTEM_PROMPT = """You are a JSON repair assistant..."""
MAX_JSON_REPAIR_ATTEMPTS = 3          # D019: 最多 3 次重试
JSON_REPAIR_TIMEOUT_SECONDS = 30.0    # D019: 30 秒超时
```

**2. ProviderPool 延迟导入守卫 (行 163-178)**
```python
_provider_pool_available = False
try:
    from quantaalpha.llm.provider_pool import (
        EmptyResponseError, AllProvidersFailedError, get_provider_pool
    )
    _provider_pool_available = True
except ImportError:
    get_provider_pool = None
    EmptyResponseError = Exception
    AllProvidersFailedError = Exception
```

**3. `_remove_markdown_json()` 辅助函数 (行 185-191)**
剥离 ` ```json ... ``` ` 和 ` ``` ... ``` ` 包装。

**4. Strategy 5 实现 (行 263-306)**
在 Strategy 4 之后、`raise json.JSONDecodeError` 之前插入：
```python
if _provider_pool_available:
    pp = get_provider_pool()
    if pp is not None:
        for _attempt in range(MAX_JSON_REPAIR_ATTEMPTS):
            messages = [...]
            try:
                repaired = pp.call_with_fallback(
                    messages, task_type="json_repair",
                    timeout=JSON_REPAIR_TIMEOUT_SECONDS,
                )
            except EmptyResponseError:
                continue  # D019: 立即切换，不增加 failure_count
            except AllProvidersFailedError:
                break     # 所有 provider 耗尽
            # 尝试解析修复后的 JSON（3 个变体）
```

### D019 约束满足
| 约束 | 实现 |
|---|---|
| 30 秒超时 | `timeout=30.0` 参数传递 |
| 最多 3 次重试 | `for _attempt in range(MAX_JSON_REPAIR_ATTEMPTS)` |
| 空响应立即切换 | `except EmptyResponseError: continue` |
| failure_count 不增加 | ProviderPool 内部处理（`EmptyResponseError` 不触发 `_report_failure_inner`）|

### Verification
```
python -m py_compile third_party/quantaalpha/quantaalpha/llm/client.py
→ Syntax OK
```

## Integration Point
- `experiment.yaml` 已有 `routing.json_repair: ["qwen-coder"]` 和 `strategy.json_repair: "single"`（S04 已配置）
- Strategy 5 通过 `provider_pool.call_with_fallback(messages, task_type="json_repair")` 路由到 `qwen-coder`
