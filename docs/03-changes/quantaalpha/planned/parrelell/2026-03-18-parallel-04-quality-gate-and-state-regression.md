---
status: planned
owner: Codex
created: 2026-03-18
parallel_mode: true
parallel_group: quantaalpha-iterate2-pilot
slice_id: slice_4
priority: P0
parent_source_docs:
  - docs/03-changes/quantaalpha/planned/2026-03-15-iterate2-03-quality-gate-and-state-regression.md
goal: 为 quality gate、planning 约束和状态流转补齐稳定回归保护，不让 iterate2 的其它切片在没有测试护栏的情况下漂移
allowed_code_paths:
  - third_party/quantaalpha/tests/test_continuous_factor_features.py
  - third_party/quantaalpha/tests/test_status_transition.py
  - third_party/quantaalpha/tests/test_planning_constraints.py
  - third_party/quantaalpha/tests/test_quality_gate.py
  - third_party/quantaalpha/quantaalpha/factors/status_rules.py
  - third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py
  - third_party/quantaalpha/quantaalpha/backtest/validation.py
forbidden_code_paths:
  - third_party/quantaalpha/quantaalpha/cli.py
  - third_party/quantaalpha/quantaalpha/factors/library.py
  - third_party/quantaalpha/quantaalpha/pipeline/loop.py
  - third_party/quantaalpha/scripts/continuous_mine.sh
test_targets:
  - third_party/quantaalpha/tests/test_status_transition.py
  - third_party/quantaalpha/tests/test_planning_constraints.py
  - third_party/quantaalpha/tests/test_quality_gate.py
disproof_command: /root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests/test_status_transition.py third_party/quantaalpha/tests/test_planning_constraints.py third_party/quantaalpha/tests/test_quality_gate.py -q
---

# Parallel Slice 4: Quality Gate And State Regression

## 目标

把 iterate2 中最容易回归的规则边界固定成独立测试：

- planning 边界约束
- quality gate 拦截坏样本
- 状态流转阈值
- gate 对高成本 backtest 的阻断效果

## 输入契约

- 规则函数和 gate helper 必须能稳定表达真实边界
- 测试不依赖外部 LLM 或外部服务

## 输出契约

本切片至少应提供：

1. 明确的主题测试文件。
2. 对关键状态阈值的显式断言。
3. 对坏样本阻断后续高成本步骤的直接证据。

## 必须做的事

1. 按主题拆分或补齐测试文件。
2. 固定质量门控坏样本集合。
3. 固定状态流转阈值断言。
4. 允许为可测性做小幅重构，但不能扩大到其它切片职责。

## 明确不做

1. 不改调度脚本。
2. 不改因子库写保护。
3. 不改 debug 轮次过滤。
4. 不改 CLI 路由。

## 测试要求

自动化测试至少覆盖：

1. NaN、inf、常数列、低有效样本比等坏样本会被 gate 拦下。
2. 坏样本不会继续进入高成本 backtest。
3. `pending_validation -> active`。
4. `active -> degraded`。
5. `active -> stale`。
6. `degraded -> deprecated`。
7. planning 越界方向会被拦截，合法方向可通过。

## 通过标准

必须同时满足：

1. 3 个主题测试文件能独立通过。
2. 至少一个测试直接证明 gate 会阻止后续高成本步骤。
3. 阈值断言写在测试里，而不是只写在注释或 report 里。

