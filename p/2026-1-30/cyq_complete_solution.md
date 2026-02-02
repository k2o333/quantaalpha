# Tushare CYQ 接口配置优化完整方案

## 1. 问题背景与分析

### 1.1 当前问题
在使用Tushare的cyq_chips和cyq_perf接口时，发现现有的date_range分页模式无法正常工作，原因是：

1. **cyq_chips接口**：必须提供ts_code参数，不支持仅使用start_date和end_date参数
2. **cyq_perf接口**：虽然支持trade_date参数，但不支持仅使用start_date和end_date参数

### 1.2 现有配置问题
- 两个接口都使用date_range分页模式
- date_range模式只传递start_date和end_date参数
- 接口需要ts_code或trade_date参数，导致调用失败

### 1.3 接口参数需求分析
- **cyq_chips**: 必须提供ts_code参数，支持ts_code + (start_date/end_date) 或 ts_code + trade_date
- **cyq_perf**: 支持ts_code + trade_date，或仅trade_date（获取所有股票），但不支持仅(start_date/end_date)

## 2. 解决方案设计

### 2.1 cyq_chips接口 - 改为stock_loop模式
- **分页模式**: `stock_loop`
- **窗口大小**: `30天`
- **参数流程**: 获取股票列表 → 对每只股票请求 → 参数: ts_code + (start_date/end_date)

### 2.2 cyq_perf接口 - 新增date_range_daily模式
- **分页模式**: `date_range_daily` (扩展现有date_range)
- **窗口大小**: `1天`
- **参数流程**: 获取交易日历 → 对每个交易日请求 → 参数: trade_date + (可选ts_code)

## 3. 代码修改方案

### 3.1 修改分页执行器 (core/pagination_executor.py)

需要在PaginationExecutor类中添加对新分页模式的支持：

```python
def execute_date_range_daily_pagination(
    self, 
    interface_config: Dict[str, Any], 
    params: Dict[str, Any], 
    context: PaginationContext, 
    make_request_callback,
    coverage_manager=None, 
    force_download=False,
    get_trade_calendar_callback=None
) -> List[Dict[str, Any]]:
    """
    按日遍历的分页模式 - 适用于cyq_perf等接口
    将日期范围分解为单个交易日，逐日请求
    """
    start_date = params.get('start_date')
    end_date = params.get('end_date')
    
    if not start_date or not end_date:
        # 如果没有提供日期范围，直接请求
        return make_request_callback(interface_config, params)
    
    # 获取交易日历
    if get_trade_calendar_callback:
        trade_days = get_trade_calendar_callback(start_date, end_date)
        trade_dates = [day['cal_date'] for day in trade_days if day.get('is_open', 0) == 1]
    else:
        # 如果没有交易日历回调，假设所有日期都是交易日
        from datetime import datetime, timedelta
        start = datetime.strptime(start_date, '%Y%m%d')
        end = datetime.strptime(end_date, '%Y%m%d')
        trade_dates = []
        current = start
        while current <= end:
            trade_dates.append(current.strftime('%Y%m%d'))
            current += timedelta(days=1)
    
    all_data = []
    for trade_date in trade_dates:
        # 为每一天创建新的参数
        daily_params = params.copy()
        daily_params['trade_date'] = trade_date
        # 移除可能冲突的日期范围参数
        daily_params.pop('start_date', None)
        daily_params.pop('end_date', None)
        
        # 检查覆盖率，如果已存在则跳过
        if coverage_manager and not force_download:
            should_skip = coverage_manager.should_skip(
                interface_config['api_name'],
                daily_params,
                strategy='daily'
            )
            if should_skip:
                continue
        
        # 发起请求
        daily_data = make_request_callback(interface_config, daily_params)
        if daily_data:
            all_data.extend(daily_data)
    
    return all_data
```

### 3.2 修改分页上下文 (core/pagination.py)

在get_window_size_for_interface函数中添加新模式的支持：

```python
def get_window_size_for_interface(interface_name: str, config: Dict[str, Any]) -> int:
    """获取接口的窗口大小"""
    pagination_config = config.get('pagination', {})
    if not pagination_config.get('enabled', False):
        return 1
    
    mode = pagination_config.get('mode', 'offset')
    if mode == 'date_range_daily':
        return 1  # 每次处理一天
    elif mode == 'stock_loop':
        # 可以根据需要调整，比如一次处理30天的数据
        return pagination_config.get('window_size_days', 30)
    else:
        return pagination_config.get('window_size_days', 365)
```

### 3.3 修改下载器 (core/downloader.py)

在_execute_pagination方法中添加新模式的处理：

```python
elif mode == 'date_range_daily':
    return self.pagination_executor.execute_date_range_daily_pagination(
        interface_config, params, context, self._make_request,
        coverage_manager=self.coverage_manager, force_download=self.force_download,
        get_trade_calendar_callback=self.get_trade_calendar
    )
```

## 4. 配置文件修改

### 4.1 cyq_chips.yaml
```yaml
api_name: cyq_chips
derived_fields:
  trade_date_dt:
    description: 日期类型的trade_date
    format: '%Y%m%d'
    source: trade_date
    type: date
description: 每日筹码分布
name: cyq_chips
output:
  primary_key:
  - ts_code
  - trade_date
  - price
  sort_by:
  - price
pagination:
  enabled: true
  mode: stock_loop  # 改为stock_loop模式
  window_size_days: 30  # 窗口改为30天
parameters:
  end_date:
    description: 结束日期 YYYYMMDD
    required: false
    type: string
  start_date:
    description: 开始日期 YYYYMMDD
    required: false
    type: string
  trade_date:
    description: 交易日期 YYYYMMDD
    required: false
    type: string
  ts_code:
    description: 股票代码
    required: true  # 设为必需
    type: string
permissions:
  min_points: 120
  query_limit: 2000
  rate_limit: 60
request:
  extra_path: ''
  method: POST
  timeout: 30
```

### 4.2 cyq_perf.yaml
```yaml
api_name: cyq_perf
derived_fields:
  trade_date_dt:
    description: 日期类型的trade_date
    format: '%Y%m%d'
    source: trade_date
    type: date
description: 每日筹码及胜率
name: cyq_perf
output:
  primary_key:
  - ts_code
  - trade_date
  sort_by:
  - trade_date
pagination:
  enabled: true
  mode: date_range_daily  # 新增模式：按日遍历
  window_size_days: 1  # 每次处理一天
parameters:
  end_date:
    description: 结束日期 YYYYMMDD
    required: false
    type: string
  start_date:
    description: 开始日期 YYYYMMDD
    required: false
    type: string
  trade_date:
    description: 交易日期 YYYYMMDD
    required: false
    type: string
  ts_code:
    description: 股票代码
    required: false
    type: string
permissions:
  min_points: 120
  query_limit: 5000
  rate_limit: 60
request:
  extra_path: ''
  method: POST
  timeout: 30
```

## 5. 实施步骤

1. **备份现有配置文件**
2. **修改pagination_executor.py** - 添加date_range_daily模式支持
3. **修改pagination.py** - 添加新模式的窗口大小处理
4. **修改downloader.py** - 添加新模式的执行逻辑
5. **更新接口配置文件** - 修改cyq_chips和cyq_perf的配置
6. **测试验证** - 运行测试确保新配置正常工作

## 6. 预期效果

- **cyq_chips接口**将按股票循环获取数据，每个股票获取30天内的筹码分布
- **cyq_perf接口**将按日期循环获取数据，每天获取所有股票或指定股票的筹码及胜率
- 解决了原配置中参数不匹配导致的API调用失败问题
- 提高了数据获取的成功率和效率

## 7. 数据分析补充

根据实际测试，cyq_chips接口返回数据的时间范围分析：
- **最早日期**: 2025年11月11日 (20251111)
- **最晚日期**: 2026年01月30日 (20260130)
- **时间跨度**: 约2个月零19天
- **总数据量**: 6000条记录
- **不同交易日总数**: 57个交易日
- **平均每个交易日数据**: 约105.3条记录

这表明当只提供ts_code参数时，接口返回该股票最近一段时间的所有历史数据，而不是单个交易日的数据。

## 8. 实施状态

- [x] 问题分析完成
- [x] 解决方案设计完成
- [x] 实施计划制定完成
- [ ] 代码修改（待实施）
- [ ] 测试验证（待实施）

## 9. 备注

此方案保持了项目的整体架构不变，仅针对特定接口的分页策略进行了优化，确保了系统的稳定性和可维护性。