---
id: T02
parent: S04
milestone: M004
status: completed
verification_result: passed
completed_at: 2026-03-24
blocker_discovered: false
observability_surfaces:
  - pytest quantaalpha/tests/test_data_capability_extensions.py
  - Individual test class counts visible in pytest output
---

# T02: 单元测试

**Status:** Completed

## Outcome

`test_data_capability_extensions.py` 创建，26 项测试全部通过。

## Test Coverage

| 测试类 | 测试数 | 覆盖内容 |
|--------|--------|----------|
| `TestAvailableFromField` | 3 | available_from 归一化（有效值、缺失、None） |
| `TestJoinModeInference` | 6 | freq → join_mode 推断 + explicit override |
| `TestDataCapabilitiesRegistry` | 4 | 现有 registry 条目 available_from 和 join_mode |
| `TestRenderDataCapabilities` | 5 | 渲染输出包含新字段 |
| `TestAutoDiscoverCapabilities` | 4 | auto_discover 防御性和 JSON 可序列化 |
| `TestInferAvailableFrom` | 2 | Parquet 推断防御性（不存在/损坏） |

## Key Design Decisions

1. **防御性测试优先** — `infer_available_from_from_parquet()` 测试不存在路径和损坏文件，确保不抛异常
2. **freq → join_mode 推断覆盖常见 freq** — daily/weekly → same_day，quarterly/monthly/annual → forward_fill
3. **显式值优先于推断** — `join_mode` 显式设置时不会被 freq 推断覆盖

## Verification Evidence

| Gate | Command | Exit | Result |
|------|---------|------|--------|
| Test run | `pytest quantaalpha/tests/test_data_capability_extensions.py -v` | 0 | 26 passed in 0.19s |
| Collect | `pytest quantaalpha/tests/test_data_capability_extensions.py --collect-only` | 0 | 26 tests collected |

## Diagnostics

```bash
# Run with verbose output
pytest quantaalpha/tests/test_data_capability_extensions.py -v

# Run specific test class
pytest quantaalpha/tests/test_data_capability_extensions.py::TestJoinModeInference -v

# Run with coverage (if pytest-cov installed)
pytest quantaalpha/tests/test_data_capability_extensions.py --cov=quantaalpha.factors.data_capability
```
