---
source_slice_doc: docs/03-changes/quantaalpha/planned/parrelell/2026-03-18-parallel-01-revalidate-cli-modes.md
parallel_group: quantaalpha-iterate2-pilot
task_kind: headless_dev
task_scope: single_agent_single_task
priority: P0
goal: 固定 revalidate 的 CLI 语义边界，让 dry-run、status-refresh、real-backtest 三种模式在命令入口和返回结构上可区分
allowed_code_paths:
  - third_party/quantaalpha/quantaalpha/cli.py
  - third_party/quantaalpha/tests/test_revalidate_cli.py
forbidden_code_paths:
  - third_party/quantaalpha/quantaalpha/factors/library.py
  - third_party/quantaalpha/quantaalpha/pipeline/loop.py
  - third_party/quantaalpha/quantaalpha/backtest/runner.py
  - third_party/quantaalpha/quantaalpha/pipeline/factor_backtest.py
audit_required: true
---

# Task

单个 coding agent 负责完成 `revalidate` CLI 模式边界开发，不涉及其它切片职责。

## 开发目标

1. 固定 `revalidate` 三种模式的入口语义。
2. 区分默认模式、`--dry-run`、`--real-backtest` 的输出字段和返回结构。
3. 让 CLI 失败场景可见。
4. 补齐 `third_party/quantaalpha/tests/test_revalidate_cli.py` 的开发侧覆盖。

## 只允许修改

- `third_party/quantaalpha/quantaalpha/cli.py`
- `third_party/quantaalpha/tests/test_revalidate_cli.py`

## 禁止修改

- `third_party/quantaalpha/quantaalpha/factors/library.py`
- `third_party/quantaalpha/quantaalpha/pipeline/loop.py`
- `third_party/quantaalpha/quantaalpha/backtest/runner.py`
- `third_party/quantaalpha/quantaalpha/pipeline/factor_backtest.py`

## 需要保留的审计材料

agent 必须在最终回答中明确给出：

1. 实际修改的文件列表。
2. 每个文件的修改摘要。
3. 实际执行过的命令列表。
4. 未执行测试的事实，或执行受限的事实。
5. 风险、未完成项、边界假设。

## 完成标准

1. 三种模式在命令帮助或运行结果中可区分。
2. Python 调用返回结构不被破坏。
3. 没有通过改其它切片文件“绕过实现”。

