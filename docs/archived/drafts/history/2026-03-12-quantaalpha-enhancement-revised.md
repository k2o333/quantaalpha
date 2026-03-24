# QuantaAlpha 因子挖掘系统增强设计方案（修订版）

## 一、文档目的

本文档用于替代原始增强设计稿中的“大而全重构”思路，改为基于当前仓库实际实现的增量演进方案。

目标不是重建一套新的因子挖掘平台，而是在不打断现有主链路的前提下，补齐以下能力：

1. 模型调用增强
2. 多时间区间回测
3. 股票池过滤
4. 因子库元数据增强
5. 长期运行支持
6. 数据维度扩展预留

核心原则：

- 保持现有 `pipeline -> factor library JSON -> frontend/backend -> backtest` 主链兼容
- 优先小步迭代，不引入第二套控制面
- 优先增强现有模块，不轻易整体重构
- 本期解决“可用性和验证能力”问题，不做“平台化重建”

---

## 二、当前系统事实基线

本修订方案以当前仓库真实实现为基础，而不是抽象理想架构。

当前已具备的关键能力如下：

### 2.1 因子挖掘主流程已存在

当前主流程已经包含：

- hypothesis 生成
- factor 构造
- factor 计算
- factor backtest
- feedback 反馈
- evolution 扩展

核心入口和链路：

- `quantaalpha/pipeline/factor_mining.py`
- `quantaalpha/pipeline/loop.py`
- `quantaalpha/pipeline/evolution/controller.py`

这意味着“因子生成、进化、回测、反馈”已经形成闭环，不需要重建新的总调度中台。

### 2.2 LLM 调用层已具备基础模型分流和 JSON 容错

当前 LLM 层已有：

- `chat_model`
- `reasoning_model`
- `chat_model_map`
- 重试配置
- `robust_json_parse()` 多策略 JSON 修复

核心位置：

- `quantaalpha/llm/config.py`
- `quantaalpha/llm/client.py`

因此，本期应在现有客户端上增强模型路由和失败回退，而不是第一步新造一个独立 `model_router.py` 并全面接管调用链。

### 2.3 因子库已经是前后端共享契约

当前因子库不是内部临时存储，而是系统事实源之一：

- `quantaalpha/pipeline/loop.py` 在反馈阶段写入因子库
- `quantaalpha/factors/library.py` 维护 JSON 结构
- `frontend-v2/backend/app.py` 直接读取因子库 JSON 并对外提供 API
- 前端页面直接消费这些字段

因此，因子库结构可以增强，但不适合在本期直接改造成 Parquet + DuckDB 主存储，更不适合引入向量数据库作为基础依赖。

### 2.4 当前已经有任务启动与状态流

`frontend-v2/backend/app.py` 已经提供：

- 启动 mining
- 启动 backtest
- 任务状态维护
- WebSocket 推送
- 因子库浏览接口

因此，“新增 orchestrator + 新 REST API”会形成第二套控制面，造成入口和状态源重复。

### 2.5 Backtest 已经可独立运行，但当前是单区间模型

当前 backtest 核心文件：

- `configs/backtest.yaml`
- `quantaalpha/backtest/run_backtest.py`
- `quantaalpha/backtest/runner.py`

现状特点：

- 支持单组 `dataset.segments`
- 支持独立 backtest 命令行执行
- 支持 custom/combined factor source

因此，多区间验证应做成对现有单区间 runner 的扩展封装，而不是推倒当前配置结构。

---

## 三、需求重述与取舍

### 3.1 保留的需求

以下需求方向合理，应纳入修订方案：

#### A. 模型调用增强

合理，目标包括：

- 区分不同任务类型使用不同模型
- 在主模型失败时自动切换备用模型
- 在平台限流或错误时进行轮询和回退

但不应直接演化成一个全新的“大而全智能路由中台”。

#### B. 回测数据过滤

合理，但应视为“可选过滤能力”，而不是架构级核心改造。

在当前默认 `csi300` 配置下，北交所股票通常并不在股票池中，因此该能力更适合做成通用过滤开关，为更宽市场回测留扩展点。

#### C. 多时间区间回测

合理，且优先级高。

因子稳定性不能只看单个时间段，多区间验证是当前系统最值得补齐的能力之一。

#### D. 因子库增强

合理，但应限制在“JSON 元数据增强”范围内：

- 状态字段
- 多区间回测历史
- 数据依赖
- 复验记录
- 进化来源

不做主存储替换。

#### E. 数据维度扩展

方向合理，但当前缺少数据接入、对齐、缓存、缺失值处理等前提，不适合一次做全。

本期只做“接口和说明能力预留”。

#### F. 24h 不间断运行

合理，但不应通过新建第二套 orchestrator 完成。

本期目标应调整为：

- 支持定时触发
- 支持失败恢复
- 支持状态观测

具体调度优先复用现有 backend 或外部调度工具。

### 3.2 不保留的方案表达

以下方案在当前仓库下属于过度设计，本期不采用：

1. 因子库整体迁移到 Parquet + DuckDB 作为主事实源
2. 引入 FAISS / Pinecone 等向量数据库作为基础能力
3. 新建独立 `quantaalpha/scheduler/orchestrator.py` 并提供第二套 REST API
4. 在本期承诺 Tushare + 基本面 + 分析师 + 资金流数据的完整接入闭环
5. 将 LLM 增强一次性扩展为复杂智能中台，而不是基于现有客户端做增强

---

## 四、修订后的总体方案

## 4.1 方案总原则

本期采用“增量增强、接口兼容、逐步上线”的方式推进，分为四条主线：

1. LLM 调用增强
2. Backtest 增强
3. Factor Library 增强
4. 长期运行支持

数据维度扩展作为预留项同步设计，但不作为本期主交付。

---

## 五、详细设计

### 5.1 LLM 调用增强

### 目标

在不破坏当前调用链的前提下，增强模型选择、失败回退和平台轮询能力。

### 修改范围

- `quantaalpha/llm/config.py`
- `quantaalpha/llm/client.py`

### 设计原则

- 不新建独立路由系统作为第一阶段前置
- 不改动业务层调用接口的基本形态
- 尽量复用现有 `reasoning_model`、`chat_model_map`、重试和 JSON 容错逻辑

### 增强内容

#### 1. 明确任务级模型覆盖

在现有 `chat_model_map` 基础上，补充更清晰的按调用标签配置能力：

- hypothesis 生成
- factor proposal / construct
- feedback
- coding / parser
- evaluator

实现方式以现有 `tag` 识别逻辑为基础，不新造并行配置体系。

#### 2. 增加 fallback 机制

当模型调用出现以下问题时，自动尝试备用模型：

- provider 限流
- 网络错误
- 明确的模型不可用错误
- 输出格式持续失败

建议新增的配置概念：

- `primary_model`
- `fallback_models`
- `provider_priority`

但这些配置应映射回现有 `LLMSettings`，而不是在业务层再抽一套平行配置对象。

#### 3. 增加平台轮询

当存在多个兼容 provider 时，可按配置进行简单轮询：

- 每个 provider 单独维护冷却窗口
- 失败后切换下一 provider
- 成功后更新计数和时间戳

该能力应实现在 `client.py` 内部，不要求外部感知。

#### 4. JSON 修复策略

当前已有 `robust_json_parse()`，本期处理方式为：

- 先保留现有本地修复逻辑
- 仅在必要时增加“一次额外修复调用”

不建议把“JSON 修复”单独升格为大型系统模块。

### 本期不做

- 不实现复杂任务复杂度评分引擎
- 不做多模型协作生成再合并去重的全流程自动编排
- 不重写全部业务调用方

---

### 5.2 回测增强

### 目标

在保持现有单区间 backtest 可运行的前提下，增加多区间验证和股票池过滤能力。

### 修改范围

- `configs/backtest.yaml`
- `quantaalpha/backtest/runner.py`
- `quantaalpha/backtest/run_backtest.py`

### 设计原则

- 保持现有单区间配置完全兼容
- 新能力全部以“可选配置”形式接入
- 优先在 runner 外围增加调度和聚合，不打散当前单次 backtest 主流程

### 配置建议

在保留当前结构的基础上，新增可选配置：

```yaml
data:
  stock_filter:
    enabled: false
    exclude_markets: []
    include_markets: []

dataset:
  multi_periods: []
  cross_period_validation:
    enabled: false
    min_periods: 1
    ic_threshold: 0.0
    stability_weight: 0.0
```

#### 1. 股票过滤

过滤逻辑定位：

- 数据集创建前
- 因子计算/回测使用的股票池确定时

实现要求：

- 默认关闭
- 仅在显式配置时启用
- 支持按市场代码或代码前缀过滤

说明：

“排除北交所”只是默认场景之一，设计上应抽象为通用股票过滤规则。

#### 2. 多区间回测

推荐方式不是替换当前 `segments`，而是新增 `multi_periods` 列表。

执行逻辑：

1. 若未配置 `multi_periods`，走原有单区间逻辑
2. 若配置 `multi_periods`，逐个 period 复用现有单区间 runner 执行
3. 收集每个 period 的 metrics
4. 生成聚合结果和跨区间稳定性判断

#### 3. 聚合结果

每个 factor 或每次 backtest 至少输出：

- 各 period 独立 metrics
- 聚合 summary
- cross-period pass/fail

聚合层建议先聚焦以下指标：

- IC
- ICIR
- Rank IC
- Rank ICIR
- annualized return
- max drawdown

### 本期不做

- 不重写 `DatasetH` 构造逻辑
- 不在第一阶段引入复杂的稳定性打分体系
- 不将所有 period 结果直接嵌进核心训练逻辑中

---

### 5.3 因子库增强

### 目标

在保持 JSON 作为主存储和前后端契约的前提下，增强因子元数据、回测历史和筛选能力。

### 修改范围

- `quantaalpha/factors/library.py`
- `quantaalpha/pipeline/loop.py`
- `frontend-v2/backend/app.py`（只做兼容扩展）

### 设计原则

- 保持当前 JSON 结构为主事实源
- 旧 JSON 文件可以继续读取
- 前后端现有字段保持不变，新字段只做追加

### 推荐 schema 增强

在 `factors[*]` 下新增以下字段：

```json
{
  "status": "active",
  "last_validated": "2026-03-13",
  "validation_score": 0.82,
  "data_requirements": {
    "fields": ["$close", "$volume"],
    "derived_fields": [],
    "freq": "daily"
  },
  "backtest_history": [],
  "evolution": {
    "parent_ids": [],
    "generation": 0,
    "mutation_type": null
  }
}
```

### 增强能力

#### 1. 因子状态管理

建议状态枚举：

- `active`
- `degraded`
- `deprecated`
- `pending_review`

状态变化先通过回测结果和复验逻辑更新，不要求引入复杂工作流。

#### 2. 回测历史保留

每次 backtest 或 multi-period validation 后，可以追加简化历史记录：

- 运行时间
- period 名称
- 关键 metrics
- 配置摘要

#### 3. 数据依赖记录

记录因子依赖的原始字段和派生字段，作为后续筛选和数据扩展的基础。

#### 4. 简单筛选能力

筛选能力优先做成应用层逻辑：

- 按状态筛选
- 按指标阈值筛选
- 按字段依赖筛选
- 按最近验证时间筛选

不在本期引入向量检索。

### 本期不做

- 不迁移主存储到 DuckDB
- 不引入语义检索基础设施
- 不将因子库改造成新的数据库服务

---

### 5.4 数据维度扩展预留

### 目标

为未来扩展更多可用数据字段建立最小可接入点，但不在本期承诺全量数据平台化。

### 修改范围

- `quantaalpha/factors/qlib_utils.py`
- 可选新增一个轻量配置或 registry 模块

### 设计原则

- 先解决“如何把可用字段说明传给 LLM”
- 不在本期解决“全量异构数据接入与统一对齐”

### 本期建议

#### 1. 轻量字段注册

可以新增一个非常轻量的 registry，用来描述：

- 字段名
- 频率
- 数据说明
- 当前是否可用

其目的仅是帮助 prompt 生成，而不是构成完整数据平台。

#### 2. prompt 注入

在 `get_data_folder_intro()` 或相邻逻辑中，把：

- 已有本地数据说明
- 注册字段说明

拼接进 prompt 上下文。

### 注意事项

未来如需真正接入：

- fundamental
- analyst
- capital_flow

必须单独明确：

- 数据源
- 更新频率
- 对齐规则
- 缺失值策略
- 缓存方式
- 与 qlib 数据索引的 join 方法

这些不应在本期设计中被默认视为“已解决”。

---

### 5.5 长期运行支持

### 目标

支持周期性运行、失败恢复和持续观察，但不引入第二套系统控制面。

### 修改范围

- 优先复用 `frontend-v2/backend/app.py`
- 可增加最小调度入口或脚本

### 推荐方案

#### 1. 复用现有 backend

已有 backend 已经能：

- 启动任务
- 维护状态
- 推送日志和结果

因此，定时运行能力应建立在现有 backend 或直接 CLI 之上。

#### 2. 外部调度优先

推荐部署方式：

- `cron`
- `systemd`
- `supervisor`

由外部调度器触发现有命令或 backend 接口。

#### 3. 本期内部可补充的最小能力

- 任务失败后状态标记
- 最近一次运行结果记录
- 对指定因子库触发定期复验

### 本期不做

- 不新建独立 orchestrator
- 不新增第二套 REST API
- 不构建完整监控告警平台

---

## 六、修改文件建议

本期建议控制在以下范围内增量修改：

| 文件 | 操作 | 说明 |
|------|------|------|
| `quantaalpha/llm/config.py` | 修改 | 增加 fallback / provider / 轮询配置 |
| `quantaalpha/llm/client.py` | 修改 | 实现模型回退和简单轮询 |
| `configs/backtest.yaml` | 修改 | 新增可选 multi-period / stock filter 配置 |
| `quantaalpha/backtest/runner.py` | 修改 | 增加 multi-period 执行与聚合 |
| `quantaalpha/backtest/run_backtest.py` | 轻微修改 | 支持新配置参数和输出说明 |
| `quantaalpha/factors/library.py` | 修改 | 增强 JSON metadata schema |
| `quantaalpha/pipeline/loop.py` | 修改 | 写入新增元数据和回测历史 |
| `frontend-v2/backend/app.py` | 修改 | 兼容返回新增字段，不破坏旧字段 |
| `quantaalpha/factors/qlib_utils.py` | 修改 | 注入扩展字段描述 |

注意：

- 不建议在本期新增超过 2 个新的一级核心模块
- 能在原模块内扩展的能力，不单独拆成大型新模块

---

## 七、实施优先级

### Phase 1：高价值、低侵入改造

1. 多时间区间回测
2. 股票池过滤
3. 因子库 metadata 增强

目标：

- 先把“因子是否稳定”看清楚
- 让因子库能记录更完整的验证信息

### Phase 2：模型调用增强

4. LLM fallback
5. provider 轮询
6. 按任务标签模型覆盖

目标：

- 缓解限流和单模型失败问题
- 不改变现有业务层调用方式

### Phase 3：长期运行与数据扩展预留

7. 定期复验入口
8. 外部调度集成说明
9. 轻量字段注册与 prompt 注入

目标：

- 支持连续运行
- 为未来数据扩展留接口

---

## 八、测试与验收标准

### 8.1 Backtest 兼容性

1. 未配置 `multi_periods` 时，现有 backtest 命令行为不变
2. 未配置 `stock_filter` 时，股票池行为不变
3. 配置 `multi_periods` 后，能输出每个区间独立结果和聚合结果

### 8.2 因子库兼容性

1. 旧 JSON 因子库仍能被读取
2. 新 JSON 因子库仍能被后端 API 和前端页面消费
3. 新增字段不存在时，系统能正常降级处理

### 8.3 LLM 兼容性

1. 未新增 fallback 配置时，模型调用行为与当前一致
2. 主模型失败时，可按配置切换到备用模型
3. provider 轮询不影响成功路径的基本稳定性

### 8.4 长期运行能力

1. 通过现有 backend 或 CLI 能被外部定时触发
2. 失败任务能留下可见状态
3. 定期回测或复验结果能追加进因子库历史

---

## 九、明确不做项

为避免项目失控，本期明确不做以下事项：

1. 不重构因子库主存储为 Parquet + DuckDB
2. 不引入 FAISS / Pinecone 向量检索
3. 不新建独立 orchestrator 和第二套 REST API
4. 不承诺 Tushare / 基本面 / 分析师 / 资金流数据的完整接入闭环
5. 不实现复杂任务复杂度路由引擎
6. 不重写当前前端因子库消费协议

---

## 十、一句话结论

本修订方案保留原始需求中真正有价值的增强方向，但将实现路径收缩为“兼容现有架构的小步迭代”。

重点是增强当前 QuantaAlpha，而不是在同一仓库内再造一套新的因子挖掘平台。
