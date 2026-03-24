# T03: 修复 universe.py:111 的 logger.warning 调用
**Slice:** S01  **Milestone:** M001
## Goal
修复 `_coerce_date()` 中 `%s` 格式为 f-string。
## Must-Haves
### Truths
- `grep "logger.warning" universe.py | grep -c "%s,"` 返回 0
### Artifacts
- `third_party/quantaalpha/quantaalpha/backtest/universe.py` line 111 已修改
## Steps
1. 将 `logger.warning("Failed to parse as_of_date=%s ...", value)` 改为 f-string。
