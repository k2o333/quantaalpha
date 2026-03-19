# Agent Result

- Task ID: `task-20260319T091804Z-0-parallel-01-revalidate-cli-modes`
- Agent: `iflow`
- Run ID: `run-20260319T091804Z`

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

```
## Modified Files

**third_party/quantaalpha/quantaalpha/cli.py**
- 添加三个模式常量：`REVALIDATE_MODE_DRY_RUN`、`REVALIDATE_MODE_STATUS_REFRESH`、`REVALIDATE_MODE_REAL_BACKTEST`
- 添加 `_compute_library_summary()` 辅助函数
- 重写 `revalidate()` 函数：
  - 新增 `real_backtest` 和 `backtest_config` 参数
  - 实现三种模式的入口语义区分（优先级：dry_run > real_backtest > status_refresh）
  - 统一返回结构：`mode`, `total_candidates`, `success`, `failed`, `skipped`, `used_existing_results`, `library_summary`, `details`
  - details 结构：`factor_id`, `before_status`, `after_status`, `stability_score`, `revalidation_source`
  - real_backtest 模式：失败时保留原始状态，单因子失败不中断批次

**third_party/quantaalpha/tests/test_revalidate_cli.py**
- 无修改（fallback 实现已与新 cli.py 逻辑一致）

---

## Command Log

无 shell 命令执行

---

## Audit Notes

1. **模式语义固定**：
   - 默认模式 = `status_refresh`：复用现有 `period_results`，刷新状态
   - `--dry-run`：只返回候选列表，不修改库文件
   - `--real-backtest`：执行真实回测，更新结果

2. **返回结构区分**：
   - `mode` 字段标识当前模式
   - `used_existing_results` 布尔值区分是否使用已有结果
   - `revalidation_source` 字段追踪数据来源

3. **失败场景可见**：
   - 每条 detail 包含 `error` 字段（失败时）
   - 失败时 `after_status` = `before_status`，`stability_score` 保持原值
   - 单因子失败不阻断批次处理

---

## Risks / Open Items

1. **BacktestRunner 集成**：`real_backtest` 模式依赖 `quantaalpha.backtest.runner.BacktestRunner`，实际运行时需要验证该模块的返回结构是否与代码预期一致（`multi_period_validation.period_results` 和 `multi_period_validation.summary`）

2. **临时文件清理**：`real_backtest` 模式创建的临时 JSON 文件未显式删除，依赖操作系统临时目录清理机制

3. **测试执行**：任务要求不做测试执行，建议后续验证 `pytest third_party/quantaalpha/tests/test_revalidate_cli.py`

```

## Stderr

```

<Execution Info>
{
  "session-id": "session-2437eb06-0028-48ea-9453-c45bbb39a82d",
  "conversation-id": "f342580a-a55f-402d-97e1-dd8dc5bfbb0e",
  "assistantRounds": 13,
  "executionTimeMs": 274505,
  "tokenUsage": {
    "input": 49138,
    "output": 593,
    "total": 49731
  }
}
</Execution Info>

```
