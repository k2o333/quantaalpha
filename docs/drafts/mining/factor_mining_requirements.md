# 因子挖掘系统需求分析与架构方案

> 文档版本: v1.0
> 创建日期: 2026-03-23
> 基于 QuantaAlpha 项目 (`/home/quan/testdata/aspipe_v4/third_party/quantaalpha`)

---

## 一、项目背景与目标

### 1.1 项目背景

QuantaAlpha 是一个基于大语言模型（LLM）驱动的量化因子自动挖掘系统，核心能力包括：
- 自动化因子发现：利用 LLM 生成市场假设，并将假设转化为可计算的因子表达式
- 进化式优化：通过变异（Mutation）和交叉（Crossover）操作，迭代优化因子质量
- 端到端回测验证：基于 Qlib 框架进行因子回测，评估因子的预测能力和投资价值

### 1.2 核心目标

构建一个 **24小时不间断运行的因子挖掘与维护系统**，实现：
1. 持续挖掘新因子
2. 定期维护已有因子（重新验证有效性）
3. 动态感知数据维度变化
4. 多模型协同工作，提升效率和质量

---

## 二、需求清单

### 需求 A：多模型混合调用（模型路由分发）

#### A.1 需求描述

| 子需求 | 说明 |
|--------|------|
| 大小模型协同 | 简单任务交给小模型（低成本），复杂任务交给大模型（高质量） |
| 多视角融合 | 不同模型对同一问题并发生成因子，由裁判模型汇总 |
| JSON 纠错模型 | 当 JSON 格式解析失败时，调用 Coding 模型自动修复 |
| 平台轮询 | 多 API Key / 多云服务商轮询，分担调用压力，避免限流 |

#### A.2 现有系统基础

| 组件 | 位置 | 说明 |
|------|------|------|
| `KNOWN_TASK_TYPES` | `quantaalpha/llm/client.py` | 已定义任务类型（hypothesis_generation, factor_construction 等） |
| `task_model_map` | `quantaalpha/llm/config.py` | 任务到模型的映射配置（已预留 `routing_tasks` 字段） |
| `robust_json_parse` | `quantaalpha/llm/client.py` | JSON 解析函数（仅有正则策略，无模型修复） |
| 多后端支持 | `quantaalpha/llm/client.py` | 已支持 OpenAI、Azure、本地 Llama、GCR Endpoint |

#### A.3 改进方案

##### A.3.1 大小模型协同

```yaml
# configs/experiment.yaml 新增配置
llm:
  task_routing:
    hypothesis_generation:
      model: "gpt-4-turbo"      # 复杂推理用大模型
      fallback: "gpt-3.5-turbo"
    code_generation:
      model: "code-llama"        # 代码生成用 Coding 模型
    brainstorming:
      model: "gpt-3.5-turbo"     # 简单头脑风暴用小模型
    json_fix:
      model: "code-llama"        # JSON 修复专用
```

##### A.3.2 多视角融合（Ensemble）

```
架构设计:

  同一 Prompt
       │
       ├──────▶ GPT-4 ──────┐
       │                     │
       ├──────▶ Claude ─────┼───▶ 裁判模型 ───▶ 最终因子
       │                     │     │
       └──────▶ Qwen ───────┘     │
                                  ▼
                           汇总策略:
                           - 取交集（保守）
                           - 取并集后去重
                           - 投票机制
                           - 融合评分
```

##### A.3.3 JSON 纠错模型

```python
# quantaalpha/llm/json_fixer.py (新增)

def fallback_json_fixer(text: str, model: str = "code-llama") -> dict:
    """
    当 robust_json_parse 的正则策略全部失效时，
    调用 Coding 模型进行 JSON 修复。
    """
    prompt = f"""
    以下文本应该是一个 JSON 对象，但格式有问题。
    请修复并返回有效的 JSON：
    
    {text}
    """
    response = llm_client.chat(prompt, model=model)
    return json.loads(response)
```

##### A.3.4 平台轮询（Load Balancing）

```yaml
# configs/experiment.yaml 新增配置
llm:
  api_pool:
    - provider: "openai"
      api_keys: ["sk-xxx1", "sk-xxx2"]
      base_url: "https://api.openai.com/v1"
    - provider: "azure"
      api_keys: ["azure-key-1"]
      base_url: "https://xxx.openai.azure.com"
    - provider: "deepseek"
      api_keys: ["sk-deepseek-1"]
      base_url: "https://api.deepseek.com/v1"
  
  load_balance:
    strategy: "round_robin"      # round_robin | random | least_latency
    retry_on_429: true
    max_retries: 3
```

---

### 需求 B：回测数据过滤（排除北交所）

#### B.1 需求描述

回测时**排除北交所股票**，仅保留主板、创业板、科创板股票。

#### B.2 现有系统基础

| 配置项 | 位置 | 当前值 |
|--------|------|--------|
| `stock_filter.enabled` | `configs/backtest.yaml:47` | `false` |
| `stock_filter.exclude_markets` | `configs/backtest.yaml:48` | `[]` |

#### B.3 改进方案

```yaml
# configs/backtest.yaml 修改
data:
  provider_uri: "~/.qlib/qlib_data/cn_data"
  region: "cn"
  market: "csi300"
  
  stock_filter:
    enabled: true
    exclude_markets: ["bj"]      # 排除北交所
    exclude_st: true             # 排除 ST 股票
    min_list_days: 60            # 上市不足60天的排除
```

---

### 需求 C：跨周期/多时间区间验证

#### C.1 需求描述

不希望只有最近1年的回测结果，而是：
1. 支持多个不连续的时间段进行回测
2. 只有在所有时间段都表现良好的因子才被认为是"跨周期有效"
3. 中间隔几年的测试可以验证因子的长期稳定性

#### C.2 现有系统基础

| 组件 | 位置 | 说明 |
|------|------|------|
| `multi_period_validation` | `configs/backtest.yaml:83` | 已预留多周期验证配置（当前 disabled） |
| `period_results` | `quantaalpha/factors/library.py` | 因子条目中已预留多周期结果字段 |
| `apply_validation_result()` | `quantaalpha/factors/library.py:580` | 已支持写入多周期验证结果 |

#### C.3 改进方案

##### C.3.1 配置增强

```yaml
# configs/backtest.yaml 修改
multi_period_validation:
  enabled: true
  fail_fast: false              # 不快速失败，收集所有区间结果
  require_all_pass: true        # 所有时段都必须达标
  
  periods:
    - name: "bull_2017"
      description: "2017年牛市环境"
      train: ["2015-01-01", "2016-12-31"]
      test:  ["2017-01-01", "2017-12-31"]
      
    - name: "bear_2018"
      description: "2018年熊市环境"
      train: ["2016-01-01", "2017-12-31"]
      test:  ["2018-01-01", "2018-12-31"]
      
    - name: "recovery_2023"
      description: "2023年复苏环境"
      train: ["2020-01-01", "2022-12-31"]
      test:  ["2023-01-01", "2024-12-31"]
  
  # 通过标准
  pass_criteria:
    min_ic: 0.03
    min_rank_ic: 0.03
    min_periods_pass: 2         # 至少通过N个周期
```

##### C.3.2 因子状态判定

```
因子跨周期验证状态:

  ┌─────────────────────────────────────────────────────────┐
  │                                                         │
  │   所有周期通过 ──────────▶ stable_active (稳定有效)      │
  │                                                         │
  │   大部分周期通过 ─────────▶ seasonal (特定环境有效)      │
  │                           + 标记有效周期                │
  │                                                         │
  │   少数周期通过 ───────────▶ degraded (效果衰减)          │
  │                                                         │
  │   全部周期失败 ───────────▶ archived (归档废弃)          │
  │                                                         │
  └─────────────────────────────────────────────────────────┘
```

---

### 需求 D：因子库功能丰富化

#### D.1 需求描述

现有因子库以 JSON 格式存储，存在以下问题：
1. 因子之间没有关联性分析
2. 没有指导新因子挖掘的知识沉淀
3. 缺少因子生命周期管理

#### D.2 现有系统基础

| 组件 | 位置 | 说明 |
|------|------|------|
| `FactorLibraryManager` | `quantaalpha/factors/library.py` | 因子库管理类 |
| 因子状态规则 | `quantaalpha/factors/status_rules.py` | 状态更新逻辑 |
| 审计日志 | `library.py:_append_audit_entry` | 状态变更记录 |

#### D.3 改进方案

##### D.3.1 因子分类标签系统

```python
# 因子条目新增字段
{
  "factor_id": "xxx",
  "factor_name": "...",
  
  # 新增：分类标签
  "tags": {
    "category": ["momentum", "reversal"],      # 因子类别
    "data_dependency": ["price_volume"],       # 数据依赖
    "market_environment": ["bull", "volatile"], # 适用市场环境
    "time_horizon": ["short_term", "intraday"] # 时间维度
  }
}
```

##### D.3.2 RAG 向量检索架构（指导新因子挖掘）

```
架构设计:

  因子挖掘流程:
  
  1. 查询向量库
     ┌─────────────────────────────────────┐
     │ SELECT * FROM factors               │
     │ WHERE embedding ~ query_embedding   │
     │ ORDER BY ic DESC                    │
     │ LIMIT 5                             │
     └─────────────────────────────────────┘
                      │
                      ▼
  2. 构建 Few-Shot Prompt
     ┌─────────────────────────────────────┐
     │ 以下是当前周期表现优秀的因子范式:     │
     │                                     │
     │ 因子A: (close - open) / open        │
     │   IC=0.12, 适用于高波动市场          │
     │                                     │
     │ 因子B: rank(volume) / rank(amount)  │
     │   IC=0.09, 流动性因子               │
     │                                     │
     │ 请总结共性，演绎新因子...            │
     └─────────────────────────────────────┘
                      │
                      ▼
  3. LLM 生成新因子
```

##### D.3.3 技术选型

| 方案 | 适用场景 | 说明 |
|------|----------|------|
| `sqlite-vss` | 轻量级部署 | SQLite 扩展，无需额外服务 |
| `ChromaDB` | 本地开发 | Python 原生，易于集成 |
| `Milvus` | 生产环境 | 高性能分布式向量数据库 |
| `Qdrant` | 云原生部署 | 支持 Docker/K8s |

##### D.3.4 因子生命周期管理

```
因子生命周期:

  ┌─────────────┐     验证通过      ┌─────────────┐
  │ pending     │ ────────────────▶ │ active      │
  │ (待验证)    │                   │ (生效中)    │
  └─────────────┘                   └─────────────┘
                                         │
                    连续N次验证失败        │
                    ┌─────────────────────┘
                    ▼
              ┌─────────────┐     重新验证通过    ┌─────────────┐
              │ degraded    │ ◀─────────────────▶ │ active      │
              │ (效果衰减)   │                    │ (生效中)    │
              └─────────────┘                    └─────────────┘
                    │
                    长期失效
                    ▼
              ┌─────────────┐
              │ archived    │
              │ (归档废弃)   │
              └─────────────┘
```

---

### 需求 E：动态数据维度感知

#### E.1 需求描述

当增加新的数据维度（如基本面数据、另类数据）时，LLM 需要知道：
1. 当前有哪些数据字段可用
2. 每个字段的含义和使用场景
3. 数据的更新频率和滞后天数

#### E.2 现有系统基础

| 组件 | 位置 | 说明 |
|------|------|------|
| `DATA_CAPABILITIES` | `quantaalpha/factors/data_capability.py:8` | 数据能力注册表 |
| `render_data_capabilities()` | `quantaalpha/factors/data_capability.py:64` | 渲染为 Prompt 文本 |
| `QlibAlphaAgentScenario` | `quantaalpha/factors/experiment.py:81` | 注入到场景描述 |

#### E.3 改进方案

##### E.3.1 数据能力注册表扩展

```python
# quantaalpha/factors/data_capability.py 扩展

DATA_CAPABILITIES = {
    "price_volume": {
        "fields": ["$open", "$close", "$high", "$low", "$volume", "$amount"],
        "freq": "daily",
        "lag_days": 0,
        "join_mode": "same_day",
        "factor_hints": ["momentum", "reversal", "volatility", "liquidity"],
        "available_from": "2010-01-01",  # 新增：数据起始日期
    },
    
    "financial": {
        "fields": ["$roa", "$roe", "$net_profit_margin", "$debt_ratio"],
        "freq": "quarterly",
        "lag_days": 45,                  # 财务数据披露滞后
        "join_mode": "forward_fill",
        "factor_hints": ["quality", "value"],
        "available_from": "2012-01-01",
    },
    
    # 新增：另类数据
    "alternative": {
        "fields": ["$sentiment", "$news_score", "$fund_flow"],
        "freq": "daily",
        "lag_days": 0,
        "join_mode": "same_day",
        "factor_hints": ["sentiment", "smart_money"],
        "available_from": "2024-01-01",
    },
}
```

##### E.3.2 自动注入到 Prompt

```python
# 现有流程（已实现）:

# 1. Scenario 初始化时
source_data = _build_source_data_description(
    use_local=use_local,
    registry_enabled=True,
    capabilities=DATA_CAPABILITIES,
)

# 2. 渲染结果示例
"""
Available data capabilities:
- price_volume: fields=$open, $close, $high, $low, $volume, $amount; 
  freq=daily; lag_days=0; join_mode=same_day; 
  typical_uses=momentum, reversal, volatility, liquidity
  
- financial: fields=$roa, $roe, $net_profit_margin; 
  freq=quarterly; lag_days=45; join_mode=forward_fill; 
  typical_uses=quality, value
  
- alternative: fields=$sentiment, $news_score, $fund_flow; 
  freq=daily; lag_days=0; join_mode=same_day; 
  typical_uses=sentiment, smart_money
"""
```

---

### 需求 F：24小时不间断运行系统

#### F.1 需求描述

构建一个自动化调度系统，实现：
1. 每日检测新数据，触发因子更新
2. 定期重验已有因子（温故）
3. 持续挖掘新因子（知新）
4. 自动处理异常和故障恢复

#### F.2 架构设计

```
┌──────────────────────────────────────────────────────────────────────────┐
│                    24小时不间断因子挖掘与维护系统                          │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                    调度中心 (Scheduler)                             │ │
│  ├────────────────────────────────────────────────────────────────────┤ │
│  │                                                                    │ │
│  │  ┌──────────────┐  ┌──────────────────────────┐  ┌──────────────┐ │ │
│  │  │ 数据监控器    │  │ 温故                      │  │ 知新         │ │ │
│  │  │              │  │ (select_revalidation_    │  │ (RAG +       │ │ │
│  │  │ 每日检测新   │  │  candidates, days=21)    │  │ 新因子挖掘)  │ │ │
│  │  │ 数据入库     │  │                          │  │              │ │ │
│  │  └──────────────┘  └──────────────────────────┘  └──────────────┘ │ │
│  │                                                                    │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                    │                                     │
│                                    ▼                                     │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                    多模型调度层 (Model Router)                      │ │
│  ├────────────────────────────────────────────────────────────────────┤ │
│  │  - 任务路由 (task_model_map)                                       │ │
│  │  - 多视角融合 (Ensemble)                                           │ │
│  │  - 平台轮询 (API Pool)                                             │ │
│  │  - JSON 纠错 (Fallback)                                            │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                    │                                     │
│                                    ▼                                     │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                    因子库 + 向量库                                  │ │
│  ├────────────────────────────────────────────────────────────────────┤ │
│  │  - JSON 存储 (现有)                                                │ │
│  │  - 状态管理 (现有)                                                 │ │
│  │  - 向量库 (新增: ChromaDB/Milvus)                                  │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                    │                                     │
│                                    ▼                                     │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                    回测引擎                                        │ │
│  ├────────────────────────────────────────────────────────────────────┤ │
│  │  - 多周期验证                                                      │ │
│  │  - 市场过滤 (排除北交所)                                           │ │
│  │  - 结果聚合                                                        │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                    │                                     │
│                                    ▼                                     │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                    数据能力注册表                                   │ │
│  ├────────────────────────────────────────────────────────────────────┤ │
│  │  price_volume │ financial │ alternative │ ... (动态扩展)           │ │
│  └────────────────────────────────────────────────────────────────────┘ │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

#### F.3 核心流程

##### F.3.1 温故（维护旧因子）

```python
# continuous/maintenance_loop.py

def run_maintenance():
    """
    定期重验已有因子
    """
    manager = FactorLibraryManager(library_path)
    
    # 选出21天(3周)未验证的 active 因子
    candidates = manager.select_revalidation_candidates(
        days=21,
        status="active"
    )
    
    for factor in candidates:
        # 使用最新数据进行回测
        result = backtest_factor(factor, latest_data_period)
        
        # 更新因子状态
        manager.apply_validation_result(
            factor_entry=factor,
            validation_result=result
        )
```

##### F.3.2 知新（挖掘新因子）

```python
# continuous/mining_loop.py

def run_mining():
    """
    持续挖掘新因子
    """
    # 1. 从向量库检索优秀因子作为 Few-Shot
    top_factors = vector_store.query(
        query="momentum reversal",
        top_k=5,
        filter={"status": "active", "ic": {">": 0.08}}
    )
    
    # 2. 构建 Prompt
    prompt = build_few_shot_prompt(top_factors)
    
    # 3. 多模型并发生成
    results = ensemble_generate(prompt, models=["gpt-4", "claude", "qwen"])
    
    # 4. 裁判模型汇总
    final_factors = judge_aggregate(results)
    
    # 5. 回测验证
    for factor in final_factors:
        result = backtest_factor(factor, multi_period=True)
        
        # 6. 存入因子库 + 向量库
        manager.add_factor(factor, result)
        vector_store.add(factor.embedding, factor.metadata)
```

---

## 三、开发优先级

| 优先级 | 需求 | 复杂度 | 价值 | 依赖 |
|--------|------|--------|------|------|
| P0 | B. 回测数据过滤（排除北交所） | ⭐ | ⭐⭐ | 无 |
| P0 | C. 多时间区间回测 | ⭐⭐ | ⭐⭐⭐⭐ | 无 |
| P1 | E. 数据维度感知 | ⭐⭐ | ⭐⭐⭐⭐ | 无 |
| P1 | D.3 RAG向量检索 | ⭐⭐⭐ | ⭐⭐⭐⭐ | 无 |
| P1 | F.3.1 温故机制 | ⭐⭐ | ⭐⭐⭐ | C |
| P2 | A. 多模型调度 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 无 |
| P2 | A.3.2 多视角融合 | ⭐⭐⭐ | ⭐⭐⭐ | A |
| P3 | D.1-D.2 因子库增强 | ⭐⭐⭐⭐ | ⭐⭐⭐ | D.3 |
| P3 | F.3.2 知新机制 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | A, D.3 |
| P4 | F. 24小时自动化 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 全部 |

---

## 四、技术选型建议

| 模块 | 推荐方案 | 备选方案 | 说明 |
|------|----------|----------|------|
| 向量数据库 | ChromaDB | sqlite-vss / Milvus | 轻量级，Python 原生 |
| 任务调度 | APScheduler | Celery / Prefect | 单机部署足够 |
| 进程管理 | Supervisor | systemd | 守护进程管理 |
| 日志监控 | Loguru + Grafana | ELK Stack | 现有 Loguru 可扩展 |
| 配置管理 | YAML + Pydantic | Hydra | 现有方案可继续使用 |

---

## 五、风险与注意事项

### 5.1 技术风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| LLM API 限流 | 挖掘中断 | 多平台轮询 + 本地模型备用 |
| 向量库数据一致性 | 检索结果不准确 | 定期同步 + 校验机制 |
| 回测资源消耗大 | 系统卡顿 | 任务队列 + 资源限流 |

### 5.2 业务风险

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| 因子过拟合 | 实盘失效 | 多周期验证 + 样本外测试 |
| 市场环境变化 | 因子失效 | 温故机制 + 状态降级 |
| 数据质量问题 | 因子偏差 | 数据校验 + 异常检测 |

---

## 六、参考文档

- QuantaAlpha 项目结构: `third_party/quantaalpha/docs/PROJECT_STRUCTURE.md`
- 实验指南: `third_party/quantaalpha/docs/experiment_guide.md`
- 用户指南: `third_party/quantaalpha/docs/user_guide.md`
- Qlib 官方文档: https://qlib.readthedocs.io/
