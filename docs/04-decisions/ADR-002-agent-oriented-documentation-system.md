# ADR-002: 面向 Agent 的文档系统与文档演化流程

Status: accepted
Owner:
Created: 2026-03-15
Updated: 2026-03-16
Outcome: accepted

## 1. Context & Problem Statement (背景与问题)

当前仓库的文档内容已经不少，但在 AI agent 实际使用时存在几个关键问题：
- **入口不清晰**：此前缺少一个真正的仓库入口文档，agent 第一次进入后不知道先看什么、再看什么。
- **规则与导航混在一起**：`rules.md` 同时承担项目说明、技术细节和约束规则，导致第一跳成本过高。
- **文档规则过长**：原 `doc-rules.md` 更像文档百科全书，不适合文档整理 agent 按任务快速路由。
- **当前事实与过程材料容易混淆**：草稿、变更记录、模块真相的边界不够显式，容易让 agent 把历史上下文误判为当前事实。
- **缺少明确的文档演化模型**：实际开发中，很多知识会经历 `draft -> change -> module / ADR / playbook / reference` 的演化，但过去没有把这条主链写清楚。

本次 session 的目标，不是单纯“增加文档”，而是把仓库文档系统重构为一套 **agent 可快速路由、可按流程整理、可逐层提升真值密度** 的体系。

## 2. Decision Drivers (决策驱动力)

- 让任何 agent 进入仓库后都能在极短时间内知道第一跳和第二跳该读什么。
- 将“导航”和“约束”解耦，降低首次上下文注入成本。
- 让文档整理类 agent / subagent 能按动作读取少量规则，而不是整本通读。
- 明确“当前真相”和“历史过程”的边界，降低误读和幻觉风险。
- 让开发中产生的文档能够沿固定路径升级，而不是长期停留在草稿状态。

## 3. Decision (决策)

我们决定将仓库文档系统重构为一套面向 agent 的分层体系，并显式采用文档演化流程作为文档治理主模型。

### 3.1 建立双入口机制：导航入口与规则入口分离

- 使用 `docs/00-governance/agent.md` 作为仓库级唯一导航入口。
- 使用 `docs/00-governance/rules.md` 作为强约束规则文档。
- 根层 `AGENTS.md` 只负责把 agent 导向 `docs/00-governance/agent.md`。

这样做的目的，是让入口文档只回答：
- 我该看什么
- 我该改哪里
- 我该做什么验证

而规则文档只回答：
- 什么能做
- 什么不能做
- 什么情况必须停下等待人工审核

### 3.2 采用文档演化主链作为治理模型

今后默认认为大多数开发知识沿下列路径演化：

`draft -> change doc -> module doc / ADR / playbook / reference doc`

含义如下：
- `draft` 承载探索、比较、临时分析
- `change doc` 承载具体实现任务的背景、计划、验证、结果
- `module doc` 承载某一模块当前有效真相
- `ADR` 承载长期结构性决策
- `playbook` 承载跨任务可复用经验
- `reference doc` 承载依赖或上游项目在本仓库中的稳定用法

不是每个任务都要走完整条链，但整理文档时必须优先用这条链判断知识应该提升到哪一层。

### 3.3 将文档规则重构为“流程优先”而不是“分类百科”

- `doc-rules.md` 只做文档工作入口与流程路由。
- `doc-workflows.md` 只定义文档整理流程和提升路径。
- `doc-standards.md` 只定义命名、状态头、放置位置、truth vs history 等稳定标准。

这意味着文档整理类 agent 以后只需要：
1. 先看 `agent.md`
2. 如果任务是文档整理，读 `doc-rules.md`
3. 再按动作只看一个流程小节
4. 如有需要，再补看一个标准小节

### 3.4 将 `docs/03-changes/` 统一为按模块组织的稳定结构

`change doc` 是文档演化主链中的关键中间层，因此它的目录结构必须稳定、可预测、易于 agent 路由。

我们决定采用以下目标结构：

```text
docs/03-changes/<module>/draft/YYYY-MM-DD-topic.md
docs/03-changes/<module>/planned/YYYY-MM-DD-topic.md
docs/03-changes/<module>/in_progress/YYYY-MM-DD-topic.md
docs/03-changes/<module>/blocked/YYYY-MM-DD-topic.md
docs/03-changes/<module>/implemented/YYYY-MM-DD-topic.md
docs/03-changes/<module>/tested/YYYY-MM-DD-topic.md
docs/03-changes/<module>/accepted/YYYY-MM-DD-topic.md
docs/03-changes/<module>/archived/YYYY-MM-DD-topic.md
```

其中：
- `app4/` 用于 `app4` 相关变更
- `quantaalpha/` 用于 `quantaalpha` 相关变更
- `backtest/` 用于 `backtest` 相关变更
- `common/` 用于跨模块变更

并约定：
- `draft/` 用于已明确模块归属、但仍在探索中的任务文档
- `planned/` 用于已经确定要开发、但尚未开始的任务文档
- `in_progress/`、`blocked/`、`implemented/`、`tested/`、`accepted/`、`archived/` 用于单任务文档的生命周期状态
- 模块根目录只保留 checklist、索引、任务集合总览等非单任务文档

做出这个决策的原因是：
- agent 更常按“任务属于哪个模块”来找上下文，而不是按年份查找
- agent 和人都需要快速分辨“还在探索”“已经排期但未开工”“正在做或已做完”
- 文档演化主链里，`change doc` 需要自然连接到对应模块文档
- 统一路径后，更容易做后续的脚本检查和自动化整理

因此，按年份直接平铺在 `docs/03-changes/2026/` 之类目录中的组织方式不再作为目标规范继续扩展。

对历史遗留内容的处理原则是：
- 旧结构可暂时保留
- 新增 change doc 应遵守模块化路径与 `draft/`、`planned/` 分层
- 历史文档可按需要逐步迁移

### 3.5 显式区分当前真相与历史过程材料

默认真相来源：
- governance docs
- overview docs
- module docs
- currently valid ADRs
- current playbooks
- current reference docs

默认过程或历史材料：
- drafts
- completed change docs
- superseded ADRs
- obsolete references
- archived docs

agent 不应默认把过程材料当成当前事实，除非是在追溯某项实现上下文。

### 3.6 模块文档统一增加 agent 快速定位区块

模块文档顶部统一增加下列区块：
- `TL;DR`
- `Entrypoints`
- `Validation`
- `Do Not Touch Blindly`
- `Known Risks`

目标是让 agent 从入口跳到模块文档后，不需要通读全文，也能先拿到：
- 改动入口
- 验证命令
- 风险区域

## 4. Consequences (影响与风险)

### Positive (收益)

- **更低的首次上下文成本**：agent 进入仓库后能更快完成上下文注入。
- **更清晰的文档职责边界**：入口、规则、模块真相、技术细节、过程材料各自职责明确。
- **更适合 subagent 协作**：文档整理任务能按流程片段路由，而不是整本阅读。
- **更容易做后续自动化**：文档演化链清晰后，未来更容易脚本化检查草稿是否应提升、变更是否遗漏模块更新等。

### Negative / Risks (风险与应对)

- **文档数量增加**：拆分后文件数会变多。
  - *应对策略：限制第一跳文件数量，保持 `agent.md` 和 `doc-rules.md` 足够短，只通过路由进入后续文档。*
- **多份文档之间可能失配**：若后续维护不严格，入口文档可能指向不存在或过时内容。
  - *应对策略：把入口文档保持简短，减少高频变动内容，把细节放到模块文档和流程文档。*
- **历史遗留的 change docs 结构仍然混杂**：
  - *应对策略：将模块化路径定为新规范，旧内容按价值和需要逐步迁移，而不是一次性强迁。*

## 5. Implementation Notes (实施说明)

本次决策已落地以下基础结构：
- 新建仓库入口 `AGENTS.md`
- 新建导航入口 `docs/00-governance/agent.md`
- 将 `docs/00-governance/rules.md` 重构为规则文档
- 将原 `doc-rules.md` 重构为短入口，并拆出 `doc-workflows.md` 与 `doc-standards.md`
- 为 `app4`、`quantaalpha`、`backtest` 模块文档补充统一的快速定位区块
- `docs/03-changes/` 已采用模块化生命周期目录结构
- 历史变更文档已迁移到模块级目录，仍在逐步按生命周期规范收敛

后续维护事项：
- 逐步清理仍然过长或职责混杂的历史文档
- 将模块根目录下的历史单任务文档按生命周期规范迁移到对应子目录
- 新增模块桶时保持生命周期目录结构一致性
