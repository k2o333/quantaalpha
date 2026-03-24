# T01: EnsembleAggregator 类实现

**Slice:** S07
**Milestone:** M004

## Goal
创建 `EnsembleAggregator` 类，实现 4 种聚合策略：intersection / union_dedup / voting / fusion_score。

## Must-Haves

### Truths
- `EnsembleAggregator` 类支持 4 种策略的 `aggregate()` 方法
- 统一输入/输出格式
- 各策略行为明确:
  - intersection: 取所有模型输出的交集（保守）
  - union_dedup: 取并集后去重
  - voting: ≥N 票通过
  - fusion_score: 加权平均评分

### Artifacts
- `third_party/quantaalpha/quantaalpha/llm/ensemble.py` — 聚合器实现

### Key Links
- S07/T03 测试依赖本任务完成
- M003 S04 的 ProviderPool 是上游

## Steps
1. 创建 `llm/ensemble.py`。
2. 定义输入数据结构:
   ```python
   class ModelOutput:
       model_name: str
       factors: List[dict]
       scores: Dict[str, float]
   ```
3. 实现 `EnsembleAggregator`:
   - `aggregate_intersection(outputs)`: 计算所有模型输出的交集
   - `aggregate_union_dedup(outputs)`: 计算并集并去重
   - `aggregate_voting(outputs, threshold)`: 投票统计
   - `aggregate_fusion_score(outputs, weights)`: 融合评分
4. 定义统一输出格式。
5. 用 `py_compile` 验证语法。

## Context
- 上游来源: `docs/drafts/mining/factor_mining_requirements.md §A.3.2`
- M003 S04 ProviderPool 提供多模型并行输出
- 4 种策略的效果需要实验验证
