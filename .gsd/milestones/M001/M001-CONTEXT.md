# M001: QuantaAlpha 关键 Bug 修复

**触发原因**: 因子挖掘工作流在执行时出现系统级死循环，导致进程卡死

**问题来源**: `docs/drafts/factormining/bug/` 下的 5 份 bug 分析报告

## 核心问题

系统在执行因子挖掘的 proposal 阶段出现大规模循环刷屏报错，由 **4 个关联 Bug** 联动引发：

### Bug 1: Logger.warning() 参数签名不匹配
- **位置**: `quantaalpha/llm/client.py:69-74`, `client.py:667`, `backtest/universe.py:111`
- **问题**: 使用标准 logging 的 `%s` 格式（多参数），但 `RDAgentLog.warning()` 只接受单个 `msg` 参数
- **影响**: 掩盖了真实的底层异常，阻碍问题排查

### Bug 2: LLM 返回空流导致 JSON 解析崩溃
- **位置**: `quantaalpha/llm/client.py:1047-1051`
- **问题**: 当 `resp` 为空字符串时，JSON 提取逻辑产生无效切片，导致 `json.loads("")` 抛出 `JSONDecodeError`
- **影响**: 空响应无法被正确处理

### Bug 3: 无限重试导致的死循环
- **位置**: `quantaalpha/factors/proposal.py:483-492`
- **问题**: `while True` 循环没有重试上限，当 LLM 持续返回空响应时陷入死循环
- **影响**: 进程卡死，无法继续

### Bug 4: JSON 字符串中的控制字符未转义
- **位置**: `quantaalpha/llm/client.py:1061-1068`
- **问题**: JSON fix 逻辑只处理 LaTeX 反斜杠，不处理控制字符（如换行符 `\n`、制表符 `\t`）
- **影响**: 包含多行文本的 JSON 解析失败

## 修复优先级

1. **Bug 1（日志参数）** - 简单，能让真实错误暴露出来
2. **Bug 2（空响应检查）** - 防止空响应导致崩溃
3. **Bug 3（无限重试）** - 防止进程卡死
4. **Bug 4（控制字符）** - 提高 JSON 解析成功率

## 成功标准

- [ ] 日志调用不再抛出 `TypeError`
- [ ] LLM 空响应被正确处理并抛出明确异常
- [ ] 因子 proposal 重试有上限，不会无限循环
- [ ] 包含控制字符的 JSON 响应能被正确解析

## 关键风险

- **子模块依赖**: quantaalpha 是子模块，修复需要确认是否影响上游
- **测试覆盖**: 需要验证修复不会破坏现有功能
