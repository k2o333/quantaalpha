# T02: 单元测试

**Slice:** S05 | **Milestone:** M003 | **Status:** Complete

## Goal
编写并运行 Strategy 5 的单元测试，覆盖所有行为和 D019 约束。

## Implementation

### Test file
`third_party/quantaalpha/tests/test_json_repair.py` — 17 tests across 6 test classes

### Test coverage

| Test class | Tests | Coverage |
|---|---|---|
| `TestStrategy5D019Constraints` | 2 | `MAX_JSON_REPAIR_ATTEMPTS == 3`, `JSON_REPAIR_TIMEOUT_SECONDS == 30.0` |
| `TestStrategy5NotCalledOnSuccess` | 2 | Strategy 1/2 成功后不触发 Strategy 5 |
| `TestStrategy5CalledOnFailure` | 1 | 无效 JSON 触发 Strategy 5 |
| `TestStrategy5MarkdownStripping` | 3 | markdown 代码块剥离、`_remove_markdown_json` 正确工作 |
| `TestStrategy5Retries` | 2 | 最多 3 次重试、所有尝试失败后抛出原始错误 |
| `TestStrategy5EmptyResponse` | 2 | D019: `EmptyResponseError` 触发重试且不增加 `failure_count` |
| `TestStrategy5GracefulDegradation` | 2 | ProviderPool 不可用时优雅降级 |
| `TestStrategy5AllProvidersFailed` | 1 | `AllProvidersFailedError` 正确降级 |
| `TestStrategy5TimeoutParam` | 2 | `timeout=30.0` 和 `task_type="json_repair"` 正确传递 |

### conftest.py 改进
`third_party/quantaalpha/tests/conftest.py` 增加了：
1. `sys.modules` 预填充 mock `rdagent`/`rdagent.log` 使 `client.py` 可导入
2. `_AlphaAgentLoggerWrapper.__delattr__` monkey-patch 使 `mock.patch.object` 清理正确工作

### Verification
```
pytest tests/test_provider_pool.py tests/test_json_repair.py -v
→ 43 passed (26 provider_pool + 17 json_repair)
```

## Key Design Decisions

1. **`skipif` 装饰器**: 如果 `_IMPORT_OK = False`（rdagent 不可用），所有测试跳过
2. **Mock 策略**: `patch("quantaalpha.llm.client.get_provider_pool")` + `patch("...client._provider_pool_available", True)` 组合
3. **`_provider_pool_available` 模块级标志**: 在导入时设置为 `True`（当 ProviderPool 符号可导入时）或 `False`
