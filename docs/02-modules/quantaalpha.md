# quantaalpha

**Status:** active
**Created:** 2026-03-14

---

## TL;DR

- `quantaalpha` is the factor mining and evaluation subsystem under `third_party/quantaalpha/`.
- Most task entrypoints are CLI commands, backtest config, factor library files, and tests.
- High-risk edits are factor-library schema changes, evaluation status rules, and backtest semantics.

## Entrypoints

- CLI: `third_party/quantaalpha/quantaalpha/cli.py`
- Configs: `third_party/quantaalpha/configs/`
- Factor library: `third_party/quantaalpha/data/factorlib/`
- Core package: `third_party/quantaalpha/quantaalpha/`
- Tests: `third_party/quantaalpha/tests/`

## Validation

- Test suite: `pytest third_party/quantaalpha/tests -v`
- Health check: `quantaalpha health_check`
- Compile check: `python -m compileall third_party/quantaalpha/quantaalpha`

## Do Not Touch Blindly

- factor-library schema and migration behavior
- status transition rules
- backtest validation flow
- LLM routing behavior

Check related change docs in `docs/03-changes/quantaalpha/` before editing these areas.

## Known Risks At A Glance

- schema drift can break existing factor libraries
- evaluation logic changes can invalidate prior statuses
- environment assumptions often depend on the `mining` conda environment

---

`quantaalpha` 是仓库里的因子挖掘与回测子系统，代码位于 [third_party/quantaalpha](/home/quan/testdata/aspipe_v4/third_party/quantaalpha)。当前这个工作区已经在原始项目基础上补了持续因子研究相关入口，所以这里更关注“怎么用”和“实际有哪些能力”。

## 主要职责

- 用 LLM 生成因子研究假设和因子表达式
- 调用 Qlib 数据与回测链路验证因子
- 把结果写入统一因子库
- 支持多轮 evolution
- 支持连续研究需要的复验、状态字段、多周期验证结果

## 当前可用命令

在本仓库建议使用：

```bash
cd /home/quan/testdata/aspipe_v4/third_party/quantaalpha
conda activate mining
```

CLI 入口：

```bash
quantaalpha mine
quantaalpha backtest
quantaalpha revalidate
quantaalpha health_check
quantaalpha collect_info
```

更底层的回测入口：

```bash
python -m quantaalpha.backtest.run_backtest -c configs/backtest.yaml
```

## 常见使用方式

### 1. 运行因子挖掘

```bash
./run.sh "Price-Volume Factor Mining"
```

或直接走 CLI 主入口：

```bash
quantaalpha mine --help
```

产物通常会落在：

- `data/results/`
- `data/factorlib/all_factors_library*.json`

### 2. 运行独立回测

```bash
python -m quantaalpha.backtest.run_backtest \
  -c configs/backtest.yaml \
  --factor-source custom \
  --factor-json data/factorlib/all_factors_library.json
```

也可以混合官方因子：

```bash
python -m quantaalpha.backtest.run_backtest \
  -c configs/backtest.yaml \
  --factor-source combined \
  --factor-json data/factorlib/all_factors_library.json
```

### 3. 启用统一股票池过滤

配置文件： [backtest.yaml](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/configs/backtest.yaml)

```yaml
data:
  stock_filter:
    enabled: true
    exclude_markets: ["bj"]
    exclude_st: true
    min_list_days: 60
```

作用：

- 统一 dataset 构建和回测使用的股票池
- 在结果 JSON 写入 `universe` 元数据

### 4. 启用多周期验证

```yaml
multi_period_validation:
  enabled: true
  fail_fast: true
  periods:
    - name: recent
      train: ["2022-01-01", "2023-12-31"]
      valid: ["2024-01-01", "2024-06-30"]
      test: ["2024-07-01", "2025-03-13"]
    - name: historical
      train: ["2017-01-01", "2019-12-31"]
      valid: ["2020-01-01", "2020-12-31"]
      test: ["2021-01-01", "2021-12-31"]
```

输出位置：

- `metrics.multi_period_validation.period_results`
- `metrics.multi_period_validation.summary`
- `metrics.stability_score`

### 5. 复验因子库

```bash
quantaalpha revalidate data/factorlib/all_factors_library.json --dry_run
quantaalpha revalidate data/factorlib/all_factors_library.json --status active --no_write
quantaalpha revalidate data/factorlib/all_factors_library.json --days 30
```

当前这个命令是“最小版”：

- 负责筛选候选因子
- 复用已有 `evaluation` 载荷进行状态更新
- 支持 `--dry_run` 和 `--no_write`

## 关键模块

| 模块 | 路径 | 作用 |
|---|---|---|
| CLI | `quantaalpha/cli.py` | `mine/backtest/revalidate` 入口 |
| 回测执行 | `quantaalpha/backtest/runner.py` | 单周期/多周期回测、股票池过滤 |
| 股票池工具 | `quantaalpha/backtest/universe.py` | 过滤规则纯函数 |
| 多周期聚合 | `quantaalpha/backtest/validation.py` | period 校验与聚合 |
| 因子库 | `quantaalpha/factors/library.py` | 因子库兼容、写回、筛选 |
| 状态规则 | `quantaalpha/factors/status_rules.py` | `pending_validation/active/stale/degraded/deprecated` |
| 数据能力注册表 | `quantaalpha/factors/data_capability.py` | prompt 注入用的数据能力描述 |
| 场景组装 | `quantaalpha/factors/experiment.py` | 将数据能力说明拼进 scenario |
| evolution | `quantaalpha/pipeline/evolution/` | parent 选择、轨迹、分流 |
| LLM 路由 | `quantaalpha/llm/client.py` | `task_type` 优先的模型选择 |

## 因子库结构

当前因子库会兼容旧 JSON，并在读取时补齐新字段：

```json
{
  "evaluation": {
    "status": "pending_validation",
    "last_validated": null,
    "stability_score": null,
    "period_results": [],
    "validation_summary": "",
    "consecutive_failures": 0
  },
  "data_requirements": {
    "dimensions": ["price_volume"],
    "fields": ["$close", "$volume"]
  }
}
```

## LLM 路由

当前支持任务级路由，优先级高于旧的 `chat_model_map`：

1. 显式 `task_type`
2. `routing_tasks`
3. `chat_model_map`
4. `chat_model`

已接入的任务类型：

- `hypothesis_generation`
- `factor_construction`
- `feedback_summarization`

## 测试与验证

这次工作区新增能力的轻量测试在：

- [test_continuous_factor_features.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/tests/test_continuous_factor_features.py)

推荐验证命令：

```bash
/root/miniforge3/envs/mining/bin/python -m unittest -q third_party/quantaalpha/tests/test_continuous_factor_features.py
/root/miniforge3/envs/mining/bin/python -m compileall third_party/quantaalpha/quantaalpha
```

## 依赖前提

- 需要可用的 Qlib 数据目录
- 因子挖掘需要可用的 OpenAI-compatible LLM API
- 建议使用 `mining` Conda 环境而不是系统 Python

## 相关文档

- [README.md](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/README.md)
- [backtest.yaml](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/configs/backtest.yaml)
- [quantaalpha2026-3-14checklist README](/home/quan/testdata/aspipe_v4/docs/03-changes/quantaalpha/quantaalpha2026-3-14checklist/README.md)
