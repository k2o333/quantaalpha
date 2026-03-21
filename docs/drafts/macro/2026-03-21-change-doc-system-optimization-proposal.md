# Change Doc System Optimization Proposal

Status: draft
Created: 2026-03-21
Owner: quan
Contributors: AI Assistant

---

## 一、问题背景

### 1.1 现状分析

#### 1.1.1 目录结构现状

当前 `docs/03-changes/` 目录结构存在不一致：

```
docs/03-changes/
├── app4/                      # 27 docs at root (扁平)
│   ├── draft/                 # 0 docs
│   ├── planned/               # 0 docs
│   ├── in_progress/           # 0 docs
│   ├── implemented/           # 0 docs
│   ├── tested/                # 0 docs
│   ├── accepted/              # 0 docs
│   └── archived/              # 0 docs
├── quantaalpha/               # 0 docs at root (嵌套)
│   ├── planned/               # 33 docs
│   ├── implemented/           # 9 docs
│   ├── tested/                # 2 docs
│   ├── accepted/              # 3 docs
│   └── archived/              # 3 docs
├── common/
│   └── accepted/              # 3 docs
└── vnpy/                      # reserved, empty
```

**核心问题**：

| 问题 | 描述 | 影响 |
|------|------|------|
| **目录结构不一致** | app4 扁平，quantaalpha 嵌套 | Agent 需要判断不同模块的目录结构 |
| **状态目录层级过深** | 8 个状态子目录 | 目录树膨胀，导航成本高 |
| **状态变更成本高** | 需要移动文件 + 修改 Status 字段 | 两处同步，易遗漏 |
| **查询依赖目录遍历** | 人工难以快速统计各状态文档数量 | 缺乏标准化工具 |

#### 1.1.2 文档治理现状

当前文档治理相关文件分散在两处：

```
/home/quan/testdata/aspipe_v4/
├── docs/00-governance/
│   ├── agent.md              # Agent 入口
│   ├── rules.md              # 规则
│   ├── doc-rules.md          # 文档规则
│   ├── doc-workflows.md      # 文档工作流
│   ├── doc-standards.md      # 文档标准
│   └── development-workflow.md
└── .trae/rules/
    ├── aspipe.md             # 与 rules.md 重叠
    └── download.md
```

**核心问题**：

| 问题 | 描述 | 影响 |
|------|------|------|
| **规则分散** | `.trae/rules/` 与 `docs/00-governance/` 内容重叠 | Agent 需要阅读多处 |
| **drafts 目录膨胀** | `docs/drafts/` 包含大量历史草稿 | 影响活跃文档定位效率 |
| **内容校验缺失** | 无自动化校验机制 | 文档一致性依赖人工 |
| **行为约束不完整** | Agent 行为约束分散 | 边界不清晰 |
| **归档流程缺失** | 无明确的文档归档和清理机制 | 历史文档累积 |

### 1.2 信息熵分析

| 操作 | 当前方案 | 问题 |
|------|----------|------|
| 查看所有进行中任务 | 遍历多个 `in_progress/` 目录 | 需要知道哪些模块存在 |
| 修改任务状态 | 移动文件 + 修改字段 | 两处修改，易遗漏 |
| 统计任务分布 | `find` + 手动统计 | 无标准化工具 |
| 查看某模块任务 | 遍历模块下 8 个子目录 | 目录结构不透明 |
| 确认 Agent 行为边界 | 阅读多处规则文件 | 约束不集中 |
| 验证文档一致性 | 人工检查 | 无自动化机制 |

---

## 二、优化目标

### 2.1 核心原则

1. **扁平化目录** - 删除状态子目录，文档直接放在模块目录下
2. **状态内聚** - 状态仅通过文档头部的 `Status:` 字段管理
3. **脚本驱动** - 用脚本扫描状态，替代目录遍历
4. **规则集中** - 合并分散的规则文件到单一入口
5. **约束明确** - 集中声明 Agent 行为边界
6. **校验自动** - 建立自动化内容校验机制

### 2.2 预期收益

| 维度 | 当前 | 目标 | 收益 |
|------|------|------|------|
| 状态变更操作数 | 2 处（移动 + 改字段） | 1 处（改字段） | -50% |
| 规则文件数量 | 2 处（docs + .trae） | 1 处（docs） | -50% |
| 状态查询方式 | 目录遍历 | 脚本命令 | 标准化 |
| Agent 约束查找 | 分散多处 | 集中一处 | 降低认知成本 |
| 文档校验 | 人工 | 自动化 | 提高效率 |

---

## 三、目录结构优化

### 3.1 Change Docs 目录简化

#### 3.1.1 当前结构（复杂）

```
docs/03-changes/
├── app4/
│   ├── draft/
│   ├── planned/
│   ├── in_progress/
│   ├── blocked/
│   ├── implemented/
│   ├── tested/
│   ├── accepted/
│   └── archived/
├── quantaalpha/
│   └── ... (同上)
└── ...
```

#### 3.1.2 目标结构（扁平）

```
docs/03-changes/
├── app4/
│   ├── 2026-02-25-cyq-chips-offset-pagination-fix.md
│   ├── 2026-02-25-disclosure-date-fix-report.md
│   └── ...
├── quantaalpha/
│   ├── 2026-03-15-iterate2-01-revalidate-semantics.md
│   ├── 2026-03-15-iterate2-02-failed-factor-debug.md
│   └── ...
├── backtest/
│   └── ...
├── common/
│   └── ...
└── vnpy/                     # reserved for future use
```

**变化**：
- 删除所有状态子目录（draft/planned/in_progress/...）
- 文档直接放在模块根目录
- 状态通过文档头部字段管理

### 3.2 规则文件合并

#### 3.2.1 当前结构（分散）

```
/home/quan/testdata/aspipe_v4/
├── docs/00-governance/rules.md
└── .trae/rules/aspipe.md
```

#### 3.2.2 目标结构（集中）

```
/home/quan/testdata/aspipe_v4/
└── docs/00-governance/
    ├── rules.md              # 合并后的唯一规则入口
    └── agent-constraints.md  # 新增：Agent 行为约束
```

**操作**：
- 将 `.trae/rules/aspipe.md` 内容合并到 `docs/00-governance/rules.md`
- `.trae/rules/` 目录可删除或保留作为历史

### 3.3 Drafts 目录清理

#### 3.3.1 当前结构（膨胀）

```
docs/drafts/
├── history/
├── prompts/
├── report/
├── factormining/
├── macro/
└── ...
```

#### 3.3.2 清理策略

| 目录 | 处理建议 | 优先级 |
|------|----------|--------|
| `drafts/history/` | 迁移有价值内容到 `03-changes/<module>/archived/`，删除冗余 | 低 |
| `drafts/prompts/` | 删除或迁移到 `.tmp/` 作为临时参考 | 低 |
| `drafts/report/` | 评估后归档或删除 | 低 |
| `drafts/factormining/` | 有价值的架构设计迁移到 `04-decisions/` | 低 |
| `drafts/macro/` | 保留活跃探索，定期清理 | 中 |

**原则**：
- 不一次性批量清理
- 在相关任务执行时顺便清理
- 保留 `.gitkeep` 确保目录存在

---

## 四、状态管理优化

### 4.1 状态简化

#### 4.1.1 当前状态（8 个）

```
draft → planned → in_progress → blocked → implemented → tested → accepted → archived
```

#### 4.1.2 建议简化为（5 个）

```
draft → planned → doing → done → archived
         ↑
      blocked (可选，标记暂停)
```

**状态含义**：

| 状态 | 含义 | 对应旧状态 |
|------|------|-----------|
| `draft` | 探索中，未确定实施 | draft |
| `planned` | 已批准，待开始 | planned |
| `doing` | 实施中 | in_progress, blocked |
| `done` | 已完成 | implemented, tested, accepted |
| `archived` | 已归档 | archived |

**简化理由**：

1. `implemented` vs `tested` vs `accepted` 的区分对单个开发者/agent 意义不大
2. 减少状态可以减少心智负担
3. `blocked` 可作为 `doing` 的子状态，用 `Blocked-by:` 字段标记

### 4.2 文档头部格式

```yaml
# 任务标题

Status: planned
Module: quantaalpha
Created: 2026-03-21
Updated: 2026-03-22
Owner: quan
Blocked-by: [可选，当 Status=doing 且被阻塞时填写]

---
```

**字段说明**：

| 字段 | 必填 | 说明 |
|------|------|------|
| `Status` | 是 | 文档状态，枚举值见上表 |
| `Module` | 是 | 所属模块，用于跨目录查询 |
| `Created` | 是 | 创建日期 |
| `Updated` | 是 | 最后更新日期，状态变更时同步更新 |
| `Owner` | 是 | 责任人 |
| `Blocked-by` | 否 | 阻塞原因，仅当 `Status=doing` 且被阻塞时填写 |

### 4.3 状态变更流程

#### 4.3.1 旧流程（需要移动文件）

```
1. 修改文档 Status 字段
2. 将文件从 planned/ 移动到 in_progress/
3. 提交变更
```

#### 4.3.2 新流程（仅修改字段）

```
1. 修改文档 Status 字段
2. 更新 Updated 字段
3. 提交变更
```

**收益**：
- 减少 50% 操作步骤
- 降低遗漏风险
- 无需关心目录结构

---

## 五、状态查询脚本

### 5.1 脚本设计

**脚本位置**: `scripts/doc_status.py`

**核心功能**：
- 扫描 `docs/03-changes/` 目录下所有文档
- 解析文档头部的 `Status:` 字段
- 支持按状态、模块、责任人等条件过滤
- 输出格式化结果或 JSON

### 5.2 使用方式

```bash
# 查看所有 doing 任务
python scripts/doc_status.py list --status doing

# 查看某模块的 planned 任务
python scripts/doc_status.py list --module quantaalpha --status planned

# 查看状态统计
python scripts/doc_status.py summary

# 输出 JSON 供其他工具使用
python scripts/doc_status.py list --status doing --json

# 查看某个 Owner 的任务
python scripts/doc_status.py list --owner quan

# 查看超过 N 天未更新的任务
python scripts/doc_status.py list --stale --days 7

# 查看被阻塞的任务
python scripts/doc_status.py list --blocked
```

### 5.3 输出示例

```bash
$ python scripts/doc_status.py list --status doing

Module: quantaalpha
├── 2026-03-15-iterate2-01-revalidate-semantics.md
│   Status: doing | Created: 2026-03-15 | Updated: 2026-03-18 | Owner: quan
└── 2026-03-15-iterate2-02-failed-factor-debug.md
    Status: doing | Created: 2026-03-15 | Updated: 2026-03-16 | Owner: quan

Total: 2 documents
```

```bash
$ python scripts/doc_status.py summary

Status Summary:
  draft:     5
  planned:   8
  doing:     3
  done:     12
  archived: 10

By Module:
  app4:       27 documents
  quantaalpha: 48 documents
  common:      3 documents
```

```bash
$ python scripts/doc_status.py list --stale --days 7

Module: quantaalpha
└── 2026-03-10-old-task.md
    Status: doing | Created: 2026-03-10 | Updated: 2026-03-10 | Owner: quan
    ⚠️  11 days since last update

Total: 1 stale document(s)
```

---

## 六、Agent 行为约束

### 6.1 新增文件：`agent-constraints.md`

**文件位置**: `docs/00-governance/agent-constraints.md`

**核心内容**：

```markdown
# Agent Behavior Constraints

Status: active
Created: 2026-03-21
Owner: quan

## 1. Purpose

本文档定义 AI coding agent 在本仓库中的行为边界和约束规则。

## 2. Mandatory Reading Order

每次任务开始前，agent 必须按以下顺序阅读：

1. `docs/00-governance/agent.md` - 了解路由
2. `docs/00-governance/rules.md` - 了解约束
3. `docs/00-governance/agent-constraints.md` - 了解行为边界
4. 目标模块文档 - 了解上下文

## 3. Prohibited Actions

### 3.1 绝对禁止（未经人类明确授权）

| 行为 | 原因 |
|------|------|
| 修改 `docs/00-governance/` 下的任何文件 | 治理文档变更需人工审批 |
| 创建新的 ADR | 架构决策需人工审批 |
| 删除任何文档 | 可能丢失历史上下文 |
| 修改 `third_party/vnpy/` 或 `third_party/glue/` | 非默认编辑目标 |
| 将不确定变更合并到 main 分支 | 违反分支策略 |
| 自动提交代码 | 提交需人工确认 |
| 将 drafts 视为当前事实 | drafts 是探索性内容 |

### 3.2 条件禁止（需满足条件后可执行）

| 行为 | 允许条件 |
|------|----------|
| 修改模块文档 | change doc 已 accepted 且行为确实改变 |
| 创建新模块文档 | 新模块已稳定运行 |
| 归档 change doc | 任务已 accepted 超过 30 天 |

## 4. Required Actions

### 4.1 任务开始时必须

- [ ] 确认目标模块
- [ ] 确认目标文件
- [ ] 确认验证范围
- [ ] 确认是否需要人工审查

### 4.2 任务结束时必须

- [ ] 更新或创建 change doc
- [ ] 执行验证命令并记录结果
- [ ] 判断是否需要更新模块文档
- [ ] 判断是否需要人工审查

## 5. Risk-Based Review Requirements

| 风险等级 | 场景示例 | 审查要求 |
|----------|----------|----------|
| **低风险** | 文档修正、日志调整、注释修改 | 无需人工审查 |
| **中风险** | 单模块 Bug 修复、配置调整 | 建议人工审查 |
| **高风险** | 分页逻辑、存储路径、去重行为、Schema 变更 | **必须人工审查** |

## 6. Output Requirements

### 6.1 任务报告必须包含

```markdown
## Status
[completed | partial | blocked]

## Files Changed
- [文件路径]: [变更说明]

## Files Reviewed But Not Changed
- [文件路径]: [未变更原因]

## Validation Results
[执行的命令和结果]

## Residual Gaps
[未完成项或遗留问题]
```

### 6.2 禁止的输出行为

- ❌ 报告"通过"但无法复现验证命令
- ❌ 声称"完成"但存在未解决的冲突
- ❌ 省略失败的验证步骤
```

### 6.2 更新 agent.md

在 `docs/00-governance/agent.md` 中添加：

```markdown
## Agent Constraints Summary

完整行为约束见 `agent-constraints.md`

**核心禁止项**：
- ❌ 修改 governance 文档
- ❌ 删除任何文档
- ❌ 将 drafts 视为事实
- ❌ 自动提交代码

**核心要求**：
- ✅ 任务开始前阅读 rules.md + agent-constraints.md
- ✅ 任务结束后更新 change doc
- ✅ 高风险变更必须人工审查
```

---

## 七、内容校验机制

### 7.1 新增文件：`validation-checklist.md`

**文件位置**: `docs/00-governance/validation-checklist.md`

**核心内容**：

```markdown
# Documentation Validation Checklist

Status: active
Created: 2026-03-21
Owner: quan

## 1. Automatic Validation

### 1.1 Path-Status Consistency

检查文档路径与状态字段是否一致（仅适用于旧目录结构）：

- [ ] `draft/` 目录下的文档 Status 为 `draft`
- [ ] `planned/` 目录下的文档 Status 为 `planned`
- [ ] `in_progress/` 目录下的文档 Status 为 `in_progress` 或 `doing`
- [ ] `archived/` 目录下的文档 Status 为 `archived`

### 1.2 Required Fields Completeness

- [ ] 所有 change doc 包含 Status、Created、Owner 字段
- [ ] 所有 ADR 包含 Context、Decision、Consequences 章节
- [ ] 所有模块文档包含 TL;DR、Entrypoints、Validation 章节

### 1.3 Reference Integrity

- [ ] 内部链接指向存在的文件
- [ ] 路由表中列出的文件实际存在

## 2. Manual Validation

### 2.1 Content Consistency

- [ ] 模块文档描述与代码实际行为一致
- [ ] change doc 的实现结果与模块文档无冲突
- [ ] ADR 决策与当前实践一致

### 2.2 Truth Source Priority

- [ ] 无将 drafts 作为真相引用的情况
- [ ] 已归档文档未被标记为当前事实

## 3. Validation Scripts

### 3.1 Status-Path Consistency

```bash
python scripts/validate_doc_status.py
```

### 3.2 Link Integrity

```bash
python scripts/validate_doc_links.py
```

### 3.3 Field Completeness

```bash
python scripts/validate_doc_fields.py
```

## 4. Periodic Validation

### 4.1 Monthly Tasks

- [ ] 检查 `drafts/` 目录，清理超过 60 天的草稿
- [ ] 检查 `done` 状态的文档，归档超过 30 天的文档
- [ ] 运行所有校验脚本

### 4.2 Quarterly Tasks

- [ ] 审查 ADR 是否需要更新或 supersede
- [ ] 审查 playbooks 是否需要补充
- [ ] 审查 reference docs 是否过时
```

### 7.2 校验脚本

**建议创建以下脚本**：

| 脚本路径 | 功能 |
|----------|------|
| `scripts/validate_doc_status.py` | 检查文档状态与目录位置一致性（兼容旧结构） |
| `scripts/validate_doc_links.py` | 检查内部链接有效性 |
| `scripts/validate_doc_fields.py` | 检查必需字段完整性 |
| `scripts/doc_status.py` | 状态查询（见第五部分） |

---

## 八、工作流程文档化

### 8.1 补充 doc-workflows.md

在 `docs/00-governance/doc-workflows.md` 中补充：

```markdown
## Archive Workflow

### When to archive

- change doc 状态为 `done` 超过 30 天
- draft 已被提升或废弃超过 30 天
- ADR 已被 superseded

### Archive process

1. 确认文档状态为 `done`
2. 修改 Status 为 `archived`
3. 更新 Updated 字段
4. （可选）移动到子目录 `archived/` 便于物理隔离

### What to keep in archived docs

- 完整的变更历史
- 验证证据
- 决策理由

### What to remove

- 临时调试输出
- 过时的命令示例
- 已废弃的配置片段

## Periodic Cleanup Workflow

### Monthly tasks

- [ ] 检查 `drafts/` 目录，清理超过 60 天的草稿
- [ ] 检查 `done` 状态的文档，归档超过 30 天的文档
- [ ] 运行 `validate_doc_status.py` 检查一致性
- [ ] 运行 `validate_doc_links.py` 检查链接有效性

### Quarterly tasks

- [ ] 审查 ADR 是否需要更新或 supersede
- [ ] 审查 playbooks 是否需要补充
- [ ] 审查 reference docs 是否过时
```

### 8.2 完整任务生命周期图

```
┌─────────────────────────────────────────────────────────────────┐
│                     Task Lifecycle                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   [探索阶段]                                                      │
│      │                                                           │
│      ▼                                                           │
│   drafts/ ─────────────────────────────────────────────────────┐│
│      │                                                          ││
│      │ 任务明确后                                                ││
│      ▼                                                          ││
│   03-changes/<module>/draft.md                                  ││
│      │                                                          ││
│      │ 审批通过                                                  ││
│      ▼                                                          ││
│   03-changes/<module>/planned.md                                ││
│      │                                                          ││
│      │ 开始实施                                                  ││
│      ▼                                                          ││
│   03-changes/<module>/doing.md ◄───── (blocked)                 ││
│      │                                    ▲                     ││
│      │ 实施完成                           │ 阻塞                 ││
│      ▼                                    │                     ││
│   03-changes/<module>/done.md ────────────┘                     ││
│      │                                                          ││
│      │ 30 天后归档                                                ││
│      ▼                                                          ││
│   03-changes/<module>/archived.md                               ││
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                     Knowledge Promotion                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   done change doc ──┬──► module doc (行为改变)                  │
│                     ├──► ADR (架构决策)                          │
│                     ├──► playbook (可复用经验)                   │
│                     └──► reference doc (依赖知识)                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 九、迁移策略

### 9.1 渐进式迁移（推荐）

**原则**：不一次性批量迁移，而是在文档状态变更时顺便迁移

**步骤**：

1. **创建脚本** `scripts/doc_status.py`
   - 支持扫描新旧两种目录结构
   - 自动检测文档位置和状态

2. **更新规范** `docs/00-governance/doc-standards.md`
   - 定义新的目录结构规范
   - 定义新的状态值
   - 保留对旧结构的兼容说明

3. **新文档按新规范创建**
   - 直接放在模块根目录
   - 使用简化的状态值

4. **旧文档渐进迁移**
   - 当文档状态变更时，顺便移动到根目录
   - 更新状态字段为简化值
   - 优先级：低

5. **清理空目录**
   - 确认所有文档迁移后
   - 删除空的状态子目录

### 9.2 不要做的事

❌ **不要一次性批量迁移 quantaalpha 的 48 个文档**

原因：
1. 可能破坏文档间引用链接
2. 风险高，收益不明显
3. 没有紧急性

❌ **不要立即删除状态子目录**

原因：
1. 旧文档仍在使用
2. 需要渐进迁移
3. 保留一段时间作为过渡期

❌ **不要一次性创建所有校验脚本**

原因：
1. 需求不明确
2. 可能过度设计
3. 在实际使用中逐步完善

---

## 十、需要修改的文件

### 10.1 新增文件

| 文件 | 说明 | 优先级 |
|------|------|--------|
| `scripts/doc_status.py` | 状态查询脚本 | P0 |
| `docs/00-governance/agent-constraints.md` | Agent 行为约束 | P0 |
| `docs/00-governance/validation-checklist.md` | 内容校验清单 | P0 |
| `scripts/validate_doc_status.py` | 状态校验脚本 | P1 |
| `scripts/validate_doc_links.py` | 链接校验脚本 | P1 |
| `scripts/validate_doc_fields.py` | 字段校验脚本 | P1 |

### 10.2 修改文件

| 文件 | 修改内容 | 优先级 |
|------|----------|--------|
| `docs/00-governance/doc-standards.md` | 更新目录结构说明，定义新状态值 | P0 |
| `docs/00-governance/doc-workflows.md` | 更新状态变更流程，补充归档和清理流程 | P0 |
| `docs/00-governance/agent.md` | 添加脚本使用说明，添加约束摘要 | P0 |
| `docs/00-governance/rules.md` | 合并 `.trae/rules/aspipe.md` 内容 | P1 |

### 10.3 可删除内容（待迁移完成后）

- `docs/03-changes/<module>/draft/` 等子目录
- 相关的 `.gitkeep` 文件
- `.trae/rules/` 目录（内容已合并后）

---

## 十一、信息熵对比

| 操作 | 旧方案 | 新方案 | 收益 |
|------|--------|--------|------|
| 查看所有进行中任务 | 遍历多个子目录 | `doc_status.py list --status doing` | 单一入口 |
| 修改任务状态 | 移动文件 + 修改字段 | 仅修改字段 | 减少 50% 操作 |
| 查看某模块任务 | 遍历模块下多个子目录 | `doc_status.py list --module X` | 无需知道目录结构 |
| 统计任务分布 | 手动统计 | `doc_status.py summary` | 自动化 |
| 确认 Agent 行为边界 | 阅读多处规则文件 | 阅读 agent-constraints.md | 降低认知成本 |
| 验证文档一致性 | 人工检查 | 运行校验脚本 | 自动化 |

---

## 十二、风险与缓解

### 12.1 风险

| 风险 | 描述 | 影响 |
|------|------|------|
| **文档引用断裂** | 旧文档可能有相对路径引用 | 移动后会失效 |
| **Agent 不熟悉新规范** | 需要更新 agent.md | 短期混乱 |
| **迁移不完整** | 新旧结构并存导致混淆 | 中期混乱 |
| **脚本依赖** | 脚本故障导致查询失败 | 低 |

### 12.2 缓解措施

| 风险 | 缓解措施 |
|------|----------|
| **文档引用断裂** | 渐进迁移，不批量移动；脚本兼容新旧结构 |
| **Agent 不熟悉新规范** | 更新 agent.md；在 system prompt 中强调 |
| **迁移不完整** | 明确迁移时间线；不设置硬性截止日期 |
| **脚本依赖** | 脚本简单可维护；提供手动查询备选 |

---

## 十三、决策建议

### 13.1 推荐采纳

- ✅ 扁平化目录结构
- ✅ 状态内聚到文档字段
- ✅ 脚本驱动查询
- ✅ 渐进式迁移策略
- ✅ 集中 Agent 行为约束
- ✅ 建立自动化校验机制

### 13.2 需要确认

- ⏸️ 状态简化方案：`draft → planned → doing → done → archived`
  - 是否保留 `blocked` 作为子状态？
  - 是否需要更细粒度的状态？

### 13.3 不推荐

- ❌ 一次性批量迁移
- ❌ 立即删除旧目录结构
- ❌ 过度设计校验脚本

---

## 十四、下一步行动

如果方案确认，建议执行顺序：

1. [ ] 创建 `scripts/doc_status.py`（支持新旧两种模式）
2. [ ] 创建 `docs/00-governance/agent-constraints.md`
3. [ ] 创建 `docs/00-governance/validation-checklist.md`
4. [ ] 更新 `docs/00-governance/doc-standards.md`
5. [ ] 更新 `docs/00-governance/doc-workflows.md`
6. [ ] 更新 `docs/00-governance/agent.md`
7. [ ] 新文档按新规范创建
8. [ ] 旧文档渐进迁移（低优先级）
9. [ ] 创建校验脚本（可选，按需）

---

## 附录 A：状态查询脚本实现草案

```python
#!/usr/bin/env python3
"""
doc_status.py - Query and manage documentation status

Usage:
    python scripts/doc_status.py list [--status STATUS] [--module MODULE] [--owner OWNER]
    python scripts/doc_status.py summary
    python scripts/doc_status.py list --stale --days N
"""

import os
import re
import json
import argparse
from pathlib import Path
from typing import Optional

# Configuration
CHANGES_DIR = Path(__file__).parent.parent / "docs" / "03-changes"
VALID_STATUSES = {"draft", "planned", "doing", "done", "archived"}

def parse_doc_header(content: str) -> dict:
    """Parse YAML-like header from markdown content."""
    header = {}
    lines = content.split('\n')
    in_header = False
    
    for line in lines:
        if line.startswith('# '):
            break  # End of header
        if ':' in line and not line.startswith('---'):
            key, value = line.split(':', 1)
            header[key.strip()] = value.strip()
    
    return header

def scan_documents(changes_dir: Path) -> list:
    """Scan all change documents and extract status."""
    results = []
    
    for module_dir in changes_dir.iterdir():
        if not module_dir.is_dir():
            continue
        
        for doc_file in module_dir.glob("*.md"):
            try:
                content = doc_file.read_text()
                header = parse_doc_header(content)
                
                results.append({
                    "module": module_dir.name,
                    "file": doc_file.name,
                    "path": str(doc_file),
                    "status": header.get("Status", "unknown"),
                    "created": header.get("Created", "unknown"),
                    "updated": header.get("Updated", header.get("Created", "unknown")),
                    "owner": header.get("Owner", "unknown"),
                })
            except Exception as e:
                print(f"Error reading {doc_file}: {e}")
    
    return results

def list_documents(docs: list, status: Optional[str] = None, module: Optional[str] = None,
                   owner: Optional[str] = None, stale: bool = False, days: int = 7):
    """List documents matching criteria."""
    from datetime import datetime, timedelta
    
    filtered = docs
    
    if status:
        filtered = [d for d in filtered if d["status"] == status]
    
    if module:
        filtered = [d for d in filtered if d["module"] == module]
    
    if owner:
        filtered = [d for d in filtered if d["owner"] == owner]
    
    if stale:
        cutoff = datetime.now() - timedelta(days=days)
        stale_docs = []
        for d in filtered:
            try:
                updated = datetime.strptime(d["updated"], "%Y-%m-%d")
                if updated < cutoff:
                    stale_docs.append(d)
            except:
                pass
        filtered = stale_docs
    
    # Group by module
    by_module = {}
    for doc in filtered:
        if doc["module"] not in by_module:
            by_module[doc["module"]] = []
        by_module[doc["module"]].append(doc)
    
    # Output
    for module in sorted(by_module.keys()):
        print(f"\nModule: {module}")
        for doc in sorted(by_module[module], key=lambda x: x["created"]):
            print(f"├── {doc['file']}")
            print(f"│   Status: {doc['status']} | Created: {doc['created']} | Updated: {doc['updated']} | Owner: {doc['owner']}")
            if stale and doc.get("blocked_by"):
                print(f"│   ⚠️  Blocked by: {doc['blocked_by']}")
    
    print(f"\nTotal: {len(filtered)} document(s)")

def summary_documents(docs: list):
    """Show status summary."""
    from collections import defaultdict
    
    status_count = defaultdict(int)
    module_count = defaultdict(int)
    
    for doc in docs:
        status_count[doc["status"]] += 1
        module_count[doc["module"]] += 1
    
    print("\nStatus Summary:")
    for status in VALID_STATUSES:
        count = status_count.get(status, 0)
        print(f"  {status}:{' ' * (10 - len(status))}{count}")
    
    print("\nBy Module:")
    for module in sorted(module_count.keys()):
        count = module_count[module]
        print(f"  {module}:{' ' * (15 - len(module))}{count} documents")

def main():
    parser = argparse.ArgumentParser(description="Query documentation status")
    subparsers = parser.add_subparsers(dest="command")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List documents")
    list_parser.add_argument("--status", choices=VALID_STATUSES)
    list_parser.add_argument("--module")
    list_parser.add_argument("--owner")
    list_parser.add_argument("--stale", action="store_true")
    list_parser.add_argument("--days", type=int, default=7)
    list_parser.add_argument("--json", action="store_true")
    
    # Summary command
    subparsers.add_parser("summary", help="Show status summary")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    docs = scan_documents(CHANGES_DIR)
    
    if args.command == "list":
        if args.json:
            # Filter first
            filtered = docs
            if args.status:
                filtered = [d for d in filtered if d["status"] == args.status]
            if args.module:
                filtered = [d for d in filtered if d["module"] == args.module]
            if args.owner:
                filtered = [d for d in filtered if d["owner"] == args.owner]
            print(json.dumps(filtered, indent=2))
        else:
            list_documents(docs, args.status, args.module, args.owner, args.stale, args.days)
    elif args.command == "summary":
        summary_documents(docs)

if __name__ == "__main__":
    main()
```

---

## 附录 B：与原有方案的对比

| 维度 | 原有详细方案 | 简化方案 | 本优化方案 |
|------|-------------|----------|-----------|
| 目录层级 | 8 层状态子目录 | 扁平 | 扁平 |
| 状态数量 | 8 个 | 5 个 | 5 个 |
| 规则文件 | 分散多处 | 未涉及 | 集中一处 |
| Agent 约束 | 分散 | 未涉及 | 集中声明 |
| 校验机制 | 缺失 | 未涉及 | 自动化 |
| 归档流程 | 缺失 | 未涉及 | 明确文档化 |
| 迁移策略 | 未明确 | 渐进式 | 渐进式 |

本方案整合了原有两个方案的优点，并补充了：
1. Agent 行为约束集中化
2. 内容校验自动化
3. 归档和清理流程文档化
4. 规则文件合并
