# 缓存问题修复建议

## 核心问题

系统中多个接口的缓存机制未被正确激活，导致重复下载相同数据，浪费API调用次数。

## 三大问题点

### 1. 并行下载器完全绕过缓存
**文件**: `app/parallel_downloader.py`
**位置**: 第77行 `_download_single_task` 方法
**问题**: 直接调用 `strategy.download()` 而不是 `strategy.download_with_cache()`

### 2. 调度器缓存检查不完整
**文件**: `app/download_scheduler.py`
**位置**: 第640行条件判断
**问题**: 只有 `['daily', 'daily_basic', 'moneyflow']` 三个接口使用缓存，其他接口直接调用 `strategy.download()`

### 3. tscode_historical模式完全无缓存
**文件**: `app/download_scheduler.py` 和 `app/parallel_downloader.py`
**问题**: 使用ts_code参数的接口（pro_bar, top10_holders等）通过并行下载器处理，完全绕过缓存

## 修复方案

### 方案一：最小改动修复（推荐）

1. **修改并行下载器**
   ```python
   # 在 parallel_downloader.py 第77行
   # 原代码:
   result_df = strategy.download(**adapted_params)
   # 修改为:
   result_df = strategy.download_with_cache(**adapted_params)
   ```

2. **扩展调度器缓存检查**
   ```python
   # 在 download_scheduler.py 第640行
   # 原代码:
   if interface_name in ['daily', 'daily_basic', 'moneyflow']:
   # 修改为:
   if interface_name in ['daily', 'daily_basic', 'moneyflow', 'cyq_perf', 'cyq_chips', 'stk_factor', 'stk_factor_pro', 'moneyflow_dc', 'moneyflow_ths', 'moneyflow_ind_dc', 'moneyflow_mkt_dc', 'moneyflow_cnt_ths', 'moneyflow_ind_ths']:
   ```

### 方案二：统一缓存策略

1. **重构下载策略调用**
   在所有下载路径中统一使用 `strategy.download_with_cache()` 方法

2. **添加配置驱动的缓存控制**
   通过配置文件明确指定哪些接口启用缓存，而不是硬编码在代码中

## 影响范围

### 直接受益接口
- pro_bar（复权行情）
- top10_holders（前十大股东）
- stk_rewards（股票激励）
- pledge_detail（股权质押）
- fina_audit（财务审计）
- cyq_perf, cyq_chips（筹码分布）
- stk_factor, stk_factor_pro（风险因子）
- moneyflow系列（资金流向）

## 验证方法

1. 运行重复下载测试，第二次调用应该显著快于第一次
2. 检查缓存目录是否生成相应文件
3. 添加日志确认缓存命中率提升

## 预期效果

修复后可显著减少API调用次数，提高下载效率，节省TuShare积分消耗。