---
source_dev_task_doc: docs/03-changes/quantaalpha/planned/parrelell/dev/parallel-01-revalidate-cli-modes.task.md
task_kind: headless_code_review
goal: 复核 revalidate CLI 模式边界任务的实现质量
review_only: true
audit_required: true
---

# Task

单个 agent 完成这块 code review，只做审查，不做代码修改，不做测试执行。

## Review 目标

- 检查默认模式、`--dry-run`、`--real-backtest` 的入口语义是否被正确实现
- 检查三种模式的输出字段和返回结构是否清晰且没有重复实现
- 检查 CLI 失败场景是否真实可见
- 检查是否越界修改了不该动的文件

## 重点关注

- `third_party/quantaalpha/quantaalpha/cli.py`
- `third_party/quantaalpha/tests/test_revalidate_cli.py`
- 如有必要，可只读查看：
  - `third_party/quantaalpha/quantaalpha/pipeline/factor_backtest.py`
  - `third_party/quantaalpha/quantaalpha/backtest/runner.py`
  - `third_party/quantaalpha/quantaalpha/factors/library.py`

## 输出要求

最终输出只保留这四段：

- Findings
- Open Questions
- Files Checked
- Residual Risks

如果没有发现问题，`Findings` 里明确写 `No findings`。
