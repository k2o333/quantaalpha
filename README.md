# QuantaAlpha

QuantaAlpha 是一个面向量化因子研究的自动化挖掘模块，覆盖数据能力发现、因子生成、表达式编码、回测验证、因子入库、持续重验与 RAG 增强检索。

这个 README 面向第一次进入本子模块的开发者，帮助快速定位核心闭环、主要入口和常用命令。更细的使用说明可参考 [quantaalpha_usage_guide.txt](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha_usage_guide.txt)。

## 模块闭环

QuantaAlpha 当前主要由 8 个闭环组成：

1. 数据下载与能力注入  
   Parquet 数据经过 `data_capability.py` 做 schema 注册、`available_from` 推断与 PIT 对齐，最终注入因子挖掘 prompt。

2. 因子挖掘核心循环  
   假设生成 -> 因子构造 -> 编码计算 -> 回测验证 -> 反馈学习。核心循环在 [loop.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/pipeline/loop.py)。

3. 因子库生命周期  
   因子入库、状态迁移、定期重验由 [library.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/library.py) 和 [status_rules.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/status_rules.py) 管理。

4. RAG 增强挖掘  
   活跃因子可同步到向量库，由 [vector_store.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/vector_store.py) 和 [fewshot.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/fewshot.py) 提供语义或 fallback 检索能力。

5. 连续调度自治  
   数据监控、触发挖掘、重验与熔断逻辑集中在 [continuous/main.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/continuous/main.py) 和 [orchestrator.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/continuous/orchestrator.py)。

6. 质量管控  
   一致性、复杂度、冗余检查由 [consistency_checker.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/regulator/consistency_checker.py) 等模块完成。

7. 容错与恢复  
   多 Provider 健康监控、空响应检测、有限重试与故障恢复位于 `llm/*` 与因子循环内部。

8. 进化探索  
   Original / Mutation / Crossover 的进化式探索由 `pipeline/evolution/*` 控制。

## 关键入口

如果你只想快速找到主入口，优先看这些文件：

- CLI 入口: [cli.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/cli.py)
- 启动入口: [launcher.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/launcher.py)
- 因子挖掘主循环: [loop.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/pipeline/loop.py)
- 多方向挖掘与进化编排: [factor_mining.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/pipeline/factor_mining.py)
- 因子库管理: [library.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/library.py)
- 标签推断: [tag_inference.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/tag_inference.py)
- 向量检索: [vector_store.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/vector_store.py)
- Few-shot / RAG 注入: [fewshot.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/factors/fewshot.py)
- 持续运行主入口: [main.py](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/continuous/main.py)
- 连续调度设计说明: [DESIGN.md](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/quantaalpha/continuous/DESIGN.md)

## 目录结构

核心目录大致如下：

- `quantaalpha/pipeline/`
  因子挖掘循环、回测衔接、进化编排。
- `quantaalpha/factors/`
  因子表达式、因子库、标签、RAG、质量门控、加载器。
- `quantaalpha/continuous/`
  连续运行、调度、熔断、影响分桶、告警。
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
quantaalpha revalidate data/factorlib/all_factors_library.json --dry_run
quantaalpha revalidate data/factorlib/all_factors_library.json --days 21
quantaalpha revalidate data/factorlib/all_factors_library.json --factor_ids f1,f2
quantaalpha revalidate data/factorlib/all_factors_library.json --status active --no_write
```

### 独立回测

```bash
python -m quantaalpha.backtest.run_backtest \
  -c configs/backtest.yaml \
  --factor-source custom \
  --factor-json data/factorlib/all_factors_library.json

python -m quantaalpha.backtest.run_backtest \
  -c configs/backtest.yaml \
  --factor-source combined \
  --factor-json data/factorlib/all_factors_library.json
```

### Web 界面

```bash
cd frontend-v2
bash start.sh
```

默认访问地址是 `http://localhost:3000`。

## 输出路径

常见输出位置：

- 因子库: `data/factorlib/all_factors_library*.json`
- 回测指标: `data/results/backtest_v2_results/*_backtest_metrics.json`
- 回测汇总: `data/results/backtest_v2_results/batch_summary.json`
- 日志: `log/`

## Python API 示例

```python
from quantaalpha.factors.library import FactorLibraryManager

manager = FactorLibraryManager("data/factorlib/all_factors_library.json")
summary = manager.get_summary()

print(f"总因子数: {summary['total_factors']}")
print(f"活跃因子数: {summary['active_count']}")

candidates = manager.select_revalidation_candidates(days=21)
print(f"待重验因子数: {len(candidates)}")
```

## 配置说明

常用配置文件：

- `configs/experiment.yaml`
  挖掘主实验配置，包括 planning、execution、evolution、quality_gate 和 provider_pool。
- `configs/backtest.yaml`
  回测配置，包括股票池过滤和多周期验证。
- `.env`
  环境变量与路径配置。

## 开发提示

- 因子标签补全与兜底逻辑现在依赖统一标签推断模块，不要在多个入口各写一套标签规则。
- 向量检索支持 ChromaDB，也支持 fallback-safe Jaccard 模式；在依赖不完整的环境里不要默认假设语义检索可用。
- 连续调度链路的真实接线点优先看 `continuous/main.py`，不要只盯着单个 adapter 或 helper。
- 当前工作树里可能存在临时文件或历史产物，提交前先做针对性清理和确认。
