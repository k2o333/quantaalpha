# M005: Mining Pipeline 关键 Bug 修复 — Context

**Gathered:** 2026-03-24
**Status:** Ready for planning
**Source:** `docs/drafts/mining/problems/20260324_bug_fix_plan.md`
**Verified-by:** `docs/drafts/mining/problems/20260324_verified_bugs_and_fixes.md`

---

## Background

在对 factor mining pipeline 的系统性排查中，发现并验证了 6 个 Bug（Bug-1 至 Bug-6）。
这些 Bug 集中在以下层面：
1. 模块导入层（`quantaalpha.log` 依赖缺失 `rdagent.log`）
2. 表达式规范化层（`normalize_corrected_expression` 对脏字符串放行）
3. LLM prompt 约束层（`consistency_check_system` 未强制输出格式）
4. LLM API 错误处理层（BadRequest 重试不区分可恢复/不可恢复）
5. JSON 修复层（转义修复不完整且有重复代码）
6. Prompt 配置层（`proposal.yaml` 被后续赋值遮蔽）

活跃修复路径为：
`check_consistency() → corrected_expression → proposal.py normalize_corrected_expression() → parser re-check`

`expression_correction_system` 存在于 prompt 配置中但未接入当前运行时，对其的修改不会影响实际行为。

## Implementation Decisions

- **修复顺序**: Bug-6 → Bug-2+Bug-1（联合）→ Bug-3 → Bug-5 → Bug-4
- **Fallback logger**: 使用 Python 标准 `logging` 模块实现，保持 `logger.info/warning/error/exception/log_trace_path/set_trace_path` 接口兼容
- **表达式提取策略**: 优先提取赋值语句的右侧值，而非跳过赋值行——跳过赋值行会删掉唯一有效表达式
- **vendored copy**: `third_party/quantaalpha/quantaalpha/log/__init__.py` 需与主包保持一致，不允许两份代码行为发散

## Agent's Discretion

- fallback logger 实现细节（类名、模块路径）由 agent 决定
- JSON 转义的正则实现细节由 agent 决定，只需通过指定的验证用例
- `proposal.yaml` 是删除还是归档由 agent 根据内容决定

## Deferred Ideas

- 集成 `expression_correction_system` 到运行时修复路径（属于架构改进，不在此 milestone 范围内）
- 完全替换 rdagent logger（本次只做兼容 fallback）
