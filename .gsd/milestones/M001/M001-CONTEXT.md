# M001: QuantaAlpha 关键 Bug 修复

**触发原因**: 因子挖掘工作流在执行时出现系统级死循环，导致进程卡死

**问题来源**: `docs/drafts/factormining/bug/` 下的 5 份 bug 分析报告

**日志来源**:
- `third_party/facotors/terminal/20260321_190705.txt` (第一次运行，卡死)
- `third_party/facotors/terminal/20260321_214610.txt` (第二次运行，部分成功)

---

## 核心问题

系统在执行因子挖掘的 **factor_construct** 阶段出现大规模循环刷屏报错，由 **4 个高优先级 Bug** 联动引发。

**本里程碑未覆盖的问题**: 第二份日志 (`20260321_214610.txt`) 暴露了一个额外 Bug - `'dict' object has no attribute 'replace'`（consistency check 数据类型错误），该问题将在 M002 中处理。

---

### Bug 1: Logger.warning() 参数签名不匹配（主要触发点）

**核心位置**: `quantaalpha/llm/client.py:69-74` (`log_tokenizer_fallback_once` 函数)

**同类隐患**（建议一并修复）:
- `quantaalpha/llm/client.py:667` (`get_model_for_task` 方法)
- `quantaalpha/backtest/universe.py:111` (`_coerce_date` 函数)

**问题**: 使用标准 logging 的 `%s` 格式（多参数），但 `RDAgentLog.warning()` 只接受单个 `msg` 参数。

**影响**: 掩盖了真实的底层异常，阻碍问题排查。

---

### Bug 2: LLM 返回空流导致 JSON 提取崩溃

**位置**: `quantaalpha/llm/client.py:1047-1051`

**问题**: 
- 当 `resp` 为空字符串时，`resp.find('{')` 返回 `-1`，`resp.rfind('}')+1` 返回 `0`
- 切片 `resp[-1:0]` 得到空字符串，后续 `json.loads("")` 抛出 `JSONDecodeError`

**影响**: 空响应无法被正确处理。

---

### Bug 3: 无限重试导致的死循环

**位置**: `quantaalpha/factors/proposal.py:483-492` (`_convert_with_history_limit` 方法，**factor_construct 阶段**)

**问题**: 
- `while True` 循环没有重试上限
- **触发条件**: 对**任意持续的 JSON 解析失败**（包括空响应、控制字符导致的解析错误）都没有退出条件
- 本次事故中因 LLM 返回空响应触发，但控制字符导致的解析错误同样会触发

**影响**: 进程卡死，无法继续。

---

### Bug 4: JSON 控制字符缺少转义处理

**位置**: `quantaalpha/llm/client.py:1061-1068`

**问题**: JSON fix 逻辑**缺少**控制字符转义处理，当前只覆盖 LaTeX 反斜杠。

**影响**: 包含多行文本（含实际换行符、制表符等）的 JSON 解析失败。

**证据**: 终端日志 `20260321_214610.txt`:
```
JSON fix failed: Invalid control character at: line 4 column 33 (char 83)
```

---

## 修复优先级

1. **Bug 1（日志参数）** - 简单，能让真实错误暴露出来
2. **Bug 2（空响应检查）** - 与 Bug 3 联动修复，防止无意义的 JSON 解析
3. **Bug 3（无限重试）** - 关键，防止进程卡死
4. **Bug 4（控制字符）** - 提高 JSON 解析成功率

---

## 成功标准

- [ ] 主要日志调用 (`client.py:69-74`) 不再抛出 `TypeError`
- [ ] LLM 空响应被正确检测并触发重试逻辑（而非直接崩溃）
- [ ] factor_construct 阶段重试有明确上限（如 10 次），不会无限循环
- [ ] 包含换行符、制表符等控制字符的 JSON 响应能被正确解析
- [ ] **本里程碑未完成**: `'dict' object has no attribute 'replace'` 错误（M002 处理）

---

## 关键风险

- **子模块依赖**: quantaalpha 是子模块，修复需要确认是否影响上游
- **测试覆盖**: 需要验证修复不会破坏现有功能
- **Bug 触发条件**: 取决于 LLM 返回内容（第二次运行因返回非空响应而部分成功）
