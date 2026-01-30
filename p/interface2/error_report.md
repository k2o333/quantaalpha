# aspipe_v4 Interface2 错误报告

生成时间: 2026-01-30
输出目录: /home/quan/testdata/aspipe_v4/p/interface2/output

## 错误分类汇总

### 1. scan_parquet() 参数错误 (ERROR)

**问题描述**: 预加载交易日历时，`scan_parquet()` 函数接收到了不支持的参数 `extra_columns`

**影响范围**: 15个接口文件
- top10_holders.txt
- top10_floatholders.txt
- stk_rewards.txt
- stk_factor_pro.txt
- pledge_stat.txt
- pledge_detail.txt
- income_vip.txt
- forecast_vip.txt
- fina_mainbz_vip.txt
- fina_indicator_vip.txt
- fina_audit.txt
- express_vip.txt
- dividend.txt
- disclosure_date.txt
- cashflow_vip.txt

**错误示例**:
```
2026-01-30 17:06:16,914 - core.cache_warmer - ERROR - 预加载交易日历失败: scan_parquet() got an unexpected keyword argument 'extra_columns'
```

**建议修复**: 检查 `core.cache_warmer` 模块中调用 `scan_parquet()` 的代码，移除或替换 `extra_columns` 参数

---

### 2. 股票列表路径错误 (ERROR)

**问题描述**: 预加载股票列表时，传入的路径 `data/stock_basic` 是一个目录而不是文件

**影响范围**: 15个接口文件（同上）

**错误示例**:
```
2026-01-30 17:06:16,915 - core.cache_warmer - ERROR - 预加载股票列表失败: expected a file path; 'data/stock_basic' is a directory
```

**建议修复**: 
- 检查 `data/stock_basic` 目录结构，确认正确的文件路径
- 修改代码以读取目录中的文件，或指定具体的文件名

---

### 3. 读取股票列表失败 (WARNING)

**问题描述**: 从 Data 目录读取股票列表失败，路径 `data/stock_basic` 是目录而非文件

**影响范围**: 15个接口文件（同上）

**错误示例**:
```
2026-01-30 17:06:17,648 - core.downloader - WARNING - Failed to read stock list from Data dir: expected a file path; 'data/stock_basic' is a directory
```

**建议修复**: 同错误 #2

---

### 4. delist_date 字段缺失 (WARNING)

**问题描述**: 无法推导 `delist_date_dt` 字段，因为数据源中缺少 `delist_date` 列

**影响范围**: 所有16个接口文件

**错误示例**:
```
2026-01-30 17:06:18,803 - core.schema_manager - WARNING - Failed to derive field delist_date_dt: unable to find column 'delist_date'; valid columns: ['ts_code', 'symbol', 'name', 'area', 'industry', 'cnspell', 'market', 'list_date', 'act_name', 'act_ent_type', 'exchange', 'list_status', 'is_hs', '_update_time']
```

**建议修复**: 
- 更新数据源以包含 `delist_date` 字段
- 或修改 schema_manager 以处理该字段缺失的情况

---

### 5. 重复记录警告 (WARNING)

**问题描述**: 在数据处理过程中发现重复记录

**影响范围**: 12个接口文件

| 接口名称 | 重复记录数 |
|---------|----------|
| fina_indicator_vip | 107 |
| top10_floatholders | 541 |
| top10_holders | 114 |
| balancesheet_vip | 38 |
| income_vip | 13 |
| cashflow_vip | 13 |
| forecast_vip | 9 |
| pledge_detail | 3 |
| fina_mainbz_vip | 3 |

**错误示例**:
```
2026-01-30 17:06:19,448 - core.processor - WARNING - Found 114 duplicate records for interface top10_holders
```

**建议修复**: 
- 检查数据源是否存在重复
- 优化去重逻辑
- 确认是否需要保留重复记录

---

### 6. 无数据下载警告 (WARNING)

**问题描述**: 某些接口没有下载到任何数据

**影响范围**: 4个接口文件

| 接口名称 |
|---------|
| stk_rewards |
| pledge_stat |
| dividend |
| disclosure_date |

**错误示例**:
```
2026-01-30 17:06:11,865 - __main__ - WARNING - No data downloaded for stk_rewards
```

**建议修复**: 
- 检查 API 接口是否正常
- 确认查询参数是否正确
- 检查网络连接

---

### 7. 目录不存在警告 (WARNING)

**问题描述**: 交易日历或股票列表目录不存在

**影响范围**: 1个接口文件 (balancesheet_vip.txt)

**错误示例**:
```
2026-01-30 17:04:18,986 - core.cache_warmer - WARNING - 交易日历目录不存在: data/trade_cal
2026-01-30 17:04:18,987 - core.cache_warmer - WARNING - 股票列表目录不存在: data/stock_basic
```

**建议修复**: 
- 创建缺失的目录
- 或配置正确的目录路径

---

## 按文件详细错误列表

### balancesheet_vip.txt
- WARNING - 交易日历目录不存在: data/trade_cal
- WARNING - 股票列表目录不存在: data/stock_basic
- WARNING - Failed to derive field delist_date_dt
- WARNING - Found 38 duplicate records

### cashflow_vip.txt
- ERROR - 预加载交易日历失败: scan_parquet() got an unexpected keyword argument 'extra_columns'
- ERROR - 预加载股票列表失败: expected a file path; 'data/stock_basic' is a directory
- WARNING - Failed to read stock list from Data dir
- WARNING - Failed to derive field delist_date_dt
- WARNING - Found 13 duplicate records

### disclosure_date.txt
- ERROR - 预加载交易日历失败: scan_parquet() got an unexpected keyword argument 'extra_columns'
- ERROR - 预加载股票列表失败: expected a file path; 'data/stock_basic' is a directory
- WARNING - Failed to read stock list from Data dir
- WARNING - Failed to derive field delist_date_dt
- WARNING - No data downloaded

### dividend.txt
- ERROR - 预加载交易日历失败: scan_parquet() got an unexpected keyword argument 'extra_columns'
- ERROR - 预加载股票列表失败: expected a file path; 'data/stock_basic' is a directory
- WARNING - Failed to read stock list from Data dir
- WARNING - Failed to derive field delist_date_dt
- WARNING - No data downloaded

### express_vip.txt
- ERROR - 预加载交易日历失败: scan_parquet() got an unexpected keyword argument 'extra_columns'
- ERROR - 预加载股票列表失败: expected a file path; 'data/stock_basic' is a directory
- WARNING - Failed to read stock list from Data dir
- WARNING - Failed to derive field delist_date_dt

### fina_audit.txt
- ERROR - 预加载交易日历失败: scan_parquet() got an unexpected keyword argument 'extra_columns'
- ERROR - 预加载股票列表失败: expected a file path; 'data/stock_basic' is a directory
- WARNING - Failed to read stock list from Data dir
- WARNING - Failed to derive field delist_date_dt

### fina_indicator_vip.txt
- ERROR - 预加载交易日历失败: scan_parquet() got an unexpected keyword argument 'extra_columns'
- ERROR - 预加载股票列表失败: expected a file path; 'data/stock_basic' is a directory
- WARNING - Failed to read stock list from Data dir
- WARNING - Failed to derive field delist_date_dt
- WARNING - Found 107 duplicate records

### fina_mainbz_vip.txt
- ERROR - 预加载交易日历失败: scan_parquet() got an unexpected keyword argument 'extra_columns'
- ERROR - 预加载股票列表失败: expected a file path; 'data/stock_basic' is a directory
- WARNING - Failed to read stock list from Data dir
- WARNING - Failed to derive field delist_date_dt
- WARNING - Found 3 duplicate records

### forecast_vip.txt
- ERROR - 预加载交易日历失败: scan_parquet() got an unexpected keyword argument 'extra_columns'
- ERROR - 预加载股票列表失败: expected a file path; 'data/stock_basic' is a directory
- WARNING - Failed to read stock list from Data dir
- WARNING - Failed to derive field delist_date_dt
- WARNING - Found 9 duplicate records

### income_vip.txt
- ERROR - 预加载交易日历失败: scan_parquet() got an unexpected keyword argument 'extra_columns'
- ERROR - 预加载股票列表失败: expected a file path; 'data/stock_basic' is a directory
- WARNING - Failed to read stock list from Data dir
- WARNING - Failed to derive field delist_date_dt
- WARNING - Found 13 duplicate records

### pledge_detail.txt
- ERROR - 预加载交易日历失败: scan_parquet() got an unexpected keyword argument 'extra_columns'
- ERROR - 预加载股票列表失败: expected a file path; 'data/stock_basic' is a directory
- WARNING - Failed to read stock list from Data dir
- WARNING - Failed to derive field delist_date_dt
- WARNING - Found 3 duplicate records

### pledge_stat.txt
- ERROR - 预加载交易日历失败: scan_parquet() got an unexpected keyword argument 'extra_columns'
- ERROR - 预加载股票列表失败: expected a file path; 'data/stock_basic' is a directory
- WARNING - Failed to read stock list from Data dir
- WARNING - Failed to derive field delist_date_dt
- WARNING - No data downloaded

### stk_factor_pro.txt
- ERROR - 预加载交易日历失败: scan_parquet() got an unexpected keyword argument 'extra_columns'
- ERROR - 预加载股票列表失败: expected a file path; 'data/stock_basic' is a directory
- WARNING - Failed to read stock list from Data dir
- WARNING - Failed to derive field delist_date_dt

### stk_rewards.txt
- ERROR - 预加载交易日历失败: scan_parquet() got an unexpected keyword argument 'extra_columns'
- ERROR - 预加载股票列表失败: expected a file path; 'data/stock_basic' is a directory
- WARNING - Failed to read stock list from Data dir
- WARNING - Failed to derive field delist_date_dt
- WARNING - No data downloaded

### top10_floatholders.txt
- ERROR - 预加载交易日历失败: scan_parquet() got an unexpected keyword argument 'extra_columns'
- ERROR - 预加载股票列表失败: expected a file path; 'data/stock_basic' is a directory
- WARNING - Failed to read stock list from Data dir
- WARNING - Failed to derive field delist_date_dt
- WARNING - Found 541 duplicate records

### top10_holders.txt
- ERROR - 预加载交易日历失败: scan_parquet() got an unexpected keyword argument 'extra_columns'
- ERROR - 预加载股票列表失败: expected a file path; 'data/stock_basic' is a directory
- WARNING - Failed to read stock list from Data dir
- WARNING - Failed to derive field delist_date_dt
- WARNING - Found 114 duplicate records

---

## 优先修复建议

### 高优先级
1. **修复 scan_parquet() 参数错误** - 影响所有接口的核心功能
2. **修复股票列表路径错误** - 影响所有接口的数据读取
3. **修复 delist_date 字段缺失问题** - 影响所有接口的数据完整性

### 中优先级
4. **处理重复记录** - 影响数据质量，特别是 top10_floatholders (541条) 和 fina_indicator_vip (107条)
5. **调查无数据下载问题** - 影响4个接口的数据获取

### 低优先级
6. **创建缺失目录** - 仅影响 balancesheet_vip.txt

---

## 统计摘要

- 总共检查文件数: 16
- 发现错误行数: 76
- ERROR 级别: 30
- WARNING 级别: 46
- 受影响接口数: 16
