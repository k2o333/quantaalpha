# QuantaAlpha 回测引擎双轨迁移方案

## Qlib + Polars/Parquet 双引擎架构设计

---

## 一、背景与目标

### 1.1 项目背景

QuantaAlpha 是一个基于 LLM 的智能因子挖掘框架，当前版本采用 Qlib 作为底层数据存储和回测引擎。随着业务数据规模扩大和实时性要求提升，现有架构面临以下挑战：

- **数据格式限制**：Qlib 的 HDF5 格式在并行读取和增量更新方面存在瓶颈
- **计算性能瓶颈**：Pandas 在处理大规模面板数据时内存占用高、计算效率低
- **生态依赖过重**：Qlib 的强耦合增加了系统复杂度和部署成本

### 1.2 改道目标

本次改道的核心目标是构建 **Qlib + Polars/Parquet 双引擎并存架构**，通过配置化切换实现：

| 目标维度 | 具体指标 |
|---------|---------|
| **双引擎并存** | Qlib 和 Polars 两套引擎同时可用，配置切换 |
| **结果一致性** | 两引擎中间产物和最终结果数值一致 |
| **性能提升** | Polars 回测速度提升 3-5 倍，内存占用降低 50% |
| **数据标准化** | 支持 Parquet 格式，列式存储和高效压缩 |
| **计算引擎升级** | 采用 Polars 替代 Pandas，利用其向量化执行和惰性求值特性 |
| **架构解耦** | 消除对 Qlib 的强依赖，降低系统复杂度 |
| **可扩展性** | 支持更灵活的因子计算表达式和自定义回测策略 |

### 1.3 核心需求：双引擎并存与验证

```
核心设计原则：
├─ 双引擎并存：Qlib 引擎和 Polars 引擎同时存在
├─ 配置化切换：通过配置文件选择使用哪个引擎
├─ 中间产物验证：每一步计算结果可对比验证
├─ 结果准确性：确保两引擎最终结果数值一致
└─ 渐进式迁移：先验证一致性，再切换生产环境

验证机制：
├─ 数据层：数据加载后数值对比
├─ 因子层：因子计算结果逐行对比
├─ 信号层：信号生成逻辑对比
├─ 收益层：收益率序列对比
└─ 指标层：IC、IR、最大回撤等指标对比
```

### 1.4 改道范围

```
改道范围界定：
├─ 数据层：新增 Parquet 数据源 (保留 Qlib HDF5)
├─ 计算层：新增 Polars 计算引擎 (保留 Pandas)
├─ 回测层：新增 Polars 回测引擎 (保留 Qlib 回测)
├─ 因子计算：新增 Polars 函数库 (保留 Pandas function_lib)
├─ 配置层：新增引擎选择配置项
└─ 验证层：新增中间产物对比验证机制

保留不变：
├─ LLM 因子挖掘流程
├─ 因子进化策略
├─ 表达式解析逻辑 (AST 生成)
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

## 三、双引擎架构设计

### 3.1 总体架构设计

#### 3.1.1 目标架构：双引擎并存

```
┌──────────────────────────────────────────────────────────────────────┐
│                    QuantaAlpha 双引擎架构                              │
├──────────────────────────────────────────────────────────────────────┤
│                                                                       │
│   ┌──────────────┐      ┌──────────────────────┐      ┌───────────┐ │
│   │   因子挖掘    │─────→│     引擎路由层        │─────→│  回测结果  │ │
│   │  (LLM驱动)   │      │  (Engine Router)     │      │  绩效报告  │ │
│   └──────────────┘      └──────────────────────┘      └───────────┘ │
│          │                       │                                    │
│          ↓                       ↓                                    │
│   ┌──────────────┐      ┌──────────────────────┐                     │
│   │  表达式解析   │      │  config.engine_type  │                     │
│   │ (AST生成)    │      │  = "qlib" | "polars" │                     │
│   └──────────────┘      └──────────────────────┘                     │
│                                  │                                    │
│                    ┌─────────────┴─────────────┐                     │
│                    ↓                           ↓                      │
│   ┌────────────────────────┐    ┌────────────────────────┐          │
│   │     Qlib 引擎          │    │     Polars 引擎         │          │
│   ├────────────────────────┤    ├────────────────────────┤          │
│   │ • QlibDataLoader       │    │ • PolarsDataLoader      │          │
│   │ • Pandas Function Lib  │    │ • Polars Function Lib   │          │
│   │ • Qlib Backtest        │    │ • Polars Backtest       │          │
│   │ • HDF5 数据源          │    │ • Parquet 数据源        │          │
│   └────────────────────────┘    └────────────────────────┘          │
│                    │                           │                      │
│                    └─────────────┬─────────────┘                     │
│                                  ↓                                    │
│                    ┌──────────────────────────┐                      │
│                    │     验证对比层            │                      │
│                    │  (Validation Layer)      │                      │
│                    │ • 中间产物对比            │                      │
│                    │ • 数值差异报告            │                      │
│                    └──────────────────────────┘                      │
│                                                                       │
└──────────────────────────────────────────────────────────────────────┘
```

#### 3.1.2 分层设计原则

```
┌─────────────────────────────────────────────────────────┐
│  应用层 (Application)                                    │
│  ├── 因子挖掘流程 (保留)                                  │
│  ├── 进化策略 (保留)                                      │
│  └── 回测配置 (扩展：engine_type 选择)                    │
├─────────────────────────────────────────────────────────┤
│  路由层 (Router)                                         │
│  ├── BacktestEngineRouter (新增)                        │
│  └── 根据配置选择引擎实现                                 │
├─────────────────────────────────────────────────────────┤
│  引擎层 (Engine)                                         │
│  ├── QlibBacktestRunner (保留)                          │
│  ├── PolarsBacktestRunner (新增)                        │
│  ├── QlibFactorCalculator (保留)                        │
│  └── PolarsFactorCalculator (新增)                      │
├─────────────────────────────────────────────────────────┤
│  数据层 (Data)                                           │
│  ├── QlibDataLoader (保留)                              │
│  ├── PolarsDataLoader (新增)                            │
│  ├── HDF5 数据源 (保留)                                  │
│  └── Parquet 数据源 (新增)                               │
├─────────────────────────────────────────────────────────┤
│  计算层 (Compute)                                        │
│  ├── Pandas Function Lib (保留)                         │
│  ├── Polars Function Lib (新增)                         │
│  └── Expression Parser (适配：双后端支持)                 │
├─────────────────────────────────────────────────────────┤
│  验证层 (Validation)                                     │
│  ├── DataValidator (新增)                               │
│  ├── FactorValidator (新增)                             │
│  ├── BacktestValidator (新增)                           │
│  └── DiffReportGenerator (新增)                         │
└─────────────────────────────────────────────────────────┘
```

### 3.2 配置化切换机制

#### 3.2.1 配置文件设计

```yaml
# configs/backtest.yaml
engine:
  # 引擎类型: "qlib" | "polars" | "both"(对比验证模式)
  type: "both"

  # 对比验证模式配置
  validation:
    enabled: true                    # 是否启用对比验证
    save_intermediate: true          # 是否保存中间产物
    diff_threshold: 1e-6             # 数值差异容忍阈值
    report_dir: "./validation_reports"  # 验证报告目录

  # Qlib 引擎配置
  qlib:
    provider_uri: "~/.qlib/qlib_data/cn_data"
    region: "cn"

  # Polars 引擎配置
  polars:
    data_path: "./data/parquet"
    lazy_mode: true                  # 是否使用惰性求值

data:
  start_time: "2020-01-01"
  end_time: "2023-12-31"
  market: "csi300"

backtest:
  # ... 其他回测配置
```

#### 3.2.2 引擎路由实现

```python
# quantaalpha/backtest/engine_router.py
from typing import Dict, Optional, Literal
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

EngineType = Literal["qlib", "polars", "both"]

class BacktestEngineRouter:
    """回测引擎路由器：根据配置选择使用哪个引擎"""

    def __init__(self, config: Dict):
        self.config = config
        self.engine_type: EngineType = config['engine']['type']
        self.validation_enabled = config['engine'].get('validation', {}).get('enabled', False)

        # 初始化引擎实例
        self._qlib_runner = None
        self._polars_runner = None

    def run(self, expressions: Dict[str, str], **kwargs) -> Dict:
        """执行回测，根据配置选择引擎"""

        if self.engine_type == "qlib":
            return self._run_qlib(expressions, **kwargs)

        elif self.engine_type == "polars":
            return self._run_polars(expressions, **kwargs)

        elif self.engine_type == "both":
            return self._run_both_with_validation(expressions, **kwargs)

        else:
            raise ValueError(f"Unknown engine type: {self.engine_type}")

    def _run_qlib(self, expressions: Dict, **kwargs) -> Dict:
        """使用 Qlib 引擎执行"""
        if self._qlib_runner is None:
            from .runner import BacktestRunner
            self._qlib_runner = BacktestRunner(self.config)
        return self._qlib_runner.run(expressions=expressions, **kwargs)

    def _run_polars(self, expressions: Dict, **kwargs) -> Dict:
        """使用 Polars 引擎执行"""
        if self._polars_runner is None:
            from .polars_runner import PolarsBacktestRunner
            self._polars_runner = PolarsBacktestRunner(self.config)
        return self._polars_runner.run(expressions=expressions, **kwargs)

    def _run_both_with_validation(self, expressions: Dict, **kwargs) -> Dict:
        """双引擎并行执行并对比验证"""
        from .validator import BacktestValidator

        logger.info("="*60)
        logger.info("Running dual-engine validation mode")
        logger.info("="*60)

        # 1. 执行 Qlib 引擎
        logger.info("[1/2] Running Qlib engine...")
        qlib_result = self._run_qlib(expressions, **kwargs)

        # 2. 执行 Polars 引擎
        logger.info("[2/2] Running Polars engine...")
        polars_result = self._run_polars(expressions, **kwargs)

        # 3. 对比验证
        validator = BacktestValidator(self.config)
        validation_report = validator.compare_results(
            qlib_result, polars_result,
            expressions=expressions
        )

        # 4. 输出验证报告
        validator.save_report(validation_report)

        return {
            "qlib": qlib_result,
            "polars": polars_result,
            "validation": validation_report
        }
```

### 3.3 中间产物验证机制

#### 3.3.1 验证点设计

```
验证点流程图：

┌─────────────────────────────────────────────────────────────────┐
│                        验证点检查流程                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Stage 1: 数据加载验证                                           │
│  ┌─────────────┐    ┌─────────────┐    ┌──────────────────┐    │
│  │ Qlib 数据   │    │ Parquet数据 │    │ 数据一致性报告    │    │
│  │ (HDF5)      │ ─→ │ (Parquet)   │ ─→ │ • 行数对比       │    │
│  │             │    │             │    │ • 列值对比       │    │
│  └─────────────┘    └─────────────┘    │ • 数据类型对比    │    │
│                                        └──────────────────┘    │
│                    ↓                                             │
│  Stage 2: 因子计算验证                                           │
│  ┌─────────────┐    ┌─────────────┐    ┌──────────────────┐    │
│  │ Pandas 因子 │    │ Polars 因子 │    │ 因子一致性报告    │    │
│  │ 计算        │ ─→ │ 计算        │ ─→ │ • 逐行对比       │    │
│  │             │    │             │    │ • 相关系数       │    │
│  └─────────────┘    └─────────────┘    │ • 差异分布       │    │
│                                        └──────────────────┘    │
│                    ↓                                             │
│  Stage 3: 信号生成验证                                           │
│  ┌─────────────┐    ┌─────────────┐    ┌──────────────────┐    │
│  │ Qlib 信号   │    │ Polars 信号 │    │ 信号一致性报告    │    │
│  │ (预测值)    │ ─→ │ (预测值)    │ ─→ │ • 排序对比       │    │
│  │             │    │             │    │ • 分位数对比     │    │
│  └─────────────┘    └─────────────┘    └──────────────────┘    │
│                    ↓                                             │
│  Stage 4: 收益计算验证                                           │
│  ┌─────────────┐    ┌─────────────┐    ┌──────────────────┐    │
│  │ Qlib 收益   │    │ Polars 收益 │    │ 收益一致性报告    │    │
│  │ 序列        │ ─→ │ 序列        │ ─→ │ • 日收益对比     │    │
│  │             │    │             │    │ • 累计收益对比    │    │
│  └─────────────┘    └─────────────┘    └──────────────────┘    │
│                    ↓                                             │
│  Stage 5: 指标计算验证                                           │
│  ┌─────────────┐    ┌─────────────┐    ┌──────────────────┐    │
│  │ Qlib 指标   │    │ Polars 指标 │    │ 指标一致性报告    │    │
│  │ (IC/IR等)   │ ─→ │ (IC/IR等)   │ ─→ │ • IC 对比        │    │
│  │             │    │             │    │ • IR 对比        │    │
│  └─────────────┘    └─────────────┘    │ • 最大回撤对比    │    │
│                                        └──────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### 3.3.2 验证器实现

```python
# quantaalpha/backtest/validator.py
import numpy as np
import pandas as pd
import polars as pl
from typing import Dict, Any, Optional
from pathlib import Path
import json
import logging
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class ValidationReport:
    """验证报告数据结构"""
    stage: str                    # 验证阶段
    passed: bool                  # 是否通过
    correlation: Optional[float]  # 相关系数
    mean_diff: Optional[float]    # 均值差异
    max_diff: Optional[float]     # 最大差异
    diff_ratio: Optional[float]   # 差异比例
    details: Dict[str, Any]       # 详细信息


class BacktestValidator:
    """回测结果验证器"""

    def __init__(self, config: Dict):
        self.config = config
        validation_config = config.get('engine', {}).get('validation', {})
        self.diff_threshold = validation_config.get('diff_threshold', 1e-6)
        self.save_intermediate = validation_config.get('save_intermediate', True)
        self.report_dir = Path(validation_config.get('report_dir', './validation_reports'))
        self.report_dir.mkdir(parents=True, exist_ok=True)

        self.reports: list[ValidationReport] = []

    def compare_results(self,
                        qlib_result: Dict,
                        polars_result: Dict,
                        expressions: Dict = None) -> Dict:
        """对比两个引擎的结果"""

        summary = {
            "total_stages": 5,
            "passed_stages": 0,
            "failed_stages": [],
            "reports": []
        }

        # Stage 1: 因子值对比
        if 'factors' in qlib_result and 'factors' in polars_result:
            report = self._compare_factors(
                qlib_result['factors'],
                polars_result['factors']
            )
            self.reports.append(report)
            summary['reports'].append(asdict(report))
            if report.passed:
                summary['passed_stages'] += 1
            else:
                summary['failed_stages'].append('factors')

        # Stage 2: 信号值对比
        if 'signals' in qlib_result and 'signals' in polars_result:
            report = self._compare_signals(
                qlib_result['signals'],
                polars_result['signals']
            )
            self.reports.append(report)
            summary['reports'].append(asdict(report))
            if report.passed:
                summary['passed_stages'] += 1
            else:
                summary['failed_stages'].append('signals')

        # Stage 3: 收益序列对比
        if 'returns' in qlib_result and 'returns' in polars_result:
            report = self._compare_returns(
                qlib_result['returns'],
                polars_result['returns']
            )
            self.reports.append(report)
            summary['reports'].append(asdict(report))
            if report.passed:
                summary['passed_stages'] += 1
            else:
                summary['failed_stages'].append('returns')

        # Stage 4: IC 指标对比
        if 'metrics' in qlib_result and 'metrics' in polars_result:
            report = self._compare_metrics(
                qlib_result['metrics'],
                polars_result['metrics']
            )
            self.reports.append(report)
            summary['reports'].append(asdict(report))
            if report.passed:
                summary['passed_stages'] += 1
            else:
                summary['failed_stages'].append('metrics')

        # Stage 5: 累计收益对比
        if 'cumulative_returns' in qlib_result and 'cumulative_returns' in polars_result:
            report = self._compare_cumulative_returns(
                qlib_result['cumulative_returns'],
                polars_result['cumulative_returns']
            )
            self.reports.append(report)
            summary['reports'].append(asdict(report))
            if report.passed:
                summary['passed_stages'] += 1
            else:
                summary['failed_stages'].append('cumulative_returns')

        summary['all_passed'] = summary['passed_stages'] == summary['total_stages']

        return summary

    def _compare_factors(self,
                         qlib_factors: pd.DataFrame,
                         polars_factors: pl.DataFrame) -> ValidationReport:
        """对比因子值"""
        # 转换 Polars 到 Pandas 进行对比
        polars_pd = polars_factors.to_pandas()

        # 确保索引对齐
        qlib_sorted = qlib_factors.sort_index()
        polars_sorted = polars_pd.sort_index()

        # 计算相关系数
        correlations = []
        for col in qlib_sorted.columns:
            if col in polars_sorted.columns:
                corr = qlib_sorted[col].corr(polars_sorted[col])
                correlations.append(corr)

        mean_corr = np.mean(correlations) if correlations else 0

        # 计算差异
        diff = (qlib_sorted - polars_sorted).abs()
        mean_diff = diff.mean().mean()
        max_diff = diff.max().max()

        # 判断是否通过
        passed = mean_corr > 0.999 and max_diff < self.diff_threshold

        return ValidationReport(
            stage="factors",
            passed=passed,
            correlation=mean_corr,
            mean_diff=float(mean_diff),
            max_diff=float(max_diff),
            diff_ratio=float((diff > self.diff_threshold).sum().sum() / diff.size),
            details={
                "column_correlations": {qlib_sorted.columns[i]: correlations[i]
                                        for i in range(len(correlations))},
                "qlib_shape": qlib_sorted.shape,
                "polars_shape": polars_sorted.shape
            }
        )

    def _compare_signals(self,
                         qlib_signals: pd.Series,
                         polars_signals: pl.Series) -> ValidationReport:
        """对比信号值"""
        polars_pd = polars_signals.to_pandas()

        # 相关系数
        correlation = qlib_signals.corr(polars_pd)

        # 差异
        diff = (qlib_signals - polars_pd).abs()
        mean_diff = diff.mean()
        max_diff = diff.max()

        passed = correlation > 0.999 and max_diff < self.diff_threshold

        return ValidationReport(
            stage="signals",
            passed=passed,
            correlation=float(correlation),
            mean_diff=float(mean_diff),
            max_diff=float(max_diff),
            diff_ratio=float((diff > self.diff_threshold).sum() / len(diff)),
            details={
                "qlib_len": len(qlib_signals),
                "polars_len": len(polars_pd)
            }
        )

    def _compare_returns(self,
                         qlib_returns: pd.Series,
                         polars_returns: pl.Series) -> ValidationReport:
        """对比收益序列"""
        polars_pd = polars_returns.to_pandas()

        correlation = qlib_returns.corr(polars_pd)
        diff = (qlib_returns - polars_pd).abs()
        mean_diff = diff.mean()
        max_diff = diff.max()

        passed = correlation > 0.98 and max_diff < 0.001

        return ValidationReport(
            stage="returns",
            passed=passed,
            correlation=float(correlation),
            mean_diff=float(mean_diff),
            max_diff=float(max_diff),
            diff_ratio=float((diff > 0.001).sum() / len(diff)),
            details={
                "qlib_mean_return": float(qlib_returns.mean()),
                "polars_mean_return": float(polars_pd.mean()),
                "qlib_std": float(qlib_returns.std()),
                "polars_std": float(polars_pd.std())
            }
        )

    def _compare_metrics(self,
                         qlib_metrics: Dict,
                         polars_metrics: Dict) -> ValidationReport:
        """对比评估指标"""
        diff_details = {}
        max_diff = 0

        for key in ['IC', 'ICIR', 'Rank IC', 'Rank ICIR', 'annualized_return',
                    'information_ratio', 'max_drawdown', 'calmar_ratio']:
            qlib_val = qlib_metrics.get(key)
            polars_val = polars_metrics.get(key)

            if qlib_val is not None and polars_val is not None:
                diff = abs(qlib_val - polars_val)
                max_diff = max(max_diff, diff)
                diff_details[key] = {
                    "qlib": qlib_val,
                    "polars": polars_val,
                    "diff": diff
                }

        # IC 相关指标要求更高精度
        ic_passed = True
        if 'IC' in diff_details:
            ic_passed = diff_details['IC']['diff'] < 0.001

        passed = max_diff < 0.01 and ic_passed

        return ValidationReport(
            stage="metrics",
            passed=passed,
            correlation=None,
            mean_diff=None,
            max_diff=max_diff,
            diff_ratio=None,
            details=diff_details
        )

    def _compare_cumulative_returns(self,
                                    qlib_cum: pd.Series,
                                    polars_cum: pl.Series) -> ValidationReport:
        """对比累计收益"""
        polars_pd = polars_cum.to_pandas()

        correlation = qlib_cum.corr(polars_pd)
        diff = (qlib_cum - polars_pd).abs()
        mean_diff = diff.mean()
        max_diff = diff.max()

        # 累计收益差异容忍度稍高
        passed = correlation > 0.99 and max_diff < 0.01

        return ValidationReport(
            stage="cumulative_returns",
            passed=passed,
            correlation=float(correlation),
            mean_diff=float(mean_diff),
            max_diff=float(max_diff),
            diff_ratio=float((diff > 0.01).sum() / len(diff)),
            details={
                "qlib_final": float(qlib_cum.iloc[-1]),
                "polars_final": float(polars_pd.iloc[-1])
            }
        )

    def save_report(self, summary: Dict, filename: str = None):
        """保存验证报告"""
        if filename is None:
            from datetime import datetime
            filename = f"validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        report_path = self.report_dir / filename

        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2, default=str)

        logger.info(f"Validation report saved: {report_path}")

        # 打印摘要
        self._print_summary(summary)

    def _print_summary(self, summary: Dict):
        """打印验证摘要"""
        print("\n" + "="*60)
        print("VALIDATION SUMMARY")
        print("="*60)
        print(f"Passed: {summary['passed_stages']}/{summary['total_stages']}")

        if summary['failed_stages']:
            print(f"Failed stages: {summary['failed_stages']}")
        else:
            print("All stages passed!")

        print("="*60)
```

### 3.4 数据格式映射

#### 3.4.1 列名映射规范

| Qlib 列名 | Parquet 列名 | 数据类型 | 说明 |
|----------|-------------|---------|------|
| $open | open | Float64 | 开盘价 |
| $close | close | Float64 | 收盘价 |
| $high | high | Float64 | 最高价 |
| $low | low | Float64 | 最低价 |
| $volume | vol/volume | Float64 | 成交量 |
| $amount | amount | Float64 | 成交额 |
| $factor | adj_factor | Float64 | 复权因子 |
| instrument | ts_code | String | 股票代码 |
| datetime | trade_date | Date/DateTime | 交易日期 |

#### 3.4.2 索引映射

| 维度 | Qlib 索引 | Polars 列 | 说明 |
|-----|----------|----------|------|
| 时间 | datetime (level 0) | trade_date | MultiIndex 第一层 |
| 股票 | instrument (level 1) | ts_code | MultiIndex 第二层 |

### 3.5 函数映射：Pandas → Polars

#### 3.5.1 核心函数对照表

| 操作 | Pandas (function_lib.py) | Polars 实现 |
|-----|--------------------------|------------|
| 时序均值 | `df.groupby('instrument').transform(lambda x: x.rolling(p).mean())` | `col.rolling_mean(p).over('ts_code')` |
| 时序标准差 | `df.groupby('instrument').transform(lambda x: x.rolling(p).std())` | `col.rolling_std(p).over('ts_code')` |
| 截面排名 | `df.groupby('datetime').rank(pct=True)` | `col.rank().over('trade_date') / col.count().over('trade_date')` |
| 截面均值 | `df.groupby('datetime').transform('mean')` | `col.mean().over('trade_date')` |
| 时序相关 | `df.groupby('instrument').apply(lambda x: x.rolling(p).corr(y))` | `pl.rolling_corr(a, b, p).over('ts_code')` |
| 时序差分 | `df.groupby('instrument').transform(lambda x: x.diff(p))` | `col.diff(p).over('ts_code')` |
| 时序延迟 | `df.groupby('instrument').transform(lambda x: x.shift(p))` | `col.shift(p).over('ts_code')` |

---

## 四、实施步骤

### 4.1 实施路线图

```
┌────────────────────────────────────────────────────────────────────┐
│                        实施时间线 (5周)                              │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Week 1          Week 2          Week 3          Week 4     Week 5│
│  ├─ 基础设施      ├─ 核心开发      ├─ 验证机制      ├─ 集成    ├─上线│
│  │                │                │                │          │    │
│  ├─ 数据层        ├─ Function Lib  ├─ Validator    ├─ 端到端  ├─灰度│
│  ├─ 数据加载器     ├─ 表达式编译器   ├─ 对比报告     ├─ 性能测试├─监控│
│  └─ 格式转换      └─ 双引擎路由     └─ 中间产物保存  └─ 一致性  └─文档│
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
- [ ] 保持与 Qlib 数据输出格式兼容

关键代码结构：

```python
# quantaalpha/backtest/polars_data_loader.py
import polars as pl
from pathlib import Path
from typing import Optional, Dict, List

class PolarsDataLoader:
    """Parquet 数据加载器 (与 Qlib 格式兼容)"""

    # 列名映射：Parquet -> Qlib
    COLUMN_MAPPING = {
        "open": "$open",
        "close": "$close",
        "high": "$high",
        "low": "$low",
        "vol": "$volume",
        "volume": "$volume",
        "amount": "$amount",
        "ts_code": "instrument",
        "trade_date": "datetime"
    }

    def __init__(self, data_path: str, config: Dict = None):
        self.data_path = Path(data_path)
        self.config = config or {}
        self._lazy_df: Optional[pl.LazyFrame] = None

    def load(self,
             start_date: str = None,
             end_date: str = None,
             instruments: List[str] = None,
             columns: List[str] = None) -> pl.LazyFrame:
        """惰性加载数据，返回 LazyFrame"""
        if self._lazy_df is None:
            self._lazy_df = self._scan_parquet_files()

        df = self._lazy_df

        # 日期过滤
        if start_date:
            df = df.filter(pl.col("trade_date") >= start_date)
        if end_date:
            df = df.filter(pl.col("trade_date") <= end_date)

        # 股票过滤
        if instruments:
            df = df.filter(pl.col("ts_code").is_in(instruments))

        # 列选择
        if columns:
            # 支持 Qlib 风格列名
            parquet_cols = [self._reverse_map_col(c) for c in columns]
            df = df.select(parquet_cols)

        return self._normalize_columns(df)

    def load_as_pandas(self, **kwargs) -> 'pd.DataFrame':
        """加载为 Pandas DataFrame (兼容 Qlib 格式)"""
        lf = self.load(**kwargs)
        pdf = lf.collect().to_pandas()

        # 设置 MultiIndex (datetime, instrument)
        pdf = pdf.set_index(['datetime', 'instrument'])
        return pdf.sort_index()

    def _scan_parquet_files(self) -> pl.LazyFrame:
        """扫描 Parquet 文件"""
        if self.data_path.is_file():
            return pl.scan_parquet(self.data_path)
        else:
            # 支持目录下的分区文件
            return pl.scan_parquet(f"{self.data_path}/**/*.parquet")

    def _normalize_columns(self, df: pl.LazyFrame) -> pl.LazyFrame:
        """列名标准化为 Qlib 风格"""
        rename_map = {}
        for old, new in self.COLUMN_MAPPING.items():
            if old in df.columns:
                rename_map[old] = new

        if rename_map:
            df = df.rename(rename_map)
        return df

    def _reverse_map_col(self, qlib_col: str) -> str:
        """Qlib 列名 -> Parquet 列名"""
        reverse_map = {v: k for k, v in self.COLUMN_MAPPING.items()}
        return reverse_map.get(qlib_col, qlib_col)

    def validate_against_qlib(self, qlib_df: 'pd.DataFrame') -> Dict:
        """与 Qlib 数据对比验证"""
        polars_df = self.load_as_pandas()

        # 对齐索引
        common_index = qlib_df.index.intersection(polars_df.index)

        results = {
            "qlib_rows": len(qlib_df),
            "polars_rows": len(polars_df),
            "common_rows": len(common_index),
            "column_diff": list(set(qlib_df.columns) - set(polars_df.columns))
        }

        # 数值对比
        for col in qlib_df.columns:
            if col in polars_df.columns:
                qlib_vals = qlib_df.loc[common_index, col]
                polars_vals = polars_df.loc[common_index, col]
                corr = qlib_vals.corr(polars_vals)
                results[f"{col}_correlation"] = corr

        return results
```

**Day 3-4: 数据格式转换工具**

任务清单：
- [ ] 开发 HDF5 → Parquet 转换脚本
- [ ] 实现数据校验逻辑
- [ ] 批量转换现有数据
- [ ] 验证转换后数据一致性

```python
# tools/convert_h5_to_parquet.py
import polars as pl
import pandas as pd
import tables
from pathlib import Path
from typing import Dict
import logging

logger = logging.getLogger(__name__)

def convert_qlib_to_parquet(qlib_data_path: str,
                            output_path: str,
                            validate: bool = True) -> Dict:
    """将 Qlib HDF5 数据转换为 Parquet 格式"""

    qlib_path = Path(qlib_data_path)
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    report = {
        "source": str(qlib_path),
        "output": str(output_path),
        "files_converted": 0,
        "validation_results": []
    }

    # 查找所有 .data 文件 (Qlib 格式)
    data_files = list(qlib_path.rglob("*.data"))

    for data_file in data_files:
        try:
            # 读取 Qlib 数据
            with tables.open_file(str(data_file), 'r') as f:
                # ... 解析 Qlib 数据格式

                # 转换为 Polars
                df = pl.DataFrame({
                    'ts_code': instrument_col,
                    'trade_date': datetime_col,
                    'open': open_col,
                    'close': close_col,
                    # ... 其他列
                })

                # 写入 Parquet
                output_file = output_path / f"{data_file.stem}.parquet"
                df.write_parquet(output_file, compression='snappy')

                report["files_converted"] += 1
                logger.info(f"Converted: {data_file} -> {output_file}")

        except Exception as e:
            logger.error(f"Failed to convert {data_file}: {e}")

    # 验证
    if validate:
        validation = validate_conversion(qlib_data_path, str(output_path))
        report["validation_results"] = validation

    return report
```

**Day 5: 引擎路由基础**

任务清单：
- [ ] 创建 `BacktestEngineRouter` 类
- [ ] 实现配置解析
- [ ] 单元测试：路由逻辑

**Week 1 验收标准 (CP1)**

| 验收项 | 验收标准 | 验证方法 |
|-------|---------|---------|
| 数据加载器 | 1. 能正确读取 Parquet 文件<br>2. 列名映射正确<br>3. 日期过滤有效 | 单元测试覆盖 100% |
| 数据一致性 | 1. 与 Qlib 加载的数据行数一致<br>2. 关键列数值差异 < 1e-10<br>3. 索引对齐正确 | 对比测试：同一段日期数据，Qlib vs Polars |
| 性能基准 | 1. 数据加载速度提升 > 3x<br>2. 内存占用降低 > 30% | 性能测试：1年/5年数据加载对比 |
| 代码质量 | 1. 单元测试通过率 100%<br>2. 代码覆盖率 > 80%<br>3. 无 P0/P1 级别 Bug | CI 流水线检查 |

**交付物清单**
- [ ] `PolarsDataLoader` 类及单元测试
- [ ] HDF5 → Parquet 转换脚本
- [ ] 数据一致性验证报告
- [ ] 性能基准测试报告
- [ ] `BacktestEngineRouter` 基础框架

---

#### 4.2.2 Week 2: 核心计算层开发

**Day 6-8: Polars Function Lib**

任务清单：
- [ ] 实现所有时序函数 (ts_mean, ts_std, ts_corr, ts_rank, ts_delta, ts_delay 等)
- [ ] 实现所有截面函数 (cs_rank, cs_mean, cs_zscore, cs_std 等)
- [ ] 实现数学运算函数 (abs, sign, log, exp, sqrt 等)
- [ ] 实现逻辑运算函数 (where, and, or, gt, lt 等)
- [ ] 确保与 function_lib.py 输出格式一致

关键代码结构：

```python
# quantaalpha/factors/coder/polars_function_lib.py
import polars as pl
from typing import Union

# ============================================================
# 时序函数 (Time-Series Functions)
# ============================================================

def ts_mean(expr: pl.Expr, window: int) -> pl.Expr:
    """时序均值 - 对应 Pandas: TS_MEAN"""
    return expr.rolling_mean(window_size=window, min_periods=1).over("ts_code")

def ts_std(expr: pl.Expr, window: int) -> pl.Expr:
    """时序标准差 - 对应 Pandas: TS_STD"""
    return expr.rolling_std(window_size=window, min_periods=1).over("ts_code")

def ts_sum(expr: pl.Expr, window: int) -> pl.Expr:
    """时序求和 - 对应 Pandas: TS_SUM"""
    return expr.rolling_sum(window_size=window, min_periods=1).over("ts_code")

def ts_max(expr: pl.Expr, window: int) -> pl.Expr:
    """时序最大值 - 对应 Pandas: TS_MAX"""
    return expr.rolling_max(window_size=window, min_periods=1).over("ts_code")

def ts_min(expr: pl.Expr, window: int) -> pl.Expr:
    """时序最小值 - 对应 Pandas: TS_MIN"""
    return expr.rolling_min(window_size=window, min_periods=1).over("ts_code")

def ts_rank(expr: pl.Expr, window: int) -> pl.Expr:
    """时序排名 - 对应 Pandas: TS_RANK"""
    return expr.rolling_map(
        lambda s: s.rank(pct=True).iloc[-1] if len(s) > 0 else None,
        window_size=window
    ).over("ts_code")

def ts_corr(a: pl.Expr, b: pl.Expr, window: int) -> pl.Expr:
    """时序相关系数 - 对应 Pandas: TS_CORR"""
    return pl.rolling_corr(a, b, window_size=window, min_periods=2).over("ts_code")

def ts_cov(a: pl.Expr, b: pl.Expr, window: int) -> pl.Expr:
    """时序协方差 - 对应 Pandas: TS_COVARIANCE"""
    return pl.rolling_cov(a, b, window_size=window, min_periods=2).over("ts_code")

def ts_delta(expr: pl.Expr, period: int = 1) -> pl.Expr:
    """时序差分 - 对应 Pandas: DELTA"""
    return expr.diff(n=period).over("ts_code")

def ts_delay(expr: pl.Expr, period: int = 1) -> pl.Expr:
    """时序延迟 - 对应 Pandas: DELAY"""
    return expr.shift(n=period).over("ts_code")

def ts_zscore(expr: pl.Expr, window: int) -> pl.Expr:
    """时序标准化 - 对应 Pandas: TS_ZSCORE"""
    mean = expr.rolling_mean(window_size=window, min_periods=1).over("ts_code")
    std = expr.rolling_std(window_size=window, min_periods=1).over("ts_code")
    return (expr - mean) / std

def ts_argmax(expr: pl.Expr, window: int) -> pl.Expr:
    """最大值位置 - 对应 Pandas: TS_ARGMAX"""
    return expr.rolling_map(
        lambda s: len(s) - s.arg_max() - 1 if len(s) > 0 else None,
        window_size=window
    ).over("ts_code")

def ts_argmin(expr: pl.Expr, window: int) -> pl.Expr:
    """最小值位置 - 对应 Pandas: TS_ARGMIN"""
    return expr.rolling_map(
        lambda s: len(s) - s.arg_min() - 1 if len(s) > 0 else None,
        window_size=window
    ).over("ts_code")

# ============================================================
# 截面函数 (Cross-Sectional Functions)
# ============================================================

def cs_rank(expr: pl.Expr) -> pl.Expr:
    """截面排名 (百分位) - 对应 Pandas: RANK"""
    return expr.rank(method="average").over("trade_date") / \
           expr.count().over("trade_date")

def cs_mean(expr: pl.Expr) -> pl.Expr:
    """截面均值 - 对应 Pandas: MEAN"""
    return expr.mean().over("trade_date")

def cs_std(expr: pl.Expr) -> pl.Expr:
    """截面标准差 - 对应 Pandas: STD"""
    return expr.std().over("trade_date")

def cs_zscore(expr: pl.Expr) -> pl.Expr:
    """截面标准化 - 对应 Pandas: ZSCORE"""
    mean = expr.mean().over("trade_date")
    std = expr.std().over("trade_date")
    return (expr - mean) / std

def cs_max(expr: pl.Expr) -> pl.Expr:
    """截面最大值 - 对应 Pandas: MAX (cross-sectional)"""
    return expr.max().over("trade_date")

def cs_min(expr: pl.Expr) -> pl.Expr:
    """截面最小值 - 对应 Pandas: MIN (cross-sectional)"""
    return expr.min().over("trade_date")

def cs_median(expr: pl.Expr) -> pl.Expr:
    """截面中位数 - 对应 Pandas: MEDIAN"""
    return expr.median().over("trade_date")

# ============================================================
# 数学函数 (Math Functions)
# ============================================================

def abs_(expr: pl.Expr) -> pl.Expr:
    """绝对值 - 对应 Pandas: ABS"""
    return expr.abs()

def sign(expr: pl.Expr) -> pl.Expr:
    """符号函数 - 对应 Pandas: SIGN"""
    return expr.sign()

def log(expr: pl.Expr) -> pl.Expr:
    """自然对数 - 对应 Pandas: LOG"""
    return (expr + 1).log()

def exp(expr: pl.Expr) -> pl.Expr:
    """指数函数 - 对应 Pandas: EXP"""
    return expr.exp()

def sqrt(expr: pl.Expr) -> pl.Expr:
    """平方根 - 对应 Pandas: SQRT"""
    return expr.sqrt()

def power(expr: pl.Expr, n: Union[int, float]) -> pl.Expr:
    """幂函数 - 对应 Pandas: POW"""
    return expr.pow(n)

# ============================================================
# 逻辑函数 (Logic Functions)
# ============================================================

def where(condition: pl.Expr, true_val: pl.Expr, false_val: pl.Expr) -> pl.Expr:
    """条件选择 - 对应 Pandas: WHERE"""
    return pl.when(condition).then(true_val).otherwise(false_val)

def and_(a: pl.Expr, b: pl.Expr) -> pl.Expr:
    """逻辑与 - 对应 Pandas: AND"""
    return a & b

def or_(a: pl.Expr, b: pl.Expr) -> pl.Expr:
    """逻辑或 - 对应 Pandas: OR"""
    return a | b

def gt(a: pl.Expr, b: pl.Expr) -> pl.Expr:
    """大于 - 对应 Pandas: GT"""
    return a > b

def lt(a: pl.Expr, b: pl.Expr) -> pl.Expr:
    """小于 - 对应 Pandas: LT"""
    return a < b

def ge(a: pl.Expr, b: pl.Expr) -> pl.Expr:
    """大于等于 - 对应 Pandas: GE"""
    return a >= b

def le(a: pl.Expr, b: pl.Expr) -> pl.Expr:
    """小于等于 - 对应 Pandas: LE"""
    return a <= b

def eq(a: pl.Expr, b: pl.Expr) -> pl.Expr:
    """等于 - 对应 Pandas: EQ"""
    return a == b

def ne(a: pl.Expr, b: pl.Expr) -> pl.Expr:
    """不等于 - 对应 Pandas: NE"""
    return a != b
```

**Day 9-10: 表达式编译器扩展**

任务清单：
- [ ] 扩展 `expr_parser.py` 支持 Polars 后端
- [ ] 实现 AST → Polars Expression 转换
- [ ] 保持与 Pandas 后端 API 兼容
- [ ] 支持嵌套表达式和复杂运算

```python
# quantaalpha/factors/coder/expr_compiler.py
from typing import Dict, Literal, Union
import polars as pl
import pandas as pd
from . import polars_function_lib as pl_func
from . import function_lib as pd_func

BackendType = Literal["pandas", "polars"]

class ExpressionCompiler:
    """表达式编译器：支持 Pandas 和 Polars 双后端"""

    def __init__(self, backend: BackendType = "pandas"):
        self.backend = backend
        self._func_map = self._build_func_map()

    def _build_func_map(self) -> Dict:
        """构建函数映射表"""
        if self.backend == "polars":
            return {
                # 时序函数
                "TS_MEAN": pl_func.ts_mean,
                "TS_STD": pl_func.ts_std,
                "TS_SUM": pl_func.ts_sum,
                "TS_MAX": pl_func.ts_max,
                "TS_MIN": pl_func.ts_min,
                "TS_RANK": pl_func.ts_rank,
                "TS_CORR": pl_func.ts_corr,
                "TS_COVARIANCE": pl_func.ts_cov,
                "TS_ZSCORE": pl_func.ts_zscore,
                "DELTA": pl_func.ts_delta,
                "DELAY": pl_func.ts_delay,
                "TS_ARGMAX": pl_func.ts_argmax,
                "TS_ARGMIN": pl_func.ts_argmin,

                # 截面函数
                "RANK": pl_func.cs_rank,
                "MEAN": pl_func.cs_mean,
                "STD": pl_func.cs_std,
                "ZSCORE": pl_func.cs_zscore,
                "MAX": pl_func.cs_max,
                "MIN": pl_func.cs_min,
                "MEDIAN": pl_func.cs_median,

                # 数学函数
                "ABS": pl_func.abs_,
                "SIGN": pl_func.sign,
                "LOG": pl_func.log,
                "EXP": pl_func.exp,
                "SQRT": pl_func.sqrt,
                "POW": pl_func.power,

                # 逻辑函数
                "WHERE": pl_func.where,
                "AND": pl_func.and_,
                "OR": pl_func.or_,
                "GT": pl_func.gt,
                "LT": pl_func.lt,
                "GE": pl_func.ge,
                "LE": pl_func.le,
                "EQ": pl_func.eq,
                "NE": pl_func.ne,

                # 算术运算 (使用 Polars 原生)
                "ADD": lambda a, b: a + b,
                "SUBTRACT": lambda a, b: a - b,
                "MULTIPLY": lambda a, b: a * b,
                "DIVIDE": lambda a, b: a / b,
            }
        else:
            # Pandas 后端使用原有 function_lib
            return {
                "TS_MEAN": pd_func.TS_MEAN,
                "TS_STD": pd_func.TS_STD,
                # ... 映射所有函数
                "ADD": pd_func.ADD,
                "SUBTRACT": pd_func.SUBTRACT,
                "MULTIPLY": pd_func.MULTIPLY,
                "DIVIDE": pd_func.DIVIDE,
            }

    def compile(self, parsed_expr: str, df: Union[pd.DataFrame, pl.DataFrame]):
        """编译并执行表达式"""
        # 解析后的表达式是函数调用字符串
        # 如: "TS_CORR(RANK($open), RANK($volume), 10)"

        # 获取数据列
        if self.backend == "polars":
            return self._compile_polars(parsed_expr, df)
        else:
            return self._compile_pandas(parsed_expr, df)

    def _compile_polars(self, expr_str: str, df: pl.DataFrame) -> pl.Expr:
        """编译为 Polars 表达式"""
        # 将 $column 替换为 pl.col("column")
        import re
        expr_str = re.sub(r'\$(\w+)', r'pl.col("\1")', expr_str)

        # 在 eval 环境中注入函数
        eval_env = {"pl": pl, **self._func_map}

        try:
            expr = eval(expr_str, {"__builtins__": {}}, eval_env)
            return expr
        except Exception as e:
            raise ValueError(f"Failed to compile expression: {expr_str}\nError: {e}")

    def _compile_pandas(self, expr_str: str, df: pd.DataFrame):
        """编译为 Pandas 操作"""
        # 使用原有的 function_lib 执行
        eval_env = {**self._func_map, "np": __import__("numpy")}
        return eval(expr_str, {"__builtins__": {}}, eval_env)

**Week 2 验收标准 (CP2)**

| 验收项 | 验收标准 | 验证方法 |
|-------|---------|---------|
| 函数库完整性 | 1. 覆盖 Alpha158 全部 158 个因子所需函数<br>2. 每个函数有对应的 Pandas 和 Polars 实现<br>3. 函数签名与原有 function_lib 兼容 | 函数清单对比 |
| 因子计算准确性 | 1. 单因子计算：相关系数 > 0.999<br>2. 多因子组合：相关系数 > 0.999<br>3. 均值/标准差差异 < 0.1% | 100 个代表性因子对比测试 |
| 表达式编译器 | 1. 支持所有 Alpha158 表达式<br>2. AST → Polars 转换正确<br>3. 编译速度 < 100ms/表达式 | 表达式测试集覆盖 |
| 性能基准 | 1. 单因子计算速度提升 > 5x<br>2. Alpha158 全套计算 < 30s | 性能对比测试 |
| 代码质量 | 1. 单元测试通过率 100%<br>2. 函数覆盖率 > 90% | CI 检查 |

**交付物清单**
- [ ] `polars_function_lib.py` 及完整单元测试
- [ ] `ExpressionCompiler` 双后端实现
- [ ] 因子计算准确性验证报告
- [ ] 性能基准测试报告
- [ ] 函数使用文档

---

#### 4.2.3 Week 3: 验证机制开发

**Day 11-13: 验证器开发**

任务清单：
- [ ] 实现 `BacktestValidator` 类
- [ ] 实现数据加载对比验证
- [ ] 实现因子计算对比验证
- [ ] 实现信号生成对比验证
- [ ] 实现收益计算对比验证
- [ ] 实现指标计算对比验证
- [ ] 生成差异报告

**Day 14-15: 中间产物保存与对比**

任务清单：
- [ ] 实现中间产物持久化机制
- [ ] 支持分阶段保存因子值、信号、收益等
- [ ] 实现差异可视化输出

```python
# quantaalpha/backtest/intermediate_saver.py
import polars as pl
import pandas as pd
from pathlib import Path
from typing import Dict, Any, Union
import json
import logging

logger = logging.getLogger(__name__)

class IntermediateSaver:
    """中间产物保存器"""

    def __init__(self, save_dir: str, engine_type: str):
        self.save_dir = Path(save_dir)
        self.engine_type = engine_type
        self.save_dir.mkdir(parents=True, exist_ok=True)

    def save_stage(self, stage_name: str, data: Any, metadata: Dict = None):
        """保存某一阶段的中间产物"""
        stage_dir = self.save_dir / stage_name
        stage_dir.mkdir(exist_ok=True)

        if isinstance(data, pl.DataFrame):
            data.write_parquet(stage_dir / f"{self.engine_type}_data.parquet")
        elif isinstance(data, pd.DataFrame):
            data.to_parquet(stage_dir / f"{self.engine_type}_data.parquet")
        elif isinstance(data, (pd.Series, pl.Series)):
            if isinstance(data, pl.Series):
                data.to_frame().write_parquet(stage_dir / f"{self.engine_type}_series.parquet")
            else:
                data.to_frame().to_parquet(stage_dir / f"{self.engine_type}_series.parquet")
        else:
            # 字典或其他类型
            with open(stage_dir / f"{self.engine_type}_data.json", 'w') as f:
                json.dump(data, f, default=str, indent=2)

        if metadata:
            with open(stage_dir / f"{self.engine_type}_metadata.json", 'w') as f:
                json.dump(metadata, f, default=str, indent=2)

        logger.info(f"Saved intermediate: {stage_name} ({self.engine_type})")

    def load_stage(self, stage_name: str) -> Any:
        """加载某一阶段的中间产物"""
        stage_dir = self.save_dir / stage_name

        parquet_file = stage_dir / f"{self.engine_type}_data.parquet"
        json_file = stage_dir / f"{self.engine_type}_data.json"

        if parquet_file.exists():
            if self.engine_type == "polars":
                return pl.read_parquet(parquet_file)
            else:
                return pd.read_parquet(parquet_file)
        elif json_file.exists():
            with open(json_file, 'r') as f:
                return json.load(f)

        return None

**Week 3 验收标准 (CP3)**

| 验收项 | 验收标准 | 验证方法 |
|-------|---------|---------|
| 验证器功能 | 1. 支持 5 个阶段验证（数据/因子/信号/收益/指标）<br>2. 每个阶段生成详细差异报告<br>3. 差异可视化输出 | 全流程验证测试 |
| 中间产物保存 | 1. 支持 Parquet/JSON 格式<br>2. 元数据完整（时间戳、版本、配置）<br>3. 加载功能正常 | 读写测试 |
| 验证准确性 | 1. 能正确识别差异<br>2. 误报率 < 1%<br>3. 漏报率 = 0% | 注入已知差异测试 |
| 报告质量 | 1. 报告包含：差异统计、样本对比、可视化图表<br>2. 报告可读性良好 | 人工评审 |
| 性能 | 验证过程耗时 < 总回测时间的 10% | 性能测试 |

**交付物清单**
- [ ] `BacktestValidator` 完整实现
- [ ] `IntermediateSaver` 中间产物管理
- [ ] 验证报告模板和示例
- [ ] 差异可视化组件
- [ ] 验证器使用文档

---

#### 4.2.4 Week 4: 集成测试

**Day 16-17: 端到端测试**

任务清单：
- [ ] 双引擎端到端流程测试
- [ ] 验证全流程一致性
- [ ] 边界情况处理

**Day 18-19: 性能基准测试**

任务清单：
- [ ] 数据加载性能对比
- [ ] 因子计算性能对比
- [ ] 回测执行性能对比
- [ ] 内存使用对比

**Day 20: 集成完成**

任务清单：
- [ ] 完成所有单元测试
- [ ] 完成集成测试
- [ ] 更新配置文件模板

**Week 4 验收标准 (CP4)**

| 验收项 | 验收标准 | 验证方法 |
|-------|---------|---------|
| 端到端一致性 | 1. 完整回测流程：数据→因子→信号→收益→指标<br>2. 日收益率相关系数 > 0.98<br>3. 累计收益差异 < 1%<br>4. IC 差异 < 0.001 | 10 个典型因子全流程测试 |
| 风险指标一致性 | 1. IR 差异 < 5%<br>2. 最大回撤差异 < 5%<br>3. 夏普比率差异 < 5% | 风险指标对比 |
| 性能达标 | 1. 回测速度提升 > 5x<br>2. 内存占用降低 > 40%<br>3. 单因子回测 < 10s | 性能基准测试 |
| 边界情况 | 1. 空数据/缺失值处理正确<br>2. 单股票/少股票场景正常<br>3. 极端行情（涨跌停）处理正确 | 边界测试用例 |
| 稳定性 | 1. 连续运行 100 次无错误<br>2. 内存无泄漏 | 稳定性测试 |

**交付物清单**
- [ ] 端到端测试报告
- [ ] 性能基准测试报告
- [ ] 一致性验证报告
- [ ] 边界测试报告
- [ ] 配置文件模板
- [ ] 集成测试通过证明

---

#### 4.2.5 Week 5: 上线准备

**Day 21-22: 文档与培训**

任务清单：
- [ ] 更新用户文档
- [ ] 编写配置指南
- [ ] 编写迁移指南

**Day 23-24: 灰度发布**

任务清单：
- [ ] 配置开关验证
- [ ] 小范围测试
- [ ] 监控告警配置

**Day 25: 正式上线**

任务清单：
- [ ] 全量发布
- [ ] 监控运行状态
- [ ] 问题快速响应机制

**Week 5 验收标准 (CP5)**

| 验收项 | 验收标准 | 验证方法 |
|-------|---------|---------|
| 文档完整性 | 1. 用户文档更新完成<br>2. 配置指南完整<br>3. 迁移指南清晰 | 文档评审 |
| 灰度发布 | 1. 配置开关工作正常<br>2. 小范围测试通过率 100%<br>3. 监控告警配置完成 | 灰度测试报告 |
| 生产稳定性 | 1. 连续运行 7 天无 P0/P1 故障<br>2. 错误率 < 0.1%<br>3. 性能指标达标 | 生产监控 |
| 回滚能力 | 1. 能在 5 分钟内切换回 Qlib 引擎<br>2. 回滚过程数据不丢失 | 回滚演练 |
| 用户反馈 | 1. 无重大功能投诉<br>2. 性能满意度 > 90% | 用户调研 |

**交付物清单**
- [ ] 用户操作手册
- [ ] 配置指南
- [ ] 迁移指南
- [ ] 灰度测试报告
- [ ] 上线检查清单
- [ ] 回滚操作手册
- [ ] 监控告警配置
- [ ] 问题响应流程

---

### 4.3 关键检查点

| 检查点 | 时间 | 验收标准 |
|-------|------|---------|
| CP1 | Week 1 结束 | 双数据加载器通过单元测试，数据一致性验证通过 |
| CP2 | Week 2 结束 | Polars 函数库完成，因子计算相关系数 > 0.999 |
| CP3 | Week 3 结束 | 验证机制完成，中间产物对比差异 < 阈值 |
| CP4 | Week 4 结束 | 端到端测试通过，IC 相关系数 > 0.99 |
| CP5 | Week 5 结束 | 生产环境灰度发布，无重大异常 |

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

### 5.2 一致性验证标准

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
- 最大差异 < 1e-6
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
- IC 差异 < 0.001
```

### 5.3 业务价值

| 价值维度 | 具体收益 |
|---------|---------|
| **效率提升** | 因子迭代周期从小时级缩短到分钟级 |
| **成本降低** | 计算资源需求减少 50-60% |
| **能力扩展** | 支持更大规模数据 (全市场 10 年历史) |
| **风险控制** | 双引擎验证机制确保结果准确性 |
| **维护简化** | 逐步降低 Qlib 依赖，减少技术债务 |

---

## 六、关键实现优化建议

### 6.1 函数实现优化

#### 6.1.1 ts_rank 性能优化

**问题**：使用 `rolling_map` + Python lambda 会触发 Python GIL，影响性能。

**优化方案**：使用纯 Polars 原生表达式实现

```python
# 优化前（性能较差）
def ts_rank(expr: pl.Expr, window: int) -> pl.Expr:
    return expr.rolling_map(
        lambda s: s.rank(pct=True).iloc[-1] if len(s) > 0 else None,
        window_size=window
    ).over("ts_code")

# 优化后（纯 Polars 实现）
def ts_rank(expr: pl.Expr, window: int) -> pl.Expr:
    """时序排名 - 纯 Polars 实现，避免 Python 回调"""
    return expr.rolling(
        index_column="trade_date",
        period=f"{window}d"
    ).agg(
        (pl.col("value").rank() / pl.col("value").count()).last()
    )
```

#### 6.1.2 其他需要优化的函数

| 函数 | 优化前 | 优化后 | 预期提升 |
|-----|--------|--------|---------|
| `ts_argmax` | `rolling_map` + lambda | 使用 `arg_max()` 原生方法 | 3-5x |
| `ts_argmin` | `rolling_map` + lambda | 使用 `arg_min()` 原生方法 | 3-5x |
| `ts_skew` | `scipy.stats.skew` | Polars 内置 `skew()` | 2-3x |
| `ts_kurt` | `scipy.stats.kurtosis` | Polars 内置 `kurtosis()` | 2-3x |

### 6.2 表达式编译器优化

#### 6.2.1 避免使用 eval()

**问题**：文档中的 `eval()` 方式存在安全隐患且不够健壮

```python
# 不推荐：存在安全隐患
def _compile_polars(self, expr_str: str, df: pl.DataFrame) -> pl.Expr:
    expr_str = re.sub(r'\$(\w+)', r'pl.col("\1")', expr_str)
    eval_env = {"pl": pl, **self._func_map}
    expr = eval(expr_str, {"__builtins__": {}}, eval_env)  # 安全风险
    return expr
```

**推荐方案**：基于 AST 的代码生成器

```python
# quantaalpha/factors/coder/polars_code_generator.py

class PolarsCodeGenerator:
    """AST → Polars Expression 代码生成器"""
    
    def __init__(self):
        self.func_map = self._build_func_map()
    
    def generate(self, ast_node: dict) -> pl.Expr:
        """递归生成 Polars 表达式"""
        node_type = ast_node.get('type')
        
        if node_type == 'function_call':
            return self._gen_function_call(ast_node)
        elif node_type == 'column_ref':
            return self._gen_column_ref(ast_node)
        elif node_type == 'binary_op':
            return self._gen_binary_op(ast_node)
        elif node_type == 'number':
            return pl.lit(ast_node['value'])
        else:
            raise ValueError(f"Unknown node type: {node_type}")
    
    def _gen_function_call(self, node: dict) -> pl.Expr:
        """生成函数调用表达式"""
        func_name = node['name']
        args = [self.generate(arg) for arg in node['args']]
        
        if func_name in self.func_map:
            return self.func_map[func_name](*args)
        else:
            raise ValueError(f"Unknown function: {func_name}")
    
    def _gen_column_ref(self, node: dict) -> pl.Expr:
        """生成列引用表达式"""
        col_name = node['name'].lstrip('$')  # 移除 $ 前缀
        return pl.col(col_name)
    
    def _gen_binary_op(self, node: dict) -> pl.Expr:
        """生成二元运算表达式"""
        left = self.generate(node['left'])
        right = self.generate(node['right'])
        op = node['operator']
        
        op_map = {
            '+': lambda a, b: a + b,
            '-': lambda a, b: a - b,
            '*': lambda a, b: a * b,
            '/': lambda a, b: a / b,
        }
        
        if op in op_map:
            return op_map[op](left, right)
        else:
            raise ValueError(f"Unknown operator: {op}")
```

### 6.3 数据类型一致性优化

#### 6.3.1 统一列名映射

**问题**：文档中 `ts_code` 和 `instrument` 混用，需要统一。

**解决方案**：建立标准化的列名映射规范

```python
# quantaalpha/backtest/data_schema.py

from enum import Enum
from typing import Dict

class ColumnNames(Enum):
    """标准化列名定义"""
    # 股票代码
    STOCK_CODE = "ts_code"          # 内部统一使用 ts_code
    # 日期
    TRADE_DATE = "trade_date"       # 内部统一使用 trade_date
    # 价格数据
    OPEN = "open"
    CLOSE = "close"
    HIGH = "high"
    LOW = "low"
    # 成交量
    VOLUME = "vol"

# Qlib 兼容映射（输出时使用）
QLIB_COLUMN_MAP: Dict[str, str] = {
    "ts_code": "instrument",
    "trade_date": "datetime",
    "open": "$open",
    "close": "$close",
    "high": "$high",
    "low": "$low",
    "vol": "$volume",
}

class DataTypeConverter:
    """处理 Qlib 和 Polars 之间的数据类型转换"""
    
    @staticmethod
    def to_polars(df, source_type: str = "qlib") -> pl.DataFrame:
        """转换为 Polars DataFrame"""
        if isinstance(df, pd.DataFrame):
            # 处理 Qlib 的多层索引
            if isinstance(df.index, pd.MultiIndex):
                df = df.reset_index()
            
            # 列名标准化（移除 $ 前缀）
            df.columns = [c.lstrip('$') for c in df.columns]
            
            # 重命名为内部标准列名
            reverse_map = {v: k for k, v in QLIB_COLUMN_MAP.items()}
            df = df.rename(columns=reverse_map)
            
            return pl.from_pandas(df)
        
        elif isinstance(df, pl.DataFrame):
            return df
        
        else:
            raise TypeError(f"Unsupported data type: {type(df)}")
    
    @staticmethod
    def to_qlib_format(df: pl.DataFrame) -> pd.DataFrame:
        """转换为 Qlib 格式（用于对比验证）"""
        df_pd = df.to_pandas()
        
        # 应用 Qlib 列名映射
        df_pd = df_pd.rename(columns=QLIB_COLUMN_MAP)
        
        # 设置多层索引
        if "datetime" in df_pd.columns and "instrument" in df_pd.columns:
            df_pd = df_pd.set_index(["datetime", "instrument"]).sort_index()
        
        return df_pd
```

### 6.4 验证阈值精细化

#### 6.4.1 分层验证阈值

**问题**：`diff_threshold: 1e-6` 对于金融数据可能过于严格

**优化方案**：根据数据类型设置差异化阈值

```python
# quantaalpha/backtest/validation_thresholds.py

from dataclasses import dataclass
from typing import Dict

@dataclass
class ValidationThresholds:
    """验证阈值配置"""
    
    # 因子值验证
    FACTOR_CORRELATION: float = 0.999      # 相关系数
    FACTOR_MEAN_RELATIVE_DIFF: float = 0.001  # 均值相对差异 < 0.1%
    FACTOR_STD_RELATIVE_DIFF: float = 0.001   # 标准差相对差异 < 0.1%
    FACTOR_MAX_ABS_DIFF: float = 1e-4         # 最大绝对差异
    
    # 收益率验证
    RETURN_CORRELATION: float = 0.98       # 日收益率相关系数
    RETURN_MAX_ABS_DIFF: float = 1e-4      # 日收益率最大差异
    CUM_RETURN_RELATIVE_DIFF: float = 0.01  # 累计收益相对差异 < 1%
    
    # 风险指标验证
    IC_ABS_DIFF: float = 0.001             # IC 绝对差异
    IR_RELATIVE_DIFF: float = 0.05         # IR 相对差异 < 5%
    MDD_RELATIVE_DIFF: float = 0.05        # 最大回撤相对差异 < 5%
    SHARPE_RELATIVE_DIFF: float = 0.05     # 夏普比率相对差异 < 5%
    
    # 数值精度容忍（根据数据量级调整）
    @staticmethod
    def get_precision_threshold(value_range: tuple) -> float:
        """根据数值范围返回合适的精度阈值"""
        min_val, max_val = value_range
        range_size = max_val - min_val
        
        if range_size > 1000:
            return 1e-3  # 大范围数据容忍更高绝对误差
        elif range_size > 100:
            return 1e-4
        elif range_size > 10:
            return 1e-5
        else:
            return 1e-6  # 小范围数据要求更高精度

# 使用示例
THRESHOLDS = ValidationThresholds()

# 验证因子值
def validate_factor_values(qlib_values: pd.Series, polars_values: pd.Series) -> Dict:
    correlation = qlib_values.corr(polars_values)
    mean_diff = abs(qlib_values.mean() - polars_values.mean()) / abs(qlib_values.mean())
    max_diff = (qlib_values - polars_values).abs().max()
    
    return {
        "passed": (
            correlation > THRESHOLDS.FACTOR_CORRELATION and
            mean_diff < THRESHOLDS.FACTOR_MEAN_RELATIVE_DIFF and
            max_diff < THRESHOLDS.FACTOR_MAX_ABS_DIFF
        ),
        "correlation": correlation,
        "mean_relative_diff": mean_diff,
        "max_abs_diff": max_diff,
    }
```

### 6.5 实施优先级建议

| 优先级 | 优化项 | 实施阶段 | 影响 |
|-------|--------|---------|------|
| P0 | 表达式编译器 AST 实现 | Week 2 | 安全性 + 可维护性 |
| P0 | 列名映射标准化 | Week 1 | 避免数据混乱 |
| P1 | `ts_rank` 等函数优化 | Week 2-3 | 性能提升 3-5x |
| P1 | 分层验证阈值 | Week 3 | 减少误报 |
| P2 | 数据类型转换器 | Week 2 | 代码复用性 |

---

## 七、风险与应对措施

### 7.1 技术风险

| 风险 | 概率 | 影响 | 应对措施 |
|-----|------|------|---------|
| Polars API 变更 | 中 | 高 | 封装抽象层，隔离 API 直接调用 |
| 数值精度差异 | 中 | 高 | 建立精度容忍机制，设置差异阈值；双引擎验证 |
| 内存溢出 | 低 | 高 | 实现分块处理，监控内存使用 |
| 表达式兼容性问题 | 中 | 中 | 建立表达式测试集，逐步扩展支持 |
| 双引擎结果不一致 | 中 | 高 | 中间产物验证机制，逐阶段排查 |

### 7.2 项目风险

| 风险 | 概率 | 影响 | 应对措施 |
|-----|------|------|---------|
| 工期延误 | 中 | 中 | 设置缓冲时间，优先级排序 |
| 人员变动 | 低 | 中 | 文档完善，知识共享 |
| 回滚需求 | 低 | 高 | 保留 Qlib 引擎，配置开关快速切换 |

### 7.3 风险监控机制

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
├─ 数值差异 > 阈值 → 红色告警
└─ 错误率 > 1% → 红色告警
```

---

## 八、附录

### 8.1 术语表

| 术语 | 说明 |
|-----|------|
| Qlib | 微软开源的量化投资平台 |
| Polars | 高性能 DataFrame 库 (Rust 实现) |
| Parquet | 列式存储文件格式 |
| IC | Information Coefficient，信息系数 |
| Rank IC | 排名信息系数 |
| 截面计算 | Cross-sectional，同一时间点不同股票的计算 |
| 时序计算 | Time-series，同一股票不同时间点的计算 |
| 双引擎 | Qlib 引擎和 Polars 引擎并存运行 |
| 中间产物 | 回测流程中各阶段的计算结果 |

### 8.2 参考资源

- Polars 官方文档: https://docs.pola.rs/
- Parquet 格式规范: https://parquet.apache.org/
- QuantaAlpha 仓库: https://github.com/QuantaAlpha/QuantaAlpha
- Qlib 文档: https://qlib.readthedocs.io/

### 8.3 相关文件清单

```
新增文件：
├── quantaalpha/backtest/
│   ├── engine_router.py              # 引擎路由器
│   ├── polars_data_loader.py         # Polars 数据加载器
│   ├── polars_runner.py              # Polars 回测引擎
│   ├── polars_factor_calculator.py   # Polars 因子计算器
│   ├── validator.py                  # 结果验证器
│   └── intermediate_saver.py         # 中间产物保存器
├── quantaalpha/factors/coder/
│   ├── polars_function_lib.py        # Polars 函数库
│   └── expr_compiler.py              # 表达式编译器 (双后端)
└── tools/
    └── convert_h5_to_parquet.py      # 数据转换工具

修改文件：
├── quantaalpha/backtest/runner.py         # 保留原实现
├── quantaalpha/factors/coder/expr_parser.py # 适配双后端
├── quantaalpha/factors/coder/function_lib.py # 保留原实现
└── configs/backtest.yaml                  # 增加引擎选择配置

### 8.4 新增优化相关文件（第六章）

```
新增优化文件：
├── quantaalpha/factors/coder/
│   ├── polars_code_generator.py      # AST → Polars 代码生成器
│   └── expr_compiler.py              # 基于 AST 的表达式编译器
├── quantaalpha/backtest/
│   ├── data_schema.py                # 标准化列名定义
│   ├── data_type_converter.py        # 数据类型转换器
│   └── validation_thresholds.py      # 分层验证阈值配置
```

### 8.5 配置示例

```yaml
# configs/backtest.yaml 完整示例

# 引擎配置
engine:
  type: "both"  # "qlib" | "polars" | "both"

  validation:
    enabled: true
    save_intermediate: true
    diff_threshold: 1e-6
    report_dir: "./validation_reports"

  qlib:
    provider_uri: "~/.qlib/qlib_data/cn_data"
    region: "cn"

  polars:
    data_path: "./data/parquet"
    lazy_mode: true

# 数据配置
data:
  start_time: "2020-01-01"
  end_time: "2023-12-31"
  market: "csi300"

# 数据集配置
dataset:
  label: "Ref($close, -2) / Ref($close, -1) - 1"
  segments:
    train: ["2020-01-01", "2021-12-31"]
    valid: ["2022-01-01", "2022-06-30"]
    test: ["2022-07-01", "2023-12-31"]

# 模型配置
model:
  type: "lgb"
  params:
    loss: "mse"
    colsample_bytree: 0.8879
    learning_rate: 0.0421
    subsample: 0.8789
    lambda_l1: 205.6999
    lambda_l2: 577.2378
    max_depth: 8
    num_leaves: 210
    num_threads: 20

# 回测配置
backtest:
  backtest:
    start_time: "2022-07-01"
    end_time: "2023-12-31"
    account: 100000000
    benchmark: "SH000300"
    exchange_kwargs:
      freq: "day"
      limit_threshold: 0.095
      deal_price: "close"
  strategy:
    class: "TopkDropoutStrategy"
    module_path: "qlib.contrib.strategy.signal_strategy"
    kwargs:
      topk: 50
      n_drop: 5

# 实验配置
experiment:
  name: "dual_engine_validation"
  recorder: "recorder"
  output_dir: "./backtest_results"

# LLM 配置
llm:
  cache_dir: "./factor_cache"
  auto_extract_cache: true
```

---

**文档版本**: v2.2
**编写日期**: 2026-03-10
**编写人**: AI Assistant
**审核状态**: 已优化（含详细验收标准）
**变更记录**:
- v2.2: 补充 Week 1-5 详细验收标准和交付物清单，明确每一步的验收要求
- v2.1: 新增第六章"关键实现优化建议"，包含函数优化、表达式编译器优化、数据类型一致性优化、验证阈值精细化
- v2.0: 增加双引擎并存架构、配置化切换、中间产物验证机制
- v1.0: 初始版本，单引擎迁移方案
