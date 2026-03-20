---
stage: dev
task_key: parallel-03-debug-failure-filter
recommended_agent: opencode
next_stage: test
source_doc: docs/03-changes/quantaalpha/planned/parrelell/2026-03-18-parallel-03-debug-failure-filter.md
allowed_code_paths:
  - third_party/quantaalpha/quantaalpha/pipeline/loop.py
  - third_party/quantaalpha/tests/test_debug_failure_filter.py
forbidden_code_paths:
  - third_party/quantaalpha/quantaalpha/cli.py
  - third_party/quantaalpha/quantaalpha/factors/library.py
  - third_party/quantaalpha/quantaalpha/factors/status_rules.py
  - third_party/quantaalpha/quantaalpha/backtest/runner.py
---

# Dev Task: Debug Failure Filter

目标：

- 让后续 debug 轮次只处理失败因子
- 保证成功因子不再进入高成本步骤

本阶段只做开发，不执行测试。

阶段边界：

- 当前是 `dev` 阶段，测试由后续 `test` 阶段负责
- 如果 `agent.md`、`rules.md`、`AGENTS.md` 提到常规验证建议，本阶段一律不执行测试命令
- 需要通过文档交接，而不是在本阶段自行补测试闭环

要做：

- 固定失败因子定义
- 让下一轮真实消费失败集合
- 补齐提前结束和最大轮次保护
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
