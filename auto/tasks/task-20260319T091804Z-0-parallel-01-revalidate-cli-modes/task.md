---
source_slice_doc: docs/03-changes/quantaalpha/planned/parrelell/2026-03-18-parallel-01-revalidate-cli-modes.md
task_kind: headless_dev
goal: 固定 revalidate 的 CLI 模式边界
audit_required: true
---

# Task

单个 agent 完成这一块开发，只做代码修改，不做测试执行。

## 目标

- 固定默认模式、`--dry-run`、`--real-backtest` 的入口语义
- 区分三种模式的输出字段和返回结构
- 让 CLI 失败场景可见

## 可改文件

- `third_party/quantaalpha/quantaalpha/cli.py`
- `third_party/quantaalpha/tests/test_revalidate_cli.py`

## 禁止修改

- `third_party/quantaalpha/quantaalpha/factors/library.py`
- `third_party/quantaalpha/quantaalpha/pipeline/loop.py`
- `third_party/quantaalpha/quantaalpha/backtest/runner.py`
- `third_party/quantaalpha/quantaalpha/pipeline/factor_backtest.py`

## 审计材料

最终输出必须写清楚：

- 修改了哪些文件
- 每个文件改了什么
- 实际执行了哪些命令
- 风险和未完成项

