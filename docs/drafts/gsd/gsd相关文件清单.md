# GSD 相关文件清单

## 一、项目级 GSD 核心文件

| 文件 | 说明 |
|------|------|
| `.gsd/STATE.md` | 运行时状态（派生缓存，下次会话优先读取） |
| `.gsd/DECISIONS.md` | 架构决策登记（append-only） |
| `.gsd/KNOWLEDGE.md` | 项目级知识积累（规则、模式、教训） |
| `.gsd/PROJECT.md` | 项目当前状态 living doc |
| `.gsd/REQUIREMENTS.md` | 需求契约（active/validated/deferred） |
| `.gsd/OVERRIDES.md` | 用户通过 `/gsd steer` 发出的覆盖指令 |
| `.gsd/preferences.md` | GSD 配置（isolation mode、unique_milestone_ids 等） |
| `.gsd/runtime/` | 系统管理目录（dispatch state） |
| `.gsd/activity/` | 系统管理目录（JSONL 执行日志） |
| `.gsd/worktrees/` | auto-mode worktree checkouts |

---

## 二、Milestone 目录结构

每个 milestone 有独立目录：

| 路径 | 说明 |
|------|------|
| `.gsd/milestones/M001/` | M001 根目录 |
| `.gsd/milestones/M001/M001-META.json` | Milestone 元数据 |
| `.gsd/milestones/M001/M001-ROADMAP.md` | Milestone 计划（slice 列表、依赖、risk） |
| `.gsd/milestones/M001/M001-CONTEXT.md` | 可选：讨论阶段用户决策 |
| `.gsd/milestones/M001/M001-RESEARCH.md` | 可选：代码库/技术调研 |
| `.gsd/milestones/M001/M001-SUMMARY.md` | Milestone 汇总（slice 完成时更新） |
| `.gsd/milestones/M001/M001-VALIDATION.md` | 可选：milestone 验收 |

每个 milestone 下还有 slices 子目录（见下）。

---

## 三、Slice 目录结构

每个 slice 有独立目录：

| 路径 | 说明 |
|------|------|
| `slices/S01/S01-PLAN.md` | Slice 计划（task 分解） |
| `slices/S01/S01-CONTEXT.md` | 可选：slice 级讨论决策 |
| `slices/S01/S01-RESEARCH.md` | 可选：slice 级调研 |
| `slices/S01/S01-SUMMARY.md` | Slice 汇总（slice 完成时写入） |
| `slices/S01/S01-UAT.md` | 非阻塞人工测试脚本（slice 完成时写入） |
| `slices/S01/continue.md` | 临时：中断恢复点（ consumed 后删除） |
| `slices/S01/tasks/T01-PLAN.md` | 单个任务计划 |
| `slices/S01/tasks/T01-SUMMARY.md` | 单个任务汇总 |

---

## 四、GSD Agent 核心文件（`/root/.gsd/agent/`）

### 4.1 方法论文档
| 路径 | 说明 |
|------|------|
| `GSD-WORKFLOW.md` | **核心**：GSD 工作流方法论（Discuss → Research → Plan → Execute → Verify → Summarize → Advance） |

### 4.2 Agent 定义
| 路径 | 说明 |
|------|------|
| `agents/javascript-pro.md` | JS 专用 agent |
| `agents/typescript-pro.md` | TS 专用 agent |
| `agents/scout.md` | 代码库侦察 agent |
| `agents/worker.md` | 工作执行 agent |
| `agents/researcher.md` | 调研 agent |

### 4.3 Prompts（`extensions/gsd/prompts/`）
| 路径 | 说明 |
|------|------|
| `system.md` | GSD 系统 prompt |
| `workflow-start.md` | 工作流启动 |
| `discuss.md` / `guided-discuss-milestone.md` / `guided-discuss-slice.md` | 讨论阶段 |
| `research-milestone.md` / `research-slice.md` / `guided-research-slice.md` | 调研阶段 |
| `plan-milestone.md` / `plan-slice.md` / `guided-plan-milestone.md` / `guided-plan-slice.md` | 规划阶段 |
| `execute-task.md` / `guided-execute-task.md` / `guided-resume-task.md` | 执行阶段 |
| `complete-slice.md` / `guided-complete-slice.md` | Slice 完成 |
| `complete-milestone.md` / `validate-milestone.md` | Milestone 完成/验收 |
| `quick-task.md` | 快速任务 |
| `reactive-execute.md` | 响应式执行 |
| `reassess-roadmap.md` | 路线图重评 |
| `replan-slice.md` | Slice 重规划 |
| `run-uat.md` | 运行 UAT |
| `queue.md` | 队列管理 |
| `doctor-heal.md` / `heal-skill.md` | 诊断修复 |
| `triage-captures.md` | 问题分类 |
| `forensics.md` | 取证分析 |
| `rewrite-docs.md` | 重写文档 |
| `review-migration.md` | 迁移审查 |
| `worktree-merge.md` | Worktree 合并 |
| `discuss-headless.md` | Headless 讨论 |

### 4.4 Templates（`extensions/gsd/templates/`）
| 路径 | 说明 |
|------|------|
| `roadmap.md` | Milestone roadmap 模板 |
| `slice-context.md` | Slice context 模板 |
| `plan.md` | Slice plan 模板 |
| `task-plan.md` | Task plan 模板 |
| `task-summary.md` | Task summary 模板 |
| `slice-summary.md` | Slice summary 模板 |
| `milestone-summary.md` | Milestone summary 模板 |
| `milestone-validation.md` | Milestone validation 模板 |
| `uat.md` | UAT 模板 |
| `research.md` | Research 模板 |
| `context.md` | Context 模板 |
| `decisions.md` | Decisions 模板 |
| `knowledge.md` | Knowledge 模板 |
| `requirements.md` | Requirements 模板 |
| `project.md` | Project 模板 |
| `reassessment.md` | Reassessment 模板 |
| `preferences.md` | Preferences 模板 |
| `state.md` | State 模板 |
| `runtime.md` | Runtime 模板 |
| `secrets-manifest.md` | Secrets manifest 模板 |

### 4.5 Workflow Templates（`extensions/gsd/workflow-templates/`）
| 路径 | 说明 |
|------|------|
| `bugfix.md` | Bugfix 工作流 |
| `hotfix.md` | 热修复工作流 |
| `small-feature.md` | 小功能工作流 |
| `full-project.md` | 完整项目工作流 |
| `refactor.md` | 重构工作流 |
| `dep-upgrade.md` | 依赖升级工作流 |
| `security-audit.md` | 安全审计工作流 |
| `spike.md` | 技术探针工作流 |

### 4.6 Skills（`skills/` 和 `extensions/gsd/skills/`）
| Skill 名称 | 路径 | 说明 |
|------------|------|------|
| accessibility | `skills/accessibility/` | WCAG 2.1 无障碍审计 |
| agent-browser | `skills/agent-browser/` | 浏览器自动化 |
| best-practices | `skills/best-practices/` | 现代 Web 开发最佳实践 |
| code-optimizer | `skills/code-optimizer/` | 深度代码优化审计 |
| core-web-vitals | `skills/core-web-vitals/` | LCP/INP/CLS 优化 |
| create-gsd-extension | `skills/create-gsd-extension/` | 创建 GSD 扩展 |
| create-skill | `skills/create-skill/` | 创建 skill 指导 |
| create-workflow | `skills/create-workflow/` | 创建 YAML 工作流 |
| debug-like-expert | `skills/debug-like-expert/` | 深度调试模式 |
| frontend-design | `skills/frontend-design/` | 前端界面设计 |
| github-workflows | `skills/github-workflows/` | GitHub Actions CI/CD |
| lint | `skills/lint/` | 代码检查和格式化 |
| make-interfaces-feel-better | `skills/make-interfaces-feel-better/` | 界面打磨 |
| react-best-practices | `skills/react-best-practices/` | React/Next.js 性能 |
| review | `skills/review/` | 代码审查 |
| test | `skills/test/` | 测试生成和运行 |
| userinterface-wiki | `skills/userinterface-wiki/` | UI/UX 最佳实践 |
| web-design-guidelines | `skills/web-design-guidelines/` | Web 界面规范审查 |
| web-quality-audit | `skills/web-quality-audit/` | 综合 Web 质量审计 |
| gsd-headless | `extensions/gsd/skills/gsd-headless/` | GSD headless 模式 |

### 4.7 Extensions
| 路径 | 说明 |
|------|------|
| `extensions/gsd/docs/preferences-reference.md` | Preferences 配置参考 |
| `extensions/gsd/docs/claude-marketplace-import.md` | Marketplace 导入指南 |
| `extensions/browser-tools/BROWSER-TOOLS-V2-PROPOSAL.md` | Browser tools v2 提案 |
| `extensions/ttsr/ttsr-interrupt.md` | TTSR 中断处理 |

---

## 五、Superpowers Skills（`/root/.agents/skills/superpowers/`）

| Skill 名称 | 说明 |
|------------|------|
| using-superpowers | 使用 superpowers 的引导 |
| brainstorming | 创意发散 |
| writing-plans | 编写计划 |
| writing-skills | 编写 skills |
| systematic-debugging | 系统调试 |
| test-driven-development | TDD |
| receiving-code-review | 接收代码审查 |
| requesting-code-review | 请求代码审查 |
| finishing-a-development-branch | 完成开发分支 |
| verification-before-completion | 完工前验证 |
| executing-plans | 执行计划 |
| subagent-driven-development | 子 agent 驱动开发 |
| using-git-worktrees | Git worktree 使用 |
| dispatching-parallel-agents | 并行 agent 分派 |

---

## 六、当前项目 GSD Milestones

| Milestone | 路径 | 状态 |
|-----------|------|------|
| M001 | `.gsd/milestones/M001/` | 已完成 |
| M002 | `.gsd/milestones/M002/` | 已完成 |
| M003 | `.gsd/milestones/M003/` | 进行中 |

---

## 七、文件关系图

```
GSD-WORKFLOW.md  ────────────────────────── 方法论核心
    │
    ├── extensions/gsd/prompts/    ───────  各阶段引导
    ├── extensions/gsd/templates/  ───────  产出格式模板
    ├── extensions/gsd/workflow-templates/  工作流模板
    ├── extensions/gsd/skills/     ───────  GSD 专用 skills
    └── skills/                    ───────  通用 skills

.gsd/                          ─────────── 项目 GSD 根目录
    ├── STATE.md               ←── 运行时派生状态
    ├── DECISIONS.md           ←── 架构决策登记
    ├── KNOWLEDGE.md           ←── 项目知识积累
    ├── PROJECT.md             ←── 项目当前状态
    ├── REQUIREMENTS.md        ←── 需求契约
    ├── preferences.md         ←── 配置
    └── milestones/
          └── M001/           ←── Milestone 根目录
                ├── M001-ROADMAP.md      ←── 核心：slice 计划
                ├── M001-CONTEXT.md
                ├── M001-RESEARCH.md
                ├── M001-SUMMARY.md
                └── slices/
                      └── S01/
                            ├── S01-PLAN.md        ←── 核心：task 分解
                            ├── S01-SUMMARY.md
                            ├── S01-UAT.md
                            ├── continue.md        ←── 临时恢复点
                            └── tasks/
                                  ├── T01-PLAN.md
                                  └── T01-SUMMARY.md
```

---

## 八、快速参考

**下次会话第一件事：** 读 `.gsd/STATE.md`，它告诉你当前在哪。

**Planning/research 时必读：** `.gsd/DECISIONS.md`，不违背已有决策。

**执行前必读：** 当前 milestone 的 `M###-CONTEXT.md` 和 active slice 的 `S##-CONTEXT.md`（如果存在）。
