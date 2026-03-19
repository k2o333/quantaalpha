# Agent Result

- Task ID: `task-20260319T091556Z-0-parallel-01-revalidate-cli-modes`
- Agent: `iflow`
- Run ID: `run-20260319T091556Z`

## Prompt

```
完成一个开发任务，只做开发，不做测试执行。

目标：
- 固定 revalidate 默认模式、--dry-run、--real-backtest 的入口语义
- 区分三种模式的输出字段和返回结构
- 让 CLI 失败场景可见

只允许修改：
- third_party/quantaalpha/quantaalpha/cli.py
- third_party/quantaalpha/tests/test_revalidate_cli.py

禁止修改：
- third_party/quantaalpha/quantaalpha/factors/library.py
- third_party/quantaalpha/quantaalpha/pipeline/loop.py
- third_party/quantaalpha/quantaalpha/backtest/runner.py
- third_party/quantaalpha/quantaalpha/pipeline/factor_backtest.py

最终输出只保留这四段：
- Modified Files
- Command Log
- Audit Notes
- Risks / Open Items
```

## Output

