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

## Execution Environment

- Preferred Python: `/root/miniforge3/envs/mining/bin/python`
- Preferred CLI binary: `/root/miniforge3/envs/mining/bin/quantaalpha`
- Conda environment: `mining`
- When documenting or running validation commands for `quantaalpha`, prefer the explicit interpreter or CLI path above

## Validation

- Test suite: `/root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests -v`
- Health check: `/root/miniforge3/envs/mining/bin/quantaalpha health_check`
- Compile check: `/root/miniforge3/envs/mining/bin/python -m compileall third_party/quantaalpha/quantaalpha`

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
# dry_run 模式：只输出候选列表
quantaalpha revalidate data/factorlib/all_factors_library.json --dry-run

# status_refresh 模式（默认）：基于历史结果刷新状态
quantaalpha revalidate data/factorlib/all_factors_library.json --status active --no-write

# real_backtest 模式：真正重跑回测
quantaalpha revalidate data/factorlib/all_factors_library.json --real-backtest --backtest-config configs/backtest.yaml
```

当前这个命令是“最小版”：

- 负责筛选候选因子
- 复用已有 `evaluation` 载荷进行状态更新
- 支持 `--dry_run` 和 `--no_write`

revalidate 支持三种模式：

| 模式 | 参数 | 行为 |
|------|------|------|
| `dry_run` | `--dry-run` | 只输出候选列表，不写库 |
| `status_refresh` | (默认) | 基于已有 period_results 刷新状态 |
| `real_backtest` | `--real-backtest` | 真正重跑回测并写回新结果 |

返回结构包含：
- `mode`: 当前模式
- `total_candidates`: 候选因子数
- `success/failed/skipped`: 执行结果统计
- `used_existing_results`: 是否使用历史结果
- `library_summary`: 因子库状态分布

### 6. 外部调度

```bash
cd third_party/quantaalpha
bash scripts/continuous_mine.sh
```

脚本职责：
1. 执行一次 `mine`
2. 执行一次 `revalidate --dry-run`
3. 输出本轮摘要（`SUMMARY: key=value` 格式）

环境变量覆盖：
- `PROJECT_ROOT`: 项目根目录
- `FACTOR_LIBRARY_PATH`: 因子库路径
- `MINE_CONFIG`: mine 配置文件

## 关键模块

| 模块 | 路径 | 作用 |
|---|---|---|
| CLI | `quantaalpha/cli.py` | `mine/backtest/revalidate` 入口（支持三种 revalidate 模式） |
| 回测执行 | `quantaalpha/backtest/runner.py` | 单周期/多周期回测、股票池过滤 |
| 股票池工具 | `quantaalpha/backtest/universe.py` | 过滤规则纯函数 |
| 多周期聚合 | `quantaalpha/backtest/validation.py` | period 校验与聚合、稳定性分数计算 |
| 因子库 | `quantaalpha/factors/library.py` | 因子库兼容、写回、筛选、摘要、审计、文件锁 |
| 状态规则 | `quantaalpha/factors/status_rules.py` | `pending_validation/active/stale/degraded/deprecated` 状态流转 |
| 失败追踪 | `quantaalpha/factors/failure_tracker.py` | 失败因子追踪、重试筛选 |
| 数据能力注册表 | `quantaalpha/factors/data_capability.py` | prompt 注入用的数据能力描述 |
| 场景组装 | `quantaalpha/factors/experiment.py` | 将数据能力说明拼进 scenario |
| evolution | `quantaalpha/pipeline/evolution/` | parent 选择、轨迹、分流 |
| LLM 路由 | `quantaalpha/llm/client.py` | `task_type` 优先的模型选择 |
| 调度脚本 | `scripts/continuous_mine.sh` | 外部调度入口 |

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

Iterate 2 新增测试文件：

| 测试文件 | 覆盖范围 |
|---------|---------|
| `test_revalidate_cli.py` | revalidate 三种模式、返回结构 |
| `test_debug_failure_filter.py` | 失败因子追踪、重试筛选 |
| `test_status_transition.py` | 状态流转规则、阈值断言 |
| `test_planning_constraints.py` | 规划约束、禁止方向拦截 |
| `test_quality_gate.py` | 质量门控、数据质量检查 |
| `test_scheduler_summary.py` | 调度摘要、审计记录 |
| `test_factor_library_locking.py` | 文件锁、并发写入保护 |

推荐验证命令：

```bash
# 运行所有 Iterate 2 测试
/root/miniforge3/envs/mining/bin/python -m pytest third_party/quantaalpha/tests/test_revalidate_cli.py third_party/quantaalpha/tests/test_status_transition.py third_party/quantaalpha/tests/test_planning_constraints.py third_party/quantaalpha/tests/test_quality_gate.py third_party/quantaalpha/tests/test_factor_library_locking.py -v

# 编译检查
/root/miniforge3/envs/mining/bin/python -m compileall third_party/quantaalpha/quantaalpha
```

## 依赖前提

- 需要可用的 Qlib 数据目录
- 因子挖掘需要可用的 OpenAI-compatible LLM API
- 建议使用 `mining` Conda 环境而不是系统 Python

## 相关文档

- [README.md](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/README.md)
- [backtest.yaml](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/configs/backtest.yaml)
- [continuous factor research checklist](/home/quan/testdata/aspipe_v4/docs/03-changes/quantaalpha/2026-03-14-continuous-factor-research-checklist.md)

### Iterate 2 变更文档 (已测试)

- [2.1 revalidate语义澄清与真实复验链路](/home/quan/testdata/aspipe_v4/docs/03-changes/quantaalpha/tested/2026-03-15-iterate2-01-revalidate-semantics-and-real-backtest.md)
- [2.2 失败因子重试过滤](/home/quan/testdata/aspipe_v4/docs/03-changes/quantaalpha/tested/2026-03-15-iterate2-02-failed-factor-debug-filter.md)
- [2.3 质量门控与状态流转回归测试](/home/quan/testdata/aspipe_v4/docs/03-changes/quantaalpha/tested/2026-03-15-iterate2-03-quality-gate-and-state-regression.md)
- [2.4 外部调度脚本与状态审计](/home/quan/testdata/aspipe_v4/docs/03-changes/quantaalpha/tested/2026-03-15-iterate2-04-external-scheduler-summary-and-audit.md)
- [2.5 因子库写入保护](/home/quan/testdata/aspipe_v4/docs/03-changes/quantaalpha/tested/2026-03-15-iterate2-05-factor-library-write-lock.md)
