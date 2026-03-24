# QuantaAlpha 持续因子研究系统设计评估与优化建议

## 一、文档目的

本文档基于以下两部分内容形成：

1. 既有设计稿《QuantaAlpha 持续因子研究系统设计文档》
2. `third_party/quantaalpha` 当前代码实现

目标不是重复原设计，而是回答三个更具体的问题：

1. 原设计中哪些方向值得直接采纳
2. 哪些方向需要按现有代码结构做收敛，而不是原样落地
3. 哪些建议当前阶段不应优先投入

本文强调：

- 以现有代码结构为边界做演进
- 优先建设对持续因子研究真正有复利价值的能力
- 避免“为未来抽象而抽象”

---

## 二、现状核对结论

结合当前仓库实现，可以确认以下事实。

### 2.1 LLM 层已有基础路由和健壮 JSON 解析，但还不是任务策略层

当前 LLM 配置中已经存在：

- `chat_model`
- `reasoning_model`
- `chat_model_map`

其中：

- `chat_model_map` 已可按调用方 tag 映射模型
- `reasoning_model` 已承担高推理成本任务
- `robust_json_parse()` 已能处理 markdown 包裹 JSON、常见转义、trailing comma、截断 JSON 等问题

但需要注意：

- 现有 `chat_model_map` 是“按调用类名/函数名”选模型，不是“按任务类型”显式配置
- 现有实现没有 provider 级 failover、轮询或负载分摊机制

因此，原设计提出的“任务策略化路由”是有价值的，但不需要一开始就落成四层大架构。

### 2.2 Backtest 当前仍是单周期验证

当前 `configs/backtest.yaml` 中只有一组：

- `train`
- `valid`
- `test`

回测流程默认围绕这组区间执行，尚未形成“跨市场阶段、跨时间窗口”的稳定性验证能力。

这一点是原设计中最值得优先落实的部分之一。

### 2.3 股票池当前没有统一过滤入口

当前回测相关代码中，多处直接调用 `D.instruments(...)`：

- label 计算
- 因子加载
- portfolio backtest

这意味着股票池定义并没有统一治理入口。

更重要的是，如果只在 backtest 末端过滤股票池，会造成：

- 训练宇宙与回测宇宙不一致
- 因子计算范围与组合交易范围不一致

因此，股票池治理不能只在 `_train_and_backtest()` 单点追加逻辑，而应统一作用于数据加载、标签构建和回测执行。

### 2.4 因子库已具备归档能力，但缺少“研究状态”层

当前因子库已经保存：

- `factor_id`
- `factor_name`
- `factor_expression`
- `factor_implementation_code`
- `metadata`
- `backtest_results`
- `feedback`

其中 `metadata` 已含：

- `evolution_phase`
- `trajectory_id`
- `parent_trajectory_ids`

这说明因子库已经不是纯结果文件，而是具备一定研究轨迹信息。

但当前仍缺少：

- 最近验证时间
- 稳定性评分
- 依赖数据字段
- 生命周期状态
- 历次验证摘要

所以原设计中“把因子库升级为研究知识库”的方向成立，而且应该优先做最小闭环。

### 2.5 数据能力描述当前仍偏文件说明，不是结构化能力注册

当前 `get_data_folder_intro()` 主要做的是：

- 读取 debug data folder
- 把文件内容或结构说明拼接成 prompt 文本

这能帮助模型理解“有哪些数据文件”，但不足以清晰表达：

- 哪些字段可用
- 字段频率
- 披露滞后
- 对齐方式
- 适合构建的因子类型

因此，原设计中的“Data Capability Registry”方向是合理的，但首版不需要做成独立平台模块。

### 2.6 当前代码并非“只有一个 provider”

现有 LLM 代码除了普通 `openai_base_url` 外，还已经支持：

- Azure chat / embedding 端点
- embedding 独立 base URL
- GCR endpoint
- llama 本地分支

因此，“provider 弹性”不是伪需求，只是当前阶段不必优先做统一 ProviderPool 抽象。

如果未来目标真的是持续运行或长时间批量挖掘，那么 provider 级 fallback 仍然有实际价值。

---

## 三、对原设计的采纳建议

## 3.1 建议直接采纳

以下方向建议直接纳入近期规划。

### 3.1.1 多周期验证

这是当前最有价值的能力补强。

原因：

- 当前系统容易筛出“某一阶段偶然有效”的因子
- 因子库里缺少长期稳定性画像
- 这是后续状态管理、复验和知识沉淀的基础

建议实现方式：

- 不单独新建 `MultiPeriodValidationEngine`
- 直接在 `BacktestRunner` 上增加配置驱动的 period 循环
- 输出 period 级结果和聚合稳定性指标

建议首版输出：

- `period_results`
- `ic_mean`
- `ic_std`
- `rank_ic_mean`
- `rank_ic_std`
- `win_rate_by_period`
- `stability_score`

### 3.1.2 股票池治理

这是当前回测链路的真实痛点，应尽快补齐。

建议目标：

- 支持排除北交所
- 支持排除 ST
- 后续可扩展停牌、上市天数、价格异常等过滤条件

建议实现方式：

- 不在 backtest 单点硬编码
- 在回测 runner 内增加统一的 universe resolver
- 训练标签、因子读取、回测股票池共用同一套过滤结果

这类统一入口比只加一个 `stock_filter` 配置更重要。

此外建议把实际生效的股票池过滤规则写入实验元数据，例如：

- `exclude_markets`
- `exclude_st`
- `min_list_days`
- 其他启用的过滤条件

这样做的价值在于：

- 保证实验可复现
- 便于后续排查因子表现变化是否来自 universe 变化
- 为批量复验和前端展示提供统一依据

### 3.1.3 因子库状态字段

建议立刻补充最小状态层。

最小字段建议：

- `evaluation.last_validated`
- `evaluation.stability_score`
- `evaluation.period_results`
- `evaluation.validation_summary`
- `data_requirements.fields`
- `data_requirements.dimensions`

状态字段建议不要压缩得过头。

不建议只保留：

- `active`
- `stale`
- `deprecated`

更合理的最小集合是：

- `pending_validation`
- `active`
- `degraded`
- `stale`
- `deprecated`

其中：

- `pending_validation` 用于新因子初次落库后等待完整复验
- `degraded` 用于最近复验表现变差但不必立即淘汰
- `stale` 用于长期未复验、需要进入复验队列的因子

这里建议把 `stale` 保留为持久化状态，而不是仅作为派生视图。

原因是：

- 后续手动 revalidate CLI 需要直接筛选待复验因子
- 前端和调度侧通常更依赖显式状态，而不是每次临时计算
- `stale` 与 `degraded` 的运维含义不同，前者代表“时间上过期”，后者代表“效果上退化”

### 3.1.4 数据能力注册表的最小版

建议做，但范围要收敛。

首版不必引入独立模块系统或数据库，只需提供结构化配置，例如：

- 数据维度名
- 字段列表
- 频率
- 滞后天数
- 对齐方式
- 可构造的典型因子类别

这个能力最好放在 scenario/source-data 侧统一注入，而不是只在 hypothesis generator 里临时塞 prompt。

原因是当前场景描述本来就是在 scenario 初始化阶段注入的，放在这层更一致，也更便于后续复用。

---

## 3.2 建议“收敛后采纳”

以下方向本身成立，但不建议按原设计完整实现。

### 3.2.1 多模型研究层

原设计提出：

- `TaskPolicy`
- `ModelProfiles`
- `ProviderPool`
- `RepairChain`

方向没有问题，但当前阶段应收敛为：

1. 先把 `chat_model_map` 升级成按任务类型路由
2. 保留 `reasoning_model` 负责高成本任务
3. 保留 `chat_model` 或 cheap model 负责轻量任务
4. 暂不做 fanout 并行生成
5. 暂不做统一 ProviderPool

推荐配置形式：

```yaml
llm_routing:
  tasks:
    hypothesis_generation: reasoning_model
    factor_construction: reasoning_model
    evaluation_screening: chat_model
    feedback_summarization: chat_model
```

这样做的好处是：

- 复用现有配置和调用方式
- 代码侵入小
- 足以支撑当前阶段的成本控制和任务分层

### 3.2.2 Provider 弹性

不建议当前就做统一 provider pool、轮询、熔断、健康检查全套能力。

但也不建议简单判断为“完全不需要”。

如果未来目标包括：

- 长时间连续运行
- 限流环境下批量挖掘
- 多 endpoint 成本切换

那么 provider fallback 迟早会成为实际需求。

因此建议：

- 当前阶段只保留接口设计余地
- 暂不投入完整实现

### 3.2.3 持续维护闭环

原设计中的 Mining / Validation / Revalidation / DataSync / Scheduling 闭环是长期方向。

但当前更务实的做法是先做手动复验闭环：

1. 因子库写入 `last_validated`
2. 提供手动 revalidate CLI
3. 复验结果回写因子库状态

只有当这三步跑顺后，再考虑自动调度。

---

## 3.3 建议暂不做

### 3.3.1 JSON 修复链

当前 `robust_json_parse()` 已覆盖大部分常见异常。

在没有明确证据表明结构化输出仍频繁失败之前，不建议引入“修复专用 coding model”链路。

### 3.3.2 多模型并行 hypothesis / factor generation

`fanout=2` 这类并行生成在理论上能增加视角多样性，但当前会明显增加：

- 调用成本
- 去重复杂度
- 后续评估负担

建议先不做，等单模型产出已经稳定、且确实遇到“风格塌缩”问题时再补。

### 3.3.3 向量库 / 向量索引层

当前因子库存储已经有：

- expression
- metadata
- trajectory
- feedback

在现阶段，基于 JSON + metadata 过滤仍然足够。

建议只有当以下条件出现时再考虑：

- 因子规模明显扩大
- 需要语义相似检索而不是结构化筛选
- metadata 过滤已无法满足召回质量

是否以 5000 为阈值可以作为经验值，但不建议写成硬规则。

---

## 四、对工程实现的具体建议

## 4.1 第一阶段建议落地项

建议第一阶段只做四件事：

1. 统一股票池过滤入口
2. 多周期验证配置与结果聚合
3. 因子库 `evaluation` / `data_requirements` 扩展
4. 最小版数据能力注册表

这是最小但完整的闭环，因为它会同时提升：

- 回测可信度
- 因子可维护性
- 因子库复用价值
- LLM 对可用数据的理解质量

其中多周期验证的结果聚合，建议不只输出截面预测指标，还补充一层交易与风险指标。

建议首版至少记录：

- `ic_mean`
- `ic_std`
- `rank_ic_mean`
- `rank_ic_std`
- `win_rate_by_period`
- `max_drawdown_by_period`
- `turnover_by_period`
- `stability_score`

原因是：

- 仅看 IC 稳定不等于组合层面稳定
- 多周期验证的目标应同时覆盖“预测有效性”与“可交易性”
- 后续 `degraded` 判定不能只靠单一 IC 阈值

## 4.2 第二阶段建议落地项

1. 任务级 LLM 路由
2. 手动 revalidate CLI
3. 因子状态更新规则

推荐 CLI 形态：

```bash
quantaalpha revalidate --days 30
```

这会比直接做 24 小时调度器更可控。

这一阶段还建议补一项：

4. 让多周期稳定性结果参与 evolution 策略

建议方向：

- 稳定性更高的因子优先作为 mutation / crossover 的 parent
- `degraded` 因子优先进入复验或轻量修复，而不是直接淘汰
- `stale` 因子进入定期复验队列

这样做可以把“验证结果”真正反馈回“因子演化”，而不是只停留在因子库展示层。

## 4.3 第三阶段再考虑

1. 自动调度器
2. provider 级 failover
3. 多模型并行生成
4. 向量检索层

---

## 五、建议的文档修订方向

如果后续要继续完善原设计文档，建议做以下修订：

### 5.1 把“目标架构”与“首版落地”分开写

当前设计稿中长期目标和短期实施方案交织在一起，容易导致实现时超前设计。

建议拆成：

- 长期蓝图
- 首版最小实现
- 阶段性升级条件

### 5.2 明确哪些能力要统一入口

尤其是：

- 股票池过滤
- 数据能力描述

这两类能力如果只在某个末端步骤补丁式接入，很容易造成链路前后不一致。

### 5.3 明确哪些状态是“持久化字段”，哪些是“派生视图”

例如：

- `degraded` 适合做持久化状态
- `stale` 更适合根据 `last_validated` 动态推导

这样能减少状态流转复杂度。

---

## 六、最终建议

综合现有代码与原设计，建议形成以下共识。

### 6.1 立即做

- 统一股票池治理
- 多周期验证
- 因子库状态与稳定性字段
- 最小版数据能力注册表

### 6.2 收敛后做

- 任务级 LLM 路由
- 手动 revalidate 命令
- provider fallback 预留扩展位
- 多周期稳定性结果接入 evolution 选父逻辑

### 6.3 暂不做

- JSON 修复专用模型链
- 多模型并行生成
- 向量库
- 24 小时调度器

一句话总结：

原设计方向整体正确，但实现策略应从“平台化抽象优先”调整为“统一入口、最小闭环、逐步演进优先”。
