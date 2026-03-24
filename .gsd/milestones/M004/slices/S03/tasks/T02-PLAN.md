# T02: fewshot.py relatedness 评分增强 + 测试

**Slice:** S03
**Milestone:** M004

## Goal
在 fewshot.py 的 relatedness 评分公式中加入标签匹配维度，使因子检索能考虑标签相似性。

## Must-Haves

### Truths
- relatedness 评分公式扩展为: 40% Jaccard + 30% 共享字段 + 30% 标签匹配
- 标签匹配权重可配置
- 新建因子时可附带标签

### Artifacts
- `third_party/quantaalpha/quantaalpha/factors/fewshot.py` — 评分逻辑修改
- `third_party/quantaalpha/tests/test_factor_tags.py` — 标签评分测试

### Key Links
- 依赖 S03/T01 完成的 tags 字段定义

## Steps
1. 阅读 `fewshot.py`，找到 `calculate_relatedness()` 或类似评分函数。
2. 提取现有评分逻辑（保持 40% Jaccard + 30% 共享字段）。
3. 新增 `calculate_tag_similarity(tags1, tags2)` 函数，计算标签重叠度。
4. 修改评分公式: `0.4 * jaccard + 0.3 * shared_fields + 0.3 * tag_similarity`。
5. 创建 `test_factor_tags.py`，测试:
   - 标签初始化默认值
   - 标签相似度计算
   - 不同标签组合的 relatedness 差异
   - 无标签因子处理
6. 运行 pytest，确认 8+ 测试通过。

## Context
- 上游: S03/T01 的 tags 字段定义
- 下游: S06 向量检索会进一步增强检索能力
- 标签权重 40/30/30 可根据实验结果调整
