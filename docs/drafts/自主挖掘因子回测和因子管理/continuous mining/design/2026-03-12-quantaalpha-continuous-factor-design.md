# QuantaAlpha 持续因子研究系统设计文档

## 一、文档目标

本文档面向当前 `quantaalpha` 仓库，设计一套可落地的增强方案，使系统从“单次因子挖掘与回测工具”逐步升级为“持续因子研究系统”。

目标能力包括：

1. 多模型协作挖掘因子
2. 回测数据过滤与股票池治理
3. 多时间跨度、多周期的稳定性验证
4. 因子库从结果归档升级为研究知识库
5. 数据维度扩展后，LLM 能理解当前可用数据能力
6. 系统根据新数据、新维度、新回测结果持续维护因子状态
7. 支持 24 小时不间断运行

本文档强调：

- 满足原始业务目标
- 基于当前仓库实际结构演进
- 采用分阶段、小步闭环的实现方式

---

## 二、背景与问题定义

当前系统已经具备较完整的因子挖掘主链路：

- 方向生成
- hypothesis 生成
- 因子表达式构造
- 因子计算
- 回测
- feedback
- evolution
- 因子库写入
- 前后端任务启动与状态展示

但从“持续研究”的角度看，当前仍存在以下不足：

### 2.1 挖掘阶段过于依赖单模型或单类模型配置

当前系统虽然已有 `chat_model`、`reasoning_model`、`chat_model_map` 等配置，但还缺少：

- 不同任务类型使用不同模型组
- 同一问题由多个模型并行给出不同视角
- 输出失败后专用格式修复链路
- 同类模型在不同 provider 之间轮询分压

这导致：

- 成本控制能力不足
- 单模型风格偏置明显
- 平台限流或故障时弹性不足

### 2.2 回测验证只看单套时间区间，稳定性信息不足

当前 backtest 主要围绕单组 `train / valid / test` 时间段运行。

这会导致：

- 因子是否跨周期有效看不清
- 容易选出仅在最近一段时间偶然有效的因子
- 因子库中缺少“长期稳定性”画像

### 2.3 因子库更像结果存档，而不是研究知识库

当前因子库存储了：

- 因子表达式
- 部分回测结果
- 实验 metadata

但缺少：

- 因子依赖的数据字段与数据维度
- 跨周期稳定性信息
- 最近验证时间
- 当前状态与失效信息
- 演化来源与父子关系
- 对未来因子生成的指导价值

### 2.4 数据维度扩展后，LLM 无法天然理解“现在有哪些字段可以用”

例如后续接入：

- 基本面数据
- 分析师数据
- 资金流数据
- 行业维度数据

仅靠静态 prompt 很难让 LLM 正确理解：

- 当前哪些字段可用
- 字段频率是什么
- 是否有披露滞后
- 如何与日频行情对齐
- 这些字段适合构造什么类型的因子

### 2.5 缺少持续维护闭环

当以下事件发生时，系统应当自动响应：

- 新的一天数据到达
- 新数据维度接入
- 某因子长期未回测
- 某因子最近表现明显退化

当前系统还没有把这些事件和因子状态维护打通，导致无法形成 24h 持续研究闭环。

---

## 三、总体设计目标

目标不是在仓库内再造一个全新的量化平台，而是在现有 QuantaAlpha 主链之上增加四层能力：

1. `多模型研究层`
2. `多周期验证层`
3. `研究知识库层`
4. `持续维护调度层`

形成如下闭环：

```text
数据更新 / 新维度接入
        ↓
数据能力注册表更新
        ↓
多模型生成 hypothesis / factors
        ↓
表达式检查 / 去重 / 初筛
        ↓
多周期回测验证
        ↓
因子库更新状态、稳定性、依赖、演化信息
        ↓
筛选可维护、可变异、需复验的因子
        ↓
再次进入挖掘 / 复验 / 演化
```

最终系统具备以下属性：

- 知道当前有哪些数据能用
- 知道哪些因子长期稳定
- 知道哪些因子过期或退化
- 知道下一轮挖掘应该参考哪些已有成果
- 能持续生成、验证、维护和更新因子

---

## 四、总体架构

```text
┌────────────────────────────────────────────────────────────┐
│            Continuous Factor Research Orchestrator         │
│  (任务编排: Mining / Validation / Revalidation / Sync)     │
└───────────────┬───────────────────────────────┬────────────┘
                │                               │
                ▼                               ▼
┌───────────────────────────┐      ┌───────────────────────────┐
│    Multi-Model Research   │      │   Continuous Maintenance   │
│ hypothesis / factor gen   │      │ stale scan / revalidate    │
│ repair / provider routing │      │ state update / scheduling  │
└───────────────┬───────────┘      └───────────────┬───────────┘
                │                                  │
                ▼                                  ▼
┌────────────────────────────────────────────────────────────┐
│               Multi-Period Validation Engine              │
│  single-period backtest + cross-period stability scoring  │
└───────────────┬────────────────────────────────────────────┘
                │
                ▼
┌────────────────────────────────────────────────────────────┐
│                  Factor Knowledge Library                 │
│ expression / metadata / data requirements / history /     │
│ stability / evolution / usage guidance / current status   │
└───────────────┬────────────────────────────────────────────┘
                │
                ▼
┌────────────────────────────────────────────────────────────┐
│                  Data Capability Registry                 │
│ available dimensions / fields / freq / lag / join rules   │
└────────────────────────────────────────────────────────────┘
```

说明：

- `Multi-Model Research` 负责生成能力
- `Validation Engine` 负责验证能力
- `Factor Knowledge Library` 负责知识沉淀
- `Data Capability Registry` 负责“LLM 知道现在有哪些数据能用”
- `Orchestrator` 负责把这些任务连接起来，支持持续运行

---

## 五、模块设计

## 5.1 多模型研究层

### 5.1.1 目标

满足以下需求：

1. 难问题交给大模型，简单问题交给小模型
2. 同一问题由多个模型给出不同看法
3. JSON 或结构输出错误时交给 coding 模型修复
4. 同类模型在不同平台之间轮询，分摊调用压力

### 5.1.2 设计思路

不把所有逻辑塞进一个“大路由器”类，而是拆成四个清晰能力：

1. `TaskPolicy`
2. `ModelProfiles`
3. `ProviderPool`
4. `RepairChain`

### 5.1.3 TaskPolicy：按任务类型选择模型组

不同任务应使用不同模型策略：

| 任务类型 | 目标 | 推荐模型类型 |
|----------|------|--------------|
| hypothesis_generation | 生成研究方向与假设 | 大推理模型 |
| factor_construction | 构造表达式与因子描述 | 大推理模型 + 中模型 |
| evaluation_screening | 低成本筛查和格式校验 | 小模型 |
| json_repair | 修复结构化输出 | coding 模型 |
| feedback_summarization | 总结回测反馈 | 大模型或中模型 |
| mutation_generation | 基于已有因子变异 | 大模型 + 中模型 |

建议引入配置层：

```yaml
llm_routing:
  tasks:
    hypothesis_generation:
      primary_group: reasoning_large
      fallback_groups: [reasoning_medium]
      fanout: 2
    factor_construction:
      primary_group: reasoning_large
      fallback_groups: [reasoning_medium]
      fanout: 2
    evaluation_screening:
      primary_group: cheap_small
      fallback_groups: [reasoning_medium]
      fanout: 1
    json_repair:
      primary_group: coding_model
      fanout: 1
```

其中：

- `fanout=2` 表示同一任务可让两个模型并行输出两个视角
- `fallback_groups` 表示主模型失败时的替代模型组

### 5.1.4 ModelProfiles：定义模型能力

系统应维护模型能力描述，而不是仅维护模型名字。

每个模型 profile 建议包含：

- provider
- model_name
- cost_level
- reasoning_strength
- formatting_strength
- coding_strength
- max_context
- stable_json_output

示例：

```yaml
model_profiles:
  reasoning_large:
    - provider: openai
      model: gpt-4o
    - provider: dashscope
      model: qwen-max

  reasoning_medium:
    - provider: deepseek
      model: deepseek-v3

  cheap_small:
    - provider: aliyun
      model: qwen2.5-7b

  coding_model:
    - provider: mistral
      model: codestral-latest
```

### 5.1.5 ProviderPool：平台轮询与压力分担

目标：

- 同类模型来自不同 provider 时做轮询
- 避免单 provider 被打满
- 出现限流时自动切换

ProviderPool 应维护：

- provider 当前冷却时间
- 最近失败次数
- 最近成功率
- 每分钟调用计数

调度策略建议：

1. 先从优先级高的 provider 取
2. 若 provider 进入 cooldown，跳过
3. 若调用失败，标记失败并切换下一个 provider
4. 若成功，更新状态并继续使用

适用场景：

- 同一个大模型来自多个平台
- 同一类中模型在多个平台可替代
- 某平台临时不稳定时自动降级

### 5.1.6 多模型并行观点生成

对于 hypothesis 和 factor generation，可采用“多模型并行 + 后置筛查”的方式：

1. 同一 research direction 发给多个模型
2. 每个模型生成一组 hypothesis 或 factors
3. 合并候选集合
4. 用重复度检查、结构合法性和低成本筛选缩小集合
5. 最终进入 backtest

优点：

- 增加观点多样性
- 避免单模型风格锁死
- 提高新颖因子产出概率

注意：

- 不能所有并行结果都直接进入回测
- 必须先做去重和初筛，否则成本会快速膨胀

### 5.1.7 JSON / 结构修复链

处理顺序建议如下：

1. 主模型输出
2. 本地 `robust_json_parse()` 尝试修复
3. 若仍失败，进入 `RepairChain`
4. `RepairChain` 使用 coding 模型只修复结构，不改变语义

修复 prompt 约束必须明确：

- 不允许改业务含义
- 只允许修复 JSON 结构、转义、括号、逗号、字段引用
- 输出必须是合法 JSON

### 5.1.8 输出去重与质量初筛

在多模型产出进入高成本 backtest 之前，建议增加一层轻筛：

- 表达式是否可解析
- 结构是否缺关键字段
- 与已有因子表达式是否重复
- 与历史高相关因子是否极度相似
- 是否违反数据使用约束

这层可以用：

- 规则检查
- 现有 regulator
- 小模型辅助筛查

---

## 5.2 回测数据过滤与股票池治理

### 5.2.1 目标

满足当前需求：

- 排除北交所股票

同时把该能力抽象成可复用的股票池过滤层，而不是一次性写死。

### 5.2.2 设计思路

建议新增配置：

```yaml
data:
  stock_filter:
    enabled: true
    exclude_markets: ["bj"]
    include_markets: []
    exclude_prefixes: []
    exclude_tags: []
```

### 5.2.3 过滤层位置

过滤应在以下两个阶段生效：

1. 数据集构造前
2. 因子计算使用的 universe 确定时

原因：

- 训练、验证、回测应基于同一过滤后的 universe
- 如果只在最后交易层过滤，会导致训练样本和回测样本不一致

### 5.2.4 扩展方向

未来除北交所以外，还可支持：

- ST 股票过滤
- 新股过滤
- 停牌率过滤
- 流动性过滤
- 自定义名单黑白名单

因此该模块应抽象为通用 `StockUniverseFilter`。

---

## 5.3 多周期验证引擎

### 5.3.1 目标

满足需求：

- 调整 `train / valid / test` 数据区间
- 同一因子在两个或多个相隔数年的时间跨度上回测
- 挑出跨周期稳定有效的因子和策略

### 5.3.2 设计思路

将当前单区间 backtest 扩展为两层结构：

1. `SinglePeriodBacktest`
2. `MultiPeriodValidation`

其中单区间 backtest 继续复用现有 `BacktestRunner`。

### 5.3.3 配置设计

建议在保留当前 `dataset.segments` 的基础上，新增：

```yaml
dataset:
  segments:
    train: ["2016-01-01", "2020-12-31"]
    valid: ["2021-01-01", "2021-12-31"]
    test: ["2022-01-01", "2025-12-26"]

  multi_periods:
    - name: "recent_1y"
      train: ["2023-01-01", "2023-12-31"]
      valid: ["2024-01-01", "2024-06-30"]
      test: ["2024-07-01", "2025-03-13"]

    - name: "historical_cycle"
      train: ["2018-01-01", "2019-12-31"]
      valid: ["2020-01-01", "2020-06-30"]
      test: ["2020-07-01", "2021-12-31"]

  cross_period_validation:
    enabled: true
    min_pass_periods: 2
    ic_threshold: 0.02
    rank_ic_threshold: 0.02
    max_metric_dispersion: 0.5
```

### 5.3.4 执行逻辑

当 `multi_periods` 为空时：

- 按当前逻辑执行单次 backtest

当 `multi_periods` 存在时：

1. 遍历每个 period
2. 为每个 period 复用现有 dataset 构建和 backtest 流程
3. 收集 period metrics
4. 计算跨周期稳定性分数
5. 输出 `cross_period_pass/fail`

### 5.3.5 稳定性评估

建议给每个因子计算以下聚合信息：

- `period_results`
- `period_pass_count`
- `stability_score`
- `cross_period_pass`
- `failure_reason`

稳定性评分的核心参考维度：

- IC 平均值
- IC 波动
- Rank IC 平均值
- 收益是否只集中在单一周期
- 回撤是否明显失控

### 5.3.6 验证结果用途

多周期验证结果不只是展示，更要直接进入因子库：

- 决定因子状态
- 决定是否进入 active 候选池
- 决定是否值得 mutation / crossover
- 决定是否作为未来因子生成参考

---

## 5.4 因子知识库

### 5.4.1 目标

满足需求：

- 因子库不再只是简单 JSON 存档
- 已有因子要能指导未来因子生成
- 系统能维护因子的使用性和状态信息

### 5.4.2 设计定位

第一阶段仍保留 JSON 作为主存储事实源，但将其增强为“知识库结构”。

后续如果数据量增大，可在 JSON 之外增加索引层，但不影响主逻辑。

### 5.4.3 因子记录结构

建议每个因子至少包含以下信息：

```json
{
  "factor_id": "xxx",
  "factor_name": "xxx",
  "factor_expression": "xxx",
  "factor_description": "xxx",
  "factor_formulation": "xxx",
  "data_requirements": {
    "dimensions": ["price_volume"],
    "fields": ["$close", "$volume"],
    "derived_fields": ["$return"],
    "freq_constraints": ["daily"]
  },
  "evaluation": {
    "status": "active",
    "last_validated": "2026-03-13",
    "stability_score": 0.81,
    "cross_period_pass": true
  },
  "backtest_history": [],
  "evolution": {
    "parent_ids": [],
    "generation": 0,
    "source_model": "qwen-max",
    "source_task_type": "factor_construction"
  },
  "usage_guidance": {
    "suitable_regimes": [],
    "known_failure_modes": [],
    "recommended_mutation_directions": []
  }
}
```

### 5.4.4 核心能力

#### 1. 因子状态管理

建议状态枚举：

- `active`
- `degraded`
- `stale`
- `pending_validation`
- `pending_revalidation`
- `deprecated`

状态变更依据：

- 多周期验证结果
- 最近一次验证时间
- 最近一段时间的性能变化
- 数据维度变更或新数据到达情况

#### 2. 回测历史维护

每次回测结果都应至少保留：

- 时间戳
- 回测 period 名称
- 关键 metrics
- 配置摘要
- 使用的数据过滤规则

这样可以回答：

- 这个因子多久没测了
- 它在哪些周期表现稳定
- 它最近是否退化

#### 3. 数据依赖追踪

对每个因子记录：

- 使用了哪些字段
- 属于哪些数据维度
- 是否依赖低频数据
- 是否存在频率对齐限制

这是后续：

- 数据维度感知
- 因子筛选
- 自动复验

的基础。

#### 4. 演化与来源追踪

保留因子的家谱：

- 来自哪个 hypothesis
- 由哪个模型生成
- 是否从已有因子 mutation / crossover 而来
- 父因子有哪些

这有助于：

- 找到成功演化路径
- 回收高价值 parent factor
- 控制重复尝试

### 5.4.5 如何让因子库指导未来生成

这是整个系统飞轮的关键。

在新一轮挖掘前，应从因子库中取出“参考因子集合”，提供给 LLM：

1. 当前方向下表现最稳定的因子
2. 已经做过但失败的思路
3. 当前数据维度下已覆盖和未覆盖的字段组合
4. 可用于 mutation 的高价值 parent factors

建议提供以下检索方法：

- `get_reference_factors(direction, data_fields, market_regime)`
- `get_top_stable_factors(top_k)`
- `get_stale_factors_for_revalidation(days_since_last=21)`
- `get_mutation_candidates(style, top_k)`
- `get_underexplored_field_combinations()`

### 5.4.6 第一阶段是否需要向量库

不强制。

第一阶段可以先用以下方式支持“指导作用”：

- metadata 过滤
- 关键字段索引
- 简单 embedding 或相似表达式规则
- 文本描述检索

当规模足够大时，再引入向量索引层。

---

## 5.5 数据能力注册表

### 5.5.1 目标

满足需求：

- 新增数据维度后，LLM 能知道当前系统可用数据已经变化
- 能理解不同数据维度对应的可构造因子逻辑不同
- 例如基本面数据不能被当作普通日频价量字段随意使用

### 5.5.2 设计定位

`Data Capability Registry` 不是数据仓库，而是“当前可用数据能力说明层”。

它的职责是回答：

- 当前有哪些数据维度可用
- 每个维度有哪些字段
- 频率是什么
- 是否存在滞后
- 如何与主行情数据对齐
- 适合构造什么类型的因子
- 哪些用法不允许

### 5.5.3 数据结构建议

```json
{
  "dimensions": {
    "price_volume": {
      "fields": ["$open", "$close", "$high", "$low", "$volume"],
      "freq": "daily",
      "join_mode": "native",
      "lag_days": 0,
      "availability_status": "active",
      "description": "标准日频价量数据"
    },
    "fundamental": {
      "fields": ["$pe", "$pb", "$roe", "$revenue_growth"],
      "freq": "quarterly",
      "join_mode": "asof",
      "lag_days": 1,
      "availability_status": "active",
      "description": "财务与估值类基本面数据"
    }
  }
}
```

### 5.5.4 LLM 如何感知新增数据维度

每次进入 hypothesis / factor generation 时，系统动态注入：

1. 当前可用维度列表
2. 每个维度的字段说明
3. 频率和时点约束
4. 可构造因子示例
5. 典型错误用法

例如基本面数据，系统不仅要告诉 LLM 有 `PE/PB/ROE`，还要告诉它：

- 这是低频字段
- 有披露时滞
- 应使用 as-of 对齐
- 不应构造未来函数
- 更适合估值、盈利质量、财务改善类因子

### 5.5.5 与因子知识库的关系

两者形成联动：

- `Data Capability Registry` 告诉 LLM“你能用什么”
- `Factor Knowledge Library` 告诉 LLM“这些数据曾经生成过什么、哪些有效”

二者合起来，LLM 才能真正理解“新增数据维度会改变可挖掘因子空间”。

---

## 5.6 持续维护与 24h 运行

### 5.6.1 目标

满足最终需求：

- 根据现有数据和因子持续挖掘
- 根据新增数据和新增维度更新因子使用性信息
- 根据新的回测结果更新因子状态
- 长期未回测的因子自动复验
- 系统支持 24 小时不间断运行

### 5.6.2 任务类型设计

建议将持续运行拆成五类任务：

#### 1. Mining Job

作用：

- 根据研究方向、当前数据能力和参考因子生成新 hypothesis 和新因子

输入：

- 研究方向
- 当前可用数据维度
- 参考因子集合

输出：

- 新因子 candidates

#### 2. Validation Job

作用：

- 对新因子执行多周期回测
- 生成稳定性评分

输出：

- `cross_period_pass`
- `stability_score`
- `period_results`

#### 3. Revalidation Job

作用：

- 对长期未验证的因子重新回测

触发条件示例：

- `last_validated > 21 days`
- 新的一批行情数据到达

#### 4. Data Sync / Dimension Update Job

作用：

- 新的一天数据到达后，更新 registry
- 新数据维度接入后，更新字段说明和可用性信息
- 标记受影响因子为“待复验”或“可扩展”

#### 5. Library Maintenance Job

作用：

- 因子去重
- 更新状态
- 统计可变异候选
- 清理失效因子
- 生成下一轮参考因子集

### 5.6.3 因子状态流转

建议定义如下状态流：

```text
new_factor
  → pending_validation
  → active
  → degraded
  → stale
  → pending_revalidation
  → active / deprecated
```

状态含义：

- `pending_validation`: 新因子尚未完成多周期验证
- `active`: 当前表现稳定，可作为参考和候选
- `degraded`: 最近结果退化，但仍值得关注
- `stale`: 长时间未验证
- `pending_revalidation`: 已进入复验队列
- `deprecated`: 长期失效或明显无维护价值

### 5.6.4 24h 运行实现方式

建议不要一开始就做复杂分布式系统，而采用轻量任务编排：

- 常驻调度进程
- 周期性检查任务队列
- 支持 cron / systemd / supervisor 托管

第一阶段可采用：

- 日级别 `data refresh`
- 小时级别 `mining/validation`
- 周级别 `full revalidation`

### 5.6.5 基本监控项

至少记录：

- 最近一次成功 mining 时间
- 最近一次成功 validation 时间
- 最近一次 data sync 时间
- 各 provider 失败率
- stale 因子数量
- active / degraded / deprecated 分布

这些指标足以支撑第一阶段 24h 运行。

---

## 六、关键数据结构

## 6.1 因子知识库结构

```json
{
  "metadata": {
    "created_at": "2026-03-13T00:00:00",
    "last_updated": "2026-03-13T00:00:00",
    "total_factors": 0,
    "version": "2.0"
  },
  "factors": {
    "factor_id": {
      "factor_name": "",
      "factor_expression": "",
      "factor_description": "",
      "factor_formulation": "",
      "data_requirements": {
        "dimensions": [],
        "fields": [],
        "derived_fields": [],
        "freq_constraints": []
      },
      "evaluation": {
        "status": "pending_validation",
        "last_validated": null,
        "stability_score": null,
        "cross_period_pass": null
      },
      "backtest_history": [],
      "evolution": {
        "parent_ids": [],
        "generation": 0,
        "source_model": "",
        "source_task_type": ""
      },
      "usage_guidance": {
        "suitable_regimes": [],
        "known_failure_modes": [],
        "recommended_mutation_directions": []
      }
    }
  }
}
```

## 6.2 数据能力注册表结构

```json
{
  "dimensions": {
    "price_volume": {
      "fields": [],
      "freq": "daily",
      "join_mode": "native",
      "lag_days": 0,
      "availability_status": "active",
      "description": ""
    }
  }
}
```

## 6.3 多周期验证结果结构

```json
{
  "period_results": [
    {
      "name": "recent_1y",
      "metrics": {}
    },
    {
      "name": "historical_cycle",
      "metrics": {}
    }
  ],
  "summary": {
    "period_pass_count": 2,
    "stability_score": 0.81,
    "cross_period_pass": true
  }
}
```

---

## 七、与当前仓库的集成建议

### 7.1 推荐修改位置

| 模块 | 建议文件 |
|------|----------|
| 多模型任务策略与 provider 轮询 | `quantaalpha/llm/config.py`、`quantaalpha/llm/client.py` |
| 多模型并行生成与 repair chain 接入 | `quantaalpha/factors/proposal.py`、相关调用点 |
| 股票池过滤 | `configs/backtest.yaml`、`quantaalpha/backtest/runner.py` |
| 多周期验证 | `quantaalpha/backtest/runner.py`、`quantaalpha/backtest/run_backtest.py` |
| 因子知识库 schema 扩展 | `quantaalpha/factors/library.py`、`quantaalpha/pipeline/loop.py` |
| 数据能力注册表 | 新增轻量模块，接入 `quantaalpha/factors/qlib_utils.py` |
| 持续维护调度 | 新增轻量 orchestrator，或复用现有 backend/CLI 任务发起能力 |

### 7.2 不建议的实现方式

为避免项目一开始就膨胀，不建议：

1. 第一阶段就把因子库主存储迁移到大型数据库
2. 第一阶段就引入复杂分布式调度
3. 第一阶段就把所有新增数据维度完整打通
4. 第一阶段就让所有多模型产出都进入高成本回测

建议先建立最小闭环，再逐步增强。

---

## 八、分阶段实施计划

## Phase 1：验证闭环与知识沉淀

目标：

- 解决“哪些因子长期稳定”这个核心问题
- 让因子库开始积累有用知识

内容：

1. 股票池过滤
2. 多周期回测
3. 因子库 schema 增强
4. 因子状态管理
5. stale/revalidation 基础逻辑
6. 数据能力注册表最小版

交付结果：

- 系统能知道哪些因子跨周期稳定
- 系统能知道哪些因子多久没回测了
- LLM 能看到当前可用字段与数据维度说明

## Phase 2：多模型协作增强

目标：

- 提升生成多样性、弹性和成本效率

内容：

1. TaskPolicy
2. ModelProfiles
3. ProviderPool
4. RepairChain
5. 多模型并行 hypothesis / factor generation
6. 输出初筛与去重

交付结果：

- 大小模型分工明确
- 多 provider 分压可用
- JSON 结构故障自动修复
- 多模型对同一问题给出不同候选

## Phase 3：持续研究运行

目标：

- 形成 24 小时持续研究闭环

内容：

1. Mining Job
2. Validation Job
3. Revalidation Job
4. Data Sync Job
5. Library Maintenance Job
6. 基础监控指标

交付结果：

- 因子可持续新增
- 因子状态可持续更新
- 新数据和新维度能驱动自动复验与新一轮挖掘

---

## 九、测试与验收标准

### 9.1 多模型层

1. 同一任务可按配置选择不同模型组
2. 主模型失败时可自动 fallback
3. 同类 provider 可轮询
4. JSON 解析失败时可进入修复链
5. 多模型并行输出能进入统一初筛

### 9.2 回测层

1. 排除北交所过滤生效
2. 单区间 backtest 行为保持兼容
3. 多周期 backtest 能输出各 period 结果和聚合结果
4. 稳定性评分能写回因子库

### 9.3 因子知识库

1. 新字段写入成功
2. 旧因子记录仍可读取
3. 能按状态、字段依赖、最近验证时间筛选
4. 能取出 mutation / revalidation 候选

### 9.4 数据能力注册表

1. 新增数据维度后，prompt 内容发生变化
2. LLM 可看到字段频率和约束说明
3. 基本面等低频字段不会被当作普通日频字段无约束使用

### 9.5 持续维护

1. stale 因子能被扫描出来
2. 超过阈值天数的因子能进入复验队列
3. 新数据到达后可触发相关任务
4. 任务状态和最近成功时间可观测

---

## 十、风险与注意事项

### 10.1 多模型并发会显著增加成本

必须通过以下方式控制：

- fanout 限制
- 输出初筛
- 高成本回测前去重
- 按任务类型分配大小模型

### 10.2 新数据维度最容易引入未来函数问题

必须显式维护：

- lag 规则
- join 模式
- 数据频率
- 可用时点

### 10.3 因子库规模增长后，JSON 检索效率会下降

第一阶段可接受，但应预留后续索引层能力，例如：

- SQLite / DuckDB 辅助索引
- embedding 辅助检索

### 10.4 24h 运行先以“稳定可维护”为主

第一阶段不要追求复杂分布式能力，先把：

- 任务可调度
- 状态可观察
- 错误可恢复

做好即可。

---

## 十一、一句话结论

本方案的核心是把 QuantaAlpha 从“单次因子挖掘工具”演进为“多模型驱动、跨周期验证、数据维度感知、可持续维护的因子研究系统”。

系统通过多模型协作生成因子，通过多周期回测筛选长期稳定因子，通过因子知识库沉淀经验，通过数据能力注册表让 LLM 感知新增数据维度，并通过持续调度与复验机制实现 24 小时不间断挖掘和维护。
