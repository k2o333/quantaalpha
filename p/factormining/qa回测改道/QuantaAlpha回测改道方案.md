# QuantaAlpha 回测引擎改道方案

## 从 Qlib 到 Polars+Parquet 架构迁移

---

## 一、背景与目标

### 1.1 项目背景

QuantaAlpha 是一个基于 LLM 的智能因子挖掘框架，当前版本采用 Qlib 作为底层数据存储和回测引擎。随着业务数据规模扩大和实时性要求提升，现有架构面临以下挑战：

- **数据格式限制**：Qlib 的 HDF5 格式在并行读取和增量更新方面存在瓶颈
- **计算性能瓶颈**：Pandas 在处理大规模面板数据时内存占用高、计算效率低
- **生态依赖过重**：Qlib 的强耦合增加了系统复杂度和部署成本

### 1.2 改道目标

本次改道的核心目标是将 QuantaAlpha 的回测引擎从 Qlib 迁移至 Polars+Parquet 架构，实现：

| 目标维度 | 具体指标 |
|---------|---------|
| **性能提升** | 回测速度提升 3-5 倍，内存占用降低 50% |
| **数据标准化** | 统一使用 Parquet 格式，支持列式存储和高效压缩 |
| **计算引擎升级** | 采用 Polars 替代 Pandas，利用其向量化执行和惰性求值特性 |
| **架构解耦** | 消除对 Qlib 的强依赖，降低系统复杂度 |
| **可扩展性** | 支持更灵活的因子计算表达式和自定义回测策略 |

### 1.3 改道范围

```
改道范围界定：
├─ 数据层：Qlib HDF5 → Parquet 文件
├─ 计算层：Pandas DataFrame → Polars DataFrame/LazyFrame
├─ 回测层：Qlib 回测引擎 → 自定义 Polars 回测引擎
├─ 因子计算：Pandas groupby → Polars over/transform
└─ 配置层：Qlib 配置 → 自定义配置格式

保留不变：
├─ LLM 因子挖掘流程
├─ 因子进化策略
├─ 表达式解析逻辑
└─ 评估指标体系
```

---

## 二、现状分析

### 2.1 当前架构剖析

#### 2.1.1 数据流架构

```
┌─────────────────────────────────────────────────────────────┐
│                     QuantaAlpha 当前架构                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │   因子挖掘    │───→│   因子计算    │───→│   回测评估    │   │
│  │  (LLM驱动)   │    │  (Qlib/pd)   │    │  (Qlib引擎)  │   │
│  └──────────────┘    └──────────────┘    └──────────────┘   │
│         │                   │                   │            │
│         ↓                   ↓                   ↓            │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐   │
│  │  表达式生成   │    │  HDF5 数据   │    │  绩效报告    │   │
│  │  factor.py   │    │  daily_pv.h5 │    │  IC/收益率   │   │
│  └──────────────┘    └──────────────┘    └──────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

#### 2.1.2 核心组件依赖

| 组件 | 当前实现 | 文件路径 | 依赖程度 |
|-----|---------|---------|---------|
| 数据加载 | Qlib DataLoader | `backtest/runner.py` | 强依赖 |
| 因子计算 | Pandas + function_lib | `factors/coder/function_lib.py` | 强依赖 |
| 表达式解析 | pyparsing | `factors/coder/expr_parser.py` | 中等依赖 |
| 回测引擎 | Qlib 回测 | `backtest/runner.py` | 强依赖 |
| 评估指标 | Qlib 指标计算 | `factors/coder/eva_utils.py` | 中等依赖 |

### 2.2 性能瓶颈分析

#### 2.2.1 数据读取瓶颈

当前 Qlib 数据格式的问题：

- **HDF5 格式限制**：不支持真正的列式并行读取
- **索引结构复杂**：多层索引 (datetime, instrument) 在 Pandas 中操作开销大
- **数据冗余**：预计算的 $return 等字段占用额外存储

#### 2.2.2 计算性能瓶颈

以 Alpha3 因子计算为例：

```python
# 当前 Pandas 实现（示意）
def calculate_alpha3_pd(df):
    # 1. 截面排名 - 需要 groupby
    df['open_rank'] = df.groupby('datetime')['$open'].rank()
    df['vol_rank'] = df.groupby('datetime')['$volume'].rank()
    
    # 2. 时序相关 - 需要双重 groupby
    df['alpha3'] = df.groupby('instrument').apply(
        lambda x: x['open_rank'].rolling(10).corr(x['vol_rank'])
    )
    return df

# 性能问题：
# - groupby 操作产生大量中间对象
# - Python 层面的循环和函数调用开销
# - 内存中同时存在多个临时 DataFrame
```

#### 2.2.3 回测执行瓶颈

当前回测流程的性能热点：

1. **数据对齐**：每日数据与因子值对齐时的索引操作
2. **组合构建**：截面排序和分位数计算
3. **收益计算**：循环遍历持仓计算日收益

### 2.3 技术债务评估

| 债务类型 | 严重程度 | 描述 |
|---------|---------|------|
| 强耦合 | 高 | 回测逻辑与 Qlib 深度绑定，难以单元测试 |
| 性能债务 | 高 | Pandas 在大数据量下性能急剧下降 |
| 维护成本 | 中 | Qlib 版本升级可能引入兼容性问题 |
| 扩展性 | 中 | 新增自定义回测逻辑需要修改多处代码 |

---

## 三、改道策略设计

### 3.1 总体架构设计

#### 3.1.1 目标架构

```
┌─────────────────────────────────────────────────────────────────┐
│                  QuantaAlpha Polars 架构                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌──────────────┐      ┌──────────────────┐      ┌──────────┐ │
│   │   因子挖掘    │─────→│   因子计算引擎    │─────→│  回测引擎 │ │
│   │  (LLM驱动)   │      │  (Polars Expr)   │      │ (Polars) │ │
│   └──────────────┘      └──────────────────┘      └──────────┘ │
│          │                       │                       │      │
│          ↓                       ↓                       ↓      │
│   ┌──────────────┐      ┌──────────────────┐      ┌──────────┐ │
│   │  表达式解析   │      │   Parquet 数据   │      │ 绩效报告  │ │
│   │ (兼容层)     │      │  (列式存储)      │      │ IC/收益  │ │
│   └──────────────┘      └──────────────────┘      └──────────┘ │
│                                                                  │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │              Polars Function Lib (向量化)                │  │
│   │  cs_rank | ts_mean | ts_corr | ts_std | cs_zscore ...   │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### 3.1.2 分层设计原则

```
┌─────────────────────────────────────────────────────────┐
│  应用层 (Application)                                    │
│  ├── 因子挖掘流程 (保留)                                  │
│  ├── 进化策略 (保留)                                      │
│  └── 回测配置 (扩展)                                      │
├─────────────────────────────────────────────────────────┤
│  服务层 (Service)                                        │
│  ├── PolarsBacktestRunner (新增)                        │
│  ├── PolarsFactorCalculator (新增)                      │
│  └── FactorEvaluator (适配)                             │
├─────────────────────────────────────────────────────────┤
│  数据层 (Data)                                           │
│  ├── PolarsDataLoader (新增)                            │
│  ├── ParquetDataSource (新增)                           │
│  └── DataTransformer (新增)                             │
├─────────────────────────────────────────────────────────┤
│  计算层 (Compute)                                        │
│  ├── Polars Function Lib (新增)                         │
│  ├── Expression Parser (适配)                           │
│  └── Vectorized Operations (Polars原生)                  │
└─────────────────────────────────────────────────────────┘
```

### 3.2 核心策略

#### 3.2.1 数据格式迁移策略

**策略：渐进式迁移**

```
Phase 1: 双轨并行 (2周)
├─ 保留 Qlib 数据作为基准
├─ 开发 Parquet 数据加载器
└─ 数据一致性校验

Phase 2: 灰度切换 (1周)
├─ 支持配置化数据源选择
├─ 部分实验使用 Parquet
└─ 性能对比监控

Phase 3: 全面切换 (1周)
├─ 默认使用 Parquet
├─ Qlib 作为兼容备选
└─ 文档和培训更新
```

**数据映射规范**：

| Qlib 列名 | Parquet 列名 | 数据类型 | 说明 |
|----------|-------------|---------|------|
| $open | open | Float64 | 开盘价 |
| $close | close | Float64 | 收盘价 |
| $high | high | Float64 | 最高价 |
| $low | low | Float64 | 最低价 |
| $volume | vol/volume | Float64 | 成交量 |
| instrument | ts_code | String | 股票代码 |
| datetime | trade_date | Date/DateTime | 交易日期 |

#### 3.2.2 计算引擎升级策略

**核心原则：表达式兼容，执行高效**

```python
# 策略示意：保持表达式语法不变，底层执行引擎切换

# 输入表达式 (保持不变)
expr = "ts_corr(cs_rank($open), cs_rank($volume), 10)"

# 解析阶段：生成抽象语法树 (AST)
ast = parse_expression(expr)

# 编译阶段：AST → Polars Expression
polars_expr = compile_to_polars(ast)
# 例如: pl.rolling_corr(
#           pl.col("open").rank().over("trade_date"),
#           pl.col("vol").rank().over("trade_date"),
#           window_size=10
#       ).over("ts_code")

# 执行阶段：惰性求值
result = df.with_columns(factor=polars_expr).collect()
```

#### 3.2.3 回测引擎重构策略

**事件驱动 → 向量化批量处理**

```
传统事件驱动回测：
┌─────────────────────────────────────┐
│ for date in trade_dates:            │
│     for stock in universe:          │
│         handle_market_event()       │
│         check_signals()             │
│         execute_orders()            │
└─────────────────────────────────────┘
问题：Python 循环开销大，难以并行化

目标向量化回测：
┌─────────────────────────────────────┐
│ # 1. 批量计算所有信号 (Polars)      │
│ signals = df.with_columns(...)      │
│                                     │
│ # 2. 批量生成目标持仓 (向量化)       │
│ target_positions = compute_target() │
│                                     │
│ # 3. 批量计算收益 (矩阵运算)         │
│ returns = compute_returns()         │
└─────────────────────────────────────┘
优势：充分利用 SIMD 和并行计算
```

### 3.3 关键技术决策

#### 3.3.1 Polars vs Pandas 选型

| 维度 | Polars | Pandas | 决策 |
|-----|--------|--------|------|
| 执行速度 | 快 (Rust核心) | 慢 (Python循环) | Polars |
| 内存效率 | 高 (列式压缩) | 中 (行式存储) | Polars |
| API 成熟度 | 较新 | 成熟 | Polars (足够用) |
| 生态兼容性 | 增长中 | 丰富 | 可接受 |
| 惰性求值 | 原生支持 | 有限 | Polars |

#### 3.3.2 表达式解析方案

**方案对比**：

| 方案 | 实现复杂度 | 性能 | 兼容性 | 推荐度 |
|-----|-----------|------|--------|--------|
| A. 完全重写解析器 | 高 | 高 | 需验证 | ★★☆ |
| B. 适配现有 pyparsing | 中 | 中 | 高 | ★★★ |
| C. 表达式 → SQL → Polars | 中 | 中 | 中 | ★★☆ |

**选定方案 B**：在现有 `expr_parser.py` 基础上，增加 Polars 代码生成后端。

#### 3.3.3 数据存储方案

```
Parquet 文件组织：

/data/parquet/
├── daily/                          # 日频数据
│   ├── 2024/
│   │   ├── 20240101.parquet       # 按日期分区
│   │   ├── 20240102.parquet
│   │   └── ...
│   └── 2023/
│       └── ...
├── by_stock/                       # 按股票分区 (可选)
│   ├── 000001.SZ.parquet
│   └── ...
└── combined/                       # 合并文件 (小数据集)
    └── daily_all.parquet

分区策略：
- 大数据量：按日期分区，便于并行读取和增量更新
- 小数据量：单文件，减少文件句柄开销
```

---

## 四、实施步骤

### 4.1 实施路线图

```
┌────────────────────────────────────────────────────────────────────┐
│                        实施时间线 (4周)                             │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Week 1          Week 2          Week 3          Week 4           │
│  ├─ 基础设施      ├─ 核心开发      ├─ 集成测试      ├─ 上线切换      │
│  │                │                │                │              │
│  ├─ 数据层        ├─ 计算层        ├─ 端到端测试     ├─ 灰度发布     │
│  ├─ 数据加载器     ├─ Function Lib  ├─ 性能基准测试   ├─ 监控告警     │
│  └─ 格式转换      └─ 表达式编译器   └─ 一致性验证     └─ 文档完善     │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### 4.2 详细实施计划

#### 4.2.1 Week 1: 基础设施搭建

**Day 1-2: 数据层开发**

任务清单：
- [ ] 创建 `PolarsDataLoader` 类
- [ ] 实现 Parquet 文件读取和列名映射
- [ ] 支持日期范围过滤和惰性加载

关键代码结构：

```python
# quantaalpha/backtest/polars_data_loader.py
class PolarsDataLoader:
    """Parquet 数据加载器"""
    
    def __init__(self, data_path: str):
        self.data_path = Path(data_path)
        self._lazy_df: Optional[pl.LazyFrame] = None
    
    def load(self, start_date: str = None, end_date: str = None) -> pl.LazyFrame:
        """惰性加载数据"""
        if self._lazy_df is None:
            self._lazy_df = self._scan_parquet_files()
        
        df = self._lazy_df
        if start_date:
            df = df.filter(pl.col("trade_date") >= start_date)
        if end_date:
            df = df.filter(pl.col("trade_date") <= end_date)
        
        return self._normalize_columns(df)
    
    def _normalize_columns(self, df: pl.LazyFrame) -> pl.LazyFrame:
        """列名标准化 (兼容 Qlib 命名)"""
        mapping = {
            "open": "$open",
            "close": "$close",
            "high": "$high",
            "low": "$low",
            "vol": "$volume",
            "ts_code": "instrument",
            "trade_date": "datetime"
        }
        for old, new in mapping.items():
            df = df.rename({old: new})
        return df
```

**Day 3-4: 数据格式转换工具**

任务清单：
- [ ] 开发 HDF5 → Parquet 转换脚本
- [ ] 实现数据校验逻辑
- [ ] 批量转换现有数据

**Day 5: 基础测试**

任务清单：
- [ ] 单元测试：数据加载器
- [ ] 数据一致性验证
- [ ] 性能基准测试 (vs Qlib)

#### 4.2.2 Week 2: 核心计算层开发

**Day 6-7: Polars Function Lib**

任务清单：
- [ ] 实现核心时序函数 (ts_mean, ts_std, ts_corr, ts_rank)
- [ ] 实现核心截面函数 (cs_rank, cs_mean, cs_zscore)
- [ ] 实现数学运算函数 (abs, sign, log, exp)

函数实现示例：

```python
# quantaalpha/factors/coder/polars_function_lib.py
import polars as pl

def ts_mean(expr: pl.Expr, window: int) -> pl.Expr:
    """时序均值"""
    return expr.rolling_mean(window_size=window)

def ts_corr(a: pl.Expr, b: pl.Expr, window: int) -> pl.Expr:
    """时序相关系数"""
    return pl.rolling_corr(a, b, window_size=window)

def cs_rank(expr: pl.Expr) -> pl.Expr:
    """截面排名 (0-1)"""
    return expr.rank(method="min").over("datetime") / \
           expr.count().over("datetime")
```

**Day 8-9: 表达式编译器**

任务清单：
- [ ] 扩展 `expr_parser.py` 支持 Polars 代码生成
- [ ] 实现表达式 → Polars Expression 转换
- [ ] 支持嵌套表达式和复杂运算

**Day 10: 因子计算器**

任务清单：
- [ ] 创建 `PolarsFactorCalculator` 类
- [ ] 集成数据加载和表达式计算
- [ ] 实现因子缓存机制

#### 4.2.3 Week 3: 回测引擎与集成

**Day 11-12: 回测引擎核心**

任务清单：
- [ ] 创建 `PolarsBacktestRunner` 类
- [ ] 实现向量化信号生成
- [ ] 实现组合构建逻辑

回测引擎结构：

```python
# quantaalpha/backtest/polars_runner.py
class PolarsBacktestRunner:
    """基于 Polars 的回测引擎"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.data_loader = PolarsDataLoader(config['data_path'])
        self.calculator = PolarsFactorCalculator()
    
    def run(self, expressions: Dict[str, str]) -> Dict:
        """执行回测"""
        # 1. 加载数据
        df = self.data_loader.load().collect()
        
        # 2. 计算因子
        factors = self.calculator.compute(df, expressions)
        
        # 3. 生成信号 (向量化)
        signals = self._generate_signals(factors)
        
        # 4. 计算收益 (向量化)
        returns = self._calculate_returns(signals)
        
        # 5. 计算指标
        metrics = self._compute_metrics(returns)
        
        return metrics
```

**Day 13: 评估指标实现**

任务清单：
- [ ] 实现 IC 计算 (向量化)
- [ ] 实现 Rank IC 计算
- [ ] 实现收益率曲线计算

**Day 14: 集成测试**

任务清单：
- [ ] 端到端流程测试
- [ ] 与 Qlib 版本结果对比
- [ ] 性能基准测试

#### 4.2.4 Week 4: 测试优化与上线

**Day 15-16: 一致性验证**

任务清单：
- [ ] 相同因子表达式结果对比
- [ ] 回测结果差异分析
- [ ] 边界情况处理

**Day 17-18: 性能优化**

任务清单：
- [ ] 惰性求值优化
- [ ] 内存使用优化
- [ ] 并行计算优化

**Day 19-20: 上线准备**

任务清单：
- [ ] 配置开关实现 (Qlib/Polars 切换)
- [ ] 监控和日志完善
- [ ] 文档更新

### 4.3 关键检查点

| 检查点 | 时间 | 验收标准 |
|-------|------|---------|
| CP1 | Week 1 结束 | 数据加载器通过单元测试，性能提升 20% |
| CP2 | Week 2 结束 | 核心因子计算结果与 Qlib 一致 |
| CP3 | Week 3 结束 | 端到端回测通过，IC 相关系数 > 0.99 |
| CP4 | Week 4 结束 | 生产环境灰度发布，无重大异常 |

---

## 五、预期效果评估

### 5.1 性能提升预期

#### 5.1.1 数据加载性能

| 指标 | Qlib (HDF5) | Polars (Parquet) | 提升 |
|-----|-------------|------------------|------|
| 1年数据加载 | 15s | 3s | 5x |
| 5年数据加载 | 60s | 10s | 6x |
| 内存占用 | 8GB | 3GB | 2.7x |

#### 5.1.2 因子计算性能

以 Alpha158 全套因子计算为例：

| 指标 | Pandas | Polars | 提升 |
|-----|--------|--------|------|
| 计算时间 | 120s | 20s | 6x |
| 内存峰值 | 12GB | 4GB | 3x |
| CPU 利用率 | 100% (单核) | 400% (多核) | 4x |

#### 5.1.3 回测执行性能

| 指标 | Qlib 回测 | Polars 回测 | 提升 |
|-----|-----------|-------------|------|
| 单因子回测 | 30s | 5s | 6x |
| 多因子组合 | 120s | 15s | 8x |
| 日收益计算 | 10s | 1s | 10x |

### 5.2 准确性验证

#### 5.2.1 因子值一致性

```
验证方法：
1. 选取 100 个代表性因子
2. 相同表达式分别用 Qlib 和 Polars 计算
3. 对比因子值分布

验收标准：
- 相关系数 > 0.999
- 均值差异 < 0.1%
- 标准差差异 < 0.1%
```

#### 5.2.2 回测结果一致性

```
验证方法：
1. 选取 10 个典型因子进行回测
2. 对比日收益率序列
3. 对比累计收益曲线
4. 对比风险指标 (IR, 最大回撤等)

验收标准：
- 日收益率相关系数 > 0.98
- 累计收益差异 < 1%
- 风险指标差异 < 5%
```

### 5.3 业务价值

| 价值维度 | 具体收益 |
|---------|---------|
| **效率提升** | 因子迭代周期从小时级缩短到分钟级 |
| **成本降低** | 计算资源需求减少 50-60% |
| **能力扩展** | 支持更大规模数据 (全市场 10 年历史) |
| **维护简化** | 去除 Qlib 依赖，减少技术债务 |

---

## 六、风险与应对措施

### 6.1 技术风险

| 风险 | 概率 | 影响 | 应对措施 |
|-----|------|------|---------|
| Polars API 变更 | 中 | 高 | 封装抽象层，隔离 API 直接调用 |
| 数值精度差异 | 中 | 高 | 建立精度容忍机制，设置差异阈值 |
| 内存溢出 | 低 | 高 | 实现分块处理，监控内存使用 |
| 表达式兼容性问题 | 中 | 中 | 建立表达式测试集，逐步扩展支持 |

### 6.2 项目风险

| 风险 | 概率 | 影响 | 应对措施 |
|-----|------|------|---------|
| 工期延误 | 中 | 中 | 设置缓冲时间，优先级排序 |
| 人员变动 | 低 | 中 | 文档完善，知识共享 |
| 回滚需求 | 低 | 高 | 保留 Qlib 代码分支，配置开关 |

### 6.3 风险监控机制

```
监控指标：
├─ 性能指标
│  ├─ 数据加载时间
│  ├─ 因子计算时间
│  └─ 回测执行时间
├─ 准确性指标
│  ├─ 因子值相关系数
│  ├─ 回测收益差异
│  └─ 风险指标差异
└─ 稳定性指标
   ├─ 内存使用率
   ├─ 错误率
   └─ 任务成功率

告警阈值：
├─ 性能下降 > 20% → 黄色告警
├─ 相关系数 < 0.99 → 红色告警
└─ 错误率 > 1% → 红色告警
```

---

## 七、附录

### 7.1 术语表

| 术语 | 说明 |
|-----|------|
| Qlib | 微软开源的量化投资平台 |
| Polars | 高性能 DataFrame 库 (Rust 实现) |
| Parquet | 列式存储文件格式 |
| IC | Information Coefficient，信息系数 |
| Rank IC | 排名信息系数 |
| 截面计算 | Cross-sectional，同一时间点不同股票的计算 |
| 时序计算 | Time-series，同一股票不同时间点的计算 |

### 7.2 参考资源

- Polars 官方文档: https://docs.pola.rs/
- Parquet 格式规范: https://parquet.apache.org/
- QuantaAlpha 仓库: https://github.com/QuantaAlpha/QuantaAlpha

### 7.3 相关文件清单

```
新增文件：
├── quantaalpha/backtest/
│   ├── polars_data_loader.py      # 数据加载器
│   ├── polars_runner.py           # 回测引擎
│   └── polars_factor_calculator.py # 因子计算器
├── quantaalpha/factors/coder/
│   └── polars_function_lib.py     # Polars 函数库
└── tools/
    └── convert_h5_to_parquet.py   # 数据转换工具

修改文件：
├── quantaalpha/backtest/runner.py         # 增加配置分支
├── quantaalpha/factors/coder/expr_parser.py # 增加 Polars 后端
└── configs/backtest.yaml                  # 增加数据源配置
```

---

**文档版本**: v1.0  
**编写日期**: 2026-03-10  
**编写人**: AI Assistant  
**审核状态**: 待审核