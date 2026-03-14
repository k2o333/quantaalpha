# 时间序列因子研究方向

## 1. 动量因子 (Momentum Factors)

### 1.1 收益率动量
| 因子名称 | 描述 | 计算公式 | 预期方向 |
|---------|------|----------|---------|
| `return_5d` | 5日收益率 | `(close / close.shift(5)) - 1` | 正向 |
| `return_10d` | 10日收益率 | `(close / close.shift(10)) - 1` | 正向 |
| `return_20d` | 20日收益率 | `(close / close.shift(20)) - 1` | 正向 |
| `return_60d` | 60日收益率 | `(close / close.shift(60)) - 1` | 正向 |
| `return_120d` | 120日收益率 | `(close / close.shift(120)) - 1` | 正向 |
| `return_250d` | 250日收益率 | `(close / close.shift(250)) - 1` | 正向 |

### 1.2 相对动量
| 因子名称 | 描述 | 计算公式 | 预期方向 |
|---------|------|----------|---------|
| `return_rel_20d` | 20日相对收益率 | `return_20d - benchmark_return_20d` | 正向 |
| `return_rel_60d` | 60日相对收益率 | `return_60d - benchmark_return_60d` | 正向 |
| `momentum_20_10d` | 20日动量减去10日动量 | `return_20d - return_10d` | 正向 |

### 1.3 动量加速
| 因子名称 | 描述 | 计算公式 | 预期方向 |
|---------|------|----------|---------|
| `momentum_accel_20d` | 20日动量加速度 | `return_20d - 2*return_10d + return_5d` | 正向 |

---

## 2. 波动率因子 (Volatility Factors)

### 2.1 历史波动率
| 因子名称 | 描述 | 计算公式 | 预期方向 |
|---------|------|----------|---------|
| `volatility_5d` | 5日波动率 | `pct_change.rolling_std(5)` | 负向 |
| `volatility_10d` | 10日波动率 | `pct_change.rolling_std(10)` | 负向 |
| `volatility_20d` | 20日波动率 | `pct_change.rolling_std(20)` | 负向 |
| `volatility_60d` | 60日波动率 | `pct_change.rolling_std(60)` | 负向 |
| `volatility_120d` | 120日波动率 | `pct_change.rolling_std(120)` | 负向 |

### 2.2 相对波动率
| 因子名称 | 描述 | 计算公式 | 预期方向 |
|---------|------|----------|---------|
| `volatility_rel_20d` | 20日相对波动率 | `volatility_20d / volatility_60d` | 负向 |
| `volatility_rank_20d` | 20日波动率排名 | `rank(volatility_20d)` | 负向 |

### 2.3 波动率变化
| 因子名称 | 描述 | 计算公式 | 预期方向 |
|---------|------|----------|---------|
| `volatility_change_20d` | 波动率变化 | `volatility_20d - volatility_60d` | 待验证 |

---

## 3. 量价因子 (Price-Volume Factors)

### 3.1 成交量因子
| 因子名称 | 描述 | 计算公式 | 预期方向 |
|---------|------|----------|---------|
| `volume_ma5_ratio` | 成交量/5日均量 | `volume / volume.rolling_mean(5)` | 待验证 |
| `volume_ma20_ratio` | 成交量/20日均量 | `volume / volume.rolling_mean(20)` | 待验证 |
| `volume_ma60_ratio` | 成交量/60日均量 | `volume / volume.rolling_mean(60)` | 待验证 |
| `volume_change_5d` | 5日成交量变化 | `(volume / volume.shift(5)) - 1` | 待验证 |

### 3.2 成交额因子
| 因子名称 | 描述 | 计算公式 | 预期方向 |
|---------|------|----------|---------|
| `amount_ma5_ratio` | 成交额/5日均额 | `amount / amount.rolling_mean(5)` | 待验证 |
| `amount_ma20_ratio` | 成交额/20日均额 | `amount / amount.rolling_mean(20)` | 待验证 |

### 3.3 换手率因子
| 因子名称 | 描述 | 计算公式 | 预期方向 |
|---------|------|----------|---------|
| `turnover_5d` | 5日平均换手率 | `turnover.rolling_mean(5)` | 待验证 |
| `turnover_20d` | 20日平均换手率 | `turnover.rolling_mean(20)` | 待验证 |
| `turnover_60d` | 60日平均换手率 | `turnover.rolling_mean(60)` | 待验证 |
| `turnover_change_20d` | 换手率变化 | `turnover_20d - turnover_60d` | 待验证 |

---

## 4. 趋势因子 (Trend Factors)

### 4.1 移动平均线因子
| 因子名称 | 描述 | 计算公式 | 预期方向 |
|---------|------|----------|---------|
| `ma5_price_ratio` | 价格/5日均线 | `close / close.rolling_mean(5)` | 正向 |
| `ma10_price_ratio` | 价格/10日均线 | `close / close.rolling_mean(10)` | 正向 |
| `ma20_price_ratio` | 价格/20日均线 | `close / close.rolling_mean(20)` | 正向 |
| `ma60_price_ratio` | 价格/60日均线 | `close / close.rolling_mean(60)` | 正向 |
| `ma120_price_ratio` | 价格/120日均线 | `close / close.rolling_mean(120)` | 正向 |
| `ma250_price_ratio` | 价格/250日均线 | `close / close.rolling_mean(250)` | 正向 |

### 4.2 均线交叉因子
| 因子名称 | 描述 | 计算公式 | 预期方向 |
|---------|------|----------|---------|
| `ma5_ma20_diff` | 5日-20日均线差 | `ma5 - ma20` | 正向 |
| `ma10_ma60_diff` | 10日-60日均线差 | `ma10 - ma60` | 正向 |
| `ma20_ma120_diff` | 20日-120日均线差 | `ma20 - ma120` | 正向 |
| `ma_cross_signal` | 均线金叉死叉 | `sign(ma5_ma20_diff)` | 正向 |

### 4.3 指数移动平均线因子
| 因子名称 | 描述 | 计算公式 | 预期方向 |
|---------|------|----------|---------|
| `ema12_price_ratio` | 价格/EMA12 | `close / close.ewm(span=12).mean()` | 正向 |
| `ema26_price_ratio` | 价格/EMA26 | `close / close.ewm(span=26).mean()` | 正向 |
| `ema12_ema26_diff` | EMA12-EMA26 | `ema12 - ema26` | 正向 |

---

## 5. 均值回归因子 (Mean Reversion Factors)

### 5.1 价格偏离因子
| 因子名称 | 描述 | 计算公式 | 预期方向 |
|---------|------|----------|---------|
| `price_deviation_20d` | 20日价格偏离度 | `(close - close.rolling_mean(20)) / close.rolling_mean(20)` | 负向 |
| `price_deviation_60d` | 60日价格偏离度 | `(close - close.rolling_mean(60)) / close.rolling_mean(60)` | 负向 |
| `price_deviation_120d` | 120日价格偏离度 | `(close - close.rolling_mean(120)) / close.rolling_mean(120)` | 负向 |

### 5.2 滚动Z-Score因子
| 因子名称 | 描述 | 计算公式 | 预期方向 |
|---------|------|----------|---------|
| `price_zscore_20d` | 20日价格Z-Score | `(close - close.rolling_mean(20)) / close.rolling_std(20)` | 负向 |
| `price_zscore_60d` | 60日价格Z-Score | `(close - close.rolling_mean(60)) / close.rolling_std(60)` | 负向 |
| `volume_zscore_20d` | 20日成交量Z-Score | `(volume - volume.rolling_mean(20)) / volume.rolling_std(20)` | 待验证 |

---

## 6. 统计因子 (Statistical Factors)

### 6.1 分位数因子
| 因子名称 | 描述 | 计算公式 | 预期方向 |
|---------|------|----------|---------|
| `price_quantile_20d` | 20日价格分位数 | `rank(pct_change.rolling(20))` | 待验证 |
| `price_quantile_60d` | 60日价格分位数 | `rank(pct_change.rolling(60))` | 待验证 |
| `volume_quantile_20d` | 20日成交量分位数 | `rank(volume.rolling(20))` | 待验证 |

### 6.2 峰度与偏度
| 因子名称 | 描述 | 计算公式 | 预期方向 |
|---------|------|----------|---------|
| `return_skew_20d` | 20日收益率偏度 | `pct_change.rolling(20).skew()` | 待验证 |
| `return_kurt_20d` | 20日收益率峰度 | `pct_change.rolling(20).kurt()` | 待验证 |
| `return_skew_60d` | 60日收益率偏度 | `pct_change.rolling(60).skew()` | 待验证 |

---

## 7. 相关性因子 (Correlation Factors)

### 7.1 价格成交量相关
| 因子名称 | 描述 | 计算公式 | 预期方向 |
|---------|------|----------|---------|
| `price_volume_corr_20d` | 20日价格-成交量相关 | `corr(close, volume).rolling(20)` | 待验证 |
| `price_volume_corr_60d` | 60日价格-成交量相关 | `corr(close, volume).rolling(60)` | 待验证 |

### 7.2 行业相关
| 因子名称 | 描述 | 计算公式 | 预期方向 |
|---------|------|----------|---------|
| `industry_rel_return_20d` | 20日行业相对收益 | `return_20d - industry_return_20d` | 正向 |
| `industry_rel_return_60d` | 60日行业相对收益 | `return_60d - industry_return_60d` | 正向 |

---

## 8. 滞后因子 (Lagged Factors)

### 8.1 历史收益滞后
| 因子名称 | 描述 | 计算公式 | 预期方向 |
|---------|------|----------|---------|
| `return_lag1` | 1日滞后收益 | `return.shift(1)` | 负向 |
| `return_lag2` | 2日滞后收益 | `return.shift(2)` | 负向 |
| `return_lag3` | 3日滞后收益 | `return.shift(3)` | 负向 |
| `return_lag5` | 5日滞后收益 | `return.shift(5)` | 负向 |

### 8.2 累计收益滞后
| 因子名称 | 描述 | 计算公式 | 预期方向 |
|---------|------|----------|---------|
| `cumreturn_lag5` | 5日累计收益滞后 | `(close.shift(5) / close.shift(10)) - 1` | 待验证 |
| `cumreturn_lag10` | 10日累计收益滞后 | `(close.shift(10) / close.shift(20)) - 1` | 待验证 |

---

## 9. 滚动窗口统计因子

### 9.1 滚动最大值/最小值
| 因子名称 | 描述 | 计算公式 | 预期方向 |
|---------|------|----------|---------|
| `high_20d_ratio` | 当前价格/20日最高 | `close / close.rolling_max(20)` | 正向 |
| `low_20d_ratio` | 当前价格/20日最低 | `close / close.rolling_min(20)` | 负向 |
| `high_low_range_20d` | 20日最高-最低范围 | `(close.rolling_max(20) - close.rolling_min(20)) / close` | 待验证 |

### 9.2 滚动窗口均值偏差
| 因子名称 | 描述 | 计算公式 | 预期方向 |
|---------|------|----------|---------|
| `ma5_ma20_deviation` | 5日均线与20日均线偏差 | `(ma5 - ma20) / ma20` | 待验证 |
| `ma20_ma60_deviation` | 20日均线与60日均线偏差 | `(ma20 - ma60) / ma60` | 待验证 |

---

## 10. 时间序列分解因子

### 10.1 趋势与周期分离
| 因子名称 | 描述 | 计算公式 | 预期方向 |
|---------|------|----------|---------|
| `trend_component_20d` | 20日趋势成分 | 线性回归斜率 × 时间 | 待验证 |
| `cycle_component_20d` | 20日周期成分 | `close - trend_component` | 待验证 |
| `detrend_return_20d` | 去趋势收益 | `(close / trend_component) - 1` | 待验证 |

---

## 因子方向验证优先级

| 优先级 | 因子类别 | 说明 |
|--------|---------|------|
| 高 | 动量因子 | 经典因子，方向明确 |
| 高 | 波动率因子 | 经典因子，方向明确 |
| 高 | 均线因子 | 简单有效 |
| 中 | 量价因子 | 需要验证方向 |
| 中 | 均值回归因子 | 与动量方向相反 |
| 低 | 统计因子 | 方向待验证 |
| 低 | 相关性因子 | 需要结合行业数据 |

---

## 数据来源

| 数据表 | 可用字段 |
|--------|----------|
| `daily` | `open`, `high`, `low`, `close`, `vol`, `amount` |
| `daily_basic` | `turnover`, `turnover_rate`, `volume_ratio` |
| `adj_factor` | `adj_factor` |

---

**创建日期**: 2026-03-01
**版本**: v1.0
