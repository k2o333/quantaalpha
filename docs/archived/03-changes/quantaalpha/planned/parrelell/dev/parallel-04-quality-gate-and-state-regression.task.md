---
doc_type: operational_artifact
classification: operational_artifact
source_slice_doc: docs/03-changes/quantaalpha/2026-03-18-parallel-04-quality-gate-and-state-regression.md  # historical; flat path is the source of truth
task_kind: headless_dev
goal: 为 quality gate、planning 约束和状态流转补齐开发侧回归保护
audit_required: true
---

# Task

单个 agent 完成这一块开发，只做代码修改，不做测试执行。

## 目标

- 固定质量门控坏样本集合
- 固定状态流转阈值断言
- 必要时做小幅可测性重构

## 可改文件

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

## 审计材料

最终输出必须写清楚：

- 修改了哪些文件
- 每个文件改了什么
- 实际执行了哪些命令
- 风险和未完成项

