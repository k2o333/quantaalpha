# 缓存问题综合摘要

## 发现的问题

在对aspipe_v4系统进行分析后，我们发现了一个广泛的缓存机制不激活问题，不仅限于最初报告的pro_bar接口，而是影响了多个接口类型。

## 主要问题点

1. **并行下载路径绕过缓存**
   - 位置：`app/parallel_downloader.py`第77行
   - 影响：所有通过并行下载器的接口都绕过缓存，包括pro_bar, top10_holders等核心接口

2. **调度器缓存检查不完整**
   - 位置：`app/download_scheduler.py`第640行
   - 问题：只对`['daily', 'daily_basic', 'moneyflow']`三个接口启用缓存，其他日度数据接口直接跳过

3. **tscode_historical模式完全无缓存**
   - 问题：使用`--tscode-historical`、`--holders-data`或`--pro-bar-only`参数的接口完全绕过缓存机制

## 受影响接口分类

### 完全无缓存（最高优先级修复）
- **tscode_historical模式接口**：stk_rewards, top10_holders, pledge_detail, fina_audit, pro_bar
- **问题**：使用并行下载器，完全跳过缓存机制

### 部分无缓存（高优先级修复）
- **其他日度数据接口**：cyq_perf, cyq_chips, stk_factor, stk_factor_pro, moneyflow系列接口
- **问题**：调度器条件判断不完整，导致这些接口不使用缓存

### 正确使用缓存（无需修复）
- **财务数据接口**：income, balancesheet, cashflow, fina_indicator等
- **静态数据接口**：stock_basic, trade_cal等

## 修复建议

1. **立即修复**：修改`parallel_downloader.py`中的`_download_single_task`方法，使用`strategy.download_with_cache()`替代`strategy.download()`
2. **扩展缓存覆盖**：修改`download_scheduler.py`，扩展缓存检查覆盖所有日度数据接口
3. **统一缓存策略**：建立统一的缓存配置机制，避免硬编码

## 预期效果

修复后将显著减少API调用次数，提高下载效率，并节省TuShare积分消耗，特别是对于高频率调用的接口如pro_bar和top10_holders。