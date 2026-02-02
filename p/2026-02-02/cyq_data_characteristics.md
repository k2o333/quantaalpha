# cyq_chips / cyq_perf 数据特性与窗口策略分析

## 根据 Tushare 官方文档的关键信息

### 1. 数据时间范围

**cyq_chips (每日筹码分布)**
- 数据起始时间：**2018年起**
- 更新频率：每日下午5-6点更新
- 文档原文：*"Data is available from 2018 and is updated daily between 5-6 PM"*

**cyq_perf (每日筹码及胜率)**
- 数据起始时间：**2018年起**
- 更新频率：每日下午5-6点更新
- 单次请求限制：最多5000条记录
- 文档原文：*"Data is updated daily between 5-6 PM and is available from 2018 onwards"*

### 2. 参数支持情况

两个接口都支持以下参数：
- `ts_code` - 股票代码（可选）
- `trade_date` - 交易日期（可选）
- `start_date` - 开始日期（可选）
- `end_date` - 结束日期（可选）

**关键特性**：当只提供 `ts_code` 而不提供日期范围时，API 会返回该股票的**全历史数据**（从2018年开始）。

## 回答你的问题

### Q1: 窗口分块是从最近开始还是从最远开始？

**取决于 `execute_date_range_pagination` 的实现**。

查看 `pagination.py:100-154` 的 `generate_date_range_params` 方法：

```python
def generate_date_range_params(...):
    # 过滤交易日
    trade_days = [day for day in self.context.trade_calendar
                  if day.get('is_open', 0) == 1 and
                     start_date <= day['cal_date'] <= end_date]
    
    # 排序
    trade_days.sort(key=lambda x: x['cal_date'])
    
    # 生成分窗
    for i in range(0, len(trade_days), window_size):
        window_days = trade_days[i:i + window_size]
```

**结论**：
- `trade_days.sort(key=lambda x: x['cal_date'])` 是按日期**升序排序**（从远到近）
- 窗口生成使用 `range(0, len(trade_days), window_size)`，是**从远到近**遍历
- 所以数据是**从上市日期（最远）开始向现在（最近）**获取

### Q2: 股票早些日子没有数据怎么处理？

根据 Tushare 文档，cyq 接口的数据**从2018年开始**，对于2018年之前上市的股票：

1. **API 行为**：当请求2018年之前的数据时，API 不会报错，但也不会返回数据
2. **实际观察**：从日志中看到 `Downloaded 6000 records`，说明 API 自动返回了从2018年开始的所有可用数据

**当前代码的处理方式**：

在 `download_single_stock` 方法中：
```python
if 'start_date' in parameter_config and 'start_date' not in stock_params:
    list_date = stock.get('list_date', '20050101')
    stock_params['start_date'] = list_date
```

这里使用股票的 `list_date`（上市日期）作为 `start_date`，但如果上市日期早于2018年：
- API 会忽略2018年之前的数据
- 只返回2018年之后的数据

**这是合理的默认行为**，因为：
1. API 本身没有2018年之前的数据
2. 使用 `list_date` 可以确保获取股票的全部可用历史

### Q3: 是否需要窗口分块？

**根据 Tushare 文档的建议**：

1. **cyq_chips**：文档没有明确说明单次请求限制，但返回的是**多行数据**（每个价格点一行）
   - 如果股票历史长、价格波动大，数据量可能很大
   - 建议分窗口以控制单次请求数据量

2. **cyq_perf**：文档明确说明 *"API has a limit of 5000 records per request"*
   - 对于全历史数据，可能超过5000条限制
   - **必须进行分窗口或分页处理**

## 建议的窗口策略

### 方案1：保持现状（不分窗口）

**优点**：
- 代码简单
- 对于单个股票的短期数据，一次请求即可

**缺点**：
- cyq_perf 可能超过5000条限制
- 无法控制单次请求的数据量

### 方案2：实现30天窗口分块（推荐）

**实现方式**：
在 `download_single_stock` 方法中，当 `mode == 'stock_loop'` 时：

```python
elif mode == 'stock_loop':
    window_size_days = pagination_config.get('window_size_days')
    if window_size_days and window_size_days > 0:
        # 使用日期范围分页进行窗口分块
        stock_data = self.pagination_executor.execute_date_range_pagination(
            interface_config, stock_params, context, self._make_request,
            coverage_manager=self.coverage_manager, force_download=self.force_download,
            get_trade_calendar_callback=self.get_trade_calendar
        )
    else:
        stock_data = self._make_request(interface_config, stock_params)
```

**优点**：
- 符合配置文件的 `window_size_days: 30` 设置
- 控制单次请求数据量，避免超过API限制
- 便于增量更新（可以跳过已下载的窗口）

**缺点**：
- 需要修改代码
- 增加请求次数（但可以通过覆盖率检查跳过已下载的窗口）

### 方案3：使用 offset 分页（备选）

cyq_perf 支持 offset/limit 分页，可以在 `cyq_perf.yaml` 中配置：

```yaml
pagination:
  enabled: true
  mode: offset
  limit_key: limit
  offset_key: offset
  default_limit: 5000
```

**优点**：
- 不需要日期窗口分块逻辑
- 自动处理大数据量

**缺点**：
- 不符合当前设计文档的意图
- 增量更新粒度较粗（只能按股票级别跳过）

## 结论

1. **数据方向**：从上市日期（最远）开始向现在（最近）获取
2. **缺失数据处理**：API 自动处理，只返回2018年之后的数据
3. **推荐方案**：实现30天窗口分块，以控制单次请求数据量并支持更细粒度的增量更新
