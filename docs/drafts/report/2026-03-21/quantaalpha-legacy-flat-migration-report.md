# quantaalpha 活跃 Legacy Change Doc 扁平化迁移报告

Date: 2026-03-21
Operator: opencode agent
Playbook: `docs/05-playbooks/03-changes-flat-migration-playbook.md`
Task Scope: 迁移 `docs/03-changes/quantaalpha/planned/`、`in_progress/`、`blocked/` 中的活跃 legacy change docs 至模块扁平路径 `docs/03-changes/quantaalpha/YYYY-MM-DD-*.md`
Constraint: 不得修改 `docs/00-governance/`

---

## 一、任务前置

根据 `agent.md` 要求，任务开始前阅读了以下文件：

1. `docs/00-governance/agent.md` — 确认了工作流优先级、路由规则和验证入口
2. `docs/00-governance/rules.md` — 确认了禁止创建新 status 子目录、change doc status 应存在于 metadata 等强制规则
3. `docs/05-playbooks/03-changes-flat-migration-playbook.md` — 确认了迁移步骤、metadata 规范、引用更新范围和完成判据
4. `docs/00-governance/doc-validation.md` — 确认了验证规则和 `scripts/doc_index.py` 的角色

## 二、扫描与盘点

### 2.1 Legacy 活跃目录扫描结果

对所有模块执行 `find <module>/{planned,in_progress,blocked} -name "*.md" -not -name "README.md"`，结果如下：

| 模块 | planned | in_progress | blocked | 合计 |
|---|---|---|---|---|
| app4 | 0 | 0 | 0 | 0 |
| quantaalpha | 27 | 0 | 0 | 27 |
| backtest | 0 | 0 | 0 | 0 |
| common | 0 | 0 | 0 | 0 |
| vnpy | 0 | 0 | 0 | 0 |

**quantaalpha/planned/** 中实际内容分类：

- 7 篇主计划文档（iterate2 系列 + orchestrator + data-capability-registry）
- 4 篇 parallel slice 文档（`parrelell/` 子目录）
- 16 篇 `.task.md` 文件（dev/test/review 阶段 agent 任务文档）
- 2 篇 README.md

### 2.2 迁移决策

根据 playbook **Core Rule** 和 **Do Not Over-Migrate** 原则：

- **迁移**：7 篇主计划文档 + 4 篇 parallel slice 文档（source-of-truth change docs）
- **不迁移**：16 篇 `.task.md` 文件（agent 任务执行产物，不是 source-of-truth change doc）
- **不迁移**：2 篇 README.md（索引页面，不是 change doc）
- **不更新**：`docs/drafts/` 下对 legacy 路径的历史引用（playbook 明确说不要在同一次 pass 中清理历史草稿引用）

### 2.3 迁移前 Baseline 验证

执行 `python3 scripts/doc_index.py validate` 得到 26 个 validation issues，全部为 `app4/` 模块的已存在 flat docs 缺少 `status` metadata，与本次迁移无关。

执行 `python3 scripts/doc_index.py list --type change --module quantaalpha --status planned --json` 得到 29 篇 planned 文档（含 legacy 路径中的文档）。

## 三、迁移操作详情

### 3.1 7 篇主计划文档

对每篇文档执行了：

1. **Metadata 规范化**：将旧的 header 字段（`Status: planned`、`Priority: P0`、`Depends-on: ...`）替换为标准 YAML front matter：
   - `doc_type: change`
   - `module: quantaalpha`
   - `status: planned`
   - `owner: quan`（从 owner 字段或 agent 记录中获取）
   - `created: <date>`（从文件名日期或创建记录中获取）
   - `updated: <date>`
   - `summary: <one-line>`
   - 保留原有 `priority`、`depends_on` 等可选字段

2. **路径迁移**：从 `docs/03-changes/quantaalpha/planned/<file>.md` 迁移到 `docs/03-changes/quantaalpha/<file>.md`

3. **引用更新**：更新 `implemented/2026-03-20-iterate2-deferred-followups.md` 中的 `Depends-on` 路径，从绝对路径 `/home/quan/testdata/aspipe_v4/docs/03-changes/quantaalpha/planned/` 改为相对路径 `docs/03-changes/quantaalpha/`；同时将 `depends_on` 中的绝对路径改为相对路径

| # | Source | Target | Old Status | New Status |
|---|---|---|---|---|
| 1 | `planned/2026-03-15-iterate2-01-revalidate-semantics-and-real-backtest.md` | `2026-03-15-iterate2-01-revalidate-semantics-and-real-backtest.md` | planned (path) | `status: planned` |
| 2 | `planned/2026-03-15-iterate2-02-failed-factor-debug-filter.md` | `2026-03-15-iterate2-02-failed-factor-debug-filter.md` | planned (path) | `status: planned` |
| 3 | `planned/2026-03-15-iterate2-03-quality-gate-and-state-regression.md` | `2026-03-15-iterate2-03-quality-gate-and-state-regression.md` | planned (path) | `status: planned` |
| 4 | `planned/2026-03-15-iterate2-04-external-scheduler-summary-and-audit.md` | `2026-03-15-iterate2-04-external-scheduler-summary-and-audit.md` | planned (path) | `status: planned` |
| 5 | `planned/2026-03-15-iterate2-05-factor-library-write-lock.md` | `2026-03-15-iterate2-05-factor-library-write-lock.md` | planned (path) | `status: planned` |
| 6 | `planned/2026-03-18-continuous-orchestrator-minimal-skeleton.md` | `2026-03-18-continuous-orchestrator-minimal-skeleton.md` | planned (path) | `status: planned` |
| 7 | `planned/2026-03-18-data-capability-registry-reintegration.md` | `2026-03-18-data-capability-registry-reintegration.md` | planned (path) | `status: planned` |

### 3.2 4 篇 Parallel Slice 文档

这些文档原本在 `planned/parrelell/` 子目录中（含 typo "parrelell" 而非 "parallel"）。对每篇执行了：

1. **Metadata 规范化**：保留原有的 `parallel_mode`、`parallel_group`、`slice_id`、`parent_source_docs` 等字段，增加标准字段：`doc_type: change`、`module: quantaalpha`、`updated: 2026-03-18`、`summary`
2. **parent_source_docs 路径修正**：将 `docs/03-changes/quantaalpha/planned/2026-03-15-iterate2-*.md` 改为相对路径 `2026-03-15-iterate2-*.md`（已被迁移到 flat path）
3. **路径迁移**：从 `planned/parrelell/<file>.md` 迁移到 `docs/03-changes/quantaalpha/<file>.md`

| # | Source | Target | Old Status | New Status |
|---|---|---|---|---|
| 8 | `planned/parrelell/2026-03-18-parallel-01-revalidate-cli-modes.md` | `2026-03-18-parallel-01-revalidate-cli-modes.md` | planned (path) | `status: planned` |
| 9 | `planned/parrelell/2026-03-18-parallel-02-real-backtest-library-ops.md` | `2026-03-18-parallel-02-real-backtest-library-ops.md` | planned (path) | `status: planned` |
| 10 | `planned/parrelell/2026-03-18-parallel-03-debug-failure-filter.md` | `2026-03-18-parallel-03-debug-failure-filter.md` | planned (path) | `status: planned` |
| 11 | `planned/parrelell/2026-03-18-parallel-04-quality-gate-and-state-regression.md` | `2026-03-18-parallel-04-quality-gate-and-state-regression.md` | planned (path) | `status: planned` |

### 3.3 引用更新

仅更新了 1 处高价值引用：

- `docs/03-changes/quantaalpha/implemented/2026-03-20-iterate2-deferred-followups.md` 中的 5 条 `Depends-on` 路径，从 absolute path `/home/quan/testdata/aspipe_v4/docs/03-changes/quantaalpha/planned/...` 改为相对路径 `docs/03-changes/quantaalpha/...`

未更新的引用（per playbook 不在同一次 pass 清理的范围）：

- `docs/drafts/` 下对 legacy planned 路径的引用（历史草稿和报告）
- `.task.md` 文件中对 slice doc 的引用（operational artifacts，非 source-of-truth）
- batch status JSON 文件中的路径（系统运行产物）

## 四、验证结果

### 4.1 `python3 scripts/doc_index.py validate`

```
Validation issues:
- 03-changes/app4/2026-02-25-cyq-chips-offset-pagination-fix.md: missing status
- 03-changes/app4/2026-02-25-disclosure-date-duplicate-save-analysis.md: missing status
- ... (26 issues, all pre-existing in app4 module)
```

**结论**：迁移后的 11 篇 quantaalpha 文档均无 validation issues。26 个 pre-existing issues 来自 `app4/` 模块，不在本次任务范围。

### 4.2 `python3 scripts/doc_index.py list --type change --module quantaalpha --status planned --json`

结果：29 篇 planned 文档，其中 11 篇已在 flat path（迁移完成），16 篇为 legacy 路径中的 `.task.md` 文件，2 篇为 README.md。

## 五、未迁移清单

以下 16 篇文档留在 legacy 路径，**未迁移原因**：

### 5.1 `.task.md` agent 任务文档（16 篇）

这些是 agent 执行任务时的阶段性产物（dev / test / review），包含 `source_slice_doc`、`source_doc` 等字段指向已迁移的 source doc。它们不是 source-of-truth change doc，属于 operational artifacts。

| 路径 | 阶段 |
|---|---|
| `planned/parr2/dev/parallel-01-revalidate-cli-modes.task.md` | dev |
| `planned/parr2/dev/parallel-02-real-backtest-library-ops.task.md` | dev |
| `planned/parr2/dev/parallel-03-debug-failure-filter.task.md` | dev |
| `planned/parr2/dev/parallel-04-quality-gate-and-state-regression.task.md` | dev |
| `planned/parr2/test/parallel-01-revalidate-cli-modes.task.md` | test |
| `planned/parr2/test/parallel-02-real-backtest-library-ops.task.md` | test |
| `planned/parr2/test/parallel-03-debug-failure-filter.task.md` | test |
| `planned/parr2/test/parallel-04-quality-gate-and-state-regression.task.md` | test |
| `planned/parrelell/dev/parallel-01-revalidate-cli-modes.task.md` | dev |
| `planned/parrelell/dev/parallel-02-real-backtest-library-ops.task.md` | dev |
| `planned/parrelell/dev/parallel-03-debug-failure-filter.task.md` | dev |
| `planned/parrelell/dev/parallel-04-quality-gate-and-state-regression.task.md` | dev |
| `planned/parrelell/review/parallel-01-revalidate-cli-modes.task.md` | review |
| `planned/parrelell/review/parallel-02-real-backtest-library-ops.task.md` | review |
| `planned/parrelell/review/parallel-03-debug-failure-filter.task.md` | review |
| `planned/parrelell/review/parallel-04-quality-gate-and-state-regression.task.md` | review |

**未迁移理由**：per playbook "Do Not Over-Migrate" 和 "Escalation Rule"，operational task artifacts 不是 source-of-truth change doc，且迁移它们需要连带更新 `auto/tasks/` 目录下的运行产物，范围超出 change doc 管理范畴。

### 5.2 README.md（2 篇）

- `planned/README.md`
- `planned/parr2/README.md`

**未迁移理由**：索引页面，不是 change doc。

## 六、总结

### 6.1 完成判据对照

| 判据 | 状态 |
|---|---|
| 1. doc 存在于 flat module 路径 | ✅ 11 篇全部完成 |
| 2. doc 有标准 change-doc metadata | ✅ 全部含 `doc_type`、`module`、`status`、`owner`、`created`、`updated`、`summary` |
| 3. effective status 体现在 metadata 中 | ✅ `status: planned` 写入 metadata |
| 4. 高价值引用已更新 | ✅ `implemented/2026-03-20-iterate2-deferred-followups.md` 已更新 |
| 5. `scripts/doc_index.py validate` 无新增 structural issue | ✅ 无新增 issues |

### 6.2 操作统计

- 迁移文件数：11
- metadata 编辑次数：11
- 文件移动次数：11
- 引用更新文件数：1（更新 5 条路径）
- 遗留 legacy 文件数：16（task artifacts，非 source-of-truth）
- governance/ 修改：0（符合约束）
