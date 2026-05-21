# Factor Ops

`factor_ops` 是 QuantaAlpha 因子挖掘后的自动化运营层，负责把候选因子从挖掘产物推进到可审计的 Gate、Evaluate、Lifecycle、Consumer 和报告闭环。

它不替代因子挖掘、回测执行或 app5 数据下载。它消费这些事实源：

- `FactorStoreFacade` / 因子库 registry
- app5 manifest、active parquet、schema、freshness、coverage evidence
- factor values parquet
- returns parquet
- continuous run summary

## Operator Flow

推荐流程：

```text
mining 产生候选因子
-> factor-ops post-mining
-> data-quality gate / redundancy gate
-> evaluate health / decay / regime / cluster / tier / suggested status
-> apply-status 写 metadata_json.ops 和 lifecycle_log
-> consumer payload 暴露 TS-GRU / portfolio 可用因子
-> daily workflow 根据 data update / revalidation / trigger 持续复查
-> monthly-report 汇总拒绝、退化、数据缺口和 mining prompt feedback
```

现有长驻挖掘入口仍然支持：

```bash
/root/miniforge3/envs/mining/bin/python -m quantaalpha.continuous.main start \
  --config /home/quan/testdata/aspipe_v4/config/pipeline.yaml --skip-update
```

这里的 `--skip-update` 表示跳过真实 app5 fetch/update，适合冒烟和性能测试；它不会跳过 app5 manifest、schema、freshness evidence 检查，也不会跳过 factor_ops hook。

`continuous.main once/start` 每轮通过 `quantaalpha.continuous.factor_ops_hook.run_factor_ops_cycle()` 调用共享 workflow runner，并把结构化结果写入 continuous run summary 的 `factor_ops` 字段。app4 bridge 只作为旧 continuous 链路的迁移期配置存在，不是 factor_ops 的推荐数据入口。

## CLI Commands

所有命令都挂在顶层 CLI：

```bash
/root/miniforge3/envs/mining/bin/python -m quantaalpha.cli factor-ops <command>
```

可用命令：

```text
factor-ops status
factor-ops gate
factor-ops evaluate
factor-ops post-mining
factor-ops apply-status
factor-ops daily
factor-ops monthly-report
factor-ops acceptance
```

查看状态：

```bash
/root/miniforge3/envs/mining/bin/python -m quantaalpha.cli factor-ops status \
  --library-path /home/quan/testdata/aspipe_v4/third_party/quantaalpha/data/factorlib/parquet_store
```

运行 Gate：

```bash
/root/miniforge3/envs/mining/bin/python -m quantaalpha.cli factor-ops gate factor_001 \
  --factor-values /path/to/factor_001.parquet \
  --storage-root /home/quan/testdata/aspipe_v4/log/factor_ops
```

运行 Evaluate：

```bash
/root/miniforge3/envs/mining/bin/python -m quantaalpha.cli factor-ops evaluate factor_001 \
  --factor-values /path/to/factor_001.parquet \
  --returns /path/to/returns.parquet \
  --library-path /home/quan/testdata/aspipe_v4/third_party/quantaalpha/data/factorlib/parquet_store \
  --no-write
```

挖掘后批处理：

```bash
/root/miniforge3/envs/mining/bin/python -m quantaalpha.cli factor-ops post-mining \
  --library-path /home/quan/testdata/aspipe_v4/third_party/quantaalpha/data/factorlib/parquet_store \
  --factor-values /path/to/factor_values.parquet \
  --returns /path/to/returns.parquet \
  --storage-root /home/quan/testdata/aspipe_v4/log/factor_ops \
  --dry-run
```

写回运营状态：

```bash
/root/miniforge3/envs/mining/bin/python -m quantaalpha.cli factor-ops apply-status factor_001 \
  --library-path /home/quan/testdata/aspipe_v4/third_party/quantaalpha/data/factorlib/parquet_store \
  --storage-root /home/quan/testdata/aspipe_v4/log/factor_ops \
  --to candidate \
  --tier C \
  --health-score 55 \
  --expected-version 0 \
  --reason "gate and evaluate passed"
```

生成月报：

```bash
/root/miniforge3/envs/mining/bin/python -m quantaalpha.cli factor-ops monthly-report \
  --library-path /home/quan/testdata/aspipe_v4/third_party/quantaalpha/data/factorlib/parquet_store \
  --storage-root /home/quan/testdata/aspipe_v4/log/factor_ops \
  --month 2026-05 \
  --format markdown \
  --output /home/quan/testdata/aspipe_v4/log/factor_ops/reports/2026-05.md
```

最小闭环验收：

```bash
/root/miniforge3/envs/mining/bin/python -m quantaalpha.cli factor-ops acceptance \
  --storage-root /home/quan/testdata/aspipe_v4/log/factor_ops
```

## Write Semantics

写入命令支持两个保护开关：

- `--dry-run`: 只选择和计算，不写 registry、gate_log、lifecycle_log、report。
- `--no-write`: 尽量执行计算，但跳过 durable write。

写入型命令会在返回结果中暴露 `written`：

- `written=true`: 本次确实写入 durable artifact。
- `written=false`: dry-run/no-write 或输出路径缺失。

错误结果使用 `success=false`，顶层 `quantaalpha.cli.app()` 会把这类结果转换为非零退出。

## Data Automation

factor_ops 数据自动化目标是 app5，不是 app4。

`config/pipeline.yaml` 中相关配置：

- `app5_data`: app5 `data_root`、`interface_dir`、`groups`、freshness threshold、python executable、transport。
- `factor_ops`: storage root、parquet factor library path、factor values、returns、dry-run 默认行为。

`--skip-update` 只跳过真实 app5 fetch/update，不跳过 evidence 检查。workflow 仍会读取 app5 `manifest/current.json`、active parquet schema、latest date、row count、schema hash 和 manifest drift。

缺失输入不会被 fallback 掩盖：

- 缺 factor values: `reason=missing_input`
- 缺 returns: `missing_returns=true`
- 缺 app5 manifest: `manifest_pass=false`
- 缺 active parquet 关键列: `schema_pass=false`

app4 bridge 仍可能在旧 continuous 调度里存在，但 factor_ops 新验收路径只消费 app5 evidence。

## Outputs

默认输出位置：

- Gate log: `<storage_root>/gate_log/year=YYYY/month=MM/*.parquet`
- Lifecycle log: `<storage_root>/lifecycle_log/year=YYYY/month=MM/*.parquet`
- Monthly report: `monthly-report --output` 指定路径
- Continuous run summary: `/home/quan/testdata/aspipe_v4/log/mining/continuous/runs/run_*.json`

## Code Map

- CLI command group: [commands.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factor_ops/commands.py)
- Workflow runners: [workflows/](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factor_ops/workflows)
- Gate contracts: [gate/](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factor_ops/gate)
- Evaluate contracts: [eval/](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factor_ops/eval)
- Lifecycle writer/updater: [lifecycle/](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factor_ops/lifecycle)
- Registry updater: [registry/updater.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factor_ops/registry/updater.py)
- Consumer payload builders: [consumer/](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factor_ops/consumer)
- Continuous hook: [factor_ops_hook.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/continuous/factor_ops_hook.py)
- Operator runbook: [Runbook.md](/home/quan/testdata/aspipe_v4/docs/tasks/archive/factor-ops-cli-workflow/Runbook.md)

## Verification

Focused verification:

```bash
/root/miniforge3/envs/mining/bin/python -m pytest \
  third_party/quantaalpha/tests/test_factor_ops_cli_workflow.py \
  third_party/quantaalpha/tests/test_factor_ops_workflows.py -q
```

Core regression:

```bash
/root/miniforge3/envs/mining/bin/python -m pytest \
  third_party/quantaalpha/tests/test_factor_ops_common_engines.py \
  third_party/quantaalpha/tests/test_factor_ops_logs.py \
  third_party/quantaalpha/tests/test_factor_ops_data_quality_gate.py \
  third_party/quantaalpha/tests/test_factor_ops_redundancy_gate.py \
  third_party/quantaalpha/tests/test_factor_ops_acceptance.py \
  third_party/quantaalpha/tests/test_factor_ops_cli_workflow.py \
  third_party/quantaalpha/tests/test_factor_ops_workflows.py -q
```
