# M003: QuantaAlpha 持续因子挖掘体系架构实施路线图

**Vision:** 将 D014-D019 批准的架构决策转化为可执行的代码实现，建立 24H 自治运行的技术基础

## Success Criteria
- [⚠️] **ProviderPool 实现多 Provider 并存、健康监控、自动降级** — S04 实现完成但代码未提交到子模块
- [⚠️] **Checkpoint 机制支持进程崩溃后断点续挖** — S06 实现完成但代码未提交到子模块
- [⚠️] **ResourceManager 实现 Token/磁盘/内存资源边界约束** — S08 实现完成但代码未提交到子模块
- [⚠️] **M001 教训作为设计约束写入代码和验收标准** — S09 文档完成但代码依赖未提交
- [⚠️] **ADR-001/ADR-003 架构方向转化为可运行组件** — S10 设计完成，组件未提交

## Key Risks / Unknowns
- **ProviderPool 兼容性** — 需要兼容现有代码的 APIBackend 调用模式
- **状态同步复杂性** — Checkpoint 需要处理因子库、trace、回测状态的一致性
- **资源监控精度** — Token 消耗实时追踪和磁盘空间监控需要精确实现
- **长时间稳定性** — 24H 运行场景的测试需要长时间验证

## Proof Strategy
1. **Phase 1 基础设施** (S01-S03) — 数据能力注入、Few-shot、配置优化 ✅
2. **Phase 2 核心架构** (S04, S05, ~~S06~~ ✅, ~~S07~~ ✅, S08) — ProviderPool、JSON 修复闭环、Checkpoint ✅、PIT 对齐 ✅、资源管理
3. **Phase 3 自治能力** (S09, S10) — M001 设计约束转化、ADR-003 外插模块设计
4. **集成验证** — 72 小时无人值守跑批验证

## Verification Classes
- **Contract verification**: Python 语法检查、单元测试、类型检查
- **Integration verification**: 多 Provider 切换、Checkpoint 恢复、资源拦截
- **Operational verification**: 长时间运行稳定性、资源使用监控
- **UAT / human verification**: 代码审查、设计约束合规性检查

## Milestone Definition of Done
- [ ] D016 ProviderPool 架构实现并通过测试 ⚠️ (实现完成，待 R01 提交代码到子模块)
- [x] D017 Checkpoint 机制实现断点续挖 ✅ (2026-03-23)
- [x] D013 PIT 对齐执行层，消除未来函数 ✅ (2026-03-23)
- [x] D018 ResourceManager 实现资源边界约束 ✅ (2026-03-23)
- [x] D019 M001 教训转化为代码约束和测试用例 ✅ (2026-03-23)
- [x] ADR-001 Phase 1/2 组件可运行 ✅ (2026-03-23)
- [x] ADR-003 Phase 3 架构设计完成 ✅ (2026-03-23)
- [ ] 72 小时无人值守测试通过
- [ ] 架构文档更新并同步到 DECISIONS.md

## Requirement Coverage
- Covers: 多模型路由、异常恢复、资源管理、设计约束转化
- Partially covers: 24H 自治调度（Phase 3 完成）
- Leaves for later: 因子知识库智能推荐、全自动因子复验
- Orphan risks: 上游 LiteLLM 代理对大 prompt 返回空响应的问题

## Slices

- [x] **S01: 数据能力注入最后一公里 (S1)** `risk:medium` `depends:[]`
  > After this: LLM prompt 自动注入 Parquet 数据 Schema 和时滞约束 ✅ (2026-03-23)

- [x] **S02: 因子库 Few-shot 导出 (S4)** `risk:medium` `depends:[]`
  > After this: Active 因子可按相关度导出为 LLM few-shot 示例 ✅ (2026-03-23)

- [x] **S03: P0 配置解锁优化** `risk:low` `depends:[]`
  > After this: backtest.yaml 排除北交所、激活多周期回测 ✅ (2026-03-23)

- [x] **S04: ProviderPool 核心实现 (S2/D016)** `risk:high` `depends:[S01]`
  > After this: 多 Provider 并存、健康监控、自动降级可用 ✅ (2026-03-23)

- [x] **S05: Coding 模型 JSON 修复闭环 (S3/D019)** `risk:medium` `depends:[S04]`
  > After this: JSON 解析失败触发 coding 模型修复，带超时和重试上限 ✅ (2026-03-23)

- [x] **S06: Checkpoint 与幂等性恢复 (S5/D017)** `risk:high` `depends:[]`
  > After this: 进程崩溃后可从检查点恢复，因子库支持版本历史留存 ✅ (2026-03-23)

- [x] **S07: PIT 对齐执行层 (S6/D013)** `risk:high` `depends:[S01]`
  > After this: 财务数据按 ann_date 动态对齐，消除未来函数 ✅ (2026-03-23)

- [x] **S08: ResourceManager 资源管理 (S7/D018)** `risk:medium` `depends:[S04]`
  > After this: Token/磁盘/内存资源边界约束生效 ✅ (2026-03-23)

- [x] **S09: M001 教训设计约束转化 (D019)** `risk:medium` `depends:[S04,S05,S06]`
  > After this: M001 Bug 教训作为代码约束和验收标准写入 ✅ (2026-03-23)

- [x] **S10: ADR-003 Phase 3 外插模块设计 (D015)** `risk:high` `depends:[S04,S06,S08]`
  > After this: Orchestrator、Trigger、Observability、Revalidation 模块设计完成 ✅ (2026-03-23)

---

## Remediation Slices (Round 1 — 验证发现实现未提交到子模块)

> **验证发现：** S01-S10 的 GSD artifacts（summary, UAT result, plans）已创建，但实际 Python 实现文件（provider_pool.py, checkpoint.py, resource_manager.py, fewshot.py, pit_alignment.py 等）未提交到 `third_party/quantaalpha` 子模块。工作区测试文件因 `ModuleNotFoundError: No module named 'quantaalpha'` 而无法运行。S05 UAT 文档缺失。D016 MoD 复选框未勾选。

- [ ] **R01: 提交 S01-S08 实现到 quantaalpha 子模块** `risk:critical` `depends:[]`
  > After this: 所有实现文件提交到子模块，测试可从工作区运行 ✅

- [ ] **R02: 补充 S05 UAT 文档** `risk:low` `depends:[R01]`
  > After this: S05-UAT-RESULT.md 存在并记录 17 个测试结果 ✅

- [ ] **R03: 标记 D016 MoD 完成** `risk:low` `depends:[R01]`
  > After this: 路线图 MoD 中 D016 复选框已勾选 ✅

- [ ] **R04: 修复子模块引用** `risk:medium` `depends:[R01]`
  > After this: 子模块指针指向存在的 commit，工作树可正常初始化 ✅

## Boundary Map

### S01 → S04/S07
Produces:
- data_capability.py 动态注册表实现
- prompts.yaml data_capabilities 占位符
- proposal.py prepare_context() 注入逻辑

Consumes:
- /data/*.parquet 目录结构
- Polars schema 扫描能力

### S04 → S05/S08
Produces:
- provider_pool.py ProviderPool 类
- experiment.yaml providers/routing 配置格式
- APIBackend → ProviderPool 迁移路径

Consumes:
- S01 的数据能力注册表（用于配置验证）

### S06 → S09
Produces:
- checkpoint.py LoopCheckpoint 类
- library.py versions 字段和锁超时
- 断点续挖验证测试

Consumes:
- M001 Bug 2 的教训（超时设计约束）

### S09 → 所有切片验证
Produces:
- 设计约束检查清单
- 回归测试用例

Consumes:
- KNOWLEDGE.md M001 修复经验
- D019 决策要求
