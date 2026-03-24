# QuantaAlpha 持续因子研究变更验收方法

Status: draft
Owner: QuantaAlpha team
Created: 2026-03-14
Related-to: /home/quan/testdata/aspipe_v4/docs/drafts/自主挖掘因子回测和因子管理/2026-03-14-quantaalpha-continuous-factor-implementation-checklist.md

---

## 一、文档目的

本文档不再回答“改什么”，而是回答“每个改动怎么验收”。

验收原则：

1. 先验结构，再验行为，最后验结果。
2. 能做自动化的先做自动化，手工验收只补自动化无法覆盖的部分。
3. Phase 1 先看闭环是否成立，Phase 2 再看调度和策略消费是否成立。

默认使用环境：

```bash
cd /home/quan/testdata/aspipe_v4
conda activate mining
```

基础验证命令：

```bash
/root/miniforge3/envs/mining/bin/python -m unittest -q third_party/quantaalpha/tests/test_continuous_factor_features.py
/root/miniforge3/envs/mining/bin/python -m compileall third_party/quantaalpha/quantaalpha
```

---

## 二、统一股票池过滤入口

对应变更：

- `2026-03-14-unified-stock-universe-filter.md`

### 验收目标

- dataset 构建和回测使用同一股票池
- 开关关闭时兼容旧行为
- 结果文件中能看到最终生效的过滤规则和样本数量

### 验收方法

#### 方法 A：单元级验收

看纯函数：

- `quantaalpha/backtest/universe.py`

检查点：

- `exclude_markets=["bj"]` 能正确排除 `.BJ`
- `exclude_st=true` 只在有信息时生效
- `min_list_days=60` 能过滤上市不足 60 天标的

执行：

```bash
/root/miniforge3/envs/mining/bin/python -m unittest -q third_party/quantaalpha/tests/test_continuous_factor_features.py
```

#### 方法 B：配置级验收

编辑 [backtest.yaml](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/configs/backtest.yaml)：

```yaml
data:
  stock_filter:
    enabled: true
    exclude_markets: ["bj"]
    exclude_st: true
    min_list_days: 60
```

执行一次独立回测：

```bash
cd /home/quan/testdata/aspipe_v4/third_party/quantaalpha
python -m quantaalpha.backtest.run_backtest \
  -c configs/backtest.yaml \
  --factor-source alpha158_20
```

#### 方法 C：结果级验收

打开输出结果 JSON，确认存在：

- `universe.market`
- `universe.filter_enabled`
- `universe.rules`
- `universe.instrument_count_before`
- `universe.instrument_count_after`

### 通过标准

- 开关关闭时，输出仍可生成
- 开关打开时，输出 JSON 中有 `universe`
- `instrument_count_after <= instrument_count_before`

### 失败信号

- dataset 构建时报 instrument selector 类型错误
- 回测正常结束但结果 JSON 没有 `universe`
- 开关关闭仍然影响股票池数量

---

## 三、多周期验证

对应变更：

- `2026-03-14-multi-period-validation.md`

### 验收目标

- 一个配置可以跑多个 period
- 每个 period 有独立结果
- 最终有聚合 summary 和 `stability_score`

### 验收方法

#### 方法 A：纯函数验收

关注：

- `quantaalpha/backtest/validation.py`

检查点：

- period 配置校验
- 重名 period 拒绝
- summary 能计算均值、标准差、失败数和稳定性分数

执行：

```bash
/root/miniforge3/envs/mining/bin/python -m unittest -q third_party/quantaalpha/tests/test_continuous_factor_features.py
```

#### 方法 B：配置级验收

在 [backtest.yaml](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/configs/backtest.yaml) 增加：

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

执行：

```bash
cd /home/quan/testdata/aspipe_v4/third_party/quantaalpha
python -m quantaalpha.backtest.run_backtest \
  -c configs/backtest.yaml \
  --factor-source alpha158_20
```

#### 方法 C：结果级验收

检查输出 JSON：

- `metrics.multi_period_validation.period_results`
- `metrics.multi_period_validation.summary`
- `metrics.stability_score`

### 通过标准

- `period_results` 数量等于配置的 period 数量
- `summary.period_count` 正确
- `summary.stability_score` 存在或在失败时为 `null`

### 失败信号

- 仍只跑出单周期结构
- `period_results` 缺 name 或 segments
- 配置有两个 period，但结果只有一个且无错误说明

---

## 四、因子库状态与验证字段扩展

对应变更：

- `2026-03-14-factor-library-schema-extension.md`

### 验收目标

- 新旧因子库都能读
- 新字段自动补齐
- 多周期结果能回写到 `evaluation`

### 验收方法

#### 方法 A：结构兼容验收

关注：

- `quantaalpha/factors/library.py`

检查旧 JSON 读取后是否自动带出：

- `evaluation.status`
- `evaluation.last_validated`
- `evaluation.stability_score`
- `evaluation.period_results`
- `data_requirements.dimensions`
- `data_requirements.fields`

#### 方法 B：程序化验收

可直接在 Python REPL 里验证：

```python
from quantaalpha.factors.library import FactorLibraryManager
manager = FactorLibraryManager("data/factorlib/all_factors_library.json")
first = next(iter(manager.data["factors"].values()))
print(first["evaluation"])
print(first["data_requirements"])
```

#### 方法 C：回写验收

当回测结果带有 `multi_period_validation` 时，抽查因子库 JSON：

- `evaluation.period_results` 有内容
- `evaluation.stability_score` 被更新
- `evaluation.status` 从 `pending_validation` 进入后续状态

### 通过标准

- 旧库读取不报错
- 新写入因子默认有 `evaluation` 和 `data_requirements`
- 多周期结果能进库

### 失败信号

- 旧库缺字段直接崩溃
- 新因子写入仍是旧 schema
- `metadata.version` 和实际结构不一致

---

## 五、最小版数据能力注册表

对应变更：

- `2026-03-14-data-capability-registry.md`

### 验收目标

- 数据能力描述不再散落
- scenario/source-data 能看到统一渲染结果

### 验收方法

#### 方法 A：静态结构验收

看：

- `quantaalpha/factors/data_capability.py`

应至少包含：

- `price_volume`
- `financial`

且每项至少有：

- `fields`
- `freq`
- `lag_days`
- `join_mode`

#### 方法 B：渲染输出验收

在 Python 中执行：

```python
from quantaalpha.factors.data_capability import render_data_capabilities
print(render_data_capabilities())
```

看输出是否包含：

- 字段列表
- 频率
- 滞后
- 典型用途

#### 方法 C：场景注入验收

查看：

- `quantaalpha/factors/experiment.py`

确认 `source_data` 最终会追加注册表渲染结果，而不是替换掉旧的 fallback 内容。

### 通过标准

- 渲染输出稳定
- 旧 `get_data_folder_intro()` 仍保留
- scenario 中能同时看到数据文件说明和 capability 摘要

### 失败信号

- 注册表存在，但没有被场景消费
- 渲染后只是原始 Python dict 字符串
- 注册表字段与实际字段明显不对应

---

## 六、手动 Revalidate CLI

对应变更：

- `2026-03-14-revalidate-cli.md`

### 验收目标

- 能筛选候选因子
- 支持 `dry_run`
- 支持不写回

### 验收方法

#### 方法 A：帮助级验收

```bash
cd /home/quan/testdata/aspipe_v4/third_party/quantaalpha
python -c "from quantaalpha.cli import revalidate; print(revalidate)"
```

确认 `quantaalpha/cli.py` 已暴露 `revalidate`。

#### 方法 B：只预览验收

```bash
quantaalpha revalidate data/factorlib/all_factors_library.json --dry_run
```

期望结果：

- 返回 `total_candidates`
- 返回 `details`
- 不写文件

#### 方法 C：只算不写验收

```bash
quantaalpha revalidate data/factorlib/all_factors_library.json --status active --no_write
```

验收点：

- 命令成功执行
- 输出里有 `success`
- 因子库文件时间戳不变

### 通过标准

- `days/status/factor_ids` 至少一种筛选可生效
- `--dry_run` 不写回
- `--no_write` 不改原文件

### 失败信号

- `dry_run` 仍写文件
- `status=active` 返回所有因子
- `factor_ids` 包含不存在项时完全静默

---

## 七、因子状态流转规则

对应变更：

- `2026-03-14-factor-status-transition-rules.md`

### 验收目标

- 状态变化不散落在多个入口
- 同样输入得到同样状态输出

### 验收方法

#### 方法 A：纯函数验收

看：

- `quantaalpha/factors/status_rules.py`

至少验证以下链路：

1. `pending_validation -> active`
2. `active -> stale`
3. `active -> degraded`
4. `degraded/stale -> deprecated`

#### 方法 B：程序化验收

在 Python 中构造输入：

```python
from datetime import datetime
from quantaalpha.factors.status_rules import update_factor_status
entry = {
    "factor_id": "f1",
    "evaluation": {
        "status": "active",
        "last_validated": "2026-01-01T00:00:00",
        "stability_score": 0.6,
        "period_results": [],
        "validation_summary": "",
        "consecutive_failures": 0,
    },
}
print(update_factor_status(entry, None, now=datetime(2026, 3, 14)))
```

### 通过标准

- 时间驱动可以变 stale
- 低稳定性可以变 degraded
- 连续失败可以累计

### 失败信号

- 状态永远停留在 active
- 失败次数不累计
- 缺字段输入直接崩溃

---

## 八、多周期稳定性结果接入 Evolution

对应变更：

- `2026-03-14-stability-results-in-evolution.md`

### 验收目标

- evolution 能消费 `evaluation.status` 和 `stability_score`
- parent 选择不再只看单次回测表现

### 验收方法

#### 方法 A：纯函数验收

看：

- `quantaalpha/pipeline/evolution/trajectory.py`

重点验证：

- `select_parent_factors()`
- `route_factor_by_status()`

#### 方法 B：程序化验收

构造两个 trajectory：

- 一个 `active + stability_score=0.8`
- 一个 `degraded + stability_score=0.2`

期望：

- parent 选择优先 active
- degraded 被路由到 `repair_or_hold`

### 通过标准

- 高稳定 active 因子优先级更高
- 非 active 因子不进入主演化池或被分流

### 失败信号

- 稳定性字段存在但选择逻辑完全不看
- degraded 和 active 进入同一优先级池

---

## 九、任务级 LLM 路由

对应变更：

- `2026-03-14-task-level-llm-routing.md`

### 验收目标

- 调用方可以显式传 `task_type`
- 新路由优先级高于旧 `chat_model_map`

### 验收方法

#### 方法 A：配置解析验收

看：

- `quantaalpha/llm/config.py`
- `quantaalpha/llm/client.py`

检查是否存在：

- `routing_default`
- `routing_tasks`
- `get_model_for_task()`

#### 方法 B：程序化验收

在 Python 中模拟：

```python
from quantaalpha.llm.client import APIBackend
backend = object.__new__(APIBackend)
backend.task_model_map = {"hypothesis_generation": "model-a"}
backend.routing_default = "model-default"
backend.chat_model_map = {"SomeTag": "legacy-model"}
backend.chat_model = "fallback"
print(backend.get_model_for_task("hypothesis_generation", "SomeTag"))
print(backend.get_model_for_task(None, "SomeTag"))
```

期望：

- 第一个输出 `model-a`
- 第二个输出 `legacy-model`

#### 方法 C：调用点验收

抽查调用方是否显式传入：

- `hypothesis_generation`
- `factor_construction`
- `feedback_summarization`

### 通过标准

- `task_type` 存在时优先走任务路由
- 没有 `task_type` 时兼容旧路由

### 失败信号

- 新配置字段存在但没被 client 使用
- 所有调用仍然只靠调用栈 tag 推断

---

## 十、建议验收顺序

推荐按依赖顺序验收：

1. 统一股票池过滤入口
2. 多周期验证
3. 因子库状态与验证字段扩展
4. 最小版数据能力注册表
5. 手动 Revalidate CLI
6. 因子状态流转规则
7. 多周期稳定性结果接入 Evolution
8. 任务级 LLM 路由

原因：

- 前四项决定数据协议和结果载荷
- 后四项消费这些协议

---

## 十一、最小验收清单

如果只做一轮最小验收，建议至少完成下面 8 条：

1. 单元测试通过：`test_continuous_factor_features.py`
2. `compileall` 通过
3. 回测结果 JSON 出现 `universe`
4. 回测结果 JSON 出现 `multi_period_validation`
5. 因子库 JSON 出现 `evaluation`
6. 因子库 JSON 出现 `data_requirements`
7. `quantaalpha revalidate ... --dry_run` 可运行
8. `APIBackend.get_model_for_task()` 能区分任务路由和旧路由

---

## 十二、结论

这 8 个改动的验收，不应只看“代码是否存在”，而要分成三层：

- 结构是否补齐
- 开关是否可控
- 输出是否真的被下游消费

只有三层都通过，才算这个改动真正落地。

---

## 十三、用户使用场景验收

这一节不按单一功能拆，而按“正常用户会怎么用系统”来验收。每个场景都尽量让多个改动一起被使用。

### 场景 1：研究员做一次带股票池约束的独立回测

#### 场景说明

用户已经有一份因子库，想排除北交所、排除 ST、过滤新股，然后看回测结果是否可信。

#### 涉及功能

- 统一股票池过滤入口
- 独立回测入口
- 结果元数据写出

#### 执行步骤

1. 编辑 [backtest.yaml](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/configs/backtest.yaml)，打开 `data.stock_filter`
2. 运行：

```bash
cd /home/quan/testdata/aspipe_v4/third_party/quantaalpha
python -m quantaalpha.backtest.run_backtest \
  -c configs/backtest.yaml \
  --factor-source custom \
  --factor-json data/factorlib/all_factors_library.json
```

3. 打开输出 JSON，查看 `universe`

#### 验收点

- 命令可以正常结束
- `universe.rules` 和配置一致
- `instrument_count_after` 小于或等于 `instrument_count_before`
- 没有出现“训练可以跑、回测阶段股票池又变了”的现象

### 场景 2：研究员想知道一个因子是否只在最近行情有效

#### 场景说明

用户不满足于单窗口回测，想比较 recent 和 historical 两个窗口，看这个因子是不是阶段性有效。

#### 涉及功能

- 多周期验证
- 稳定性聚合
- 因子库 evaluation 回写

#### 执行步骤

1. 在 [backtest.yaml](/home/quan/testdata/aspipe_v4/third_party/quantaalpha/configs/backtest.yaml) 打开 `multi_period_validation`
2. 配置两个以上 period
3. 运行一次回测
4. 查看回测结果 JSON 和因子库 JSON

#### 验收点

- 回测结果里有多个 `period_results`
- `summary.stability_score` 存在
- 因子库里出现 `evaluation.period_results`
- 因子状态不再只是空字符串或缺失字段

### 场景 3：研究员新增一个财务因子方向，想确认模型知道自己手上有哪些数据

#### 场景说明

用户开始做质量/价值类因子，希望 hypothesis 阶段拿到的不是模糊 prompt，而是清楚的数据维度说明。

#### 涉及功能

- 数据能力注册表
- scenario/source-data 注入
- 任务级 hypothesis 路由

#### 执行步骤

1. 打开 `quantaalpha/factors/data_capability.py`
2. 确认 `financial` 维度存在
3. 运行一次因子挖掘
4. 在日志或调试输出里查看 hypothesis 相关 prompt 内容

#### 验收点

- prompt 中能看到 `price_volume` 和 `financial` 的结构化说明
- 数据能力描述不是散落在不同 prompt 片段里的重复文字
- hypothesis 生成没有因为注册表接入而丢失原有 source-data 信息

### 场景 4：研究员想复查一个 30 天没更新的因子库

#### 场景说明

用户手里已经有一份因子库，想先看有哪些因子超过 30 天没验证，再决定是否重跑。

#### 涉及功能

- 因子库 schema 扩展
- revalidate CLI
- 状态流转规则

#### 执行步骤

1. 运行：

```bash
cd /home/quan/testdata/aspipe_v4/third_party/quantaalpha
quantaalpha revalidate data/factorlib/all_factors_library.json --days 30 --dry_run
```

2. 再运行：

```bash
quantaalpha revalidate data/factorlib/all_factors_library.json --days 30 --no_write
```

#### 验收点

- `dry_run` 能列出候选因子
- `no_write` 能返回状态更新结果但不改文件
- 因子有 `last_validated`、`stability_score`、`status`
- 超过阈值的因子能被选中

### 场景 5：研究员做完一次多周期验证后，希望 evolution 不再盲目选短期赢家

#### 场景说明

用户希望后续演化阶段优先使用稳定、活跃的因子，而不是只看某一轮偶然表现好的因子。

#### 涉及功能

- 多周期稳定性结果
- factor `evaluation.status`
- evolution parent 选择和状态分流

#### 执行步骤

1. 准备两类 trajectory：
   - 一个 `active + 高 stability_score`
   - 一个 `degraded + 低 stability_score`
2. 调用 parent 选择逻辑或运行 evolution 一轮
3. 查看 parent 选择结果和 routing 结果

#### 验收点

- `active` 高稳定因子优先成为 parent
- `degraded` 不进入主演化池
- 分流结果至少能区分 `evolution_pool`、`repair_or_hold`、`revalidate_queue`

### 场景 6：工程同学想按任务给不同模型分工

#### 场景说明

用户希望 hypothesis 用一个更强推理模型，factor construction 用更便宜或更偏代码的模型，避免所有调用都混到一个默认模型上。

#### 涉及功能

- 任务级 LLM 路由
- 旧 `chat_model_map` 兼容
- 调用方显式传 `task_type`

#### 执行步骤

1. 配置任务路由
2. 分别触发 hypothesis 生成和 factor construction
3. 查看模型选择结果

示例配置思路：

```bash
export ROUTING_DEFAULT=deepseek-chat
export ROUTING_TASKS='{"hypothesis_generation":"model-a","factor_construction":"model-b"}'
```

#### 验收点

- hypothesis 和 factor construction 最终选择的模型不同
- 没有显式 `task_type` 的旧调用仍能工作
- 路由优先级符合预期，不会静默退错模型

### 场景 7：研究员从“挖掘 -> 回测 -> 入库 -> 复验”走一条完整闭环

#### 场景说明

这是最贴近真实使用的完整场景。用户先挖掘因子，再做带股票池限制和多周期验证的回测，写入因子库，最后复验筛选候选因子。

#### 涉及功能

- 数据能力注册表
- 任务级 LLM 路由
- 统一股票池过滤
- 多周期验证
- 因子库扩展
- revalidate CLI
- 状态流转

#### 执行步骤

1. 执行一次因子挖掘
2. 对生成的因子库运行多周期回测
3. 确认因子库已写入 `evaluation` 和 `data_requirements`
4. 运行一次 `revalidate --dry_run`

#### 验收点

- 挖掘阶段 prompt 含数据能力摘要
- 回测阶段结果含 `universe` 和 `multi_period_validation`
- 入库后 JSON 含 `evaluation` 和 `data_requirements`
- 复验阶段能筛出候选因子

### 场景 8：模块维护者做升级回归，确认旧资产还能继续用

#### 场景说明

用户不是研究员，而是维护者。他最关心的是：旧因子库、旧回测配置、旧模型路由能不能继续跑。

#### 涉及功能

- schema 兼容
- 路由兼容
- 配置默认值兼容

#### 执行步骤

1. 用旧因子库 JSON 初始化 `FactorLibraryManager`
2. 用 `multi_period_validation.enabled=false` 和 `stock_filter.enabled=false` 跑旧回测配置
3. 不配 `routing_tasks`，只保留旧 `chat_model_map`

#### 验收点

- 旧 JSON 仍能读取
- 旧回测模式仍可运行
- 没有新配置时，行为接近旧逻辑

---

## 十四、场景验收通过标准

如果要说“这批改动对正常用户已经可用”，至少应满足：

1. 用户能在不改代码的情况下，通过配置打开股票池过滤和多周期验证。
2. 用户能从结果 JSON 中直接看见新能力产物，而不是只能靠日志猜。
3. 用户能从因子库里看到 `evaluation` 和 `data_requirements`。
4. 用户能执行 `revalidate` 做人工复验预览。
5. evolution 和 LLM routing 至少在最小路径上已经消费这些新字段，而不是只有 schema 没有使用。
