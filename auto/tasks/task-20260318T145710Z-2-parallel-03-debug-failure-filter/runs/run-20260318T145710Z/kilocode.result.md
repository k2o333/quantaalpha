# Agent Result

- Task ID: `task-20260318T145710Z-2-parallel-03-debug-failure-filter`
- Agent: `kilocode`
- Run ID: `run-20260318T145710Z`

## Prompt

```
你现在在无头模式下执行一个单 agent 开发任务。

任务目标：
让 debug 后续轮次只重新处理失败因子，而不是整批重复进入 coder/backtest。

只允许修改：
- third_party/quantaalpha/quantaalpha/pipeline/loop.py
- third_party/quantaalpha/tests/test_debug_failure_filter.py

禁止修改：
- third_party/quantaalpha/quantaalpha/cli.py
- third_party/quantaalpha/quantaalpha/factors/library.py
- third_party/quantaalpha/quantaalpha/factors/status_rules.py
- third_party/quantaalpha/quantaalpha/backtest/runner.py

必须完成：
1. 固定失败因子的代码级定义。
2. 让下一轮 debug 真实消费 failed_factor_ids。
3. 全部成功时提前结束。
4. 全部失败时仍受最大轮次保护。
5. 补齐 test_debug_failure_filter.py。

不要做：
1. 不要改 CLI 模式。
2. 不要改因子库写逻辑。
3. 不要改状态阈值和质量门控规则。
4. 不要扩展 LLM 路由策略。
5. 默认不要运行测试；如确有必要，只运行最小局部命令，并在最终回答中写明。

审计要求：
你的最终回答必须包含以下小节，且内容具体：
- Modified Files
- Command Log
- Audit Notes
- Risks / Open Items

其中：
- Audit Notes 必须明确说明第二轮集合如何缩减。
- 如果未跑测试，必须直接写明未跑测试。
```

## Output

