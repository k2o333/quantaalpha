# 覆盖率检测设计缺陷及混合解决方案

## 问题概述

aspipe_v4系统存在一个**根本性设计缺陷**：对所有接口使用统一的**交易日历覆盖率检测**逻辑，而不同接口的数据特征完全不同，导致多种严重问题。

## 设计缺陷分析

### 缺陷根源

在 `app4/core/coverage_manager.py` 中，硬编码使用交易日历计算覆盖率：

```python
# 只适用于date_range接口的硬编码逻辑
trade_calendar = self.downloader.get_trade_calendar(start_date, end_date)
expected_dates = {day['cal_date'] for day in trade_calendar if day.get('is_open', 0) == 1}
coverage = len(actual_dates & expected_dates) / len(expected_dates)
```

### 为什么这是错误的

| 分页模式 | 数据频率 | 预期记录数计算方式 | 计算结果 | 是否准确 |
|---------|---------|-------------------|---------|---------|
| **date_range** | 每日数据 | 交易日数量 | 正确 | ✅ 准确 |
| **stock_loop** | 季度/年度数据 | 交易日数量 | 严重错误 | ❌ 永远不准 |
| **periodic_range** | 周期性数据 | 交易日数量 | 错误 | ❌ 应该用周期数 |
| **period_range** | 不定期数据 | 交易日数量 | 不适用 | ❌ 无法计算 |

**示例：income_vip接口**
- 查询20240101-20240405（61个交易日）
- 实际数据：1条（2024Q1财报）
- 系统计算：覆盖率 = 1/61 ≈ 1.64%
- 系统决策："覆盖率太低，下载完整范围" → 重复调用API

## 导致的三个严重问题

### 问题1：API重复调用（stock_loop接口）

**现象**：stock_loop接口每次运行都重复调用API

**原因**：
- stock_loop模式用于季度/年度数据（income_vip等）
- 用交易日历计算覆盖率永远<95%
- 系统认为"覆盖率太低"，强制下载完整范围

**影响**：浪费API积分，下载速度慢

### 问题2：数据永久缺失（date_range接口）

**现象**：daily等接口达到95%覆盖率后，5%的缺失数据永远无法补上

**原因**：
```python
# coverage_manager.py:412-414
if coverage >= threshold:  # threshold = 0.95
    result = ('skip', [], "跳过下载")  # ❌ 直接跳过，不检查缺失
```

**影响**：数据完整性无法保证，某些交易日的数据永远缺失

### 问题3：修正数据丢失（去重逻辑缺陷）

**现象**：财报修正公告的数据被错误跳过

**原因**：
- 去重基于主键 `[ts_code, ann_date, end_date]`
- 修正公告的主键与原始公告完全相同
- 系统认为"主键已存在"，跳过新记录
- **完全忽略`update_flag`字段**（标记是否最新）

**影响**：数据不准确，无法获取最新的修正数据

## 混合解决方案

### 方案D：修复date_range接口的阈值逻辑

**适用范围**：`pagination.mode = date_range` 且数据频率=每日

**适用接口**（约15个）：
- daily, daily_basic
- moneyflow系列（moneyflow, moneyflow_ths等）
- cyq_chips, cyq_perf
- stock_hsgt, suspend_d
- 其他每日行情类接口

**修改内容**：

```python
# 文件：app4/core/coverage_manager.py:411-422

# 原有缺陷逻辑（删除）
if coverage >= threshold:
    result = ('skip', [], f"Coverage {coverage:.2%} >= threshold {threshold:.2%}, skipping")
elif coverage > 0.3 and missing_ranges:
    result = ('download_partial', missing_ranges, ...)
else:
    result = ('download_full', [(start_date, end_date)], ...)

# 修改为正确逻辑
if coverage >= 1.0:  # 100%覆盖才完全跳过
    result = ('skip', [], "完全覆盖，跳过")
elif coverage >= threshold:  # 95%覆盖但有缺失 → 增量下载
    result = ('download_partial', missing_ranges,
              f"Coverage {coverage:.2%} >= threshold {threshold:.2%}, downloading missing {len(missing_ranges)} ranges")
elif coverage > 0.3:  # 30%-95%覆盖 → 增量下载
    result = ('download_partial', missing_ranges,
              f"Coverage {coverage:.2%} with {len(missing_ranges)} missing ranges, downloading partial")
else:  # <30%覆盖 → 完整下载
    result = ('download_full', [(start_date, end_date)],
              f"Coverage {coverage:.2%} too low, downloading full range")
```

**效果**：
- 覆盖率≥95%但<100%时，**增量下载缺失部分**
- 覆盖率100%时，**完全跳过**
- 覆盖率30%-95%时，**增量下载**
- 覆盖率<30%时，**完整下载**

### 方案E：禁用stock_loop接口的日期覆盖检测

**适用范围**：`pagination.mode = stock_loop` 且数据频率=季度/年度

**适用接口**（约12个）：
- income_vip, income
- fina_indicator_vip
- express_vip, express
- balancesheet_vip, balancesheet
- cashflow_vip, cashflow
- top10_holders, top10_floatholders
- disclosure_date, fina_audit

**修改内容**：

```python
# 文件：app4/core/downloader.py:304-313（在_get_missing_date_ranges调用前）

# 原有逻辑（所有接口都调用覆盖率检测）
decision, ranges, message = self.coverage_manager.get_missing_date_ranges(
    interface_config['api_name'],
    window_start,
    window_end,
    **{k: v for k, v in window_params.items() if k not in ['start_date', 'end_date']}
)

# 修改为：stock_loop模式跳过日期覆盖检测
pagination_config = interface_config.get('pagination', {})
if pagination_config.get('mode') == 'stock_loop':
    # stock_loop模式不使用日期范围覆盖检测
    logger.info(f"Stock loop mode detected for {interface_config['api_name']}, skipping date range coverage check")
    
    # 改用股票存在性检测
    if self.coverage_manager:
        should_skip = self.coverage_manager.should_skip(
            interface_config['api_name'],
            window_params,
            strategy='stock'  # 检查股票是否存在
        )
        if should_skip:
            logger.info(f"Skipping window {window_start}-{window_end} for {interface_config['api_name']} (already exists)")
            continue
    
    # 不跳过则下载完整范围
    decision = 'download_full'
    ranges = [(window_start, window_end)]
    message = "Stock loop mode, downloading full range"
else:
    # 原有逻辑（包括方案D的修改）
    decision, ranges, message = self.coverage_manager.get_missing_date_ranges(...)
```

**效果**：
- stock_loop接口**不再使用错误的交易日历计算**
- 改用**股票存在性检测**（检查该股票是否已有数据）
- 避免重复调用API

### 方案H：禁用财报接口的主键去重

**适用范围**：财报类接口（income_vip, balancesheet_vip等）

**原因**：
- 财报有**补充公告**（不同ann_date）
- 财报有**修正公告**（相同主键，数据更新）
- 现有去重逻辑会**丢失修正数据**
- **不应基于主键去重**，应保留所有版本

**修改内容**：

```yaml
# 文件：app4/config/interfaces/income_vip.yaml

# 原有配置
dedup:
  enabled: true
  strategy: "primary_key"
  columns: ["ts_code", "ann_date", "end_date"]

# 修改为
dedup:
  enabled: false  # 禁用去重，保留所有版本

# 依赖update_flag字段在查询时选择最新记录
```

**查询时的处理**：

```python
# 查询时根据update_flag选择最新记录
df = pl.read_parquet('data/income_vip')
latest_df = df.filter(pl.col('update_flag') == '1')  # 只选最新记录
```

**效果**：
- 保留所有版本（原始公告、补充公告、修正公告）
- 不会丢失任何数据
- 查询时通过update_flag筛选最新记录

## 实施计划

### P0：立即修复（影响最大）

**方案E**：修复stock_loop接口的API重复调用问题
- 文件：`app4/core/downloader.py`
- 修改：添加stock_loop模式检查
- 测试：`python main.py --interface income_vip --ts_code 000002.SZ`
- 预期：第二次运行不调用API

### P1：本周修复（数据完整性）

**方案D**：修复date_range接口的95%阈值缺陷
- 文件：`app4/core/coverage_manager.py`
- 修改：调整覆盖率决策逻辑
- 测试：`python main.py --interface daily --ts_code 000001.SZ --start_date 20240101 --end_date 20240131`
- 预期：98%覆盖率时只下载缺失的2%日期

### P2：下周修复（数据准确性）

**方案H**：禁用财报接口的主键去重
- 文件：`app4/config/interfaces/income_vip.yaml`等
- 修改：`dedup.enabled = false`
- 测试：下载有修正公告的股票，验证是否保留两个版本
- 预期：保留原始公告和修正公告

## 验证方法

### 验证方案E（stock_loop接口）

```bash
# 第一次运行
python main.py --interface income_vip --ts_code 000002.SZ --start_date 20240101 --end_date 20240405
# 预期：调用API，下载1条记录

# 第二次运行
python main.py --interface income_vip --ts_code 000002.SZ --start_date 20240101 --end_date 20240405
# 预期：不调用API，直接跳过
```

### 验证方案D（date_range接口）

```bash
# 1. 先下载完整数据
python main.py --interface daily --ts_code 000001.SZ --start_date 20240101 --end_date 20240131

# 2. 删除其中几天的数据（模拟缺失）
# 手动删除data/daily/daily_*.parquet中的部分文件

# 3. 重新下载
python main.py --interface daily --ts_code 000001.SZ --start_date 20240101 --end_date 20240131
# 预期：只下载缺失的那几天，而不是完整31天
```

### 验证方案H（去重逻辑）

```bash
# 下载有修正公告的股票
python main.py --interface income_vip --ts_code 600519.SH --start_date 20240101 --end_date 20240405

# 检查数据
python -c "
import polars as pl
df = pl.read_parquet('data/income_vip')
print('总记录数:', len(df))
print('按(ts_code,end_date)分组:', df.groupby(['ts_code', 'end_date']).agg(pl.count()).sort('end_date'))
"
# 预期：如果有修正公告，同一end_date会有多条记录
```

## 总结

### 核心结论

1. **必须混合使用方案D和E**：因为不同分页模式需要完全不同的处理逻辑
2. **方案D只适用于date_range接口**：这是唯一能用交易日历计算覆盖率的接口类型
3. **方案E适用于stock_loop接口**：必须禁用错误的日期覆盖检测
4. **方案H适用于财报接口**：避免去重逻辑丢失修正数据

### 根本原因

这是**设计缺陷**导致的必然结果：
- 硬编码交易日历计算覆盖率
- 一刀切地应用于所有接口
- 忽略不同接口的数据特征差异

### 最终建议

按优先级顺序实施：
1. **立即**：方案E（减少API浪费）
2. **本周**：方案D（保证数据完整性）
3. **下周**：方案H（保证数据准确性）

这样可以系统性地解决所有问题，而不是只治标不治本。
