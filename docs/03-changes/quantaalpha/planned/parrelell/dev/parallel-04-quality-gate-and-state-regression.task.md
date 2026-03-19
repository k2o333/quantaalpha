---
source_slice_doc: docs/03-changes/quantaalpha/planned/parrelell/2026-03-18-parallel-04-quality-gate-and-state-regression.md
parallel_group: quantaalpha-iterate2-pilot
task_kind: headless_dev
task_scope: single_agent_single_task
priority: P0
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
audit_required: true
---

# Task

单个 coding agent 负责 quality gate、planning 约束和状态流转的开发侧回归保护。

## 开发目标

1. 按主题拆分或补齐测试文件。
2. 固定质量门控坏样本集合。
3. 固定状态流转阈值断言。
4. 必要时做小幅可测性重构，但不能扩到其它切片职责。

## 只允许修改

- `third_party/quantaalpha/tests/test_continuous_factor_features.py`
- `third_party/quantaalpha/tests/test_status_transition.py`
- `third_party/quantaalpha/tests/test_planning_constraints.py`
- `third_party/quantaalpha/tests/test_quality_gate.py`
- `third_party/quantaalpha/quantaalpha/factors/status_rules.py`
- `third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py`
- `third_party/quantaalpha/quantaalpha/backtest/validation.py`

## 禁止修改

- `third_party/quantaalpha/quantaalpha/cli.py`
- `third_party/quantaalpha/quantaalpha/factors/library.py`
- `third_party/quantaalpha/quantaalpha/pipeline/loop.py`
- `third_party/quantaalpha/scripts/continuous_mine.sh`

## 需要保留的审计材料

agent 必须在最终回答中明确给出：

1. 实际修改文件。
2. 每个阈值或 gate 规则的修改/断言摘要。
3. 执行命令。
4. 是否运行测试。
5. 风险、假设、未完成项。

## 完成标准

1. 至少一个测试直接证明 gate 会阻止后续高成本步骤。
2. 阈值断言写在测试里，不是只写在注释或 report 里。
3. 不通过改其它切片文件绕开实现。

