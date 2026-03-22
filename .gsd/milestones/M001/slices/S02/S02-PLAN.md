# S02: 修复无限重试死循环

**Goal:** 为因子 proposal 阶段添加最大重试次数，防止无限循环卡死
**Demo:** 当 LLM 持续返回空响应或无效 JSON 时，程序在 10 次重试后抛出异常退出，而非无限循环

## Must-Haves

- `proposal.py` 中的 `while True` 循环改为有上限的重试
- 每次重试记录当前次数/最大次数
- 达到最大重试次数后抛出明确异常

## Verification

- `python -m py_compile third_party/quantaalpha/quantaalpha/factors/proposal.py` 通过
- 代码审查确认 `while True` 已被替换为 `for attempt in range(MAX_RETRIES)`

## Observability / Diagnostics

- Runtime signals: 每次重试记录 `attempt X/MAX_RETRIES`
- Inspection surfaces: 日志显示重试进度
- Failure visibility: 达到最大重试后抛出 `RuntimeError` 包含失败原因

## Integration Closure

- Upstream surfaces consumed: S01 修复后的空响应检测
- New wiring introduced: 有限重试逻辑
- What remains: 需要 S03 修复控制字符以提高成功率

## Tasks

- [ ] **T01: 定位并修复 proposal.py 的无限重试循环** `est:20m`
  - Why: `while True` 循环在 LLM 返回空响应时导致无限重试，进程卡死
  - Files: `third_party/quantaalpha/quantaalpha/factors/proposal.py`
  - Do: 将 `while True:`（约 line 483）改为 `MAX_RETRIES = 10; for attempt in range(MAX_RETRIES):`，在循环体内使用 `attempt` 替代硬编码计数，达到最大次数后抛出 `RuntimeError("Factor proposal failed after max retries: persistent empty LLM response")`
  - Verify: `grep -n "while True" third_party/quantaalpha/quantaalpha/factors/proposal.py` 返回空，或确认不在关键路径
  - Done when: 循环有明确的最大重试次数，超限后抛出异常

## Files Likely Touched

- `third_party/quantaalpha/quantaalpha/factors/proposal.py`
