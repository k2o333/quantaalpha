# T02: ProviderPool 扩展 (least_latency + 多 Key)

**Slice:** S07
**Milestone:** M004

## Goal
扩展 ProviderPool，新增 `least_latency` 路由策略和支持同一 Provider 配置多个 API Key。

## Must-Haves

### Truths
- `least_latency` 策略追踪响应延迟，选择历史最快 Provider
- 支持 `providers[].api_keys: [key1, key2]` 列表配置
- 多 Key 时自动轮询
- experiment.yaml 包含新配置段

### Artifacts
- `third_party/quantaalpha/quantaalpha/llm/provider_pool.py` — 路由扩展
- `third_party/quantaalpha/quantaalpha/factors/prompts/experiment.yaml` — 配置扩展

### Key Links
- 依赖 S07/T01 的 EnsembleAggregator
- M003 S04 的 ProviderPool 是上游

## Steps
1. 阅读 `provider_pool.py`，找到路由策略实现位置。
2. 添加延迟追踪数据结构:
   ```python
   self._latency_tracker: Dict[str, List[float]] = defaultdict(list)
   ```
3. 实现 `least_latency` 策略:
   - 在每次调用后记录响应时间
   - 选择平均延迟最低的 Provider
4. 实现多 Key 支持:
   - 配置支持 `api_keys: [key1, key2]`
   - 轮询使用不同的 key
5. 在 `experiment.yaml` 添加配置示例。
6. 用 `py_compile` 验证语法。

## Context
- 本任务依赖 T01 的 EnsembleAggregator
- 延迟追踪需要在实际运行中积累数据
