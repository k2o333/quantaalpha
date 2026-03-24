# OPUPS: Optimized Pipeline Unified Process for Documentation System

Status: draft
Created: 2026-03-21
Owner: quan
Contributors: Antigravity AI

---

## 摘要

本方案针对 `aspipe_v4/docs` 文档体系的五大核心问题提出**统一优化方案**：

1. **目录级状态淘汰** — 消除 `03-changes/<module>/planned/` 等 8 层嵌套，文档扁平存放、状态内聚到文档头部
2. **agent.md 精准导航** — 重构导览文件为"零歧义路由表"，agent 读一个文件即可定位所有资源
3. **自动化校验** — 单脚本 `doc_check.sh` 覆盖字段完整性、链接有效性、状态合法性
4. **行为约束集中化** — 将散落在 `rules.md`、`development-workflow.md`、`.trae/rules/` 的 agent 约束收敛为 `rules.md` 内的一个明确章节
5. **生命周期工作流** — 用一张状态机图 + 一个脚本替代当前 7 个文件的分散描述

**核心设计原则**：信息只写一次（Single Source of Truth），状态只存一处（文档头部），查询只用一个命令。

---

## 一、现状诊断

### 1.1 量化分析

| 指标 | 当前值 | 问题 |
|------|--------|------|
| `03-changes/quantaalpha` 子目录数 | 8 (draft/planned/in_progress/blocked/implemented/tested/accepted/archived) | 目录结构膨胀 |
| `03-changes/app4` 子目录数 | 8（全部为空） | 无效目录占位 |
| quantaalpha 文档总数 | 48 | 分散在 8 个子目录 + 更深的 parr2/parrelell 嵌套 |
| app4 文档总数 | 27 | 全部在根目录，子目录未使用 |
| 状态变更操作步骤 | 2 步（移动文件 + 改字段） | 双写同步，易遗漏 |
| agent 需阅读的治理文件 | 7 个 | agent.md → rules.md → doc-rules.md → doc-standards.md → doc-workflows.md → development-workflow.md → doc-task-template.md |
| 规则定义位置 | 2 处 (`docs/00-governance/` + `.trae/rules/`) | 信息冗余 |
| 自动化校验脚本 | 0 | 完全依赖人工 |

### 1.2 信息熵核心矛盾

**问题一：目录-即-状态 的设计缺陷**

```
# 当前：状态 = 目录位置 + Status字段（双写）
docs/03-changes/quantaalpha/planned/2026-03-15-iterate2-01.md
                            ^^^^^^^^^^^                         ← 目录表达状态
内部 Status: planned                                             ← 字段也表达状态
```

这要求两处必须同步。app4 已经证明没人会把文件移到子目录里——27 个文件全部放在根目录、8 个子目录全部为空。

**问题二：治理文件爆炸**

agent 每次任务开始前的"必读路径"：

```
agent.md → rules.md → doc-rules.md → doc-standards.md → doc-workflows.md
           ↑                  ↑
     重复约束              路由到 doc-workflows.md 和 doc-standards.md
```

其中 `doc-rules.md` 本质上只是 `doc-workflows.md` 和 `doc-standards.md` 的路由表，增加了一次不必要的间接跳转。

**问题三：quantaalpha/planned/ 下的二级嵌套**

```
planned/
├── parr2/debug/    ← 4 个 .task.md
├── parr2/dev/      ← 4 个 .task.md
├── parr2/test/     ← 4 个 .task.md
├── parrelell/      ← 4 个 .md
├── parrelell/dev/  ← 4 个 .task.md
└── parrelell/review/ ← 4 个 .task.md
```

这是目录结构最深的区域，agent 需要遍历 3 层以上才能找到具体文档。

---

## 二、目标架构

### 2.1 设计原则

| 原则 | 含义 |
|------|------|
| **状态内聚** | 状态仅存在于文档头部 `Status:` 字段，不通过目录表达 |
| **扁平存储** | `03-changes/<module>/` 下直接放文档，禁止状态子目录 |
| **脚本即索引** | 用 `doc_check.sh` 一个脚本做状态查询 + 校验，替代目录遍历 |
| **治理文件收敛** | agent 必读文件从 7 个降到 2 个：`agent.md` + `rules.md` |
| **约束集中** | 所有 agent 行为约束写在 `rules.md` 一处 |

### 2.2 目标目录结构

```text
docs/
├── 00-governance/
│   ├── agent.md              # Agent 唯一入口：路由表 + 约束摘要 + 验证入口
│   ├── rules.md              # 唯一规则来源：行为约束 + 分支策略 + 审查要求
│   ├── doc-standards.md      # 文档类型/命名/头部格式定义（合并原 doc-rules.md 内容）
│   ├── doc-workflows.md      # 文档生命周期流程
│   └── development-workflow.md  # 研发流程细节
│
├── 01-overview/
│   └── system-overview.md
│
├── 02-modules/
│   ├── app4.md
│   ├── quantaalpha.md
│   └── backtest.md
│
├── 03-changes/               # 扁平化
│   ├── app4/
│   │   ├── 2026-02-25-cyq-chips-offset-pagination-fix.md
│   │   └── ...               # 27 个文件不动
│   ├── quantaalpha/
│   │   ├── 2026-03-15-iterate2-01-revalidate-semantics.md
│   │   ├── 2026-03-15-iterate2-02-failed-factor-debug.md
│   │   └── ...               # 渐进迁移后全部在根目录
│   ├── backtest/
│   ├── common/
│   └── vnpy/                 # reserved
│
├── 04-decisions/             # ADR 不变
├── 05-playbooks/             # 不变
├── 06-references/            # 不变
├── 07-technical/             # 不变
├── drafts/                   # 不变
└── superpowers/              # 不变
```

**关键变化**：
- `03-changes/<module>/` 下**没有** `draft/planned/in_progress/...` 子目录
- `00-governance/` 从 7 个文件减少到 5 个（删除 `doc-rules.md` 和 `doc-task-template.md`）

### 2.3 状态模型简化

**当前（8 + 2 个状态）**：
```
draft → planned → in_progress → blocked → implemented → tested → accepted → archived
                                                                  active, superseded
```

**目标（5 + 2 个状态）**：

| 状态 | 含义 | 合并了旧状态 |
|------|------|-------------|
| `draft` | 探索中，未确定实施 | draft |
| `planned` | 已批准，待开始 | planned |
| `doing` | 实施中（可用 `Blocked-by:` 标记阻塞） | in_progress, blocked |
| `done` | 已完成并验证 | implemented, tested, accepted |
| `archived` | 已归档 | archived |
| `active` | 当前有效的正式文档 | active（用于 module doc/ADR 等） |
| `superseded` | 已被新版替代 | superseded |

**简化理由**：
- `implemented/tested/accepted` 三态对单人开发 + AI 协作项目区分度不足
- `blocked` 通过 `doing` + `Blocked-by:` 字段表达更灵活
- 状态从 10 个降到 7 个，减少 30% 认知负担

---

## 三、agent.md 重构

### 3.1 新版 agent.md 设计目标

agent 读完 `agent.md` 后，应该能够：
1. 知道项目是什么（一句话）
2. 定位到任何任务需要的下一个文件（路由表）
3. 知道自己不能做什么（约束摘要）
4. 知道验证命令（代码入口 + 验证命令）
5. 知道如何查询文档状态（脚本用法）

### 3.2 新版 agent.md 结构提案

```markdown
# aspipe_v4 Agent Entry

## Read This First

1. 读本文件，定位任务目标
2. 读 `rules.md` 了解约束和审查要求
3. 根据路由表定位目标文档
4. 完成任务前运行验证

## Project In One Sentence

`aspipe_v4` is a config-driven financial data pipeline:
`app4` downloads data, `quantaalpha` mines factors, `backtest` validates strategies.

## Task Routing

| 任务类型 | 下一步阅读 |
|----------|-----------|
| 整体仓库结构 | `docs/01-overview/system-overview.md` |
| app4 下载/存储/更新 | `docs/02-modules/app4.md` |
| quantaalpha 因子挖掘 | `docs/02-modules/quantaalpha.md` |
| backtest 回测脚本 | `docs/02-modules/backtest.md` |
| 执行流详细调用链 | `docs/07-technical/*.md` |
| 某模块的变更实施记录 | `docs/03-changes/<module>/`.<br>用 `scripts/doc_check.sh status --module <module>` 查询 |
| 长期架构决策 | `docs/04-decisions/` |
| 可复用工程经验 | `docs/05-playbooks/` |
| Agent 交付质量审计 | `docs/05-playbooks/agent-delivery-audit-playbook.md` |
| planned 文档加固 | `docs/05-playbooks/planned-doc-hardening-playbook.md` |
| 上游框架用法 | `docs/06-references/` |
| 文档标准/命名/格式 | `docs/00-governance/doc-standards.md` |
| 文档生命周期流程 | `docs/00-governance/doc-workflows.md` |
| 分支/研发流程 | `docs/00-governance/development-workflow.md` |

## Constraints Summary

完整约束见 `rules.md`，此处列出核心禁止项：

**绝对禁止**（未经人类明确授权）：
- ❌ 修改 `docs/00-governance/` 下任何文件
- ❌ 删除任何文档
- ❌ 将 `docs/drafts/` 内容视为当前事实
- ❌ 自动合并到 main 分支
- ❌ 修改 `third_party/vnpy/` 或 `third_party/glue/`
- ❌ 创建新 ADR 而不经人类审批

**每次任务结束前必须**：
- ✅ 更新或创建 change doc
- ✅ 运行验证并记录结果
- ✅ 判断是否需要更新模块文档
- ✅ 高风险变更必须停下等待人工审查

## Code Entrypoints

（保留当前 agent.md 中的 Code Entrypoints 和 Validation Entrypoints，不变）

## Document Status Query

```bash
# 查看某模块所有活跃任务
scripts/doc_check.sh status --module quantaalpha --status doing

# 查看所有模块的状态统计
scripts/doc_check.sh status --summary

# 运行完整文档校验
scripts/doc_check.sh validate
```

## Do Not Assume

- `docs/drafts/` 不是事实来源
- `docs/02-modules/*.md` 定义当前有效状态
- `docs/03-changes/` 提供实施上下文，不是当前事实
- 测试通过不能替代 `rules.md` 中的审查规则
```

### 3.3 与当前 agent.md 的差异

| 维度 | 当前 | 新版 | 收益 |
|------|------|------|------|
| 约束信息 | 无（需跳转 rules.md） | 内嵌核心禁止项摘要 | agent 提前预知边界 |
| 状态查询 | 无 | 内嵌脚本用法 | agent 可直接查询任务状态 |
| 路由项 | 13 项 | 15 项（增加文档标准和研发流程） | 覆盖更完整 |
| 导航到 changes | 需要知道目录嵌套结构 | 用脚本查询 | 无需了解目录结构 |

---

## 四、治理文件收敛

### 4.1 合并策略

| 操作 | 说明 |
|------|------|
| **删除** `doc-rules.md` | 其内容（核心原则 + 路由表 + 默认关闭顺序 + 最小规则）全部并入 `doc-standards.md` |
| **删除** `doc-task-template.md` | 模板内容并入 `doc-standards.md` 的 Change Doc 章节 |
| **合并** `.trae/rules/aspipe.md` | 有价值内容并入 `rules.md`，`.trae/rules/` 可保留但标记为 deprecated |
| **扩展** `rules.md` | 增加 "Agent Behavior Constraints" 章节，集中所有行为约束 |
| **简化** `doc-standards.md` | 删除 8 层状态子目录的定义，改为扁平结构规范 |

### 4.2 agent 必读路径对比

**当前**（5 跳）：
```
agent.md → rules.md → doc-rules.md → doc-standards.md → doc-workflows.md
                                         ↓
                                    doc-task-template.md
```

**目标**（2 跳）：
```
agent.md → rules.md
```

只有当 agent 需要创建/修改文档时，才需要额外读 `doc-standards.md`。

### 4.3 rules.md 新增章节：Agent Behavior Constraints

在现有 `rules.md` 的 "Forbidden Behavior" 后追加：

```markdown
## Agent Behavior Constraints

### Prohibited Actions（未经人类明确授权）

| 行为 | 原因 |
|------|------|
| 修改 `docs/00-governance/` 下任何文件 | 治理文档变更需人工审批 |
| 创建新 ADR | 架构决策需人工审批 |
| 删除任何文档 | 可能丢失历史上下文 |
| 修改 `third_party/vnpy/` 或 `third_party/glue/` | 非默认编辑目标 |
| 自动合并 main | 需人工确认 |
| 将 drafts 视为当前事实 | drafts 是探索性内容 |

### Conditional Actions（满足条件后可执行）

| 行为 | 允许条件 |
|------|----------|
| 修改模块文档 | change doc 已 done 且行为确实改变 |
| 归档 change doc | 状态为 done 超过 30 天 |

### Task Start Checklist

任务开始时 agent 必须确认：
- [ ] 目标模块
- [ ] 目标文件
- [ ] 验证范围
- [ ] 是否需要人工审查（参考 rules.md 的 Human Review Required 章节）

### Task End Checklist

任务结束时 agent 必须：
- [ ] 更新或创建 change doc
- [ ] 执行验证并记录命令和结果
- [ ] 判断是否需要更新模块文档
- [ ] 高风险变更停止等待人工审查

### Risk-Based Review Matrix

| 风险 | 场景 | 审查要求 |
|------|------|----------|
| 低 | 文档修正、日志调整、注释 | 无需人工审查 |
| 中 | 单模块 Bug 修复、配置调整 | 建议人工审查 |
| 高 | 分页/存储/去重/Schema/并发 | **必须人工审查** |
```

---

## 五、文档状态管理

### 5.1 文档头部格式（新标准）

```yaml
# 文档标题

Status: planned
Module: quantaalpha
Created: 2026-03-21
Updated: 2026-03-22
Owner: quan
Blocked-by:                    # 可选，仅 Status=doing 且被阻塞时填写

---
```

**字段说明**：

| 字段 | 必填 | 规则 |
|------|------|------|
| `Status` | 是 | 枚举：draft/planned/doing/done/archived/active/superseded |
| `Module` | 是（change doc） | 所属模块名 |
| `Created` | 是 | 创建日期 YYYY-MM-DD |
| `Updated` | 是 | 最后更新日期，状态变更时必须同步 |
| `Owner` | 是 | 责任人 |
| `Blocked-by` | 否 | 阻塞原因描述 |

### 5.2 状态变更流程

**旧流程**（2 步）：
```
1. 修改 Status 字段
2. 将文件从 planned/ 移动到 in_progress/
```

**新流程**（1 步）：
```
1. 修改 Status 字段 + 更新 Updated 日期
```

### 5.3 状态生命周期

```
                         ┌──────────────────────────────────────┐
                         │          Knowledge Promotion          │
                         ├──────────────────────────────────────┤
                         │ done change doc ─┬─► module doc      │
                         │                  ├─► ADR             │
                         │                  ├─► playbook        │
                         │                  └─► reference doc   │
                         └──────────────────────────────────────┘
                                        ▲
                                        │
  drafts/         03-changes/<module>/
  ───────         ─────────────────────────────────────────────
  探索            draft → planned → doing ←→ blocked → done → archived
                                    (Blocked-by字段)
                                        │
                                        ▼
                              修改 Status 字段即可
                              无需移动文件
```

---

## 六、自动化校验脚本

### 6.1 统一脚本 `scripts/doc_check.sh`

**设计原则**：一个脚本，两个子命令（`status` 和 `validate`），替代人工遍历。

### 6.2 用法

```bash
# ─── 状态查询 ───

# 查看所有 doing 任务
scripts/doc_check.sh status --status doing

# 查看某模块的状态
scripts/doc_check.sh status --module quantaalpha

# 全局状态统计
scripts/doc_check.sh status --summary

# 查看超过 N 天未更新的任务
scripts/doc_check.sh status --stale 7

# JSON 输出（供其他工具消费）
scripts/doc_check.sh status --status doing --json

# ─── 校验 ───

# 运行全部校验
scripts/doc_check.sh validate

# 只检查字段完整性
scripts/doc_check.sh validate --fields

# 只检查内部链接
scripts/doc_check.sh validate --links

# 只检查 agent.md 路由表中的文件是否存在
scripts/doc_check.sh validate --routes
```

### 6.3 输出示例

```bash
$ scripts/doc_check.sh status --summary

  Status Summary
  ──────────────
  draft:      5
  planned:    8
  doing:      3
  done:      12
  archived:  10

  By Module
  ─────────
  app4:         27 docs
  quantaalpha:  48 docs
  common:        3 docs

$ scripts/doc_check.sh validate

  [PASS] Field completeness: 78/78 docs have required headers
  [FAIL] Link integrity: 2 broken links found
         - docs/03-changes/quantaalpha/2026-03-14-xxx.md:15 → docs/drafts/nonexistent.md
         - docs/05-playbooks/xxx.md:42 → docs/03-changes/quantaalpha/planned/old-file.md
  [PASS] Route table: all 15 entries in agent.md point to existing paths
  [WARN] Stale documents: 3 docs with Status=doing unchanged for >7 days
```

### 6.4 校验规则

| 校验项 | 规则 | 严重度 |
|--------|------|--------|
| Status 字段存在 | change doc 必须有 Status 字段 | ERROR |
| Status 值合法 | 必须是 draft/planned/doing/done/archived/active/superseded 之一 | ERROR |
| Created 字段存在 | 所有文档必须有 Created 日期 | ERROR |
| Owner 字段存在 | change doc 必须有 Owner | WARNING |
| 内部链接有效 | markdown 中引用的相对路径文件必须存在 | ERROR |
| 路由表有效 | agent.md 中引用的文件路径必须存在 | ERROR |
| 过期检查 | Status=doing 超过 7 天未更新 Updated | WARNING |
| Module 字段匹配 | Module 字段值应与所在目录名一致 | WARNING |

### 6.5 实现策略

使用 **Bash + grep/awk** 实现，不依赖 Python：
- 项目已有 sh 脚本约定（`auto/scripts/` 下有 bash 脚本）
- 减少 agent 运行脚本的环境依赖
- 简单易维护，不需要额外安装包

---

## 七、完整工作流文档化

### 7.1 任务全生命周期

```
┌─────────────────────────────────────────────────────────┐
│                    Task Lifecycle                         │
├─────────┬───────────────────────────────────────────────┤
│ 阶段     │ 操作                                          │
├─────────┼───────────────────────────────────────────────┤
│ 探索     │ 在 docs/drafts/ 写草稿                        │
│         │ Status: draft                                  │
│         │ 目标: 厘清问题，不需要模块定位                    │
├─────────┼───────────────────────────────────────────────┤
│ 定义     │ 提升为 03-changes/<module>/                    │
│         │ Status: draft → planned                        │
│         │ 目标: 明确实施范围、验证计划                      │
│         │ 交付物: change doc with 完整头部字段              │
├─────────┼───────────────────────────────────────────────┤
│ 实施     │ 修改 Status: doing                             │
│         │ 目标: 编码、配置、测试                           │
│         │ 如果被阻塞: 填写 Blocked-by 字段，Status 保持 doing│
├─────────┼───────────────────────────────────────────────┤
│ 完成     │ 修改 Status: done                              │
│         │ 目标: 验证通过、change doc 记录完整              │
│         │ 判断: 是否需要更新 module doc / ADR / playbook   │
├─────────┼───────────────────────────────────────────────┤
│ 归档     │ 修改 Status: archived                          │
│         │ 时机: done 超过 30 天                            │
│         │ 保留: 变更历史、验证证据、决策理由               │
│         │ 删除: 临时调试输出、过时命令示例                  │
└─────────┴───────────────────────────────────────────────┘
```

### 7.2 知识提升路径

任务完成后，检查以下提升路径：

| 产出类型 | 目标位置 | 触发条件 |
|----------|----------|----------|
| 模块行为变更 | `docs/02-modules/<module>.md` | 模块责任/接口/Schema/边界变更 |
| 长期架构决策 | `docs/04-decisions/ADR-XXX.md` | 影响多模块的策略决策 |
| 可复用工程经验 | `docs/05-playbooks/` | 跨任务可复用的模式或教训 |
| 依赖使用知识 | `docs/06-references/` | 框架/库的项目特定用法 |

### 7.3 文档清理周期

| 频率 | 动作 |
|------|------|
| 每次任务结束 | 更新 change doc，判断提升路径 |
| 每月 | `doc_check.sh validate` + 清理 doing 超 7 天的文档 + 归档 done 超 30 天的文档 |
| 每季度 | 审查 ADR 是否需要 supersede + 审查 playbooks 是否需要补充 |
| 每季度 | 清理 `docs/drafts/` 中超过 60 天未活跃的草稿 |

---

## 八、迁移策略

### 8.1 原则

**渐进式迁移，不批量变更，兼容过渡期**。

### 8.2 执行顺序

| 步骤 | 内容 | 优先级 | 风险 |
|------|------|--------|------|
| 1 | 创建 `scripts/doc_check.sh`（同时支持旧嵌套和新扁平结构） | P0 | 低 |
| 2 | 更新 `rules.md` 追加 Agent Behavior Constraints 章节 | P0 | 低 |
| 3 | 重构 `agent.md` 为新版路由表 | P0 | 中 |
| 4 | 更新 `doc-standards.md`（合并 doc-rules.md 内容，定义新状态模型） | P0 | 中 |
| 5 | 更新 `doc-workflows.md`（简化状态转换描述，去除目录移动要求） | P1 | 低 |
| 6 | 新文档一律按新规范创建（扁平存放 + 简化状态） | P1 | 低 |
| 7 | 旧文档在状态变更时顺便迁移到模块根目录 | P2 | 低 |
| 8 | 确认所有迁移完成后删除空的状态子目录 | P3 | 低 |

### 8.3 不要做的事

- ❌ 不要一次性批量移动 quantaalpha 的 48 个文档
- ❌ 不要立即删除旧的状态子目录
- ❌ 不要删除 `.trae/rules/`（标记 deprecated 即可）
- ❌ 不要在迁移完成前删除 `doc-rules.md`（先标注 superseded）

### 8.4 兼容策略

`doc_check.sh` 在过渡期内同时扫描两种结构：
```bash
# 旧结构：docs/03-changes/<module>/<status>/*.md
# 新结构：docs/03-changes/<module>/*.md
# 脚本自动检测并正确解析
```

---

## 九、信息熵对比

| 操作 | 旧方案 | 新方案 | 改进 |
|------|--------|--------|------|
| Agent 准备阶段 | 读 5-7 个文件 | 读 2 个文件 (agent.md + rules.md) | **-60% 阅读量** |
| 查看所有进行中任务 | 遍历多个子目录 | `doc_check.sh status --status doing` | **单一命令** |
| 修改任务状态 | 移动文件 + 修改字段 | 仅修改字段 | **-50% 操作** |
| 查看某模块任务 | 遍历模块下 8 个子目录 | `doc_check.sh status --module X` | **无需知道目录结构** |
| 统计任务分布 | 手动 find + 计数 | `doc_check.sh status --summary` | **自动化** |
| 验证文档一致性 | 人工逐个检查 | `doc_check.sh validate` | **自动化** |
| 确认 agent 约束 | 阅读多处规则文件 | `agent.md` 有摘要 + `rules.md` 有完整定义 | **最多 2 跳** |
| 定位变更文档 | 需要知道 `<module>/<status>/` | 只需知道 `<module>/` | **减少 1 层路径** |

---

## 十、与已有两份提案的对比

| 维度 | simplification 提案 | optimization 提案 | 本方案 (OPUPS) |
|------|---------------------|-------------------|----------------|
| 核心思路 | 扁平化 + 脚本查询 | 扁平化 + 约束 + 校验 | 扁平化 + 治理收敛 + 脚本统一 |
| 状态数量 | 5 个 | 5 个 | 7 个（含 active/superseded） |
| 治理文件合并 | 未涉及 | 新增 2 个文件 | **减少** 2 个文件 |
| 脚本实现 | Python | Python | **Bash**（零依赖） |
| agent.md 改进 | 添加脚本说明 | 添加约束摘要 | **完整重构**路由表 + 约束 + 脚本 |
| 新增文件 | 1 个脚本 | 3 个文件 + 3 个脚本 | **1 个脚本**（doc_check.sh） |
| doc-rules.md | 保留 | 保留 | **合并到 doc-standards.md** |
| 约束位置 | 未涉及 | 新增 agent-constraints.md | **写入 rules.md**（不新增文件） |
| 校验机制 | 未涉及 | 3 个独立校验脚本 | 1 个统一校验脚本 |

**OPUPS 的核心差异**：
1. **做减法而不是加法**：不新增治理文件，而是合并减少
2. **一个脚本做所有事**：`doc_check.sh` = 状态查询 + 校验，替代 4 个 Python 脚本
3. **约束不独立成文件**：Agent 行为约束写在 `rules.md` 中，而不是新建 `agent-constraints.md`
4. **消灭不必要的间接跳转**：`doc-rules.md` 只是一个路由中转站，直接合并消除

---

## 十一、待确认事项

1. **状态模型**：`done` 是否足以覆盖原 `implemented/tested/accepted` 三态？是否需要保留 `accepted` 用于明确人工验收？
2. **`doc-rules.md` 删除时机**：是立即删除还是先标注 `superseded` 保留一段时间？
3. **`doc-task-template.md`**：模板内容并入 `doc-standards.md` 是否合适？还是保留独立文件？
4. **脚本语言**：Bash 实现是否满足需求？如果未来需要更复杂的查询，是否需要 Python 作为备选？
5. **`.trae/rules/` 处理**：标记 deprecated 后何时正式删除？

---

## 十二、下一步行动

如果方案确认，建议执行顺序：

1. [ ] 创建 `scripts/doc_check.sh`（兼容新旧目录结构）
2. [ ] 更新 `docs/00-governance/rules.md`（追加 Agent Behavior Constraints 章节）
3. [ ] 重构 `docs/00-governance/agent.md`（新版路由表 + 约束摘要 + 脚本用法）
4. [ ] 更新 `docs/00-governance/doc-standards.md`（合并 doc-rules.md + 新状态模型）
5. [ ] 更新 `docs/00-governance/doc-workflows.md`（简化状态转换 + 补充归档流程）
6. [ ] 标记 `doc-rules.md` 为 superseded（在文件头部加 `Status: superseded`）
7. [ ] 新文档按新规范创建
8. [ ] 旧文档渐进迁移（低优先级）
