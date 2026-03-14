# Polars rolling_corr 使用经验总结

## 背景

在使用 Polars 实现 WorldQuant Alpha101 因子（Alpha3: `-1 * ts_corr(cs_rank(open), cs_rank(vol), 10)`）时，发现纯 Polars 版本和 Polars+Pandas 混用版本的回测结果差异巨大：
- 混用版本收益率：47.29%
- 纯 Polars 版本收益率：-4.20%

## 问题排查过程

### 第一步：怀疑计算方式不同

最初怀疑 `pl.rolling_corr()` 和 pandas 的 `rolling().corr()` 计算结果不同。

**验证结果**：两者计算结果完全一致，排除此原因。

### 为什么一开始回测结果不一致

**直接原因**：
- **Polars+Pandas 混用版本**：在 `groupby().map_groups()` 内部将数据转换为 pandas 后，使用 `pdf.sort_values("trade_date_dt")` 对每组数据按日期排序，然后计算滚动相关系数
- **纯 Polars 版本**：直接使用 `pl.rolling_corr().over("ts_code")`，没有对数据按日期排序

**根本原因**：
Polars 的 `over()` 窗口函数**不会自动对窗口内的数据排序**，它严格按照数据在 DataFrame 中的物理顺序计算。而 pandas 的 `rolling()` 默认按索引顺序计算。

当从多个 parquet 文件加载数据时：
```python
# 从22个文件加载数据
dfs = []
for f in files:
    df = pl.read_parquet(f)
    dfs.append(df)
combined = pl.concat(dfs)  # 数据顺序是文件加载顺序，不是日期顺序！
```

数据顺序是文件加载顺序，而不是日期顺序，导致纯 Polars 版本计算时窗口内的数据是乱序的。

### 第二步：发现数据排序问题

通过 debug 脚本对比两个版本的中期结果，发现：

**Polars+Pandas 混用版本**：
```python
def calc_rolling_corr(group_df):
    pdf = group_df.to_pandas()
    pdf = pdf.sort_values("trade_date_dt")  # 内部手动排序
    pdf["alpha3"] = pdf["open_rank"].rolling(window=10).corr(pdf["vol_rank"]) * -1
    return pl.from_pandas(pdf)
```

**纯 Polars 版本**（问题代码）：
```python
df = df.with_columns([
    (pl.rolling_corr("open_rank", "vol_rank", window_size=10).over("ts_code") * -1).alias("alpha3")
])
```

**关键发现**：
- 混用版本在 `groupby().apply()` 内部手动排序了数据
- 纯 Polars 版本没有排序，导致 `over("ts_code")` 窗口函数看到的数据顺序是乱的

### 第三步：验证排序问题

查看保存的 CSV 文件，发现数据顺序确实不同：

**未排序的数据**（错误）：
```
trade_date_dt  open_rank  vol_rank
2024-01-15     2022.5     5474.0   ← 第1行是1月15日
2024-01-19     2089.0     5510.0   ← 第2行是1月19日
2024-01-12     1968.0     5459.0   ← 第3行是1月12日（乱序！）
```

这导致 `rolling_corr` 计算时使用的不是按时间顺序的窗口，结果完全错误。

## 解决方案

### 修复方法

在数据加载时添加排序：

```python
def load_data(data_path: str, start_date: str, end_date: str) -> pl.DataFrame:
    # ... 加载数据 ...
    
    if dfs:
        combined = pl.concat(dfs)
        combined = combined.unique(subset=["ts_code", "trade_date"])
        
        # 关键修复：按 ts_code 和 trade_date_dt 排序
        combined = combined.sort(["ts_code", "trade_date_dt"])
        
        return combined
    return pl.DataFrame()
```

### 修复后的结果

两个版本的输出完全一致：
- 前9天都是 NaN（窗口不足10天）
- 第10天开始有值：0.190840
- 后续所有值都相同

## 核心教训

### 1. Polars 窗口函数依赖数据顺序

Polars 的 `over()` 窗口函数**不会自动排序**，它假设数据已经按分组键排好序。

```python
# 错误：数据可能乱序
df = df.with_columns([
    pl.col("value").rolling_mean(window_size=10).over("group").alias("rolling_mean")
])

# 正确：先排序再计算
df = df.sort(["group", "date"]).with_columns([
    pl.col("value").rolling_mean(window_size=10).over("group").alias("rolling_mean")
])
```

### 2. Pandas groupby 的行为差异

Pandas 的 `groupby().apply()` 每次处理一个组的数据，如果在内部排序，不会影响其他组。

Polars 的 `over()` 是按行处理的，数据顺序直接影响结果。

### 3. Debug 技巧

当发现计算结果异常时：
1. 保存中间结果到 CSV
2. 对比不同实现的中期输出
3. 检查数据顺序和类型
4. 用少量数据（如单只股票）验证

## 性能对比

修复后，纯 Polars 版本性能优势明显：

| 版本 | 总耗时 | 回测速度 |
|------|--------|----------|
| Polars+Pandas 混用版 | ~33秒 | 8.78 it/s |
| **纯 Polars 版** | **10.55秒** | **71.53 it/s** |

**速度提升：3倍以上**

## 正确使用 pl.rolling_corr

```python
import polars as pl

# 1. 确保数据已排序
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

## 相关文件

- 修复后的混用版: `/home/quan/testdata/aspipe_v4/debug_mixed_fixed.py`
- 修复后的纯 Polars 版: `/home/quan/testdata/aspipe_v4/debug_pure_polars_fixed.py`
- 回测脚本: `/home/quan/testdata/aspipe_v4/backtest_alpha101_polars.py`

## 参考

- Polars rolling_corr 文档: https://docs.pola.rs/api/python/stable/reference/expressions/api/polars.rolling_corr.html
- 关键参数 `min_samples`: 控制最小样本数，默认为 `window_size`
