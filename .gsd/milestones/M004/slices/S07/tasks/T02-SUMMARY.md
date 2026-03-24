---
id: T02
parent: S07
milestone: M004
status: completed
verification_result: passed
completed_at: 2026-03-24T02:15:30+08:00
blocker_discovered: false

# T02: ProviderPool 扩展 (least_latency + 多 Key)

## Outcome

实现了 `ProviderPool` 类，支持多 Provider 管理、多 API Key 轮询、3 种路由策略（round_robin / random / least_latency），以及细粒度延迟跟踪。

## Verification Evidence

| Gate | Command | Exit Code | Verdict |
|------|---------|-----------|---------|
| Syntax | `python -m py_compile quantaalpha/llm/provider_pool.py` | 0 | PASS |
| Import | `from quantaalpha.llm.provider_pool import ProviderPool` | 0 | PASS |
| round_robin | 9-key cycle test | 0 | PASS |
| least_latency | fastest key selection | 0 | PASS |
| Multi-key | 6-key round-robin | 0 | PASS |
| Thread safety | 4-thread concurrent test | 0 | PASS |

## Authoritative Diagnostics

```bash
# Check module loads
/root/miniforge3/envs/mining/bin/python -c "from quantaalpha.llm.provider_pool import ProviderPool"

# View pool statistics
pool = ProviderPool(routing="least_latency")
pool.add_provider("openai", api_keys=["key1"])
pool.get_stats_summary()

# Run unit tests
cd third_party/quantaalpha && /root/miniforge3/envs/mining/bin/python -m pytest quantaalpha/tests/test_ensemble.py -v
```

## Key Decisions

- **RDAgentLog debug method absent**: 记录此发现（RDAgentLog 只有 info/warning/error），移除 `logger.debug()` 调用
- **LatencyStats in-place reset**: `reset_latency_stats()` 重置 LatencyStats 对象属性而非删除 key，保持 `get_latency_stats()` 返回一致的字典结构
- **least_latency fallback**: 样本不足时优雅降级到 round_robin，不会因缺数据而崩溃
- **threading.RLock**: 使用可重入锁，支持嵌套锁定

## Patterns Established

1. **Strategy pattern for routing**: `SELECT_FUNCTIONS` dict 映射策略名到实现函数，便于扩展
2. **LatencyStats running stats**: `record(latency_ms)` 增量更新，支持 min/max/avg 查询
3. **ProviderConfig dataclass**: 统一 provider 配置结构，支持 metadata 扩展

## Observability Surfaces

- `ProviderPool.get_providers()` — 当前所有 provider 名称
- `ProviderPool.get_stats_summary()` — 包含 num_providers、每 provider/key 的 avg/min/max latency
- `ProviderPool.get_latency_stats(provider_name)` — 原始 LatencyStats 对象
- `LatencyStats.avg_latency_ms / min_latency_ms / max_latency_ms / sample_count`

## Key Files

- `third_party/quantaalpha/quantaalpha/llm/provider_pool.py` — 完整实现
- `third_party/quantaalpha/configs/experiment.yaml` — ensemble 和 provider_pool 配置段

## Downstream Consumers

- Factor mining workflow → 多模型并发生成 → ProviderPool 管理 API Key 轮询
- S08 调度中心 → 可利用 `get_stats_summary()` 监控 provider 健康状态
