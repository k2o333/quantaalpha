# S07: Ensemble 聚合层

**Goal:** 扩展 ProviderPool，新增裁判模型汇总策略（交集/并集/投票/融合评分）和 `least_latency` 路由策略，支持同 Provider 多 Key 轮询。
**Demo:** 多个模型并发生成因子后，裁判模型汇总输出最终因子列表。

## Must-Haves
- `ensemble.py` 新模块实现 `EnsembleAggregator` 类，支持 4 种聚合策略:
  - `intersection`: 取所有模型输出的交集（保守）
  - `union_dedup`: 取并集后去重
  - `voting`: 多模型投票（≥N 票通过）
  - `fusion_score`: 融合评分（加权平均）
- `provider_pool.py` 新增 `least_latency` 路由策略
- `provider_pool.py` 支持同一 Provider 配置多个 API Key
- `experiment.yaml` 新增 `ensemble` 和 `least_latency` 配置段
- 单元测试覆盖: 4 种聚合策略、least_latency 选择、多 Key 轮询

## Proof Level
- This slice proves: **contract**
- Real runtime required: no (mock Provider 响应)
- Human/UAT required: no

## Verification
- `python -m py_compile quantaalpha/llm/ensemble.py`
- `python -m py_compile quantaalpha/llm/provider_pool.py`
- `pytest quantaalpha/tests/test_ensemble.py -v`
- `grep "least_latency\|EnsembleAggregator" quantaalpha/llm/ensemble.py` returns >= 1

## Tasks

- [x] **T01: EnsembleAggregator 类实现** `est:35m`
  - Why: 聚合策略是本 Slice 核心
  - Files: `quantaalpha/llm/ensemble.py`
  - Do: 创建 EnsembleAggregator，实现 4 种策略的 aggregate() 方法；定义统一输入/输出格式
  - Verify: py_compile 通过
  - Done when: 4 种策略均可调用

- [x] **T02: ProviderPool 扩展 (least_latency + 多 Key)** `est:30m`
  - Why: 路由策略和多 Key 是平台轮询核心能力
  - Files: `quantaalpha/llm/provider_pool.py`, `quantaalpha/factors/prompts/experiment.yaml`
  - Do: 新增 least_latency 策略（追踪响应延迟，选择最快 Provider）；支持 providers[].api_keys 列表；扩展配置格式
  - Verify: py_compile 通过
  - Done when: least_latency 选择和多 Key 轮询可用

- [x] **T03: 单元测试** `est:25m`
  - Why: 验证聚合和路由逻辑
  - Files: `quantaalpha/tests/test_ensemble.py`
  - Do: Mock 多模型输出测试 4 种聚合策略；Mock 延迟数据测试 least_latency；测试多 Key 轮询
  - Verify: pytest 通过
  - Done when: 15+ 测试通过

## Files Likely Touched
- `quantaalpha/llm/ensemble.py` (new)
- `quantaalpha/llm/provider_pool.py` (modify)
- `quantaalpha/factors/prompts/experiment.yaml` (modify)
- `quantaalpha/tests/test_ensemble.py` (new)

---
estimated_steps: 12
estimated_files: 4
