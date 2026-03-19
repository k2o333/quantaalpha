# Agent Result

- Task ID: `task-20260318T145729Z-0-parallel-01-revalidate-cli-modes`
- Agent: `codebuddy`
- Run ID: `run-20260318T145729Z`

## Prompt

```
你现在在无头模式下执行一个单 agent 开发任务。

任务目标：
固定 revalidate 的 CLI 语义边界，让 dry-run、status-refresh、real-backtest 三种模式在命令入口和返回结构上可区分。

只允许修改：
- third_party/quantaalpha/quantaalpha/cli.py
- third_party/quantaalpha/tests/test_revalidate_cli.py

禁止修改：
- third_party/quantaalpha/quantaalpha/factors/library.py
- third_party/quantaalpha/quantaalpha/pipeline/loop.py
- third_party/quantaalpha/quantaalpha/backtest/runner.py
- third_party/quantaalpha/quantaalpha/pipeline/factor_backtest.py

必须完成：
1. 固定默认模式、--dry-run、--real-backtest 的入口语义。
2. 区分三种模式的输出字段和返回结构。
3. 让 CLI 失败场景可见。
4. 补齐 third_party/quantaalpha/tests/test_revalidate_cli.py 的开发侧覆盖。

不要做：
1. 不要实现真实回测内部链路。
2. 不要改因子库写入逻辑。
3. 不要改状态流转规则。
4. 不要改调度脚本。
5. 不要运行测试，除非为了读取失败信息而必须运行；如果没跑测试，要在最终回答中明确写出。

审计要求：
你的最终回答必须包含以下小节，且内容具体：
- Modified Files
- Command Log
- Audit Notes
- Risks / Open Items

其中：
- Modified Files 要列出每个实际修改文件及一句摘要。
- Command Log 要列出你实际执行过的命令。
- Audit Notes 要明确说明是否运行测试，以及为什么。
- Risks / Open Items 要写未完成项、风险和假设。
```

## Output

