# QuantaAlpha

QuantaAlpha 是一个面向量化因子研究的自动化挖掘模块，覆盖数据能力发现、因子生成、表达式编码、回测验证、因子入库、持续重验与 RAG 增强检索。

这个 README 面向第一次进入本子模块的开发者，帮助快速定位核心闭环、主要入口和常用命令。更细的使用说明可参考 [quantaalpha_usage_guide.txt](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha_usage_guide.txt)。

## 模块闭环

QuantaAlpha 当前主要由 9 个闭环组成：

1. 数据下载与能力注入
   Parquet 数据经过 `data_capability.py` 做 schema 注册、`available_from` 推断与 PIT 对齐，最终注入因子挖掘 prompt。

2. 因子挖掘核心循环
   假设生成 -> 因子构造 -> 编码计算 -> 回测验证 -> 反馈学习。核心循环在 [loop.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/pipeline/loop.py)。

3. 因子库生命周期
   因子入库、状态迁移、定期重验由 [library.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/library.py) 和 [status_rules.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/status_rules.py) 管理。

4. RAG 增强挖掘
   活跃因子可同步到向量库，由 [vector_store.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/vector_store.py) 和 [fewshot.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/fewshot.py) 提供语义或 fallback 检索能力。

5. 连续调度自治
   数据监控、触发挖掘、重验与熔断逻辑集中在 [main.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/continuous/main.py) 和 [orchestrator.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/continuous/orchestrator.py)。

6. 质量管控
   一致性、复杂度、冗余检查由 [consistency_checker.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py) 等模块完成。

7. 容错与恢复
   多 Provider 健康监控、空响应检测、有限重试与故障恢复位于 `llm/*` 与因子循环内部。

8. 进化探索
   Original / Mutation / Crossover 的进化式探索由 `pipeline/evolution/*` 控制。

9. 因子自动化运营
   挖掘后的候选因子由 `factor_ops` 串接 Gate、Evaluate、Lifecycle、Consumer、daily workflow 和 monthly report。模块说明见 [factor_ops README](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factor_ops/README.md)，操作手册见 [Runbook.md](/home/quan/testdata/aspipe_v4/docs/tasks/archive/factor-ops-cli-workflow/Runbook.md)。

## 关键入口

如果你只想快速找到主入口，优先看这些文件：

- CLI 入口: [cli.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/cli.py)
- 启动入口: [launcher.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/launcher.py)（位于仓库顶层，不在 quantaalpha 包内）
- 因子挖掘主循环: [loop.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/pipeline/loop.py)
- 多方向挖掘与进化编排: [factor_mining.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/pipeline/factor_mining.py)
- 因子库管理: [library.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/library.py)
- 数据能力发现: [data_capability.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/data_capability.py)
- 标签推断: [tag_inference.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/tag_inference.py)
- 向量检索: [vector_store.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/vector_store.py)
- Few-shot / RAG 注入: [fewshot.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/fewshot.py)
- 持续运行主入口: [main.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/continuous/main.py)
- 连续调度设计说明: [DESIGN.md](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/continuous/DESIGN.md)
- factor_ops CLI 命令组: [commands.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factor_ops/commands.py)
- factor_ops workflow runners: [workflows/](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factor_ops/workflows)
- factor_ops continuous hook: [factor_ops_hook.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/continuous/factor_ops_hook.py)

## 目录结构

核心目录大致如下：

- `quantaalpha/pipeline/`
  因子挖掘循环、回测衔接、进化编排。
- `quantaalpha/factors/`
  因子表达式、因子库、标签、RAG、质量门控、加载器。
- `quantaalpha/continuous/`
  连续运行、调度、熔断、影响分桶、告警。
- `quantaalpha/factor_ops/`
  因子挖掘后的 Gate、Evaluate、Lifecycle、Consumer、daily workflow 和 report 自动化运营层。
- `quantaalpha/llm/`
  Provider 池、客户端与模型相关配置。
- `quantaalpha/tests/`
  子模块自带测试。
- `data/`
  因子库、回测结果和中间产物。
- `configs/`
  实验与回测配置。

## 环境准备

在仓库根目录外单独进入本模块后：

```bash
cd /home/quan/testdata/aspipe_v4/third_party/quantaalpha
conda activate mining
quantaalpha health_check
```

如果通过主仓库统一环境运行，请确认这些环境变量已配置：

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `QLIB_DATA_DIR`
- `DATA_RESULTS_DIR`

## 常用命令

### 因子挖掘

```bash
quantaalpha mine --direction "动量反转因子挖掘"
./run.sh "价格量价关系因子"
quantaalpha mine --help
```

默认实验配置可参考 `configs/experiment.yaml`，其中通常会预设：

- `evolution.enabled: true`
- `max_rounds`
- `quality_gate.consistency_enabled: true`

### 因子重验

```bash
# parquet 因子池重验走 continuous backend，FactorStoreFacade 读取 parquet_store。
# 标准运行不跳过数据更新；只有 smoke/perf 诊断才显式加 --skip-update。
/root/miniforge3/envs/mining/bin/python -m quantaalpha.continuous.main once \
  --config /home/quan/testdata/aspipe_v4/config/pipeline.yaml
```

### 独立回测

```bash
python -m quantaalpha.backtest.run_backtest \
  -c configs/backtest.yaml \
  --factor-source alpha158_20

# 旧 `--factor-json` 入口只用于历史 JSON 文件排查；生产因子池以
# data/factorlib/parquet_store 为事实源。
```

### 连续运行模式

```bash
# 标准持续运行（含数据更新）
/root/miniforge3/envs/mining/bin/python -m quantaalpha.continuous.main start \
  --config /home/quan/testdata/aspipe_v4/config/pipeline.yaml

# 跳过真实 app5 fetch/update（适用于冒烟/性能测试）
# 仍会读取 app5 manifest/schema/freshness evidence，并写入 factor_ops run summary。
/root/miniforge3/envs/mining/bin/python -m quantaalpha.continuous.main start \
  --config /home/quan/testdata/aspipe_v4/config/pipeline.yaml \
  --skip-update

# 单次执行，同样走 app5 evidence 和 factor_ops hook
/root/miniforge3/envs/mining/bin/python -m quantaalpha.continuous.main once \
  --config /home/quan/testdata/aspipe_v4/config/pipeline.yaml
```

说明：`app4_bridge` 仅是旧 continuous 链路的迁移期配置；新接入的 `factor_ops` 自动化运营路径使用 `app5_data` evidence，不再把 App4 作为推荐数据入口。

### 因子自动化运营

```bash
# 因子池运营状态
/root/miniforge3/envs/mining/bin/python -m quantaalpha.cli factor-ops status \
  --library-path /home/quan/testdata/aspipe_v4/third_party/quantaalpha/data/factorlib/parquet_store

# 挖掘后批处理，默认建议先 dry-run
/root/miniforge3/envs/mining/bin/python -m quantaalpha.cli factor-ops post-mining \
  --library-path /home/quan/testdata/aspipe_v4/third_party/quantaalpha/data/factorlib/parquet_store \
  --factor-values /path/to/factor_values.parquet \
  --returns /path/to/returns.parquet \
  --storage-root /home/quan/testdata/aspipe_v4/log/factor_ops \
  --dry-run

# 最小闭环验收
/root/miniforge3/envs/mining/bin/python -m quantaalpha.cli factor-ops acceptance \
  --storage-root /home/quan/testdata/aspipe_v4/log/factor_ops
```

完整命令、输入要求、dry-run/no-write 语义和输出路径见 [factor_ops README](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factor_ops/README.md)。

### Web 界面

```bash
cd frontend-v2
bash start.sh
```

默认访问地址是 `http://localhost:3000`。

## 输出路径

常见输出位置：

- 因子库: `data/factorlib/parquet_store`
- 回测指标: `data/results/backtest_v2_results/*_backtest_metrics.json`
- 回测汇总: `data/results/backtest_v2_results/batch_summary.json`
- 日志: `log/`
- 连续运行摘要: `log/mining/continuous/runs/`

## Python API 示例

```python
from quantaalpha.factors.factor_store_facade import FactorStoreFacade

store = FactorStoreFacade("data/factorlib/parquet_store")
records = store.read_effective_factor_records()

print(f"总因子数: {len(records)}")
print(f"delta 文件数: {store.delta_file_count()}")
```

## 配置说明

常用配置文件：

- `configs/experiment.yaml`
  挖掘主实验配置，包括 planning、execution、evolution、quality_gate 和 provider_pool。
- `configs/backtest.yaml`
  回测配置，包括股票池过滤和多周期验证。
- `.env`
  环境变量与路径配置。
- `/home/quan/testdata/aspipe_v4/config/pipeline.yaml`
  连续运行模式的统一配置，涵盖 LLM、运行时、app5 data automation、factor_ops workflow、验证、熔断、退化检测、挖掘策略等；旧 `app4_bridge` 仅作为迁移期配置保留。

## 开发提示

- 因子标签补全与兜底逻辑现在依赖统一标签推断模块，不要在多个入口各写一套标签规则。
- 向量检索支持 ChromaDB，也支持 fallback-safe Jaccard 模式；在依赖不完整的环境里不要默认假设语义检索可用。
- 连续调度链路的真实接线点优先看 `continuous/main.py`，不要只盯着单个 adapter 或 helper。
- 当前工作树里可能存在临时文件或历史产物，提交前先做针对性清理和确认。

---

## 因子挖掘回测流程详解

### 回测模型

回测使用 **LightGBM (LGBModel)**，核心超参数如下：

| 参数 | 值 | 说明 |
|------|------|------|
| `loss` | mse | 均方误差损失 |
| `max_depth` | 8 | 树最大深度 |
| `num_leaves` | 210 | 叶节点数 |
| `num_threads` | 20 | 并行线程数 |
| `num_boost_round` | 500 | 最大迭代轮数 |
| `early_stopping_round` | 50 | 早停轮数 |

### 数据源

因子挖掘涉及两套数据源，在不同阶段使用：

1. **HDF5 (`daily_pv.h5`)** — 因子值计算阶段使用
   - 包含日线价格量数据（open/high/low/close/volume 等）
   - 由 `qlib_utils.generate_data_folder_from_qlib()` 从 Qlib 数据生成
   - 因子表达式的编码与计算基于此文件

2. **Qlib 数据目录** — LightGBM 回测阶段使用
   - 由 QlibDataLoader 加载基线因子
   - 由 StaticDataLoader 加载已挖掘因子的 Parquet 文件
   - 两者通过 NestedDataLoader 合并

### 基线因子

模型输入的 4 个基线因子（定义在 `conf_baseline.yaml` 中）：

| 因子 | 表达式 | 含义 |
|------|--------|------|
| 日收益率 | `($close-$open)/$open` | 当日涨跌幅 |
| 量比 | `$volume/Mean($volume, 20)` | 成交量与 20 日均量之比 |
| 振幅 | `($high-$low)/Ref($close, 1)` | 当日振幅相对前收 |
| 动量 | `$close/Ref($close, 1)-1` | 前日收益率 |

### 标签 (Label)

```
Ref($close, -2)/Ref($close, -1) - 1
```

含义：**T+2 日收盘价 / T+1 日收盘价 - 1**，即 T+1 到 T+2 的收益率。注意这不是"未来 2 日相对于 1 日的超额收益"，而是单纯的 T+1→T+2 收益率。

### 数据加载器与配置选择

- **第一轮（无历史实验）**：使用 `conf_baseline.yaml`，仅加载 QlibDataLoader 的 4 个基线因子
- **后续轮次（有已挖掘因子）**：使用 `conf_combined_factors.yaml`，通过 NestedDataLoader 合并：
  - QlibDataLoader：4 个基线因子
  - StaticDataLoader：从 `combined_factors_df.parquet` 加载已挖掘因子

### 股票池与时间切分

存在两套时间切分，取决于使用的配置文件：

#### `experiment.yaml`（单次挖掘模式）

| 阶段 | 时间范围 |
|------|----------|
| 训练集 | 2016-01-01 ~ 2019-12-31 |
| 验证集 | 2020-01-01 ~ 2020-12-31 |
| 测试集 | 2021-01-01 ~ 2025-12-26 |

#### `pipeline.yaml`（连续运行模式）

| 阶段 | 时间范围 |
|------|----------|
| 训练集 | 2020-01-01 ~ 2022-12-31 |
| 验证集 | 2023-01-01 ~ 2023-12-31 |
| 测试集 | 2024-01-01 ~ 2024-12-31 |

### 预处理流水线 (DataHandlerLP)

```
Fillna → DropnaLabel → CSRankNorm
```

1. **Fillna**：填充缺失值
2. **DropnaLabel**：删除标签为 NaN 的样本
3. **CSRankNorm**：横截面秩标准化

### 回测策略

- **策略**: TopkDropoutStrategy
- **TopK**: 50（持仓前 50 只股票）
- **N_drop**: 5（每次调仓卖出 5 只）
- **回测区间**: 测试集第一年（PortAnaRecord）
- **账户初始资金**: 1 亿
- **基准**: 沪深 300 (SH000300)

### 三类记录与评估指标

回测产生三类 Record，覆盖不同评估维度：

| Record 类型 | 评估范围 | 说明 |
|-------------|----------|------|
| SignalRecord | 全部测试集 | 生成预测信号 |
| SigAnaRecord | 全部测试集 | 计算 IC / Rank IC 等指标（**注意：非仅 1 年**） |
| PortAnaRecord | 测试集第一年 | 组合回测（Sharpe、最大回撤等） |

**重要区分**：IC/Rank IC 分析（SigAnaRecord）覆盖完整测试集（如 2021-2025 约 5 年），而组合回测（PortAnaRecord）仅 1 年。

### 因子挖掘核心循环 (AlphaAgentLoop)

```
因子假设生成 (factor_propose)
    → 因子构造 (factor_construct)
    → 因子计算 (factor_calculate)
    → 因子回测 (factor_backtest)
    → 反馈学习 (feedback)
```

#### 假设生成增强

- `_propose_with_ensemble()`: 使用 ThreadPoolExecutor 进行多模型并行假设生成
- `_with_step_model()`: 步骤级模型路由上下文管理器

#### 回测结果追踪

`_track_backtest_result()` 跟踪成功/失败，兼容两种结果格式：
- `sub_results` 字典（多子结果）
- `result` DataFrame/Series（单一结果）

### 因子存储 (Parquet Store)

- 因子通过 `save_factors_to_parquet()` 以 Parquet 格式入库
- 元数据包括：`experiment_id`、`evolution_phase`、`trajectory_id`
- 增量存储：新因子写入 delta shard 文件
- 合并机制：`maybe_compact_after_save()` 在 delta 文件数超过阈值（默认 100）时触发合并
- 去重：使用 pandarallel 进行并行去重，IC 阈值 < 0.99 视为重复
- 相似度引擎 (SimilarityEngine): AST + Jaccard 因子去重

### 质量门控

因子入库前需通过质量检查：

| 指标 | 阈值 | 说明 |
|------|------|------|
| `MIN_VALID_RATIO` | 0.6 | 最小有效率 |
| `MAX_NAN_RATIO` | 0.4 | 最大 NaN 比率 |
| `MIN_UNIQUE_VALUES` | 2 | 最小唯一值数 |

连续运行模式 (`pipeline.yaml`) 下还有额外的质量门控：

| 指标 | 阈值 |
|------|------|
| `min_ic` | 0.018 |
| `min_rank_ic` | 0.03 |
| `max_correlation` | 0.7 |
| `min_sharpe` | 0.3 |

### 进化系统

因子挖掘的进化流程为 Original → Mutation → Crossover 三阶段：

```
Original（原始因子生成）
    → Mutation（变异，对已有因子做小修改）
    → Crossover（交叉，组合不同因子的特征）
```

- 支持 `multiprocessing.Process` 并行执行
- 通过 `Queue` 收集并行结果
- 连续运行模式下的编排 DAG: `original → mutation → [llm_decide] → crossover → stop`
  - 其中 `llm_decide` 是条件节点，决定是否进入 crossover 阶段

### 资源消耗

- 单次因子回测：约 4-8 核 CPU、4-8 GB 内存
- 并行执行时：CPU 和内存按并行分支数倍增
- 每轮因子超时: 300 秒（5 分钟）

---

## 两种运行入口对比

QuantaAlpha 有两种主要运行方式：**单次挖掘模式** 和 **连续运行模式**。

### 入口一：单次挖掘模式

```bash
/root/miniforge3/envs/mining/bin/python -m quantaalpha.pipeline.factor_mining
```

- **配置文件**: `configs/experiment.yaml`
- **执行模式**: 一次性运行，完成后退出
- **核心逻辑**: `run_evolution_loop()` — 执行 Original → Mutation → Crossover 进化循环
- **适用场景**: 手动触发、调试、单次实验

### 入口二：连续运行模式

```bash
/root/miniforge3/envs/mining/bin/python -m quantaalpha.continuous.main start \
  --config /home/quan/testdata/aspipe_v4/config/pipeline.yaml
```

- **配置文件**: `/home/quan/testdata/aspipe_v4/config/pipeline.yaml`
- **执行模式**: 无限循环守护进程，持续运行
- **核心逻辑**: `_run_continuous_loop()` — 每周期执行数据监控 → 重验 → 挖掘
- **适用场景**: 长期运行、自动化生产环境

### 详细对比

| 维度 | `pipeline.factor_mining` | `continuous.main start` |
|------|--------------------------|------------------------|
| 执行模式 | 一次性，运行后退出 | 无限循环守护进程 |
| 配置文件 | `configs/experiment.yaml` | `config/pipeline.yaml` |
| 数据更新 | 无 | 有（目标数据 evidence 为 app5；旧 App4 Bridge 仅迁移期保留） |
| 因子重验 | 无 | 有（温故：定期重验已入库因子） |
| 因子挖掘 | 有（AlphaAgentLoop） | 有（AlphaAgentLoop） |
| 进化编排 | Original→Mutation→Crossover | DAG: original→mutation→[llm_decide]→crossover→stop |
| 熔断机制 | 无 | 有（3 次连续零通过触发冷却） |
| 退化检测 | 无 | 有（IC 衰减、连续低效天数、斜率阈值） |
| 模型升级 | 无 | 有（LLM Provider 分层升级，3 层 6 个 Provider） |
| 预算控制 | 无 | 有（cycle_budget_seconds=3600, per-factor timeout=300s） |
| 运行摘要 | 无 | 有（RunStore, JSON 摘要持久化） |
| 告警 | 无 | 有（Webhook 告警分发） |
| 时间切分 | 2016-2019 / 2020 / 2021-2025 | 2020-2022 / 2023 / 2024 |
| 质量门控 | 基础 (MIN_VALID_RATIO 等) | 增强 (min_ic=0.018, min_rank_ic=0.03, max_correlation=0.7, min_sharpe=0.3) |
| LLM 模型池 | 单一模型 | 多模型池 + 共识机制 + 相似度引擎 |
| `--skip-update` | 不适用 | 跳过真实 app5 fetch/update，保留 app5 evidence 检查、factor_ops hook、挖掘和重验 |

### 连续运行的三阶段自治循环

每个周期（cycle）执行以下步骤：

```
1. 数据检查 (Data Inspection)
   → 检查 app5 manifest、active parquet、schema、freshness、coverage evidence
   → 根据 app5_data.groups 和接口 evidence 形成数据摘要

2. 数据更新 (Data Update)
   → 通过 app5 更新过期接口
   → --skip-update 时仅跳过真实 fetch/update，不跳过 evidence 检查

3. 重验 (Revalidation, "温故")
   → 对已有因子在新数据上重新验证
   → 检测退化（IC 衰减等）
   → 21 天阈值触发重验

4. 挖掘 (Mining, "知新")
   → 执行因子挖掘
   → 进化 DAG 编排
   → 质量门控过滤

5. 因子运营 (Factor Ops)
   → post-mining / daily workflow 处理候选因子和复验触发
   → 结构化结果写入 continuous run summary 的 factor_ops 字段
```

### `--skip-update` 标志

- **跳过**: 真实 app5 fetch/update
- **保留**: app5 manifest/schema/freshness evidence 检查、factor_ops hook、数据监控、因子重验、因子挖掘
- **用途**: 冒烟测试、性能测试、数据已是最新且操作者显式接受不刷新数据的诊断场景
- **边界**: app4 bridge 只属于旧 continuous 链路迁移期，不是 factor_ops 新入口的数据事实源
- **生产要求**: supervisor/systemd/长期调度入口默认不应携带 `--skip-update`。如果日志里出现 `skip_update=True`，先追踪启动命令或调度配置，不要把它误判为 `pipeline.yaml` 字段。
- **价格数据验收**: app4 bridge `No price data found` 只代表旧 bridge 路径为空；backtest 价格可由配置的 app5 clean/standard-frame 路径提供。排查 IC 不可用时必须分别记录 bridge rows 和 app5 clean rows。

### 连续运行模块架构

```
CLI (continuous/main.py)
  → ContinuousOrchestrator (continuous/main.py)
    → MiningOrchestrator (continuous/orchestrator.py)
      → DefaultDataMonitor
      → DefaultRevalidationScheduler
      → DefaultMiningScheduler
        → AlphaAgentLoop (pipeline/loop.py)
```

---

## 连续运行核心机制详解

### 熔断器 (Circuit Breaker)

- **触发条件**: 3 次连续零通过（zero-pass）周期
- **冷却策略**: 触发后睡眠时间乘以 3 倍
- **最大冷却次数**: 5 次，超过后升级为 critical 告警
- **恢复**: 有成功周期后自动复位

### 退化检测 (Degradation Detection)

| 参数 | 值 | 说明 |
|------|------|------|
| `lookback_days` | 30 | 回看窗口 |
| `ic_decay_threshold` | 0.005 | IC 衰减阈值 |
| `consecutive_low_days` | 7 | 连续低效天数阈值 |
| `slope_threshold` | -0.001 | 斜率阈值 |

### 模型升级 (Model Escalation)

当 LLM 连续调用失败时自动升级模型层级：

- **3 个层级**（Tier），每个层级 2 个 Provider
- **共 6 个 LLM Provider**
- 升级条件：连续失败达到阈值
- 恢复条件：成功调用后降级回更低层级

### 影响分类器 (ImpactClassifier)

将 App4 数据接口映射到因子依赖桶：

| 桶 | 说明 |
|----|------|
| price_volume | 价格量数据 |
| financial | 财务数据 |
| moneyflow | 资金流数据 |
| chip | 筹码数据 |

### 状态持久化

- **ContinuousStateManager**: 跨周期 TrajectoryPool 持久化，原子文件保存
- **RunStore**: 每周期 JSON 摘要持久化，带 schema 版本控制，存储在 `log/mining/continuous/runs/`

### 告警分发 (AlertDispatcher)

- Webhook 方式分发告警
- 告警类型：熔断触发、退化检测、数据异常
- 配置在 `pipeline.yaml` 中

---

## 配置参数速查 (pipeline.yaml)

| 参数分组 | 关键参数 | 值 |
|---------|---------|-----|
| LLM | 默认模型 | minimax-m2.7 (via LiteLLM proxy) |
| LLM | 代理地址 | 192.168.88.7:4000 |
| LLM | 嵌入模型 | codestral-embed |
| 运行时 | 数据检查间隔 | 300s |
| 运行时 | 重验间隔 | 24h (21 天阈值) |
| 运行时 | 挖掘间隔 | 12h |
| 运行时 | 周期预算 | 3600s (1h) |
| 运行时 | 单因子超时 | 300s (5min) |
| app5_data | groups | daily / daily_basic / moneyflow |
| app5_data | interface_dir | /home/quan/testdata/aspipe_v4/app5/config/interfaces |
| app5_data | 新鲜度阈值 | 24h |
| app5_data | Python 路径 | /root/miniforge3/envs/app5/bin/python |
| factor_ops | storage_root | /home/quan/testdata/aspipe_v4/log/factor_ops |
| factor_ops | dry_run | true |
| 验证 | min_ic | 0.02 |
| 验证 | min_rank_ic | 0.01 |
| 验证 | 最大重验次数/轮 | 10 |
| 验证 | 最大挖掘次数/轮 | 5 |
| 功能开关 | enable_data_monitor | true |
| 功能开关 | enable_revalidation | true |
| 功能开关 | enable_mining | true |
| 熔断 | 连续零通过触发 | 3 次 |
| 熔断 | 冷却倍数 | 3x |
| 熔断 | 最大冷却次数 | 5 |
| 退化 | 回看窗口 | 30 天 |
| 退化 | IC 衰减阈值 | 0.005 |
| 退化 | 连续低效天数 | 7 |
| 退化 | 斜率阈值 | -0.001 |
| 挖掘 | pipeline_mode | true |
| 挖掘 | min_ic | 0.018 |
| 挖掘 | min_rank_ic | 0.03 |
| 挖掘 | max_correlation | 0.7 |
| 挖掘 | min_sharpe | 0.3 |
| 挖掘 | 编排 DAG | original→mutation→llm_decide→crossover→stop |
