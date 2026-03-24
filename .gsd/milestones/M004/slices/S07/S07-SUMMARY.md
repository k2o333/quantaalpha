---
id: S07
parent: M004
milestone: M004
status: completed
verification_result: passed
completed_at: 2026-03-24T02:16:00+08:00

# S07: Ensemble 聚合层

## Summary

为因子挖掘工作流实现了多模型 Ensemble 聚合层和增强的 ProviderPool 路由系统。覆盖 R013（多模型 Ensemble 与平台增强路由）的全部 3 项子能力：聚合策略、`least_latency` 路由、同 Provider 多 Key。

## What This Slice Delivers

### 1. EnsembleAggregator（`ensemble.py`）
4 种聚合策略，可独立或组合使用：

| 策略 | 行为 | 适用场景 |
|------|------|----------|
| `intersection` | 只保留所有模型都输出的元素 | 保守，规避假阳性 |
| `union_dedup` | 合并所有输出，去重 | 最大化覆盖率 |
| `voting` | 票数 ≥ threshold 的元素 | 民主，可调阈值 |
| `fusion_score` | 按模型质量权重评分排序 | 区分模型质量差异 |

关键设计：
- `ModelResponse` dataclass 封装模型输出 + 元数据（latency_ms, quality_score）
- `AggregatedResult` dataclass 统一返回格式，含 source_counts 和 fusion_scores
- 支持 `accumulate()` 流式积累 + `reset()` 清空
- 支持 dict 输入自动转换为 ModelResponse

### 2. ProviderPool（`provider_pool.py`）
多 Provider 管理与智能路由：

| 策略 | 行为 |
|------|------|
| `round_robin` | 依次轮询每个 Key |
| `random` | 随机选择 |
| `least_latency` | 选择历史平均延迟最低的 Key（样本不足时降级到 RR） |

关键设计：
- 线程安全（`threading.RLock`）
- 运行时 `record_latency()` 跟踪每个 Key 的延迟分布
- `get_stats_summary()` 输出每个 Provider/Key 的 avg/min/max latency
- `ProviderConfig` dataclass 支持 metadata 扩展

### 3. 配置集成（`experiment.yaml`）
新增两个顶级配置段：
- `provider_pool` — 路由策略、最小样本阈值、Provider 定义
- `ensemble` — 默认策略、voting threshold、fusion_score 权重

## Authoritative Diagnostics

```bash
# 语法检查
python -m py_compile third_party/quantaalpha/quantaalpha/llm/ensemble.py
python -m py_compile third_party/quantaalpha/quantaalpha/llm/provider_pool.py

# 单元测试
cd third_party/quantaalpha
/root/miniforge3/envs/mining/bin/python -m pytest quantaalpha/tests/test_ensemble.py -v
# Expected: 54 passed

# 功能验证
/root/miniforge3/envs/mining/bin/python -c "
from quantaalpha.llm.ensemble import EnsembleAggregator, ModelResponse
from quantaalpha.llm.provider_pool import ProviderPool

# 4 种策略验证
agg = EnsembleAggregator(strategy='union_dedup')
result = agg.aggregate([
    ModelResponse('gpt4', ['f1', 'f2']),
    ModelResponse('claude', ['f2', 'f3']),
])
assert result.output == ['f1', 'f2', 'f3']

# least_latency 验证
pool = ProviderPool(routing='least_latency')
pool.add_provider('fast', api_keys=['k1'])
pool.add_provider('slow', api_keys=['k2'])
pool.record_latency('slow', 'k2', 500.0)
pool.record_latency('fast', 'k1', 30.0)
key, _ = pool.get_key_and_provider()
assert key == 'k1'
print('OK')
"
```

## Files Created/Modified

| File | Action | Description |
|------|--------|-------------|
| `quantaalpha/llm/ensemble.py` | **new** | EnsembleAggregator 类，4 种策略实现 |
| `quantaalpha/llm/provider_pool.py` | **new** | ProviderPool 类，3 种路由策略 |
| `quantaalpha/tests/test_ensemble.py` | **new** | 54 项单元测试 |
| `configs/experiment.yaml` | modified | 新增 provider_pool 和 ensemble 配置段 |

## Key Decisions

1. **无日志策略函数**: ensemble.py 的策略函数（`_intersection_strategy` 等）不依赖 logger，避免 RDAgentLog.debug() 不存在的兼容性问题。ProviderPool 初始化和 Provider 添加保留 info 日志。
2. **LatencyStats 对象保留而非删除**: `reset_latency_stats()` 重置对象属性而非删除 key，保持 `get_latency_stats()` 返回一致的 dict 结构。
3. **least_latency 降级策略**: 样本数 < min_latency_samples 时降级到 round_robin，不会因缺数据崩溃。
4. **Dataclass 而非 dict**: ModelResponse、AggreagatedResult、ProviderConfig 使用 @dataclass，提供类型安全和清晰接口。

## Patterns Established

1. **Strategy Function Contract**: `def _strategy(responses, **kwargs) -> list[Any]`，无副作用，便于单元测试。
2. **Running Statistics Pattern**: LatencyStats.record() 增量更新 min/max/avg，支持 O(1) 插入和 O(1) 查询。
3. **Thread-Safe Pool Pattern**: `threading.RLock` + defaultdict + in-place reset，避免竞争条件。
4. **Config-Driven Architecture**: experiment.yaml 中的 provider_pool 和 ensemble 配置段定义运行时行为。

## Gotchas

1. **RDAgentLog 只有 info/warning/error**: 不能使用 `logger.debug()`，否则抛出 AttributeError。已用注释替代。
2. **get_latency_stats 对不存在 Provider 返回 None**: 不是空 dict，是 None。测试用 `assert stats is None` 验证。
3. **voting 策略保序语义**: 元素顺序来自第一个包含该元素的模型，而非按投票数排序。已通过测试固化。
4. **`mining` conda 环境**: 测试必须用 `/root/miniforge3/envs/mining/bin/python` 运行才有 rdagent 模块。

## Downstream Consumers

- **S08 调度中心**: `ProviderPool.get_stats_summary()` 可用于监控各 Provider 健康状态，`EnsembleAggregator` 可用于多模型共识决策

## Observability Surfaces

- `EnsembleAggregator.strategy` — 当前策略名
- `AggregatedResult.source_counts` — voting 下各元素得票数
- `AggregatedResult.fusion_scores` — fusion_score 下各元素评分
- `ProviderPool.get_stats_summary()` — 完整统计摘要（avg/min/max latency per key）
- `LatencyStats.avg_latency_ms / min_latency_ms / max_latency_ms / sample_count`

## Verification Results

- ✅ `python -m py_compile ensemble.py` — 0 errors
- ✅ `python -m py_compile provider_pool.py` — 0 errors
- ✅ `grep "least_latency\|EnsembleAggregator" …` — ensemble.py: 3, provider_pool.py: 14
- ✅ `pytest quantaalpha/tests/test_ensemble.py -v` — **54 passed**
- ✅ Config sections present in `experiment.yaml`
