Status: accepted
Owner: AI Assistant
Created: 2026-03-16
Updated: 2026-03-16
Outcome: accepted
Related-to: docs/04-decisions/ADR-002-agent-oriented-documentation-system.md

# ADR-002 收尾与完成判定

## Background

`ADR-002` 已经推动仓库文档系统完成了主要结构重组：

- 根入口 `AGENTS.md`
- 仓库导航入口 `docs/00-governance/agent.md`
- 规则入口 `docs/00-governance/rules.md`
- 文档治理拆分为 `doc-rules.md`、`doc-workflows.md`、`doc-standards.md`
- 模块文档补齐 agent 快速定位区块
- `docs/03-changes/` 建立模块化生命周期目录

但 `ADR-002` 当前仍保持 `Status: draft` 和 `Outcome: pending`，文档末尾保留"后续需要继续完成的工作"，因此应被视为"主体落地，但尚未正式闭环"的决策文档。

## Goal

明确 `ADR-002` 进入完成态前需要完成的动作，给出最小收尾路径。

## Non-Goals

- 不一次性迁移全部历史 change docs
- 不扩展新的治理体系范围
- 不新增不必要的治理文档

## Findings

### 已落地部分

| 决策项 | 状态 | 证据 |
|---|---|---|
| 双入口机制（AGENTS.md → agent.md） | 已落地 | 两个文件均存在且职责分离 |
| rules.md 重构为规则文档 | 已落地 | rules.md 仅含约束，不含导航 |
| doc-rules/doc-workflows/doc-standards 三层拆分 | 已落地 | 三个文件均存在 |
| 模块文档快速定位区块 | 已落地 | app4.md、quantaalpha.md、backtest.md 均有 TL;DR、Entrypoints、Validation 区块 |
| docs/03-changes/ 模块化结构 | 已落地 | app4/、quantaalpha/、backtest/、common/ 均有生命周期目录 |

### 未收口部分

| 问题 | 当前状态 | 影响 |
|---|---|---|
| ADR-002 状态仍为 draft/pending | 需要更新 | 决策未正式闭环 |
| ADR-002 末尾"后续需要继续完成的工作"提及 testing-strategy.md | 入口未引用 | 悬空引用 |
| docs/03-changes/vnpy/ 目录存在 | 空目录（无 .md 文件） | 与 ADR"推荐模块桶"列表不一致 |

### 关键验证结果

1. **testing-strategy.md 引用检查**
   - 搜索 `docs/00-governance/` 目录，未找到任何对 testing-strategy 的引用
   - 结论：当前入口并不依赖此文档，可从 ADR-002 中删除该待办项

2. **vnpy 目录检查**
   - 存在完整生命周期子目录（accepted/archived/blocked/draft/implemented/in_progress/planned/tested）
   - 但所有子目录均为空，无任何 .md 文件
   - 结论：为预留结构，可在 doc-standards.md 中添加扩展规则说明

## Decision

采用 **Option A: 最小收尾** 方案。

理由：
- ADR-002 的核心决策已全部落地
- 未完成项均为"文案对齐"性质，非结构性缺失
- testing-strategy.md 当前无实际依赖，后续可独立处理
- vnpy 为预留空结构，不影响当前决策有效性

## Implementation Tasks

### Task 1: 更新 doc-standards.md 模块桶规则

在 `docs/00-governance/doc-standards.md` 的 "Change doc structure" 和 "Preferred modules" 部分添加扩展规则：

```markdown
扩展规则：
- 推荐模块桶为 app4、quantaalpha、backtest、common
- 其他模块桶（如 vnpy）可作为预留结构保留
- 新增模块桶应保持生命周期目录结构一致性
```

### Task 2: 更新 ADR-002 实施说明

修改 `docs/04-decisions/ADR-002-agent-oriented-documentation-system.md`：

1. 删除末尾"后续需要继续完成的工作"中的 `testing-strategy.md` 待办项
2. 将 Section 5 "Implementation Notes" 更新为已落地状态
3. 更新状态头：
   - `Status: draft` → `Status: accepted`
   - `Outcome: pending` → `Outcome: accepted`

### Task 3: 更新 common change doc 状态

将 `docs/03-changes/common/2026-03-15-agent-oriented-doc-system-refactor.md` 的状态更新为 `accepted`，作为 ADR-002 实施的完成记录。

## Completion Criteria

当以下条件全部满足时，ADR-002 判定为完成：

- [x] ADR-002 状态头为 `accepted`
- [x] ADR-002 不含悬空的 testing-strategy.md 待办项
- [x] doc-standards.md 包含模块桶扩展规则说明
- [x] common change doc 状态已更新

## Validation

完成收尾后执行：

1. 检查 ADR-002 状态头与内容一致性
2. 检查 agent.md → rules.md 入口链路完整
3. 检查 doc-rules.md → doc-workflows.md / doc-standards.md 路由完整
4. 检查 docs/03-changes/ 目录结构与 doc-standards.md 说明一致

## Risks

- 低风险：修改仅为状态更新和规则澄清，不涉及结构性变更