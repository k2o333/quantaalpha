# 外插式持续因子研究模块题纲

Status: draft
Created: 2026-03-18
Type: architecture draft
Target: docs/04-decisions/

## Background

当前 `quantaalpha` 已具备因子挖掘、多周期验证、因子库状态管理等主链能力，但对 24 小时连续研究来说，仍有一批能力更适合放在主链之外：

- 持续调度与作业编排
- 数据到达触发
- 运行监控与告警
- 连续运行自动化测试框架
- 数据能力注册表服务化输出

这些能力的共同点是：

- 更偏系统外层控制，而不是单次挖掘算法本身
- 可以通过 CLI、因子库、状态摘要、事件输入与 `quantaalpha` 解耦
- 适合独立演进、独立测试、独立部署

## Goal

形成一份可提升为 ADR 的结构化决策草稿，说明哪些持续研究能力应作为“外插模块”建设，以及它们与 `quantaalpha` 主链的边界。

## Non-Goals

- 不定义 `quantaalpha` 内部算法细节
- 不替代 `ADR-001` 对持续研究总体方向的描述
- 不展开单个模块的详细实现计划
- 不把一次具体开发任务写成 `planned` 变更单

## Target Scope

本草稿只覆盖可外插实现的模块层，不覆盖必须深度侵入 `quantaalpha` 主链的能力。

建议纳入范围的外插模块：

1. `continuous-orchestrator`
2. `data-update-trigger`
3. `monitoring-and-alerting`
4. `continuous-test-harness`
5. `data-capability-registry`

## Proposed ADR Title

`ADR-00X: QuantaAlpha 持续因子研究的外插模块边界`

## Proposed Structure

### 1. Context & Problem Statement

- 为什么 24 小时连续因子研究不能只靠 `quantaalpha` 单体内部完成
- 当前主链已经具备什么
- 当前仍缺什么外层能力
- 为什么这些能力适合做成外插模块，而不是继续堆进主链

### 2. Decision Drivers

- 降低对 `quantaalpha` 主流程的侵入
- 保持主链聚焦于“挖掘、回测、因子库写入”
- 让持续运行能力可独立部署、独立测试、独立替换
- 让外层系统更容易和 `app4`、调度器、监控系统对接

### 3. Decision

核心决策建议写成：

- `quantaalpha` 保持为研究执行内核
- 连续运行相关能力通过标准接口外插实现
- 外插模块只通过稳定边界与主链通信，不直接复制业务逻辑

### 3.1 Continuous Orchestrator

- 负责 Mining、Validation、Revalidation、Library Maintenance 等作业编排
- 支持定时触发和事件触发
- 只调用已有 CLI / Python entrypoint
- 不在编排层重写回测或状态流转逻辑

### 3.2 Data Update Trigger

- 感知 `app4` 或上游数据更新
- 将数据更新事件翻译成可执行任务
- 触发特定范围的复验或补挖
- 不承担研究逻辑本身

### 3.3 Monitoring And Alerting

- 消费运行摘要、退出码、因子库状态分布、审计记录
- 输出健康状态、失败告警、长期无产出告警
- 与主链通过只读接口或结果文件解耦

### 3.4 Continuous Test Harness

- 提供调度级、黑盒级、长运行回归级测试
- 验证“连续运行系统”而不是单个函数
- 重点覆盖失败恢复、重复执行、状态一致性、空库/坏库边界

### 3.5 Data Capability Registry

- 作为独立元数据模块维护字段、频率、lag、join_mode、使用建议
- 对外提供结构化读取或 prompt 渲染接口
- 由 `quantaalpha` 在需要时消费，而不是把全部元数据硬编码在主链各处

### 4. Module Boundaries

建议明确 3 类边界：

- 调用边界：CLI、Python facade、结果 JSON、状态摘要
- 数据边界：因子库、运行日志、审计记录、数据更新时间
- 责任边界：外插模块负责调度/触发/观测，`quantaalpha` 负责研究执行

### 5. Integration Contracts

建议 ADR 中显式列出：

- orchestrator 输入输出契约
- trigger 事件格式
- monitoring 消费的最小字段
- registry 对 `quantaalpha` 提供的查询接口
- continuous tests 的目标入口与验收口径

### 6. Non-Goals / Rejected Alternatives

- 不把所有持续能力直接并入 `quantaalpha.pipeline`
- 不先引入复杂常驻服务或分布式平台
- 不在第一阶段引入数据库迁移或消息队列依赖

### 7. Consequences

正向影响：

- 主链更稳
- 模块职责更清晰
- 连续系统更容易独立演进
- 更利于自动化测试和运维

风险：

- 外层模块与主链契约漂移
- 过度外插导致链路分散
- 如果边界定义不清，可能出现重复逻辑

### 8. Implementation Notes

建议后续再拆成独立 change docs 或子设计：

- orchestrator 设计
- trigger 设计
- monitoring 设计
- test harness 设计
- registry 接入设计

## Likely Target Docs

- `docs/04-decisions/ADR-001-continuous-factor-research.md`
- 新增 `docs/04-decisions/ADR-00X-*.md`
- 如需落任务，再分别进入 `docs/03-changes/common/` 或 `docs/03-changes/quantaalpha/`

## Validation

这份题纲完成后，至少应检查：

- 是否明确区分“主链能力”和“外插模块能力”
- 是否避免把实现任务写成 ADR
- 是否能直接作为后续 ADR draft 的骨架
- 是否符合 `docs/00-governance/agent.md` 与 `doc-standards.md` 的文档分层

## Open Questions

- 外插 orchestrator 是放在仓库内还是独立仓库
- `app4` 的数据更新事件以文件时间戳、manifest 还是显式事件文件暴露
- registry 是静态配置文件还是轻量查询模块
- continuous test harness 是放在主测试树还是单独目录
