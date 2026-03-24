---
id: T01
parent: S07
milestone: M004
status: completed
verification_result: passed
completed_at: 2026-03-24T02:15:00+08:00
blocker_discovered: false

# T01: EnsembleAggregator 类实现

## Outcome

实现了 `EnsembleAggregator` 类，支持 4 种聚合策略：`intersection`、`union_dedup`、`voting`、`fusion_score`。定义了 `ModelResponse` 和 `AggregatedResult` 数据结构，支持 dict 输入自动转换为 ModelResponse。

## Verification Evidence

| Gate | Command | Exit Code | Verdict |
|------|---------|-----------|---------|
| Syntax | `python -m py_compile quantaalpha/llm/ensemble.py` | 0 | PASS |
| Import | `from quantaalpha.llm.ensemble import EnsembleAggregator` | 0 | PASS |
| Strategy instantiations | 4 strategies created | 0 | PASS |
| Functional test | 4-strategy logic test | 0 | PASS |

## Authoritative Diagnostics

```bash
# Check module loads
/root/miniforge3/envs/mining/bin/python -c "from quantaalpha.llm.ensemble import EnsembleAggregator"

# Run unit tests
cd third_party/quantaalpha && /root/miniforge3/envs/mining/bin/python -m pytest quantaalpha/tests/test_ensemble.py -v
```

## Key Decisions

- **Dataclass-based structures**: ModelResponse 和 AggregatedResult 使用 @dataclass，提供类型安全和清晰接口
- **Strategy function pattern**: 每个策略独立函数（`_intersection_strategy` 等），便于单元测试
- **Dict input auto-conversion**: aggregate() 接受 dict 列表，内部转换为 ModelResponse，降低调用方复杂度
- **RDAgentLog compatibility**: 未使用 logger（避免 debug 方法缺失问题），策略函数无副作用日志

## Patterns Established

1. **Strategy function contract**: 输入 `list[ModelResponse]`，输出 `list[Any]`，无副作用
2. **Result dataclass**: 统一返回 AggregatedResult，包含 output、strategy、source_counts、fusion_scores 等字段
3. **String normalization for dedup**: 使用 `str(item)` 作为 dedup key，兼容 dict/list/str 类型

## Observability Surfaces

- `EnsembleAggregator.strategy` — 当前策略名称
- `EnsembleAggregator.get_accumulated_count()` — 已积累响应数
- `AggregatedResult.num_models` — 来源模型数
- `AggregatedResult.source_counts` — voting 策略下各元素得票数
- `AggregatedResult.fusion_scores` — fusion_score 策略下各元素评分

## Downstream Consumers

- Factor mining workflow → 多个 LLM 模型并发生成因子 → EnsembleAggregator 汇总
- S08 调度中心 → "知新"流程中可能需要多模型共识

## Drill-Down Paths

- `third_party/quantaalpha/quantaalpha/llm/ensemble.py` — 完整实现
- `third_party/quantaalpha/quantaalpha/tests/test_ensemble.py` — 54 项测试
