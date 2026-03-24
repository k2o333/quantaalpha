---
doc_type: operational_artifact
classification: operational_artifact
stage: dev
task_key: parallel-04-quality-gate-and-state-regression
recommended_agent: codebuddy
next_stage: test
source_doc: docs/03-changes/quantaalpha/2026-03-18-parallel-04-quality-gate-and-state-regression.md  # historical; flat path is the source of truth
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
---

# Dev Task: Quality Gate And State Regression

目标：

- 固定 quality gate、planning 约束、状态流转的回归保护
- 让 gate 对高成本 backtest 的阻断有直接证据

本阶段只做开发，不执行测试。

阶段边界：

- 当前是 `dev` 阶段，测试由后续 `test` 阶段负责
- 如果 `agent.md`、`rules.md`、`AGENTS.md` 提到常规验证建议，本阶段一律不执行测试命令
- 需要通过文档交接，而不是在本阶段自行补测试闭环

要做：

- 补齐主题测试和必要的小幅可测性重构
- 固定坏样本集合、状态阈值和阻断证据

禁止操作：

- 禁止运行 `pytest`、`python -m pytest`、`coverage run -m pytest` 或任何测试命令
- 禁止安装任何包
- 禁止修改允许列表之外的文件
- 禁止做与本任务无关的重构

交接给下一阶段：

- 后续测试 agent 必须先读本文件
- 还要读本次运行生成的 `summary.md`、`*.result.md`、`status.json`

最终输出只保留：

- Modified Files
- Behavior Changes
- Validation Status
- Open Risks
- Suggested Test Focus
