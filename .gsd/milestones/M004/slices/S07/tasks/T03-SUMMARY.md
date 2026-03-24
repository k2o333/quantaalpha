---
id: T03
parent: S07
milestone: M004
status: completed
verification_result: passed
completed_at: 2026-03-24T02:15:45+08:00
blocker_discovered: false

# T03: 单元测试

## Outcome

创建了 `quantaalpha/tests/test_ensemble.py`，包含 54 项单元测试，覆盖 EnsembleAggregator 全部 4 种策略、ProviderPool 全部路由模式和并发安全性。

## Verification Evidence

| Gate | Command | Exit Code | Verdict |
|------|---------|-----------|---------|
| pytest collection | `--collect-only` | 0 | PASS — 54 tests collected |
| All tests | `pytest quantaalpha/tests/test_ensemble.py -v` | 0 | PASS — 54/54 passed |

## Test Coverage Breakdown

| Test Class | Test Count | Coverage |
|------------|------------|----------|
| `TestEnsembleAggregatorConstruction` | 5 | 策略验证、默认值 |
| `TestUnionDedupStrategy` | 5 | 交集/去重逻辑 |
| `TestIntersectionStrategy` | 5 | 交集逻辑 |
| `TestVotingStrategy` | 5 | 投票阈值/顺序 |
| `TestFusionScoreStrategy` | 3 | 权重评分 |
| `TestEnsembleAggregatorInterface` | 8 | accumulate/dict输入/reset |
| `TestProviderPoolConstruction` | 4 | 构造验证 |
| `TestProviderPoolBasicOperations` | 5 | add/remove/get |
| `TestRoundRobinRouting` | 2 | RR 轮询 |
| `TestRandomRouting` | 1 | 随机选择 |
| `TestLeastLatencyRouting` | 3 | 最快选择 |
| `TestLatencyTracking` | 5 | 统计记录/重置 |
| `TestProviderPoolThreadSafety` | 2 | 并发安全 |
| `TestProviderConfigMetadata` | 2 | 元数据存储 |

## Key Files

- `third_party/quantaalpha/quantaalpha/tests/test_ensemble.py` — 54 项测试

## Patterns Discovered via Testing

1. **`reset_latency_stats` behavior**: 重置后 key 保留在 dict 中，LatencyStats 对象属性归零。测试断言 `.sample_count == 0` 而非 key 不存在。
2. **`get_latency_stats` 对不存在的 provider 返回 None**: 测试用 `assert stats is None` 验证此行为。
3. **voting 策略保序**: 元素顺序来自第一个包含该元素的模型，而非按投票数排序。

## Drill-Down Paths

- `third_party/quantaalpha/quantaalpha/tests/test_ensemble.py` — 完整测试代码
- 单独运行: `cd third_party/quantaalpha && /root/miniforge3/envs/mining/bin/python -m pytest quantaalpha/tests/test_ensemble.py::TestLeastLatencyRouting -v`
