---
doc_type: operational_artifact
classification: operational_artifact
stage: dev
task_key: parallel-01-revalidate-cli-modes
recommended_agent: iflow
next_stage: test
source_doc: docs/03-changes/quantaalpha/2026-03-18-parallel-01-revalidate-cli-modes.md  # historical; flat path is the source of truth
allowed_code_paths:
  - third_party/quantaalpha/quantaalpha/cli.py
  - third_party/quantaalpha/tests/test_revalidate_cli.py
forbidden_code_paths:
  - third_party/quantaalpha/quantaalpha/factors/library.py
  - third_party/quantaalpha/quantaalpha/pipeline/loop.py
  - third_party/quantaalpha/quantaalpha/backtest/runner.py
  - third_party/quantaalpha/quantaalpha/pipeline/factor_backtest.py
---

# Dev Task: Revalidate CLI Modes

目标：

- 固定 `revalidate` 的三种入口语义：`status_refresh`、`dry_run`、`real_backtest`
- 区分返回结构和失败可见性

本阶段只做开发，不执行测试。

阶段边界：

- 当前是 `dev` 阶段，测试由后续 `test` 阶段负责
- 如果 `agent.md`、`rules.md`、`AGENTS.md` 提到常规验证建议，本阶段一律不执行测试命令
- 需要通过文档交接，而不是在本阶段自行补测试闭环

要做：

- 修改命令入口、参数路由、返回字段
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
