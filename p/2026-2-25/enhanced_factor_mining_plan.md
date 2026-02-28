# 因子挖掘模块整合规划 (增强版)

## 1. 背景与目标

### 1.1 现状分析
- 已有数据下载管道 (aspipe_v4)：支持从 TuShare 下载多种金融数据
- 数据存储：Polars + Parquet 格式
- 目标：整合因子挖掘能力，实现 "下载数据 → 挖因子 → 评估因子" 全流程自动化

### 1.2 核心目标
- **不依赖 Qlib**：自建轻量级因子计算框架
- **高性能**：基于 Polars 的向量化计算
- **可扩展**：支持自定义因子、自动化评估
- **易集成**：与现有数据管道无缝对接
- **标准化**：建立与 QuantaAlpha 框架兼容的因子定义和评估标准

---
## 2. 技术选型对比

| 功能 | Qlib 方案 | 自建方案 (推荐) | 说明 |
|------|-----------|-----------------|------|
| 数据存储 | Qlib 专用格式 | Parquet + 分层目录 | 更通用，易读取 |
| 计算引擎 | Qlib 表达式 | Polars Expression | 性能相当，更灵活 |
| 时间序列操作 | Qlib 内置 | Polars 窗口函数 | 原生支持，文档丰富 |
| 截面处理 | Qlib 对齐 | 自定义对齐引擎 | 轻量级，可控 |
| 因子评估 | Qlib 分析模块 | 自建 IC/衰减分析 | 按需实现，无冗余 |

---

## 3. 整体架构设计

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        因子挖掘自动化流水线                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                │
│  │   数据层      │────→│   计算层      │────→│   评估层      │                │
│  │  (已有)      │     │  (新建)      │     │  (新建)      │                │
│  └──────────────┘     └──────────────┘     └──────────────┘                │
│         │                   │                   │                          │
│         ▼                   ▼                   ▼                          │
│  ┌──────────────────────────────────────────────────────────────┐         │
│  │                      存储层 (统一)                            │         │
│  │  raw_data/  →  processed_data/  →  factors/  →  evaluation/  │         │
│  └──────────────────────────────────────────────────────────────┘         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. 模块详细设计

### 4.1 模块结构

```
app4/
├── factor/                    # 因子挖掘模块 (新建)
│   ├── __init__.py
│   ├── engine.py              # 因子计算引擎
│   ├── registry.py            # 因子注册中心
│   ├── cross_section.py       # 截面处理
│   ├── time_series.py         # 时间序列计算
│   ├── evaluator.py           # 因子评估
│   ├── storage.py             # 因子存储管理
│   ├── quantaalpha_compat.py  # QuantaAlpha 兼容层 (新增)
│   └── pipeline.py            # 流水线编排
```

### 4.2 核心模块职责

#### 4.2.1 FactorEngine (因子计算引擎)
- **职责**：执行因子计算，管理计算依赖
- **关键能力**：
  - 基于 Polars 的向量化计算
  - 支持多因子并行计算
  - 计算结果缓存
- **与现有系统集成**：
  - 读取 `StorageManager` 存储的 Parquet 文件
  - 复用 `SchemaManager` 的字段映射

#### 4.2.2 FactorRegistry (因子注册中心)
- **职责**：管理因子定义、元数据、版本
- **关键能力**：
  - 因子注册/发现
  - 因子分类 (技术因子、基本面因子、统计因子等)
  - 因子依赖关系管理
- **存储格式**：YAML/JSON 配置文件

#### 4.2.3 CrossSection (截面处理)
- **职责**：处理横截面数据对齐
- **关键能力**：
  - 交易日对齐
  - 股票池过滤
  - 缺失值处理
- **Qlib 替代方案**：
  - 自建对齐逻辑，基于 `trade_cal` 数据

#### 4.2.4 TimeSeries (时间序列计算)
- **职责**：时间序列因子计算
- **关键能力**：
  - 滚动窗口计算 (rolling)
  - 偏移计算 (shift/lag)
  - 自定义时间序列函数
- **Polars 优势**：
  - `over()` 窗口函数
  - `shift()` 偏移操作
  - 性能比 pandas 快 10-50 倍

#### 4.2.5 FactorEvaluator (因子评估)
- **职责**：因子有效性分析
- **关键能力**：
  - IC 分析 (信息系数)
  - 因子衰减分析
  - 分组收益分析
  - 换手率分析
- **输出**：评估报告 + 可视化图表

#### 4.2.6 FactorStorage (因子存储)
- **职责**：因子数据持久化
- **存储结构**：
  ```
  factors/
  ├── daily/                   # 日频因子
  │   ├── technical/           # 技术因子
  │   ├── fundamental/         # 基本面因子
  │   └── custom/              # 自定义因子
  ├── weekly/                  # 周频因子
  └── metadata/                # 因子元数据
  ```
- **文件格式**：Parquet (按日期分区)

#### 4.2.7 QuantaAlphaCompat (QuantaAlpha 兼容层)
- **职责**：提供与 QuantaAlpha 框架的兼容性接口
- **关键能力**：
  - 因子定义格式转换
  - 评估方法适配
  - 数据交换接口
  - API 标准化支持

---

## 5. 数据流设计

### 5.1 标准数据流

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  原始数据    │───→│  数据清洗    │───→│  因子计算    │───→│  因子存储    │
│  (Parquet)  │    │  (Polars)   │    │  (Engine)   │    │  (Parquet)  │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                              │
                                              ▼
                                       ┌─────────────┐
                                       │  因子评估    │
                                       │ (Evaluator) │
                                       └─────────────┘
```

### 5.2 与现有管道集成点

| 现有模块 | 集成方式 | 说明 |
|----------|----------|------|
| `StorageManager` | 读取 Parquet 文件 | 因子计算的输入源 |
| `SchemaManager` | 复用字段定义 | 确保字段名一致性 |
| `ConfigLoader` | 扩展配置 | 增加因子配置支持 |
| `main.py` | 新增 CLI 命令 | `--mode factor` |
| `stk_factor_pro` | 因子数据源 | 提供技术因子数据 |

---

## 6. 因子类型规划

### 6.1 技术因子 (Technical)

| 因子类别 | 示例 | 计算方式 |
|----------|------|----------|
| 动量因子 | `momentum_20d`, `momentum_60d` | 收益率滚动计算 |
| 波动率因子 | `volatility_20d`, `std_60d` | 标准差滚动计算 |
| 量价因子 | `volume_ratio`, `turnover_20d` | 成交量相关计算 |
| 均线因子 | `ma_ratio`, `ema_12` | 移动平均线 |

### 6.2 基本面因子 (Fundamental)

| 因子类别 | 示例 | 数据来源 |
|----------|------|----------|
| 估值因子 | `pe_ratio`, `pb_ratio` | `daily_basic` |
| 财务因子 | `roe`, `roa`, `gross_margin` | `fina_indicator_vip` |
| 成长因子 | `revenue_growth`, `profit_growth` | 财务报表计算 |

### 6.3 统计因子 (Statistical)

| 因子类别 | 示例 | 计算方式 |
|----------|------|----------|
| 分位数因子 | `price_quantile_20d` | 滚动分位数 |
| Z-Score因子 | `volume_zscore` | 标准化处理 |
| 相关性因子 | `price_volume_corr` | 滚动相关 |

---

## 7. 关键技术方案

### 7.1 Polars 表达式示例

```python
# 动量因子 (20日收益率)
df.with_columns(
    (pl.col("close") / pl.col("close").shift(20) - 1)
    .over("ts_code")
    .alias("momentum_20d")
)

# 波动率因子 (20日标准差)
df.with_columns(
    pl.col("close")
    .pct_change()
    .rolling_std(20)
    .over("ts_code")
    .alias("volatility_20d")
)

# 截面排名因子
df.with_columns(
    pl.col("momentum_20d")
    .rank()
    .over("trade_date")
    .alias("momentum_rank")
)
```

### 7.2 数据对齐方案

```python
# 交易日对齐
class CalendarAligner:
    def __init__(self, trade_cal_df):
        self.trade_dates = trade_cal_df["cal_date"].to_list()

    def align(self, df, date_col="trade_date"):
        # 只保留交易日数据
        return df.filter(pl.col(date_col).is_in(self.trade_dates))
```

### 7.3 IC 计算方案

```python
# 信息系数计算
def calculate_ic(factor_df, forward_return_col="forward_return_1d"):
    return factor_df.group_by("trade_date").agg(
        pl.corr(pl.col("factor_value"), pl.col(forward_return_col))
        .alias("ic")
    )
```

---

## 8. QuantaAlpha 集成方案

### 8.1 集成背景
为增强因子挖掘模块的标准化和可扩展性，引入 QuantaAlpha 框架的兼容性设计。QuantaAlpha 作为量化分析框架，提供因子定义、评估和回测标准。

### 8.2 兼容性设计

#### 8.2.1 因子定义格式兼容
| aspipe_v4 格式 | QuantaAlpha 格式 | 适配方案 |
|----------------|------------------|----------|
| YAML 配置文件 | JSON 配置文件 | 通过 `quantaalpha_compat.py` 实现格式转换 |
| 因子名称使用下划线 | 因子名称使用驼峰命名 | 统一因子命名规范 |
| 字段类型由 YAML 定义 | 字段类型由 Schema 定义 | 实现类型映射机制 |

#### 8.2.2 评估方法兼容
| 评估指标 | aspipe_v4 实现 | QuantaAlpha 标准 | 适配状态 |
|----------|----------------|------------------|----------|
| IC (信息系数) | 已实现 | 标准指标 | 完全兼容 |
| IR (信息比率) | 计划实现 | 标准指标 | 待实现 |
| 月度IC均值 | 计划实现 | 标准指标 | 待实现 |
| 换手率 | 计划实现 | 标准指标 | 待实现 |
| 分组回测 | 计划实现 | 标准指标 | 待实现 |

#### 8.2.3 API 接口兼容
为便于与 QuantaAlpha 或类似框架集成，提供以下标准化接口：

```python
# QuantaAlpha 兼容接口示例
class QuantaAlphaAdapter:
    def __init__(self, factor_engine):
        self.factor_engine = factor_engine

    def get_factor_data(self, factor_name, start_date, end_date, universe=None):
        """
        获取因子数据 - 符合 QuantaAlpha 数据格式
        """
        pass

    def calculate_factor_returns(self, factor_data, pricing_data, periods=(1, 5, 10)):
        """
        计算因子收益 - 符合 QuantaAlpha 计算标准
        """
        pass

    def run_factor_analysis(self, factor_data, pricing_data, **kwargs):
        """
        运行因子分析 - 生成 QuantaAlpha 标准报告
        """
        pass
```

### 8.3 集成实现路径

#### 8.3.1 短期目标 (Phase 1-2)
- [ ] 实现基本的 QuantaAlpha 数据格式转换
- [ ] 提供标准化的因子数据接口
- [ ] 兼容 QuantaAlpha 的评估指标计算

#### 8.3.2 中期目标 (Phase 3-4)
- [ ] 实现与 QuantaAlpha 框架的直接数据交换
- [ ] 开发因子结果导入/导出功能
- [ ] 提供 QuantaAlpha 风格的可视化接口

#### 8.3.3 长期目标 (Phase 5+)
- [ ] 支持 QuantaAlpha 的因子回测流程
- [ ] 实现与第三方量化平台的数据互通
- [ ] 建立因子库的共享机制

### 8.4 与现有因子数据的关系

aspipe_v4 已有的 `stk_factor_pro` 接口提供了超过300个技术因子，与计划中的因子挖掘功能有部分重叠：

| 数据来源 | 特点 | 用途 | 集成方式 |
|----------|------|------|----------|
| `stk_factor_pro` | TuShare 提供的预计算因子 | 直接使用的技术指标 | 作为因子挖掘的基准对比 |
| 自建因子 | 基于原始数据计算 | 自定义因子开发 | 与预计算因子并行存储 |
| QuantaAlpha 因子 | 第三方框架定义 | 标准化因子 | 通过适配器进行兼容 |

---

## 9. 实施计划

### Phase 1: 基础框架 (Week 1)
- [ ] 创建 `factor/` 模块结构
- [ ] 实现 `FactorEngine` 基础计算能力
- [ ] 实现 `FactorRegistry` 注册机制
- [ ] 集成测试 (读取现有 Parquet 数据)
- [ ] 实现 QuantaAlpha 兼容基础接口

### Phase 2: 核心因子 (Week 2)
- [ ] 实现常用技术因子 (动量、波动率、量价)
- [ ] 实现基本面因子 (估值、财务指标)
- [ ] 实现截面处理模块
- [ ] 因子存储管理
- [ ] 实现因子格式转换功能

### Phase 3: 评估体系 (Week 3)
- [ ] 实现 IC 分析
- [ ] 实现分组收益分析
- [ ] 实现衰减分析
- [ ] 评估报告生成
- [ ] QuantaAlpha 风格可视化

### Phase 4: 自动化集成 (Week 4)
- [ ] CLI 命令集成 (`--mode factor`)
- [ ] 流水线自动化
- [ ] 配置文件支持
- [ ] 完整测试
- [ ] 与 QuantaAlpha 框架集成测试

---

## 10. 风险与对策

| 风险 | 对策 |
|------|------|
| Polars 学习成本 | 提供完整示例代码，封装常用模式 |
| 性能瓶颈 | 利用 Polars 惰性求值，分区并行计算 |
| 内存占用 | 按日期/股票分批处理，避免全量加载 |
| 数据一致性 | 严格校验输入数据格式，统一字段命名 |
| QuantaAlpha 标准变化 | 采用适配器模式，保持兼容性 |
| 因子计算复杂度 | 分阶段实现，先实现基础因子再扩展高级因子 |

---

## 11. 附录

### 11.1 依赖项
```
polars>=0.20.0
numpy>=1.24.0
pyarrow>=14.0.0
matplotlib>=3.5.0  # 用于可视化
seaborn>=0.11.0    # 用于统计图表
```

### 11.2 参考文档
- [Polars 文档](https://docs.pola.rs/)
- [Polars 窗口函数](https://docs.pola.rs/user-guide/transformations/time-series/rolling/)
- [因子投资理论](https://en.wikipedia.org/wiki/Factor_investing)
- [量化分析最佳实践](https://www.quantstart.com/articles/)

---

**文档版本**: v2.0
**创建日期**: 2026-02-28
**状态**: 更新版本，待评审