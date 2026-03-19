---
source_slice_doc: docs/03-changes/quantaalpha/planned/parrelell/2026-03-18-parallel-03-debug-failure-filter.md
parallel_group: quantaalpha-iterate2-pilot
task_kind: headless_dev
task_scope: single_agent_single_task
priority: P0
goal: 让 debug 后续轮次只重新处理失败因子，而不是整批重复进入 coder/backtest
allowed_code_paths:
  - third_party/quantaalpha/quantaalpha/pipeline/loop.py
  - third_party/quantaalpha/tests/test_debug_failure_filter.py
forbidden_code_paths:
  - third_party/quantaalpha/quantaalpha/cli.py
  - third_party/quantaalpha/quantaalpha/factors/library.py
  - third_party/quantaalpha/quantaalpha/factors/status_rules.py
  - third_party/quantaalpha/quantaalpha/backtest/runner.py
audit_required: true
---

# Task

单个 coding agent 负责 debug 轮次失败因子过滤，只修改 loop 和对应测试。

## 开发目标

1. 固定失败因子的代码级定义。
2. 让下一轮 debug 真实消费失败集合。
3. 全部成功时提前结束 debug。
4. 全部失败时仍受最大轮次保护。
5. 补齐 `third_party/quantaalpha/tests/test_debug_failure_filter.py`。

## 只允许修改

- `third_party/quantaalpha/quantaalpha/pipeline/loop.py`
- `third_party/quantaalpha/tests/test_debug_failure_filter.py`

## 禁止修改

- `third_party/quantaalpha/quantaalpha/cli.py`
- `third_party/quantaalpha/quantaalpha/factors/library.py`
- `third_party/quantaalpha/quantaalpha/factors/status_rules.py`
- `third_party/quantaalpha/quantaalpha/backtest/runner.py`

## 需要保留的审计材料

agent 必须在最终回答中明确给出：

1. 实际修改文件。
2. 执行命令。
3. 第二轮集合如何缩减的实现摘要。
4. 是否运行测试。
5. 风险、假设、未完成项。

## 完成标准

1. 至少有一个测试直接断言第二轮传入集合已缩减。
2. 不能只靠日志字段或 tracker 字段证明完成。
3. 不通过修改其它切片文件绕开实现。

