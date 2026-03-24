# M004: 因子库深化与自治能力增强

**Vision:** 补全 `factor_mining_requirements.md` 中 GSD 未覆盖的需求缺口，完成因子库分类/检索/生命周期管理、跨周期验证标准、多模型 Ensemble 聚合、以及 24H 调度中心的设计与实现。

## Success Criteria
- [x] 跨周期验证具备 `pass_criteria` (min_ic, min_rank_ic, min_periods_pass) 自动判定
- [x] 因子库支持 `select_revalidation_candidates(days=21)` 定期复验
- [x] 因子条目具备分类标签 (category / data_dependency / market_environment / time_horizon)
- [x] 数据能力注册表新增 `available_from` + `join_mode` 字段
- [x] 因子完整生命周期状态机 (pending_validation / active / stale / degraded / deprecated) 含转换规则
- [x] RAG 向量检索替代 Jaccard 文本重叠
- [x] ProviderPool 新增 Ensemble 聚合层与 `least_latency` 路由
- [x] 24H 调度中心三合一设计完成 (数据监控 + 温故 + 知新)

## Key Risks / Unknowns
- **向量库选型** — ChromaDB / sqlite-vss / Milvus 性能与集成复杂度待评估
- **Ensemble 聚合** — 裁判模型汇总策略(投票/交集/融合评分)的效果需实验验证
- **24H 调度** — APScheduler vs Celery vs Prefect 选型，单机 vs 分布式
- **因子状态机** — seasonal 判定规则已被 pending_validation/active/stale/degraded/deprecated 五态模型替代。稳定性阈值 (active >= 0.5, degraded < 0.3) 和 stale 阈值 (30天未复验) 已实现。

## Proof Strategy
1. **Phase 1 配置增强** (S01, S04) — 跨周期验证标准、数据注册表扩展（低风险，立即可用）
2. **Phase 2 因子库增强** (S02, S03, S05) — 重验候选、分类标签、生命周期状态机
3. **Phase 3 智能检索** (S06) — RAG 向量检索（引入新依赖）
4. **Phase 4 模型增强** (S07) — Ensemble 聚合层
5. **Phase 5 自治调度** (S08) — 24H 调度中心（依赖所有前置）

## Verification Classes
- **Contract verification**: 单元测试、类型检查
- **Integration verification**: 跨模块集成测试、因子库 → 检索 → LLM 闭环
- **Operational verification**: 长时间运行稳定性
- **UAT / human verification**: 代码审查、因子质量人工抽检

## Milestone Definition of Done
- [ ] 跨周期验证通过标准实现并集成到回测流程
- [ ] 因子复验候选选择与自动调用链路完成
- [ ] 因子分类标签系统上线
- [ ] 数据能力注册表字段扩展
- [x] 因子生命周期状态机实现
- [ ] RAG 向量检索模块可用
- [ ] Ensemble 聚合层实现
- [x] 24H 调度中心设计完成
- [ ] 端到端集成测试通过

## Requirement Coverage
- Covers: factor_mining_requirements.md 中 §A.3.2, §A.3.4, §C.3.1, §C.3.2, §D.3.1, §D.3.2, §D.3.4, §E.3.1, §F.2, §F.3.1
- Partially covers: §四 技术选型
- Leaves for later: 生产环境部署、Grafana 监控面板

## Slices

- [x] **S01: 跨周期验证通过标准** `risk:low` `depends:[]`
  > After this: 回测自动判定因子是否满足 IC/Rank IC 阈值和最少通过周期数。覆盖缺口 H。

- [x] **S02: 因子重验候选选择** `risk:medium` `depends:[]`
  > After this: `select_revalidation_candidates(days=21)` 可选出需要复验的因子。覆盖缺口 F。

- [x] **S03: 因子分类标签系统** `risk:low` `depends:[]`
  > After this: 因子条目具备 category / data_dependency / market_environment / time_horizon 标签。覆盖缺口 C。

- [x] **S04: 数据能力注册表扩展** `risk:low` `depends:[]`
  > After this: 注册表新增 available_from 和 join_mode 字段，LLM 可感知数据起始日期和 join 方式。覆盖缺口 G。

- [x] **S05: 因子生命周期状态机** `risk:medium` `depends:[S02,S03]`
  > After this: 因子具备 pending_validation → active → stale/degraded/deprecated 完整状态转换规则。覆盖缺口 E。
  > 
  > **Note:** 实际实现使用 pending_validation/active/stale/degraded/deprecated 状态模型（替代原计划的 seasonal/archived）。稳定性阈值驱动状态转换。

- [x] **S06: RAG 向量检索** `risk:high` `depends:[S03]`
  > After this: 因子库支持 embedding 存储和向量相似度检索，替代 Jaccard 文本重叠。覆盖缺口 D。

- [x] **S07: Ensemble 聚合层** `risk:high` `depends:[]`
  > After this: ProviderPool 支持裁判模型汇总、交集/并集/投票/融合评分策略，及 least_latency 路由。覆盖缺口 A + B。
  >
  > **Done:** `ensemble.py` EnsembleAggregator (4 策略) + `provider_pool.py` ProviderPool (3 路由策略) + 54 项单元测试全部通过。

- [x] **S08: 24H 调度中心设计** `risk:high` `depends:[S02,S05,S06]`
  > After this: 数据监控 + 温故 + 知新三合一调度架构设计完成，技术选型确定。覆盖缺口 I + J。
  >
  > **Done:** `MiningOrchestrator` 主类 + `scheduler.py` 接口定义 + `implementations.py` 默认实现 + `DESIGN.md` 技术选型文档 + 28 项单元测试全部通过。

## Boundary Map

### S01 (独立)
Produces:
- backtest.yaml → `pass_criteria` 配置段 (min_ic, min_rank_ic, min_periods_pass)
- validation_judge.py → `evaluate_multi_period_results()` 判定函数

Consumes: M003 S03 已配置的 `multi_period_validation.periods`

### S02 (独立)
Produces:
- library.py → `select_revalidation_candidates(days, status)` 方法
- library.py → `last_validated` 时间戳字段

Consumes: M003 S06 的 `versions` 字段和 `apply_validation_result()`

### S03 (独立)
Produces:
- library.py → `_normalize_factor_entry()` 中 `tags` 字段定义
- fewshot.py → 标签匹配增强 relatedness 评分

Consumes: M003 S02 的 fewshot.py relatedness 评分逻辑

### S04 (独立)
Produces:
- data_capability.py → `available_from` + `join_mode` 字段
- `auto_discover_capabilities()` → 从 Parquet 文件推断起始日期

Consumes: M003 S01 的 data_capability.py 注册表

### S05 ← S02, S03
Produces:
- status_rules.py → 完整状态机 (pending_validation/active/stale/degraded/deprecated)
- status_rules.py → 状态转换触发规则

Consumes:
- S02 的 `last_validated` 字段
- S03 的 `tags` 字段（计划使用，实际未直接消费）

### S06 ← S03
Produces:
- vector_store.py → ChromaDB 集成模块
- fewshot.py → 向量检索替代 Jaccard

Consumes:
- S03 的因子分类标签 (用于 embedding metadata)
- M003 S02 的 fewshot.py 接口

### S07 (独立)
Produces:
- ensemble.py → `EnsembleAggregator` 类 (交集/并集/投票/融合评分)
- provider_pool.py → `least_latency` 路由策略 + 多 Key 支持

Consumes: M003 S04 的 ProviderPool 架构

### S08 ← S02, S05, S06
Produces:
- orchestrator.py → 三合一调度架构设计文档
- scheduler.py → 调度接口定义
- 技术选型文档 (向量库/任务调度/进程管理)

Consumes:
- S02 的 `select_revalidation_candidates()`
- S05 的状态机 (调度触发条件)
- S06 的向量检索 (知新流程)
