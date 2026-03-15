# backtest - 因子回测模块

**Status:** active
**Created:** 2026-03-14

---

## TL;DR

- `backtest` contains standalone scripts for factor validation, currently centered on Alpha101 workflows.
- The main entrypoints live under `backtest/start/`.
- High-risk edits are factor formulas, rolling-window semantics, and trading assumptions.

## Entrypoints

- Main run: `python backtest/start/backtest_alpha101_polars.py`
- Comparison run: `python backtest/start/backtest_alpha101.py`
- Debug scripts: `python backtest/start/debug_pure_polars_fixed.py`
- Input data: `data/stk_factor_pro/`

## Validation

- Full run: `python backtest/start/backtest_alpha101_polars.py`
- Short debug run: `python backtest/start/debug_pure_polars_fixed.py`
- Compare outputs between pure-Polars and mixed implementations when changing factor logic

## Do Not Touch Blindly

- rolling correlation implementation
- sorting assumptions on `ts_code` and `trade_date_dt`
- trading cost and portfolio rules

Read the risk notes below before changing factor computation or transaction assumptions.

## Known Risks At A Glance

- incorrect sort order breaks rolling-window math
- full-dataset runs can be memory-heavy
- formula changes can invalidate previous result comparisons

---

## Responsibility

backtest 是基于 Alpha101 因子的股票策略回测模块，负责：

1. **因子计算**：实现 WorldQuant Alpha101 因子（当前支持 Alpha3）
2. **策略回测**：模拟股票交易，评估策略表现
3. **统计分析**：计算收益率、夏普比率、最大回撤等指标
4. **调试支持**：提供因子计算过程调试工具

---

## External Interfaces

### CLI 入口

```bash
# 纯 Polars 版本回测（推荐）
python backtest/start/backtest_alpha101_polars.py

# Polars+Pandas 混用版回测
python backtest/start/backtest_alpha101.py

# 调试脚本
python backtest/start/debug_pure_polars_fixed.py
python backtest/start/debug_mixed_fixed.py
```

### 配置参数（脚本内修改）

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `DATA_PATH` | `data/stk_factor_pro` | 数据存储路径 |
| `START_DATE` | `20240101` | 回测起始日期 |
| `END_DATE` | `20241231` | 回测结束日期 |
| `capital` | `1_000_000` | 初始资金 |
| `top_k` | `20` | 选股数量 |
| `hold_days` | `5` | 持仓天数 |

---

## Key Data Structures

### SimpleBacktestEngine

简易回测引擎，封装回测逻辑：

```python
class SimpleBacktestEngine:
    capital: float          # 初始资金
    cash: float             # 现金余额
    positions: Dict[str, float]  # 持仓 {股票代码: 数量}
    trades: List[Dict]      # 交易记录
    daily_pnl: List[Dict]   # 每日盈亏
```

### 回测统计数据

```python
stats = {
    "total_return": float,    # 总收益率 (%)
    "max_drawdown": float,    # 最大回撤 (%)
    "sharpe_ratio": float,    # 夏普比率
    "total_trades": int,      # 总交易次数
    "win_rate": float,        # 胜率 (%)
    "final_value": float,     # 最终资金
    "start_date": date,       # 起始日期
    "end_date": date          # 结束日期
}
```

### 交易记录

```python
trade = {
    "date": date,           # 交易日期
    "code": str,            # 股票代码
    "action": str,          # BUY/SELL
    "price": float,         # 成交价格
    "quantity": int,        # 成交数量
    "pnl": float            # 盈亏（卖出时计算）
}
```

---

## Dependencies

### Python 包

```
polars>=0.20.0
numpy>=1.24.0
pandas>=2.0.0          # 混用版本需要
tqdm>=4.65.0
```

### 内部数据依赖

- `data/stk_factor_pro/*.parquet`：股票行情数据
- 必需字段：`ts_code`, `trade_date`, `open`, `close`, `vol`, `trade_date_dt`

### 第三方依赖

- `third_party/vnpy`：VN.PY 量化框架（当前未使用）

---

## Constraints

### 数据约束

- 数据必须按 `ts_code` 和 `trade_date_dt` 排序
- 数据格式为 Parquet
- 必须包含所有必需字段

### 交易约束

- 买入最小单位：100 股（1手）
- 买入佣金：0.05%
- 卖出佣金：0.15%
- 资金使用上限：95%

### 策略约束

- 固定持仓周期（hold_days）
- 不支持做空
- 不支持分批建仓/平仓

---

## Known Risks

### 数据排序问题

- **风险**：Polars `over()` 窗口函数不自动排序，导致 `rolling_corr` 计算错误
- **缓解措施**：加载数据后必须执行 `df.sort(["ts_code", "trade_date_dt"])`
- **参考**：`docs/05-playbooks/polars-rolling-corr-lessons.md`

### 内存消耗

- **风险**：全量数据加载可能导致内存不足
- **缓解措施**：可通过日期范围过滤数据

### 因子有效性

- **风险**：Alpha101 因子在中国 A 股市场的有效性需要验证
- **当前状态**：仅实现 Alpha3 因子，其他因子待扩展

---

## Test Entry Points

### 回测脚本

```bash
# 完整回测
python backtest/start/backtest_alpha101_polars.py

# 短期调试（1个月数据）
python backtest/start/debug_pure_polars_fixed.py
```

### 输出文件

| 文件 | 说明 |
|------|------|
| `backtest_result_polars.csv` | 纯 Polars 版本每日收益 |
| `backtest_result.csv` | 混用版本每日收益 |
| `debug_*/step1_cs_rank.csv` | 截面排名中间结果 |
| `debug_*/step2_rolling_corr.csv` | 滚动相关系数中间结果 |

### 验证方法

1. 对比纯 Polars 版本和混用版本的输出一致性
2. 检查 `alpha3` 前9天是否为 NaN（窗口不足）
3. 验证最终收益率是否合理

---

## Core Components

### backtest_alpha101_polars.py

纯 Polars 实现的回测脚本：
- 使用 `pl.rolling_corr()` 计算滚动相关系数
- 性能更优（约 3 倍速度提升）
- 推荐使用

### backtest_alpha101.py

Polars+Pandas 混用版回测脚本：
- 使用 pandas `rolling().corr()` 计算
- 兼容性更好，作为对照实现

### debug_*.py

因子计算调试脚本：
- 输出中间计算结果
- 用于问题排查

---

## Alpha3 因子说明

### 因子公式

```
Alpha3 = -1 * ts_corr(cs_rank(open), cs_rank(vol), 10)
```

- `cs_rank(x)`：截面排名，按交易日对全市场股票排名
- `ts_corr(x, y, n)`：时间序列相关系数，过去 n 天的相关性

### 实现要点

```python
# 1. 确保数据排序
df = df.sort(["ts_code", "trade_date_dt"])

# 2. 计算截面排名
df = df.with_columns([
    pl.col("open").rank().over("trade_date_dt").alias("open_rank"),
    pl.col("vol").rank().over("trade_date_dt").alias("vol_rank"),
])

# 3. 计算滚动相关系数
df = df.with_columns([
    (pl.rolling_corr("open_rank", "vol_rank", window_size=10)
       .over("ts_code") * -1).alias("alpha3")
])
```

---

## Related Docs

- `docs/05-playbooks/polars-rolling-corr-lessons.md`：Polars 滚动相关系数使用经验
- `docs/02-modules/app4.md`：数据下载与存储模块（数据来源）
