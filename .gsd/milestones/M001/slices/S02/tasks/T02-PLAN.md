# T02: 修复 proposal.py 的无限重试循环
**Slice:** S02  **Milestone:** M001
## Goal
将 `while True` 改为有限重试，添加空响应检查和超限异常。
## Must-Haves
### Truths
- `grep -n "for attempt in range" proposal.py` 找到有限循环
- `grep -n "RuntimeError" proposal.py` 找到超限异常
### Artifacts
- `third_party/quantaalpha/quantaalpha/factors/proposal.py` line 483, 491-494, 615 已修改
## Steps
1. `while True` → `for attempt in range(MAX_RETRIES)`
2. 循环内添加空响应检查 `continue`
3. 循环后 `else` 抛出 `RuntimeError`
