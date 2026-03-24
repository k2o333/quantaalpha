# QuantaAlpha 因子挖掘系统增强设计方案

## 一、需求概述

用户基于 quantaalpha 项目进行因子挖掘，需要以下增强：

| 需求 | 描述 |
|------|------|
| A. 多模型调度 | 大小模型分工、多模型协作、JSON修复、平台轮询 |
| B. 回测数据过滤 | 排除北交所股票 |
| C. 时间区间调整 | 多跨度回测区间，验证跨周期有效性 |
| D. 因子库增强 | 指导新因子生成、进化优化、回测维护、因子筛选 |
| E. 数据维度扩展 | 基本面、分析师、行业/资金流数据 |
| F. 24h不间断运行 | 持续挖掘、维护、更新因子 |

---

## 二、架构设计总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                      Factor Mining Orchestrator                      │
│  (调度器: 定时任务 + 事件驱动 + 监控告警)                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐ │
│  │ 因子挖掘任务 │  │ 因子维护任务 │  │ 数据更新任务 │  │ 回测任务    │ │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────┬──────┘ │
│         │                │                │                │        │
│         ▼                ▼                ▼                ▼        │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                    Multi-Model Router                            ││
│  │  (智能路由: 任务复杂度评估 → 大小模型选择 + 轮询 + 容错)          ││
│  └─────────────────────────────────────────────────────────────────┘│
│         │                │                │                │        │
│         ▼                ▼                ▼                ▼        │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                    Enhanced Factor Library                       ││
│  │  (增强因子库: 向量化存储 + 元数据管理 + 状态追踪 + 智能检索)       ││
│  └─────────────────────────────────────────────────────────────────┘│
│         │                │                │                │        │
│         ▼                ▼                ▼                ▼        │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                    Data Dimension Registry                       ││
│  │  (数据维度注册表: 动态注册新数据 → 自动生成可用因子模板)           ││
│  └─────────────────────────────────────────────────────────────────┘│
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 三、模块详细设计

### 3.1 多模型路由器 (Multi-Model Router)

**目标文件**: `quantaalpha/llm/model_router.py` (新建)

**核心功能**:

```python
class ModelRouter:
    """
    智能模型路由器

    功能:
    1. 任务复杂度评估 → 选择合适模型
    2. 平台轮询 → 分担API压力
    3. JSON修复 → coding模型兜底
    4. 多模型协作 → 获取不同视角
    """

    # 模型分级配置
    MODEL_TIERS = {
        "reasoning": ["qwen3-max", "gpt-4o"],      # 复杂推理
        "standard": ["qwen2.5-72b", "deepseek-v3"], # 标准任务
        "coding": ["codestral-latest"],            # JSON修复/代码
        "lightweight": ["qwen2.5-7b", "phi-4"],    # 简单任务
    }

    # 轮询策略
    ROUND_ROBIN_CONFIG = {
        "enabled": True,
        "per_platform_limit": 10,  # 每个平台每分钟限制
        "cooldown_seconds": 60,
    }
```

**实现要点**:

1. **复杂度评估器**:
   - 分析prompt长度、是否需要JSON输出、是否涉及代码
   - 评分 → 选择对应模型层级

2. **轮询调度器**:
   - 维护各平台调用计数
   - 超过阈值自动切换下一平台

3. **JSON修复流程**:
   ```
   主模型调用 → JSON解析失败
        ↓
   coding模型修复(prompt + 错误信息) → 返回修复后JSON
   ```

4. **多模型协作**:
   - 同一hypothesis用多个模型生成因子
   - 合并去重后进入回测

---

### 3.2 回测数据过滤

**目标文件**: `configs/backtest.yaml` + `quantaalpha/backtest/run_backtest.py`

**修改内容**:

```yaml
# configs/backtest.yaml 新增配置
data:
  provider_uri: "~/.qlib/qlib_data/cn_data"
  region: "cn"
  market: "csi300"
  # 新增: 股票过滤配置
  stock_filter:
    # 排除北交所股票
    exclude_markets: ["bj"]  # 北交所市场代码
    # 可选: 只保留主板+创业板+科创板
    include_markets: ["sh", "sz", "star", "gem"]
```

**实现要点**:

- 在 `run_backtest.py` 的数据加载阶段添加过滤逻辑
- 基于股票代码前缀判断市场归属

---

### 3.3 多时间区间回测

**目标文件**: `configs/backtest.yaml` + `quantaalpha/backtest/run_backtest.py`

**修改内容**:

```yaml
# configs/backtest.yaml 新增多区间配置
dataset:
  # 多时间区间配置
  time_periods:
    - name: "recent_1y"
      train: ["2024-01-01", "2024-06-30"]
      valid: ["2024-07-01", "2024-09-30"]
      test:  ["2024-10-01", "2025-03-13"]

    - name: "historical_2021"
      train: ["2018-01-01", "2020-06-30"]
      valid: ["2020-07-01", "2020-12-31"]
      test:  ["2021-01-01", "2021-12-31"]

    - name: "historical_2019"
      train: ["2016-01-01", "2018-06-30"]
      valid: ["2018-07-01", "2018-12-31"]
      test:  ["2019-01-01", "2019-12-31"]

  # 筛选标准: 因子需在至少N个区间表现稳定
  cross_period_validation:
    min_periods: 2
    ic_threshold: 0.02
    stability_weight: 0.3
```

**实现要点**:

1. 因子回测时遍历所有时间区间
2. 计算跨区间稳定性分数
3. 只有通过跨周期验证的因子才入库

---

### 3.4 增强因子库

**目标文件**: `quantaalpha/factors/library.py` (重构)

**新架构**:

```python
class EnhancedFactorLibrary:
    """
    增强因子库

    核心能力:
    1. 向量化存储 (FAISS/Pinecone) - 支持语义检索
    2. 元数据管理 - 数据依赖、回测历史、状态追踪
    3. 智能检索 - 基于场景/数据/表现筛选因子
    4. 进化支持 - 变异/交叉的历史追踪
    """

    # 因子状态
    FACTOR_STATUS = {
        "active": "当前有效",
        "degraded": "表现下降",
        "deprecated": "已失效",
        "pending_review": "待回测验证",
    }

    # 元数据字段
    METADATA_SCHEMA = {
        # 基础信息
        "factor_id": "str",
        "factor_name": "str",
        "factor_expression": "str",
        "factor_description": "str",

        # 数据依赖 (核心新增)
        "data_requirements": {
            "fields": ["$close", "$volume"],  # 使用的原始字段
            "derived_fields": ["$return"],    # 派生字段
            "time_range": "daily",
        },

        # 回测历史
        "backtest_history": [
            {
                "timestamp": "2025-03-13T10:00:00",
                "period": "recent_1y",
                "metrics": {"ic": 0.035, "ir": 1.2},
                "config_hash": "abc123",
            }
        ],

        # 状态追踪
        "status": "active",
        "last_validated": "2025-03-13",
        "validation_score": 0.85,

        # 进化信息
        "evolution": {
            "parent_ids": [],
            "generation": 0,
            "mutation_type": None,
        },

        # 使用建议 (LLM生成)
        "usage_guidance": "适用于高波动市场环境...",
    }
```

**核心方法**:

```python
# 1. 指导新因子生成
def get_reference_factors(self, scenario: str, data_fields: list) -> list:
    """根据场景和数据维度，检索相关优质因子作为参考"""

# 2. 进化优化
def get_evolution_candidates(self, strategy: str, top_k: int) -> list:
    """获取用于变异/交叉的候选因子"""

# 3. 回测维护
def get_factors_for_revalidation(self, days_since_last: int = 21) -> list:
    """获取需要重新回测的因子"""

# 4. 因子筛选
def filter_factors(self, criteria: dict) -> list:
    """
    criteria示例:
    - min_ic: 0.03
    - data_fields: ["$close", "$volume"]
    - status: ["active"]
    - cross_period_stable: True
    """
```

---

### 3.5 数据维度注册表

**目标文件**: `quantaalpha/data/dimension_registry.py` (新建)

**核心设计**:

```python
class DataDimensionRegistry:
    """
    数据维度注册表

    功能:
    1. 动态注册新数据源
    2. 自动生成数据描述 → 注入LLM prompt
    3. 追踪因子对数据的依赖
    """

    # 注册的数据维度
    DIMENSIONS = {
        "price_volume": {
            "fields": ["$open", "$close", "$high", "$low", "$volume"],
            "derived": ["$return"],
            "freq": "daily",
            "description_template": "price_volume.md.j2",
        },
        "fundamental": {
            "fields": ["$pe", "$pb", "$roe", "$revenue_growth"],
            "freq": "quarterly",
            "description_template": "fundamental.md.j2",
            "join_key": "instrument,date",
        },
        "analyst": {
            "fields": ["$analyst_rating", "$target_price", "$sentiment"],
            "freq": "daily",
            "description_template": "analyst.md.j2",
        },
        "capital_flow": {
            "fields": ["$net_inflow", "$institution_holding", "$sector"],
            "freq": "daily",
            "description_template": "capital_flow.md.j2",
        },
    }

    def register_dimension(self, name: str, config: dict):
        """注册新数据维度"""

    def get_available_fields(self) -> list:
        """获取所有可用字段列表"""

    def generate_data_description(self, dimensions: list = None) -> str:
        """生成数据描述，注入到LLM prompt"""
```

**与因子挖掘的集成**:

```python
# 在 qlib_utils.py 的 get_data_folder_intro() 中
def get_data_folder_intro(...):
    # 动态获取已注册的数据维度
    registry = DataDimensionRegistry()
    available_fields = registry.get_available_fields()

    # 生成包含所有维度的数据描述
    return registry.generate_data_description()
```

**LLM如何知道新数据可用**:

1. 数据注册时自动更新数据描述模板
2. 因子生成prompt中包含完整可用字段列表
3. 回测时验证因子所需数据是否可用

---

### 3.6 调度器 (Orchestrator)

**目标文件**: `quantaalpha/scheduler/orchestrator.py` (新建)

**采用方案**: 简单内置调度 + 外部触发接口

```python
class FactorMiningOrchestrator:
    """
    因子挖掘调度器

    功能:
    1. 定时挖掘任务 (每日/每小时)
    2. 因子维护任务 (定期回测)
    3. 数据更新响应 (新数据到达时触发)
    4. 监控告警
    """

    # 任务配置
    TASKS = {
        "daily_mining": {
            "schedule": "0 9 * * *",  # 每天9点
            "action": "run_factor_mining",
            "config": {"directions": 3, "evolution_rounds": 5},
        },
        "factor_revalidation": {
            "schedule": "0 0 * * 0",  # 每周日
            "action": "revalidate_factors",
            "config": {"days_since_last": 21},
        },
        "data_sync": {
            "trigger": "on_data_update",  # 事件触发
            "action": "sync_new_data",
        },
    }
```

**实现方式**:

- 使用 `schedule` 库处理定时任务 (轻量级)
- 提供 REST API 接口供外部调度器调用
- 支持 Docker 部署

---

## 四、关键修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `quantaalpha/llm/model_router.py` | 新建 | 多模型路由器 |
| `quantaalpha/llm/config.py` | 修改 | 添加多模型配置 |
| `quantaalpha/llm/client.py` | 修改 | 集成路由器 |
| `configs/backtest.yaml` | 修改 | 多时间区间+股票过滤 |
| `quantaalpha/backtest/run_backtest.py` | 修改 | 实现过滤和多区间回测 |
| `quantaalpha/factors/library.py` | 重构 | 增强因子库 |
| `quantaalpha/data/dimension_registry.py` | 新建 | 数据维度注册表 |
| `quantaalpha/factors/qlib_utils.py` | 修改 | 集成数据维度 |
| `quantaalpha/scheduler/orchestrator.py` | 新建 | 调度器 |
| `quantaalpha/factors/prompts/prompts.yaml` | 修改 | 更新数据字段说明 |

---

## 五、实施优先级建议

**Phase 1 (基础能力)**:
1. 多模型路由器 - 解决API压力和容错
2. 回测数据过滤 - 排除北交所
3. 多时间区间回测 - 验证跨周期有效性

**Phase 2 (因子库增强)**:
4. 增强因子库重构
5. 数据维度注册表
6. 因子维护机制

**Phase 3 (自动化)**:
7. 调度器实现
8. 监控告警
9. 24h不间断运行优化

---

## 六、确认的技术选型

| 决策项 | 选择 | 说明 |
|--------|------|------|
| 数据来源 | Tushare + 已有数据 | 支持基本面、分析师、资金流数据 |
| 存储方案 | **Parquet + DuckDB** | 列式存储高效查询，DuckDB支持复杂SQL |
| 部署模式 | 单机运行 | 使用 schedule 库定时，无需分布式 |

---

## 七、实施步骤清单

### Phase 1: 多模型路由器 (预计修改 4 个文件)

- [ ] 创建 `quantaalpha/llm/model_router.py`
  - ModelRouter 类：复杂度评估、轮询调度、JSON修复
  - 集成到 APIBackend
- [ ] 修改 `quantaalpha/llm/config.py`
  - 添加多模型配置字段
- [ ] 修改 `quantaalpha/llm/client.py`
  - 在调用处集成路由器

### Phase 2: 回测增强 (预计修改 3 个文件)

- [ ] 修改 `configs/backtest.yaml`
  - 添加股票过滤配置
  - 添加多时间区间配置
- [ ] 修改 `quantaalpha/backtest/run_backtest.py`
  - 实现北交所股票过滤
  - 实现多区间遍历回测

### Phase 3: 数据维度注册表 (新建 2 个文件)

- [ ] 创建 `quantaalpha/data/__init__.py`
- [ ] 创建 `quantaalpha/data/dimension_registry.py`
  - DataDimensionRegistry 类
  - Tushare 数据源适配
- [ ] 修改 `quantaalpha/factors/qlib_utils.py`
  - 集成数据维度描述

### Phase 4: 增强因子库 (重构 1 个文件)

- [ ] 重构 `quantaalpha/factors/library.py`
  - 迁移到 Parquet + DuckDB 存储
  - 添加元数据管理
  - 添加智能检索方法
  - 添加回测维护方法

### Phase 5: 调度器 (新建 2 个文件)

- [ ] 创建 `quantaalpha/scheduler/__init__.py`
- [ ] 创建 `quantaalpha/scheduler/orchestrator.py`
  - FactorMiningOrchestrator 类
  - 定时任务配置
  - 监控告警接口

### Phase 6: Prompt 更新

- [ ] 修改 `quantaalpha/factors/prompts/prompts.yaml`
  - 更新可用数据字段说明

---

## 八、备注

- 文档生成时间: 2026-03-13
- 项目路径: `/home/quan/testdata/aspipe_v4/third_party/quantaalpha`
