---
source_slice_doc: docs/03-changes/quantaalpha/planned/parrelell/2026-03-18-parallel-02-real-backtest-library-ops.md
task_kind: headless_dev
goal: 落真实复验内部链路、summary/audit、最小写保护和调度脚本入口
audit_required: true
---

# Task

单个 agent 完成这一块开发，只做代码修改，不做测试执行。

## 目标

- 落真实回测内部接入和结果消费
- 为因子库增加 summary 和最小审计能力
- 增加最小写锁和原子写保护
- 提供 `third_party/quantaalpha/scripts/continuous_mine.sh`

## 可改文件

- `third_party/quantaalpha/quantaalpha/factors/library.py`
- `third_party/quantaalpha/quantaalpha/backtest/runner.py`
- `third_party/quantaalpha/quantaalpha/pipeline/factor_backtest.py`
- `third_party/quantaalpha/scripts/continuous_mine.sh`
- `third_party/quantaalpha/tests/test_revalidate_real_backtest.py`
- `third_party/quantaalpha/tests/test_scheduler_summary.py`
- `third_party/quantaalpha/tests/test_factor_library_locking.py`

## 禁止修改

- `third_party/quantaalpha/quantaalpha/cli.py`
- `third_party/quantaalpha/quantaalpha/pipeline/loop.py`
- `third_party/quantaalpha/quantaalpha/factors/status_rules.py`

## 审计材料

最终输出必须写清楚：

- 修改了哪些文件
- 每个文件改了什么
- 实际执行了哪些命令
- 风险和未完成项

