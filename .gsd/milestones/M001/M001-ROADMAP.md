# M001: QuantaAlpha 关键 Bug 修复

**Vision:** 修复导致因子挖掘工作流卡死的 4 个关键 Bug，恢复系统正常运行

## Success Criteria

- [x] 日志调用不再抛出 `TypeError: takes 2 positional arguments but X were given`
- [x] LLM 空响应被正确检测并触发重试逻辑（而非直接崩溃）
- [x] **factor_construct** 阶段设置最大重试次数（如 10 次），不会无限循环
- [x] 包含换行符、制表符等控制字符的 JSON 响应能被正确解析
- [ ] **本里程碑未完成**: `'dict' object has no attribute 'replace'` 错误（M002 处理）

## Key Risks / Unknowns

- **子模块依赖风险** — quantaalpha 是第三方子模块，修复需确认是否影响其他项目使用
- **测试覆盖不足** — 不确定现有测试能否覆盖这些边界情况
- **Bug 触发条件不稳定** — 取决于 LLM 返回内容（第二次运行因返回非空响应而部分成功）

## Proof Strategy

- 日志修复 → 通过代码审查确认主要 `logger.warning()` 调用使用 f-string 格式
- 空响应检查 → 在 `_create_chat_completion_inner_function` 中添加空响应检测逻辑（返回空字符串而非抛异常，让重试逻辑处理）
- 无限重试 → 将 proposal.py 中的 `while True` 改为 `for attempt in range(MAX_RETRIES)`，并在循环内处理空响应
- 控制字符 → 在 JSON fix 逻辑中添加控制字符转义（只转义字符串内部的控制字符，不破坏 JSON 结构）

## Verification Classes

- Contract verification: Python 语法检查、静态类型检查 ✅
- Integration verification: 运行因子挖掘工作流验证修复效果
- Operational verification: 监控日志输出，确认无异常报错
- UAT / human verification: 人工检查修复后的代码逻辑

## Milestone Definition of Done

- [x] 所有 4 个 Bug 的修复代码已提交
- [x] 修复后的代码能通过 Python 语法检查
- [ ] 至少运行一次因子挖掘验证无卡死现象
- [ ] 修复文档已记录到 KNOWLEDGE.md
- [ ] **明确未完成**: `'dict' object has no attribute 'replace'` 错误（留待 M002）

## Requirement Coverage

- Covers: 因子挖掘工作流稳定性（factor_construct 阶段无限重试问题）
- Partially covers: 日志系统兼容性
- Leaves for later: 
  - 上游 LLM 代理问题排查
  - **M002**: `'dict' object has no attribute 'replace'` 错误（consistency check 数据类型问题）
- Orphan risks: 上游 LiteLLM 代理对大 prompt 返回空的问题未解决

## Slices

- [x] **S01: 修复 Logger 参数签名不匹配** `risk:medium` `depends:[]`
  > After this: 日志能正常输出，不再掩盖底层异常

- [x] **S02: 修复无限重试死循环和空响应检查** `risk:high` `depends:[S01]`
  > After this: factor_construct 有最大重试限制，空响应被检测并触发重试而非崩溃

- [x] **S03: 修复 JSON 控制字符未转义** `risk:medium` `depends:[S01]`
  > After this: 包含多行文本的 JSON 响应能被正确解析

- [ ] **S04: 运行因子挖掘验证修复效果** `risk:medium` `depends:[S01,S02,S03]`
  > After this: 确认因子挖掘工作流不再卡死，修复生效

## Boundary Map

### S01 → S02 Produces:
- `logger.warning()` 调用统一使用 f-string 格式（主要位置 `client.py:69-74`）

Consumes:
- nothing (first slice)

### S01 → S03 Produces:
- `logger.warning()` 调用统一使用 f-string 格式

Consumes:
- nothing (first slice)

### S02 内部依赖

S02 包含两个相互依赖的修复：
1. 空响应检查逻辑（在循环内检测空响应并 `continue`）
2. 有限重试循环（`while True` → `for attempt in range(MAX_RETRIES)`）

这两个修复必须在同一个切片中完成，因为空响应检查需要放在有限重试循环内部才能生效。

---

## 修复记录

**完成日期**: 2026-03-22

### 修改的文件

1. `third_party/quantaalpha/quantaalpha/llm/client.py`
   - line 69-74: `log_tokenizer_fallback_once()` 使用 f-string
   - line 667: `get_model_for_task()` 使用 f-string
   - line 1022-1027: 流式分支空响应检查
   - line 1034-1038: 非流式分支空响应检查
   - line 1078-1102: JSON 控制字符转义（`_escape_control_chars_in_json` 函数）

2. `third_party/quantaalpha/quantaalpha/backtest/universe.py`
   - line 111: `_coerce_date()` 使用 f-string

3. `third_party/quantaalpha/quantaalpha/factors/proposal.py`
   - line 483: `while True` → `for attempt in range(MAX_RETRIES)`
   - line 491-494: 循环内空响应检查
   - line 615: 循环结束 `RuntimeError`
