# T03: 单元测试

**Slice:** S07
**Milestone:** M004

## Goal
为 EnsembleAggregator 和 ProviderPool 扩展编写单元测试，覆盖 4 种聚合策略、least_latency 路由和多 Key 轮询。

## Must-Haves

### Truths
- 测试覆盖 4 种聚合策略
- 测试覆盖 least_latency 选择逻辑
- 测试覆盖多 Key 轮询
- 15+ 测试用例

### Artifacts
- `third_party/quantaalpha/tests/test_ensemble.py` — 完整测试套件

### Key Links
- 依赖 S07/T01 和 T02 完成

## Steps
1. 创建 `tests/test_ensemble.py`。
2. Mock ProviderPool 和模型响应。
3. 编写聚合策略测试:
   - `test_intersection_empty`: 无交集
   - `test_intersection_partial`: 部分交集
   - `test_intersection_full`: 完全交集
   - `test_union_dedup`: 去重验证
   - `test_voting_threshold`: 投票阈值
   - `test_fusion_score`: 融合评分计算
   - `test_fusion_score_weights`: 权重调整
4. 编写路由策略测试:
   - `test_least_latency_selection`: 最快选择
   - `test_least_latency_tie`: 平局处理
   - `test_multi_key_rotation`: Key 轮询
   - `test_multi_key_exhaustion`: Key 耗尽重置
5. 运行 pytest，确认 15+ 测试通过。

## Context
- 本任务依赖 T01 和 T02 完成
- 使用 mock 避免真实 LLM 调用
