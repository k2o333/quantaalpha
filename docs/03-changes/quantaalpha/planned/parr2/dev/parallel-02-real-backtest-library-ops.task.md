---
doc_type: operational_artifact
classification: operational_artifact
stage: dev
task_key: parallel-02-real-backtest-library-ops
recommended_agent: gemini
next_stage: test
source_doc: docs/03-changes/quantaalpha/2026-03-18-parallel-02-real-backtest-library-ops.md  # historical; flat path is the source of truth
allowed_code_paths:
  - third_party/quantaalpha/quantaalpha/factors/library.py
  - third_party/quantaalpha/quantaalpha/backtest/runner.py
  - third_party/quantaalpha/quantaalpha/pipeline/factor_backtest.py
  - third_party/quantaalpha/scripts/continuous_mine.sh
  - third_party/quantaalpha/tests/test_revalidate_real_backtest.py
  - third_party/quantaalpha/tests/test_scheduler_summary.py
  - third_party/quantaalpha/tests/test_factor_library_locking.py
forbidden_code_paths:
  - third_party/quantaalpha/quantaalpha/cli.py
  - third_party/quantaalpha/quantaalpha/pipeline/loop.py
  - third_party/quantaalpha/quantaalpha/factors/status_rules.py
---

# Dev Task: Real Backtest And Library Ops

目标：

- 落真实复验内部链路
- 固定 library summary 和 audit
- 固定最小写保护和调度脚本入口

本阶段只做开发，不执行测试。

阶段边界：

- 当前是 `dev` 阶段，测试由后续 `test` 阶段负责
- 如果 `agent.md`、`rules.md`、`AGENTS.md` 提到常规验证建议，本阶段一律不执行测试命令
- 需要通过文档交接，而不是在本阶段自行补测试闭环

要做：

- 实现真实回测结果消费和回写边界
- 完成 summary、audit、写保护和脚本入口
- 如有必要，同步补测试文件内容，但不要执行测试

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
