---
status: planned
owner: Codex
created: 2026-03-18
parallel_mode: true
parallel_group: quantaalpha-iterate2-pilot
slice_id: slice_3
priority: P0
parent_source_docs:
  - docs/03-changes/quantaalpha/planned/2026-03-15-iterate2-02-failed-factor-debug-filter.md
goal: 让 debug 后续轮次只重新处理失败因子，而不是整批重复进入 coder/backtest
allowed_code_paths:
  - third_party/quantaalpha/quantaalpha/pipeline/loop.py
  - third_party/quantaalpha/tests/test_debug_failure_filter.py
forbidden_code_paths:
  - third_party/quantaalpha/quantaalpha/cli.py
  - third_party/quantaalpha/quantaalpha/factors/library.py
  - third_party/quantaalpha/quantaalpha/factors/status_rules.py
  - third_party/quantaalpha/quantaalpha/backtest/runner.py
test_targets:
  - third_party/quantaalpha/tests/test_debug_failure_filter.py
disproof_command: /root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests/test_debug_failure_filter.py -q
---

# Parallel Slice 3: Debug Failure Filter

## 目标

把后续 debug 轮次的处理集合改成“只保留失败因子”，并保证成功因子不会重复进入高成本步骤。

## 输入契约

- `AlphaAgentLoop` 是本功能的唯一真实消费者
- 失败因子定义必须来自真实执行结果，而不是纯日志猜测

## 输出契约

每轮执行后，循环内部至少应形成：

- `successful_factor_ids`
- `failed_factor_ids`
- `failed_reasons`

下一轮 debug 只消费 `failed_factor_ids`。

## 必须做的事

1. 固定失败因子的代码级定义。
2. 让下一轮 debug 真实消费失败集合。
3. 全部成功时提前结束 debug。
4. 全部失败时仍受最大轮次保护。
5. 新增或补齐 `test_debug_failure_filter.py`。

## 明确不做

1. 不改 CLI 模式。
2. 不改因子库写逻辑。
3. 不改状态阈值和质量门控规则。
4. 不做 LLM 路由策略扩展。

## 测试要求

自动化测试至少覆盖：

1. 混合成功/失败时，第二轮只处理失败因子。
2. 成功因子不会再次进入 coder/backtest。
3. 全部成功时提前退出。
4. 全部失败时仍受最大轮次限制。
5. 失败原因能被聚合记录。

## 通过标准

必须同时满足：

1. `test_debug_failure_filter.py` 能独立通过。
2. 至少有一个测试直接断言第二轮传入集合已缩减。
3. 不能只靠日志字段或 tracker 字段证明完成。

