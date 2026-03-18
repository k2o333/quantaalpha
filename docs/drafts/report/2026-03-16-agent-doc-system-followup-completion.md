Status: accepted
Owner: iFlow CLI
Created: 2026-03-16
Outcome: accepted
Related-to: `docs/03-changes/common/draft/2026-03-16-agent-doc-system-followup-todo.md`
Related-to: `docs/04-decisions/ADR-002-agent-oriented-documentation-system.md`

# Agent Documentation System Followup Completion Report

## Summary

本任务完成了治理文档的小范围编辑，使仓库入口流程更紧密地匹配 ADR-002，并消除了 `development-workflow.md` 与 `rules.md` 之间的规则重复定义。

---

## Files Changed

| File | Action |
|------|--------|
| `docs/00-governance/agent.md` | 编辑 |
| `docs/00-governance/development-workflow.md` | 编辑 |

---

## Files Reviewed But Not Changed

| File | Reason |
|------|--------|
| `docs/00-governance/doc-rules.md` | 文档已足够简洁，保持短入口角色，明确的工作流表格路由读者到下一个具体文件，无措辞导致过度阅读的问题 |

---

## What Was Actually Changed

### `docs/00-governance/agent.md`

**Section: Task Routing**

| Before | After |
|--------|-------|
| `docs/03-changes/...` | `docs/03-changes/<module>/<status>/` |

新增路由条目：
- `long-term architectural decisions` -> `docs/04-decisions/`
- `reusable patterns and lessons` -> `docs/05-playbooks/`
- `upstream or framework usage notes` -> `docs/06-references/`

**Section: Do Not Assume**

将 `docs/03-changes/` 相关内容简化为一个简短 bullet：
- `change docs under docs/03-changes/ provide implementation context, not current truth`

### `docs/00-governance/development-workflow.md`

**Section 3: 事实来源优先级**

Before: 完整的 7 级优先级列表
After: 一句引用 `rules.md` + 3 条反假设说明

**Section 4.2: 需要使用分支的场景**

Before: 6 条分支场景列表
After: 一句引用 `rules.md` + 2 条项目特定补充（AI 探索、实验分支）

**Section 6.2: 必须由人工审查的大项**

Before: 完整的审查事项清单
After: 一句引用 `rules.md`

**Section 9: 测试规则**

Before: 完整的风险等级验证矩阵
After: 一句引用 `rules.md` + 留存验证证据说明

**Section 10: 文档更新规则**

Before: 完整的文档更新触发条件列表
After: 一句引用 `rules.md` + 流程说明

**Section 11: 临时文件和实验规则**

Before: 详细说明 + 示例列表
After: 简化为 `.tmp/` 规则

**Section 13: 最简化的日常研发单句要义**

新增说明：
- `以下为记忆辅助，权威规则以 rules.md 为准`

---

## Acceptance Checks

### agent.md

| Check | Result |
|-------|--------|
| 包含 ADRs、playbooks、references 路由 | pass |
| 03-changes 路由改为模块+状态引导 | pass |
| 保持为简短首跳入口点 | pass |
| 未在 Task Routing 下添加新的解释性小节 | pass |

### development-workflow.md

| Check | Result |
|-------|--------|
| Section 3 不再包含完整 truth priority 列表 | pass |
| Section 4.2 第一行为引用 rules.md | pass |
| Section 4.2 最多只有两个 bullets | pass |
| Section 4.2 bullets 为项目特定补充 | pass |
| Section 6.2 引用 rules.md 而非完整审查清单 | pass |
| Section 9 压缩为引用 + 验证证据说明 | pass |
| Section 10 压缩为引用 + 流程说明 | pass |
| Section 11 只留 .tmp/ 规则 | pass |
| Section 13 标记为记忆辅助 | pass |

### 与 rules.md 对照

| Check | Result |
|-------|--------|
| 不再重复定义完整分支策略 | pass |
| 不再重复定义验证矩阵 | pass |
| 不再重复定义文档更新触发条件 | pass |

---

## Review Findings

Subagent 审核确认所有检查项通过：

1. **agent.md** 已成功转型为简洁的首跳入口点，路由表格式清晰，新增了 ADRs、playbooks、references 路由。

2. **development-workflow.md** 成功实现了去重：
   - Sections 3, 4.2, 6.2, 9, 10 均正确引用 `rules.md`
   - 项目特定的补充内容（AI 探索、实验分支）保留在 Section 4.2
   - Section 13 明确标记为"记忆辅助"

3. **doc-rules.md** 保持简洁，无需修改。

---

## Residual Gaps

无明显残余问题。任务按照任务文档中的所有硬性验收标准完成。

---

## Notes

- 本任务严格遵循任务文档中的编辑范围，未创建新的治理文件
- 所有编辑均为局部修改，未进行大规模重写
- Section 4.2 的两个 bullets 均为项目特定补充，与 `rules.md` 无重复
