# M001: QuantaAlpha 关键 Bug 修复

**Vision:** 修复导致因子挖掘工作流卡死的 4 个关键 Bug，恢复系统正常运行

## Success Criteria

- 日志调用不再抛出 `TypeError: takes 2 positional arguments but X were given`
- LLM 空响应被正确检测并抛出明确异常，不再进入 JSON 解析
- 因子 proposal 阶段设置最大重试次数（如 10 次），不会无限循环
- 包含换行符、制表符等控制字符的 JSON 响应能被正确解析

## Key Risks / Unknowns

- **子模块依赖风险** — quantaalpha 是第三方子模块，修复需确认是否影响其他项目使用
- **测试覆盖不足** — 不确定现有测试能否覆盖这些边界情况

## Proof Strategy

- 日志修复 → 通过代码审查确认所有 `logger.warning()` 调用使用 f-string 格式
- 空响应检查 → 在 `_create_chat_completion_inner_function` 中添加空响应检测逻辑
- 无限重试 → 将 proposal.py 中的 `while True` 改为 `for attempt in range(MAX_RETRIES)`
- 控制字符 → 在 JSON fix 逻辑中添加控制字符转义

## Verification Classes

- Contract verification: Python 语法检查、静态类型检查
- Integration verification: 运行因子挖掘工作流验证修复效果
- Operational verification: 监控日志输出，确认无异常报错
- UAT / human verification: 人工检查修复后的代码逻辑

## Milestone Definition of Done

- [ ] 所有 4 个 Bug 的修复代码已提交
- [ ] 修复后的代码能通过 Python 语法检查
- [ ] 至少运行一次因子挖掘验证无卡死现象
- [ ] 修复文档已记录到 KNOWLEDGE.md

## Requirement Coverage

- Covers: 因子挖掘工作流稳定性
- Partially covers: 日志系统兼容性
- Leaves for later: 上游 LLM 代理问题排查
- Orphan risks: 上游 LiteLLM 代理对大 prompt 返回空的问题未解决

## Slices

- [ ] **S01: 修复 Logger 参数签名不匹配和空响应检查** `risk:medium` `depends:[]`
  > After this: 日志能正常输出，空响应能被检测到，不会导致后续 JSON 解析崩溃

- [ ] **S02: 修复无限重试死循环** `risk:high` `depends:[S01]`
  > After this: 因子 proposal 有最大重试限制，不会无限卡死

- [ ] **S03: 修复 JSON 控制字符未转义** `risk:medium` `depends:[S01]`
  > After this: 包含多行文本的 JSON 响应能被正确解析

## Boundary Map

### S01 → S02 Produces:
- `logger.warning()` 调用统一使用 f-string 格式
- `_create_chat_completion_inner_function` 有空响应检查逻辑

Consumes:
- nothing (first slice)

### S01 → S03 Produces:
- `logger.warning()` 调用统一使用 f-string 格式
- `_create_chat_completion_inner_function` 有空响应检查逻辑

Consumes:
- nothing (first slice)
