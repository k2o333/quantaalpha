# 完整日期范围数据下载方案

## 1. 当前系统分析与问题识别

### 1.1 当前实现的不足
- **数据完整性不足**：目前系统只下载各数据类型的最新快照，而非指定日期范围内的完整数据
- **日期参数未充分利用**：`--start_date` 和 `--end_date` 参数仅在日志中显示，未实际用于数据过滤
- **交易日数据缺失**：对于需要逐日获取的数据（如 daily_basic），系统未实现日期范围内循环下载
- **历史数据覆盖**：新数据可能覆盖旧数据，而非增量更新

### 1.2 现有数据类型分类
根据Tushare数据特点，将数据分为以下几类：

1. **静态数据**：stock_basic, stock_company (更新频率低)
2. **日度数据**：daily, daily_basic, moneyflow (每个交易日更新)
3. **财务数据**：income, balancesheet, cashflow (按季度/年度发布)
4. **事件数据**：dividend, forecast, express (事件发生时更新)
5. **股东数据**：top10_holders, stk_rewards (定期更新)
6. **其他数据**：namechange, stk_managers (根据需要更新)

## 2. 完整日期范围下载方案设计

### 2.1 设计目标
- 实现完整日期范围内所有交易日数据的下载
- 根据数据类型特点采用不同的下载策略
- 确保数据完整性和一致性
- 支持增量更新功能

### 2.2 数据下载策略

#### A. 静态数据下载策略
- **下载频率**：每周或每月更新一次
- **日期范围**：不依赖日期范围，仅需获取最新版本
- **存储方式**：覆盖式存储 (单文件)

#### B. 日度数据下载策略  
- **下载频率**：按指定日期范围，逐交易日下载
- **日期范围**：严格按 start_date 到 end_date 下载
- **存储方式**：按日期分区存储 (年/月/日)
- **策略示例**：根据交易日历循环下载每天数据

#### C. 财务数据下载策略
- **下载频率**：按报告期下载
- **日期范围**：下载报告期在指定范围内的数据
- **存储方式**：按报告期存储
- **策略示例**：下载2025年及以后发布的财务报告

#### D. 事件数据下载策略
- **下载频率**：按日期范围下载
- **日期范围**：下载公告日期在指定范围内的数据
- **存储方式**：按年月分区存储

### 2.3 分区存储方案

```
data/
├── basic/                 # 静态数据
│   └── stock_basic.parquet
├── daily/                 # 日度数据
│   ├── 2025/
│   │   ├── 01/
│   │   │   ├── daily_20250105.parquet
│   │   │   ├── daily_basic_20250105.parquet
│   │   │   └── moneyflow_20250105.parquet
│   │   └── 02/
│   │       └── ...
├── financial/             # 财务数据
│   ├── income.parquet
│   ├── balancesheet.parquet
│   └── cashflow.parquet
├── events/                # 事件数据
│   ├── 2025/
│   │   ├── 01/
│   │   │   ├── dividend_202501.parquet
│   │   │   └── forecast_202501.parquet
│   └── ...
└── holders/               # 股东数据
    └── ...
```

### 2.4 实现方案

#### 2.4.1 交易日历处理
- 首先获取指定日期范围内的交易日历
- 对日度数据，仅在交易日进行下载
- 对非交易日，跳过下载以提高效率

#### 2.4.2 日期范围下载逻辑
```python
def download_by_date_range(data_type, start_date, end_date):
    if is_daily_type(data_type):
        # 根据交易日历，逐日下载
        trading_days = get_trading_days(start_date, end_date)
        for trade_date in trading_days:
            download_single_day(data_type, trade_date)
    elif is_financial_type(data_type):
        # 获取报告期数据
        download_financial_data(start_date, end_date)
    else:
        # 静态数据或事件数据，按需处理
        download_by_type(data_type, start_date, end_date)
```

#### 2.4.3 增量更新机制
- 记录上次下载的日期和状态
- 支持断点续传
- 对于已存在的文件，可选择跳过或覆盖

## 3. 技术实现方案

### 3.1 核心类设计
创建 `DateRangeDownloader` 类处理日期范围下载逻辑：

```python
class DateRangeDownloader:
    def __init__(self, start_date, end_date):
        self.start_date = start_date
        self.end_date = end_date
        self.trading_calendar = self.load_trading_calendar()
        
    def download_all_types(self):
        """下载所有类型的数据"""
        available_types = self.get_available_types_by_score()
        
        for data_type in available_types:
            self.download_by_type(data_type)
            
    def download_daily_data(self, data_type):
        """下载日度数据"""
        trading_days = self.get_trading_days_in_range()
        for trade_date in trading_days:
            self.download_single_day(data_type, trade_date)
```

### 3.2 日期范围参数处理
- 支持 `--start_date`, `--end_date` 参数
- 验证日期格式和有效性
- 自动获取交易日历用于日度数据下载

### 3.3 存储管理
- 实现分区存储策略
- 确保文件命名规范
- 支持数据去重和完整性检查

## 4. 实施计划

### 第一阶段：基础架构开发
1. 创建 `DateRangeDownloader` 类
2. 实现交易日历处理功能
3. 开发分区存储管理器

### 第二阶段：数据类型适配
1. 适配各类数据的日期范围下载逻辑
2. 实现增量更新功能
3. 添加错误处理和重试机制

### 第三阶段：测试与优化
1. 全面测试各种数据类型的下载
2. 验证数据完整性和准确性
3. 性能优化

## 5. 预期效果

1. **数据完整性**：实现指定日期范围内所有交易日数据的完整下载
2. **存储优化**：按日期分区存储，便于管理和查询
3. **效率提升**：增量更新，避免重复下载
4. **扩展性**：支持多种日期范围和数据类型组合

## 6. 风险与注意事项

1. **API频次限制**：按日下载会增加API调用次数，需要实现有效的频次控制
2. **存储空间**：分区存储可能增加文件数量，需要考虑存储管理
3. **数据一致性**：确保跨日期的数据一致性，避免数据丢失
4. **错误处理**：处理下载失败、网络中断等异常情况