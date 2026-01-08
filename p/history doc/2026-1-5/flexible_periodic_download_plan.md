# Dividend接口灵活时间周期下载方案

## 问题描述

当前dividend（分红送股）接口存在数据返回限制问题：
- API对单次请求返回数据量有限制（约2000条记录）
- 即使按季度分割，某些季度的数据量仍可能超过限制
- 需要更灵活的时间周期分割策略

## 当前系统状态

### dividend接口特性
- 接口名称：dividend
- 支持参数：ts_code, ann_date, record_date, ex_date, imp_ann_date
- 数据限制：单次请求约2000条记录
- 分页配置：支持多种分页模式

### 现有分页模式
- offset: 基于偏移量的分页
- date_range: 基于日期范围的分页
- stock_loop: 基于股票循环的分页
- period_range: 基于报告期的分页
- quarterly_range: 基于季度的分页（新添加）

## 解决方案

### 1. 新增灵活时间周期分页模式

在 `/home/quan/testdata/aspipe_v4/app4/core/downloader.py` 中添加新的分页方法：

```python
def _execute_periodic_pagination(self, interface_config: Dict[str, Any],
                                params: Dict[str, Any],
                                pagination_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    执行周期性时间范围分页
    根据配置的时间周期类型（周/月/季度/年）分割日期范围
    """
    all_data = []

    # 获取日期范围
    start_date = params.get('start_date', '20050101')
    end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))

    # 获取周期类型，默认为月
    period_type = pagination_config.get('period_type', 'month')
    
    # 生成时间分割范围
    time_ranges = self._generate_time_ranges(start_date, end_date, period_type)

    # 为每个时间范围发起请求
    for idx, (range_start, range_end) in enumerate(time_ranges):
        range_params = params.copy()
        range_params['start_date'] = range_start
        range_params['end_date'] = range_end

        logger.info(f"Downloading dividend data for {period_type} range {idx+1}/{len(time_ranges)}: {range_start} - {range_end}")

        # 发起请求
        range_data = self._make_request(interface_config, range_params)

        if range_data:
            all_data.extend(range_data)
            logger.info(f"Downloaded {len(range_data)} records for {period_type} range {range_start}-{range_end}")
        else:
            logger.warning(f"No data returned for {period_type} range {range_start}-{range_end}")

    return all_data

def _generate_time_ranges(self, start_date: str, end_date: str, period_type: str) -> List[tuple]:
    """
    生成时间分割范围
    根据周期类型将日期范围分割为多个时间段
    
    Args:
        start_date: 开始日期 (YYYYMMDD)
        end_date: 结束日期 (YYYYMMDD)
        period_type: 周期类型 ('week', 'month', 'quarter', 'year')
    
    Returns:
        List of (start_date, end_date) tuples
    """
    from datetime import datetime, timedelta

    start_dt = datetime.strptime(start_date, '%Y%m%d')
    end_dt = datetime.strptime(end_date, '%Y%m%d')

    time_ranges = []
    current = start_dt

    while current <= end_dt:
        if period_type == 'week':
            # 计算当前周的结束日期（周日）
            days_until_sunday = 6 - current.weekday()  # Monday is 0, Sunday is 6
            period_end = current + timedelta(days=days_until_sunday)
        elif period_type == 'month':
            # 计算当前月的结束日期
            if current.month == 12:
                period_end = datetime(current.year + 1, 1, 1) - timedelta(days=1)
            else:
                period_end = datetime(current.year, current.month + 1, 1) - timedelta(days=1)
        elif period_type == 'quarter':
            # 计算当前季度的结束日期
            if current.month <= 3:
                period_end = datetime(current.year, 3, 31)
            elif current.month <= 6:
                period_end = datetime(current.year, 6, 30)
            elif current.month <= 9:
                period_end = datetime(current.year, 9, 30)
            else:
                period_end = datetime(current.year, 12, 31)
        elif period_type == 'year':
            # 计算当前年的结束日期
            period_end = datetime(current.year, 12, 31)
        else:
            # 默认按月
            if current.month == 12:
                period_end = datetime(current.year + 1, 1, 1) - timedelta(days=1)
            else:
                period_end = datetime(current.year, current.month + 1, 1) - timedelta(days=1)

        # 如果周期结束日期超过总结束日期，则使用总结束日期
        if period_end > end_dt:
            period_end = end_dt

        # 确定范围开始日期
        range_start = current.strftime('%Y%m%d')
        range_end = period_end.strftime('%Y%m%d')
        time_ranges.append((range_start, range_end))

        # 移动到下一个周期
        if period_type == 'week':
            current = period_end + timedelta(days=1)
        elif period_type == 'month':
            if period_end.month == 12:
                current = datetime(period_end.year + 1, 1, 1)
            else:
                current = datetime(period_end.year, period_end.month + 1, 1)
        elif period_type == 'quarter':
            if period_end.month == 3:
                current = datetime(period_end.year, 4, 1)
            elif period_end.month == 6:
                current = datetime(period_end.year, 7, 1)
            elif period_end.month == 9:
                current = datetime(period_end.year, 10, 1)
            else:
                current = datetime(period_end.year + 1, 1, 1)
        elif period_type == 'year':
            current = datetime(period_end.year + 1, 1, 1)

    return time_ranges
```

### 2. 修改分页执行逻辑

在 `_execute_pagination` 方法中添加周期性分页模式支持：

```python
def _execute_pagination(self, interface_config: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """执行分页/循环逻辑"""
    pagination_config = interface_config.get('pagination', {})
    if not pagination_config.get('enabled', False):
        # 不分页，直接请求
        return self._make_request(interface_config, params)

    mode = pagination_config.get('mode', 'offset')
    all_data = []

    if mode == 'offset':
        all_data = self._execute_offset_pagination(interface_config, params, pagination_config)
    elif mode == 'date_range':
        all_data = self._execute_date_range_pagination(interface_config, params, pagination_config)
    elif mode == 'stock_loop':
        all_data = self._execute_stock_loop_pagination(interface_config, params)
    elif mode == 'period_range':
        all_data = self._execute_period_range_pagination(interface_config, params, pagination_config)
    elif mode == 'quarterly_range':
        # 保持现有季度范围分页（兼容性）
        all_data = self._execute_quarterly_pagination(interface_config, params, pagination_config)
    elif mode == 'periodic_range':
        # 新增：周期性时间范围分页
        all_data = self._execute_periodic_pagination(interface_config, params, pagination_config)
    else:
        # 默认不分页
        all_data = self._make_request(interface_config, params)

    return all_data
```

### 3. 更新dividend接口配置

修改 `/home/quan/testdata/aspipe_v4/app4/config/interfaces/dividend.yaml`：

```yaml
name: dividend
api_name: dividend
description: "分红送股"

permissions:
  min_points: 2000
  rate_limit: 60
  query_limit: 10000

request:
  method: POST
  extra_path: ""
  timeout: 30

parameters:
  ts_code:
    type: string
    required: false
    description: "TS代码"
  ann_date:
    type: string
    required: false
    description: "公告日 YYYYMMDD"
  record_date:
    type: string
    required: false
    description: "股权登记日期 YYYYMMDD"
  ex_date:
    type: string
    required: false
    description: "除权除息日 YYYYMMDD"
  imp_ann_date:
    type: string
    required: false
    description: "实施公告日 YYYYMMDD"

pagination:
  enabled: true          # 启用分页
  mode: periodic_range   # 使用周期性时间范围分页模式
  period_type: month     # 按月分割时间范围 (可选: week, month, quarter, year)

output:
  primary_key: ["ts_code", "end_date", "ann_date"]
  sort_by: ["ann_date"]
  columns:
    ts_code: {type: string, required: true}
    end_date: {type: date, format: "%Y%m%d", required: true}
    ann_date: {type: date, format: "%Y%m%d", required: true}
    div_proc: {type: string}
    stk_div: {type: float}
    stk_bo_rate: {type: float}
    stk_co_rate: {type: float}
    cash_div: {type: float}
    cash_div_tax: {type: float}
    record_date: {type: date, format: "%Y%m%d"}
    ex_date: {type: date, format: "%Y%m%d"}
    pay_date: {type: date, format: "%Y%m%d"}
    div_listdate: {type: date, format: "%Y%m%d"}
    imp_ann_date: {type: date, format: "%Y%m%d"}
    base_date: {type: date, format: "%Y%m%d"}
    base_share: {type: float}
```

### 4. 配置参数说明

在 `pagination` 配置中新增参数：

- `mode`: 分页模式，设为 `periodic_range` 启用灵活时间周期分页
- `period_type`: 时间周期类型，可选值：
  - `week`: 按周分割
  - `month`: 按月分割
  - `quarter`: 按季度分割
  - `year`: 按年分割

## 实现效果

通过以上修改，dividend接口将能够：

1. **灵活配置时间周期**：通过配置文件选择按周/月/季度/年分割
2. **避免数据截断**：根据配置的时间周期自动分割日期范围
3. **保持数据完整性**：确保所有日期范围内的数据都被获取
4. **向后兼容**：保留现有的季度分页模式

例如：
- 配置 `period_type: month`，请求 2023-01-01 到 2023-03-31 会分割为 [2023-01-01, 2023-01-31], [2023-02-01, 2023-02-28], [2023-03-01, 2023-03-31]
- 配置 `period_type: week`，请求会被按周分割

## 测试验证

修改完成后，需要进行以下测试：

1. **配置测试**：验证不同周期类型的配置是否正确读取
2. **时间范围生成测试**：验证各种周期类型的时间范围生成是否正确
3. **数据完整性测试**：验证分割后的数据是否完整
4. **性能测试**：确保分页不会显著影响下载性能