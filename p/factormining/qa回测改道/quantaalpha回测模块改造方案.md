# QuantAlpha 回测模块改造方案

## 背景

QuantAlpha 项目当前依赖 qlib 作为回测引擎，与 rdagent 深度耦合。鉴于以下原因，需要进行改造：

1. **qlib 依赖过重**：项目中 219 处 qlib 引用，32 处 rdagent 引用
2. **数据格式锁定**：qlib 使用 HDF5 格式存储数据
3. **架构灵活性**：剥离 qlib 可以获得更大的自主权

## 当前架构

### qlib 在回测中的功能

| 功能 | qlib 实现 | 备注 |
|------|-----------|------|
| 数据加载 | `D.features()` | 从 HDF5 读取 OHLCV |
| 股票列表 | `D.instruments()` | 获取股票池 |
| 数据集封装 | `DatasetH`, `DataHandlerLP` | 训练/测试集划分 |
| 模型训练 | `LGBModel` | LightGBM 训练 |
| 回测引擎 | `qlib.backtest.backtest()` + `SimulatorExecutor` | 核心交易模拟 |
| IC分析 | `SigAnaRecord` | IC/Rank IC 计算 |
| 风险指标 | `risk_analysis` | 年化收益、最大回撤等 |

### 当前数据流

```
aspipe_v4 (TuShare API)
    ↓
Parquet (ts_code, trade_date, close, turnover_rate, ...)
    ↓
因子计算 (factor_calculator.py) ← 依赖 qlib D.features()
    ↓
回测 (backtest/runner.py) ← 依赖 qlib 完整生态
    ↓
结果输出
```

## 目标架构

### 改造后数据流

```
aspipe_v4 (TuShare API)
    ↓
Parquet (ts_code, trade_date, close, turnover_rate, ...)
    ↓
数据转换层 (aspipe → OHLCV)
    ↓
因子计算 (polars expressions)
    ↓
回测引擎 (polars + 自实现)
    ↓
结果输出
```

### 技术选型

| 组件 | 改造后方案 | 理由 |
|------|-----------|------|
| 数据格式 | Parquet | 已有，与 aspipe 兼容 |
| 数据处理 | Polars | 高性能，Python 生态 |
| 模型训练 | LightGBM | 直接调用，无需 qlib 封装 |
| 回测引擎 | 自实现 | 简化版 TopKDropout 策略 |

## 现状分析

### aspipe_v4 现有 Parquet 格式

```python
# /home/quan/testdata/aspipe_v4/data/daily_basic/
Columns: ['ts_code', 'trade_date', 'close', 'turnover_rate', 'turnover_rate_f', 
          'volume_ratio', 'pe', 'pe_ttm', 'pb', 'ps', 'ps_ttm', 'dv_ratio', 
          'dv_ttm', 'total_share', 'float_share', 'free_share', 'total_mv', 
          'circ_mv', 'trade_date_dt', '_update_time']
```

**问题**：缺少 `open`, `high`, `low`, `volume`, `vwap` 字段，无法直接用于回测。

### qlib字段

 所需| 字段 | qlib 格式 | aspipe 现状 |
|------|-----------|-------------|
| 股票代码 | instrument | ts_code ✓ |
| 日期 | datetime | trade_date ✓ |
| 开盘价 | $open | ❌ 无 |
| 最高价 | $high | ❌ 无 |
| 最低价 | $low | ❌ 无 |
| 收盘价 | $close | close ✓ |
| 成交量 | $volume | ❌ 无 |
| 成交额 | $vwap | ❌ 无 |

## 改造内容

### 1. 补充数据源

#### 1.1 新增 daily 表下载

aspipe_v4 需要新增 `daily` 表下载，包含完整 OHLCV 字段：

```yaml
# app4/config/interfaces/daily.yaml
name: daily
api_name: daily
description: "日线行情"

output:
  primary_key: ["ts_code", "trade_date"]
  fields:
    - ts_code
    - trade_date
    - open
    - high
    - low
    - close
    - volume
    - amount
```

#### 1.2 数据转换层

```python
# quantaalpha/data/loader.py
import polars as pl
from pathlib import Path
from typing import List, Tuple

class ParquetDataLoader:
    """从 aspipe parquet 加载数据并转换为回测格式"""
    
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
    
    def load_ohlcv(self, 
                   start_date: str, 
                   end_date: str, 
                   instruments: List[str] = None) -> pl.DataFrame:
        """
        加载 OHLCV 数据
        
        Returns:
            DataFrame with columns: [ts_code, trade_date, open, high, low, close, volume, amount]
        """
        daily_files = sorted(self.data_dir.glob("daily/daily_*.parquet"))
        
        dfs = []
        for f in daily_files:
            df = pl.read_parquet(f)
            df = df.filter(
                (df["trade_date"] >= start_date) & 
                (df["trade_date"] <= end_date)
            )
            if instruments:
                df = df.filter(pl.col("ts_code").is_in(instruments))
            dfs.append(df)
        
        if not dfs:
            return pl.DataFrame()
        
        result = pl.concat(dfs)
        
        # 重命名字段
        result = result.rename({
            "ts_code": "instrument",
            "trade_date": "datetime"
        })
        
        return result.sort(["datetime", "instrument"])
    
    def get_instruments(self, market: str = "all") -> List[str]:
        """获取股票列表"""
        stock_basic = list(self.data_dir.glob("stock_basic/stock_basic_*.parquet"))
        if not stock_basic:
            return []
        
        df = pl.read_parquet(stock_basic[0])
        
        if market == "all":
            return df["ts_code"].to_list()
        
        # 支持 sz, sh 市场筛选
        return df.filter(df["ts_code"].str.ends_with(f".{market.upper()}"))["ts_code"].to_list()
```

### 2. 因子计算层改造

#### 2.1 因子表达式引擎

当前依赖 qlib 表达式解析器（如 `$close/Ref($close, 1)-1`），需要替换为 polars 实现：

```python
# quantaalpha/factors/polars_expr.py
import polars as pl
from typing import Callable, Dict

class PolarsExprEngine:
    """Polars 因子表达式引擎"""
    
    def __init__(self):
        self.funcs: Dict[str, Callable] = {
            "Ref": self._ref,
            "Mean": self._mean,
            "Sum": self._sum,
            "Std": self._std,
            "Max": self._max,
            "Min": self._min,
            "Rank": self._rank,
            "Delay": self._delay,
            "TS_PCTCHANGE": self._ts_pctchange,
        }
        
        self._register_builtins()
    
    def _ref(self, col: pl.Expr, n: int) -> pl.Expr:
        """引用 n 天前值"""
        return col.shift(n)
    
    def _mean(self, col: pl.Expr, window: int) -> pl.Expr:
        return col.rolling_mean(window)
    
    def _sum(self, col: pl.Expr, window: int) -> pl.Expr:
        return col.rolling_sum(window)
    
    def _std(self, col: pl.Expr, window: int) -> pl.Expr:
        return col.rolling_std(window)
    
    def _max(self, col: pl.Expr, window: int) -> pl.Expr:
        return col.rolling_max(window)
    
    def _min(self, col: pl.Expr, window: int) -> pl.Expr:
        return col.rolling_min(window)
    
    def _rank(self, col: pl.Expr, window: int = None) -> pl.Expr:
        if window:
            return col.rolling_apply(lambda x: x.rank().iloc[-1], window)
        return col.rank()
    
    def _delay(self, col: pl.Expr, n: int) -> pl.Expr:
        return col.shift(n)
    
    def _ts_pctchange(self, col: pl.Expr, window: int) -> pl.Expr:
        return col.pct_change(window)
    
    def _register_builtins(self):
        """注册内置字段映射"""
        self.field_aliases = {
            "$open": "open",
            "$high": "high", 
            "$low": "low",
            "$close": "close",
            "$volume": "volume",
            "$amount": "amount",
        }
    
    def parse(self, expr_str: str, df: pl.DataFrame) -> pl.Series:
        """解析表达式并计算"""
        # 简化的表达式解析器
        # 完整版需要词法分析 + 递归下降解析
        pass
```

#### 2.2 因子计算示例

```python
# 示例：计算 ROC5
def calc_roc5(df: pl.DataFrame) -> pl.DataFrame:
    return df.with_columns([
        (pl.col("close") - pl.col("close").shift(5)) / pl.col("close").shift(5)
        .alias("ROC5")
    ])

# 示例：计算均线
def calc_ma(df: pl.DataFrame, window: int = 20) -> pl.DataFrame:
    return df.with_columns([
        pl.col("close").rolling_mean(window).alias(f"MA{window}")
    ])
```

### 3. 回测引擎重写

#### 3.1 核心数据结构

```python
# quantaalpha/backtest/engine.py
import polars as pl
import numpy as np
from dataclasses import dataclass
from typing import Dict, List, Optional

@dataclass
class BacktestConfig:
    """回测配置"""
    start_date: str
    end_date: str
    topk: int = 50              # 持仓股票数
    account: float = 1e8        # 初始资金
    commission_rate: float = 0.0003  # 手续费
    slip_rate: float = 0.0001   # 滑点

@dataclass 
class BacktestResult:
    """回测结果"""
    daily_returns: pl.DataFrame  # 每日收益
    positions: pl.DataFrame     # 每日持仓
    metrics: Dict[str, float]   # 指标
    
class BacktestEngine:
    """基于 polars 的回测引擎"""
    
    def __init__(self, config: BacktestConfig):
        self.config = config
    
    def run(self, 
            signals: pl.DataFrame, 
            prices: pl.DataFrame) -> BacktestResult:
        """
        执行回测
        
        Args:
            signals: 因子值, columns=[datetime, instrument, signal]
            prices: 价格数据, columns=[datetime, instrument, close, open, high, low]
        """
        # 1. 每日选股
        daily_signals = self._select_topk(signals)
        
        # 2. 计算每日收益
        daily_returns = self._calc_returns(daily_signals, prices)
        
        # 3. 计算指标
        metrics = self._calc_metrics(daily_returns)
        
        return BacktestResult(
            daily_returns=daily_returns,
            positions=daily_signals,
            metrics=metrics
        )
    
    def _select_topk(self, signals: pl.DataFrame) -> pl.DataFrame:
        """每日选取 signal 最高的 topk 只股票"""
        return signals.sort(["datetime", "signal"], descending=[True, False]) \
                     .group_by("datetime") \
                     .head(self.config.topk) \
                     .with_columns([
                         pl.lit(1.0 / self.config.topk).alias("weight")
                     ])
    
    def _calc_returns(self, 
                      positions: pl.DataFrame, 
                      prices: pl.DataFrame) -> pl.DataFrame:
        """计算每日组合收益"""
        # 关联价格数据
        pos_with_price = positions.join(
            prices, 
            on=["datetime", "instrument"], 
            how="left"
        )
        
        # 计算单日收益 (简化: 当日收盘价买入，次日收盘价卖出)
        # 完整版需要考虑滑点、手续费
        return pos_with_price.with_columns([
            (pl.col("close").pct_change() * pl.col("weight")).sum()
            .over("datetime")
            .alias("portfolio_return")
        ])
    
    def _calc_metrics(self, returns: pl.DataFrame) -> Dict[str, float]:
        """计算回测指标"""
        daily_ret = returns["portfolio_return"].to_numpy()
        
        cumret = np.cumprod(1 + daily_ret)
        
        # 年化收益
        annual_return = daily_ret.mean() * 252
        
        # 年化波动
        annual_vol = daily_ret.std() * np.sqrt(252)
        
        # 夏普比率
        sharpe = annual_return / annual_vol if annual_vol > 0 else 0
        
        # 最大回撤
        cummax = np.maximum.accumulate(cumret)
        max_drawdown = np.min((cumret - cummax) / cummax)
        
        # 信息比率 (vs 基准)
        # ...
        
        return {
            "annualized_return": annual_return,
            "annualized_volatility": annual_vol,
            "sharpe_ratio": sharpe,
            "max_drawdown": max_drawdown,
        }
```

#### 3.2 调仓逻辑（完整版）

```python
def _rebalance(self, 
               prev_positions: pl.DataFrame,
               new_signals: pl.DataFrame,
               prices: pl.DataFrame) -> pl.DataFrame:
    """
    调仓逻辑
    
    1. 卖出: 不在新信号中的股票
    2. 买入: 新信号中的股票
    
    考虑:
    - 滑点
    - 手续费
    - 最小交易量限制
    """
    # 简化的等权策略
    target_stocks = new_signals.topk(self.config.topk)
    target_weight = 1.0 / self.config.topk
    
    # 计算交易成本
    commission = prev_positions.join(
        target_stocks, 
        on="instrument", 
        how="outer"
    ).with_columns([
        (pl.col("weight").fill_null(0) - pl.col("weight_right").fill_null(0)).abs()
        .alias("trade_amount")
    ])
    
    total_commission = (commission["trade_amount"] * 
                        self.config.account * 
                        self.config.commission_rate).sum()
    
    return target_stocks.with_columns([
        pl.lit(target_weight).alias("weight")
    ])
```

### 4. IC 分析模块

```python
# quantaalpha/backtest/metrics.py
import polars as pl
import numpy as np
from scipy import stats

def calc_ic(signals: pl.DataFrame, returns: pl.DataFrame) -> Dict[str, float]:
    """
    计算 IC (Information Coefficient)
    
    Args:
        signals: [datetime, instrument, signal]
        returns: [datetime, instrument, return]
    """
    merged = signals.join(returns, on=["datetime", "instrument"])
    
    def _ic(group):
        if len(group) < 2:
            return 0
        corr, _ = stats.spearmanr(group["signal"], group["return"])
        return corr if not np.isnan(corr) else 0
    
    ic_series = merged.group_by("datetime").apply(_ic)
    
    return {
        "IC": ic_series.mean(),
        "ICIR": ic_series.mean() / ic_series.std(),
        "IC_pvalue": stats.ttest_1samp(ic_series, 0)[1],
    }

def calc_rank_ic(signals: pl.DataFrame, returns: pl.DataFrame) -> Dict[str, float]:
    """计算 Rank IC"""
    # 类似实现
    pass
```

### 5. 配置文件改造

#### 5.1 回测配置

```yaml
# configs/backtest.yaml
data:
  provider: "parquet"  # 改为 parquet
  data_dir: "../data"
  start_time: "20220101"
  end_time: "20231231"
  market: "all"

dataset:
  label: "Ref($close, -2) / Ref($close, -1) - 1"
  segments:
    train: ["20170101", "20201231"]
    valid: ["20210101", "20211231"]
    test: ["20220101", "20231231"]

model:
  type: "lgb"
  params:
    n_estimators: 100
    learning_rate: 0.05

backtest:
  topk: 50
  account: 100000000
  commission_rate: 0.0003
  slip_rate: 0.0001
```

#### 5.2 因子库配置

```yaml
# configs/factors.yaml
factor_source:
  type: "custom"
  custom:
    json_files:
      - "factors/my_factors.json"
```

## 改造工作量评估

| 模块 | 工作量 | 难度 | 优先级 |
|------|--------|------|--------|
| 1. 补充 daily 数据源 | 1-2 天 | 中 | P0 |
| 2. 数据加载适配器 | 2-3 天 | 中 | P0 |
| 3. 因子表达式引擎 | 3-5 天 | **高** | P1 |
| 4. 回测引擎 | 3-5 天 | 高 | P1 |
| 5. IC/风险指标 | 1 天 | 低 | P1 |
| 6. 配置文件适配 | 1 天 | 低 | P2 |

**总计**: 约 2-3 周开发时间

## 关键难点

### 1. 因子表达式解析

qlib 的表达式如 `Mean($close, 20) / Mean($volume, 20)` 需要完整解析：

```python
# 完整表达式解析器需要支持：
# - 运算符: +, -, *, /, ()
# - 函数: Ref, Mean, Sum, Std, Max, Min, Rank, Delay, Corr, etc.
# - 字段: $open, $high, $low, $close, $volume
# - 常量: 数字
```

建议方案：
- 初期：手动实现常用因子（ROC, MA, VOLATILITY 等）
- 后期：引入 expression-parser 库或参考 qlib 实现

### 2. 调仓成本模拟

qlib 的 SimulatorExecutor 处理了复杂的交易逻辑：
- 滑点模型
- 最小交易量
- 涨跌停限制
- 流动性约束

简化版可以先忽略，逐步迭代。

### 3. 数据对齐

- 多因子数据日期对齐
- 价格数据与信号日期对齐
- 停牌/涨跌停数据过滤

## 实施计划

### Phase 1: 数据层改造
1. 新增 daily 数据下载
2. 实现 ParquetDataLoader

### Phase 2: 核心回测
1. 实现简化版 BacktestEngine
2. 集成模型训练
3. IC/风险指标计算

### Phase 3: 完善
1. 因子表达式引擎
2. 完整调仓逻辑
3. 配置文件兼容

## 附录

### A. 字段映射表

| qlib | aspipe parquet | polars internal |
|------|----------------|-----------------|
| instrument | ts_code | instrument |
| datetime | trade_date | datetime |
| $open | - | open |
| $high | - | high |
| $low | - | low |
| $close | close | close |
| $volume | - | volume |
| $amount | - | amount |

### B. 依赖对比

| 依赖 | 当前 | 改造后 |
|------|------|--------|
| qlib | 219 处 | 0 处 |
| rdagent | 32 处 | 0 处 |
| polars | 0 处 | 必需 |
| pyarrow | 0 处 | 必需 |

### C. 目录结构建议

```
quantaalpha/
├── backtest/
│   ├── __init__.py
│   ├── engine.py          # 回测引擎
│   ├── loader.py          # 数据加载
│   ├── metrics.py         # IC/风险指标
│   └── config.py          # 配置解析
├── factors/
│   ├── polars_expr.py    # 表达式引擎
│   ├── calculator.py     # 因子计算
│   └── template/          # 因子模板
└── data/
    └── parquet_loader.py  # aspipe 数据适配
```

---

*文档创建时间: 2026-03-11*
