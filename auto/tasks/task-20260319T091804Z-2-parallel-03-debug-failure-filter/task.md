---
source_slice_doc: docs/03-changes/quantaalpha/planned/parrelell/2026-03-18-parallel-03-debug-failure-filter.md
task_kind: headless_dev
goal: 让 debug 后续轮次只重新处理失败因子
audit_required: true
---

# Task

单个 agent 完成这一块开发，只做代码修改，不做测试执行。

## 目标

- 固定失败因子的代码级定义
- 让下一轮 debug 只消费失败集合
- 全部成功时提前结束
- 全部失败时仍受最大轮次保护

## 可改文件

- `third_party/quantaalpha/quantaalpha/pipeline/loop.py`
- `third_party/quantaalpha/tests/test_debug_failure_filter.py`

## 禁止修改

- `third_party/quantaalpha/quantaalpha/cli.py`
- `third_party/quantaalpha/quantaalpha/factors/library.py`
- `third_party/quantaalpha/quantaalpha/factors/status_rules.py`
- `third_party/quantaalpha/quantaalpha/backtest/runner.py`

## 审计材料

最终输出必须写清楚：

- 修改了哪些文件
- 每个文件改了什么
- 实际执行了哪些命令
- 风险和未完成项

