# QuantaAlpha 持续因子研究能力实施清单

## 一、文档目的

本文档将设计评估结论转化为可执行的实施清单，明确：

- 每一阶段要做什么
- 主要修改哪些模块
- 如何测试
- 如何验收

本文档默认以 `third_party/quantaalpha` 当前代码结构为基础推进，优先采用“最小闭环、统一入口、逐步演进”的实施策略。

---

## 二、实施范围总览

建议按三个阶段推进。

### Phase 1

目标：先补齐研究链路中最影响结果可信度和知识沉淀质量的能力。

包含：

1. 统一股票池过滤入口
2. 多周期验证
3. 因子库状态与验证字段扩展
4. 最小版数据能力注册表

### Phase 2

目标：让系统具备手动复验和更清晰的任务级 LLM 路由能力。

包含：

1. 手动 revalidate CLI
2. 任务级 LLM 路由配置
3. 因子状态流转规则
4. 多周期稳定性结果接入 evolution

### Phase 3

目标：在前两阶段稳定后，再考虑自动化和更重的扩展能力。

包含：

1. 自动调度器
2. provider fallback
3. 多模型并行生成
4. 向量检索层

---

## 三、Phase 1 实施清单

## 3.1 统一股票池过滤入口

### 要做什么

新增统一股票池解析逻辑，确保以下环节使用同一套 universe：

- label 计算
- factor 加载
- portfolio backtest

支持的首版过滤条件建议包括：

- `exclude_markets`
- `exclude_st`
- `min_list_days`

同时要求将实际生效的过滤规则写入实验元数据和回测结果中。

### 主要修改点

- `quantaalpha/backtest/runner.py`
- `configs/backtest.yaml`

建议新增内部方法，而不是在多个位置复制过滤逻辑，例如：

- `_resolve_stock_universe()`
- `_apply_stock_filters()`

### 配置建议

```yaml
data:
  market: "csi300"
  stock_filter:
    exclude_markets: ["bj"]
    exclude_st: true
    min_list_days: 60
```

### 测试项

1. 配置关闭过滤时，股票池数量与现有逻辑一致。
2. 配置排除北交所后，股票池数量下降且结果可运行。
3. 配置排除 ST 后，训练、预测、回测均不报错。
4. label、factor、backtest 三处使用的股票集合一致。
5. 实验输出中能看到生效的 `stock_filter` 配置。

### 验收标准

- 能通过配置启用或关闭过滤
- 训练与回测使用同一 universe
- 回测结果可复现，元数据中有完整过滤规则
- 不出现“训练股票池”和“交易股票池”不一致的隐性偏差

---

## 3.2 多周期验证

### 要做什么

在现有单周期 backtest 能力上扩展配置驱动的多周期验证。

首版不要求单独抽象成独立 engine，可先在 runner 中支持：

- 遍历多个 period
- 分别执行训练/验证/测试
- 聚合 period 级指标
- 输出稳定性评分

### 主要修改点

- `quantaalpha/backtest/runner.py`
- `configs/backtest.yaml`
- 因子库写入逻辑所在模块

### 配置建议

```yaml
multi_period_validation:
  enabled: true
  periods:
    - name: "recent"
      train: ["2022-01-01", "2023-12-31"]
      valid: ["2024-01-01", "2024-06-30"]
      test: ["2024-07-01", "2025-03-13"]
    - name: "historical"
      train: ["2017-01-01", "2019-12-31"]
      valid: ["2020-01-01", "2020-12-31"]
      test: ["2021-01-01", "2021-12-31"]
```

### 首版输出建议

- `period_results`
- `ic_mean`
- `ic_std`
- `rank_ic_mean`
- `rank_ic_std`
- `win_rate_by_period`
- `max_drawdown_by_period`
- `turnover_by_period`
- `stability_score`

### 测试项

1. `enabled=false` 时，行为与现有单周期完全一致。
2. 配置两个 periods 时，确实运行两组回测。
3. 每个 period 都有独立结果输出。
4. 聚合结果中包含均值、标准差和 period 明细。
5. 单个 period 失败时，错误信息明确，且整体行为符合预期。

### 验收标准

- 可通过配置运行多组时间窗口验证
- 能得到 period 级明细和聚合稳定性指标
- 聚合结果能回写因子库
- 单周期模式不回归

---

## 3.3 因子库状态与验证字段扩展

### 要做什么

扩展因子库结构，让其从“结果归档”升级到“可持续维护的研究知识库”。

建议新增字段：

- `evaluation.status`
- `evaluation.last_validated`
- `evaluation.stability_score`
- `evaluation.period_results`
- `evaluation.validation_summary`
- `data_requirements.fields`
- `data_requirements.dimensions`

建议首版状态集合：

- `pending_validation`
- `active`
- `degraded`
- `stale`
- `deprecated`

### 主要修改点

- `quantaalpha/factors/library.py`
- 因子写库调用链
- 多周期验证结果回写逻辑

### 状态流转建议

1. 新因子入库时设为 `pending_validation`
2. 多周期验证通过后更新为 `active`
3. 复验分数明显下降时更新为 `degraded`
4. 长时间未验证时更新为 `stale`
5. 人工淘汰或连续失败时更新为 `deprecated`

### 测试项

1. 新因子写入后包含完整 `evaluation` 和 `data_requirements` 结构。
2. 历史因子库在升级后可兼容读取。
3. 多周期验证完成后能正确回写 `stability_score` 和 `period_results`。
4. 状态流转规则能按输入条件正确更新。
5. 未提供验证结果时不会破坏旧逻辑。

### 验收标准

- 新老因子库文件都可正常读取
- 因子库中可直接查看最近验证时间、状态、稳定性
- 状态字段能支持后续筛选、复验、前端展示

---

## 3.4 最小版数据能力注册表

### 要做什么

建立一份结构化的数据能力描述，并将其注入 scenario/source-data 侧，而不是只在 hypothesis generator 中临时拼 prompt。

首版描述建议覆盖：

- 数据维度名
- 可用字段
- 频率
- 滞后天数
- 对齐方式
- 适合构造的典型因子类别

### 主要修改点

- `quantaalpha/factors/qlib_utils.py`
- `quantaalpha/factors/experiment.py`
- 如有必要，新增 `quantaalpha/factors/data_capability.py`

### 数据结构建议

```python
DATA_CAPABILITIES = {
    "price_volume": {
        "fields": ["$open", "$close", "$high", "$low", "$volume", "$amount"],
        "freq": "daily",
        "lag_days": 0,
        "join_mode": "same_day",
        "factor_hints": ["momentum", "reversal", "volatility", "liquidity"],
    }
}
```

### 测试项

1. scenario 初始化时能注入结构化数据能力说明。
2. 未配置注册表时，旧的 `get_data_folder_intro()` 逻辑仍可工作。
3. prompt 中能看到字段、频率、滞后等信息。
4. 新增数据维度时，只需更新注册表即可被 prompt 感知。

### 验收标准

- 模型可见的数据能力描述从“文件说明”升级为“结构化能力说明”
- 数据能力描述不依赖手工在多个 prompt 中重复维护
- 对现有 hypothesis/factor 生成流程无破坏性影响

---

## 四、Phase 2 实施清单

## 4.1 手动 Revalidate CLI

### 要做什么

新增命令行入口，支持按时间条件筛选需要复验的因子，并执行复验后回写因子库。

建议命令：

```bash
quantaalpha revalidate --days 30
```

### 主要修改点

- CLI 入口
- 因子库筛选逻辑
- 回测调用逻辑
- 状态回写逻辑

### 测试项

1. 能筛选 `last_validated` 超过阈值的因子。
2. 能仅复验 `stale` 或 `degraded` 因子。
3. 复验后状态和验证信息被正确回写。

### 验收标准

- 可以手动批量复验指定因子集
- CLI 结果明确显示成功、失败、跳过数量
- 因子库被正确更新

---

## 4.2 任务级 LLM 路由

### 要做什么

将现有 `chat_model_map` 从“按调用类名/tag 路由”提升为“按任务类型路由”。

首版只需支持：

- `hypothesis_generation`
- `factor_construction`
- `evaluation_screening`
- `feedback_summarization`

不要求首版支持：

- fanout > 1
- provider pool
- repair chain

### 主要修改点

- `quantaalpha/llm/config.py`
- `quantaalpha/llm/client.py`
- 各任务调用处

### 测试项

1. 不配置任务路由时，行为与现有逻辑一致。
2. 配置任务路由后，不同任务使用不同模型。
3. routing 配置错误时有明确报错。

### 验收标准

- 能通过配置控制不同任务的模型选择
- 不破坏现有 `reasoning_model` / `chat_model` 逻辑

---

## 4.3 因子状态流转规则

### 要做什么

把因子状态更新从“写库时一次性赋值”升级为“规则驱动更新”。

建议至少支持：

- 时间维度流转：`active -> stale`
- 效果维度流转：`active -> degraded`
- 复验恢复：`degraded -> active`
- 淘汰流转：`stale/degraded -> deprecated`

### 测试项

1. 输入不同验证结果时，状态能正确流转。
2. 时间阈值触发 `stale` 更新。
3. 复验恢复后状态可回到 `active`。

### 验收标准

- 状态变化逻辑清晰可测试
- 不依赖人工修改 JSON 才能维护状态

---

## 4.4 多周期稳定性结果接入 Evolution

### 要做什么

让多周期验证结果参与因子演化过程，而不是只停留在因子库存档。

建议首版策略：

- 优先选择 `stability_score` 更高的因子作为 mutation parent
- `degraded` 因子优先进入复验或轻量修复
- `stale` 因子进入复验队列

### 主要修改点

- evolution 相关模块
- 因子筛选逻辑
- trajectory 选择逻辑

### 测试项

1. parent 选择会读取稳定性信息。
2. 高稳定性因子在候选排序中优先级更高。
3. `degraded`、`stale` 因子被正确分流。

### 验收标准

- 验证结果真正反馈到因子演化链路
- evolution 不再只依赖短期单次回测结果

---

## 五、Phase 3 预留项

以下能力暂不进入近期实施，但可保留接口或设计余地：

- 自动调度器
- provider fallback
- 多模型并行生成
- 向量检索层

当前要求：

- 不阻碍未来扩展
- 不为这些能力提前引入复杂抽象

---

## 六、测试与验收总表

## 6.1 必测回归项

每完成一个阶段，至少回归以下内容：

1. 单周期 backtest 保持可运行
2. 旧因子库 JSON 保持可读取
3. hypothesis 生成链路不因数据能力注册表而中断
4. 因子写库链路保持兼容
5. 未启用新配置时，旧行为尽量不变

## 6.2 建议测试方式

### 单元测试

适合覆盖：

- 股票池过滤函数
- 状态流转函数
- 稳定性聚合函数
- 数据能力注册表渲染函数

### 集成测试

适合覆盖：

- 单周期与多周期回测
- 因子库写入与回写
- revalidate CLI
- evolution 使用稳定性结果筛选 parent

### 手工验收

建议至少检查：

1. 一个带过滤配置的回测任务
2. 一个多周期验证任务
3. 一个新因子入库后的完整 JSON 结构
4. 一个 `stale` 因子的复验流程

---

## 七、交付标准

满足以下条件，可认为这一轮实施完成。

### Phase 1 完成标准

- 股票池过滤配置可用，且全链路统一生效
- 多周期验证可运行并输出聚合指标
- 因子库包含状态、验证信息、数据依赖字段
- 数据能力注册表已接入 scenario/source-data

### Phase 2 完成标准

- `revalidate` CLI 可用
- 任务级 LLM 路由可配置
- 状态流转规则稳定
- evolution 已消费稳定性结果

### 整体完成标准

- 系统从“单次挖掘+单次回测”升级为“可复验、可维护、可持续积累”的研究闭环
- 新能力不破坏现有主链路
- 核心结果可以通过配置和元数据复现

---

## 八、推荐实施顺序

建议严格按以下顺序执行：

1. 股票池过滤入口
2. 多周期验证
3. 因子库结构扩展
4. 数据能力注册表
5. revalidate CLI
6. 状态流转规则
7. evolution 接入稳定性结果
8. 任务级 LLM 路由

原因：

- 先修正 universe 和验证问题，才能得到可信的稳定性结果
- 先有验证结果和状态字段，后续复验和 evolution 才有输入
- LLM 路由优化虽然有价值，但不是当前研究闭环的最短板
