# Dividend接口季度周期下载方案

## 问题描述

当前dividend（分红送股）接口存在数据返回限制问题：
- API对单次请求返回数据量有限制（约2000条记录）
- 当使用大日期范围（如10年）时，返回数据被截断
- 需要按季度周期分割日期范围以获取完整数据

## 当前系统状态

### dividend接口特性
- 接口名称：dividend
- 支持参数：ts_code, ann_date, record_date, ex_date, imp_ann_date
- 数据限制：单次请求约2000条记录
- 分页配置：pagination.enabled: false

### 现有分页模式
- offset: 基于偏移量的分页
- date_range: 基于日期范围的分页
- stock_loop: 基于股票循环的分页
- period_range: 基于报告期的分页

## 解决方案

### 1. 新增季度分页模式

在 `/home/quan/testdata/aspipe_v4/app4/core/downloader.py` 中添加新的分页方法：

```python
def _execute_quarterly_pagination(self, interface_config: Dict[str, Any], 
                                 params: Dict[str, Any],
                                 pagination_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    执行季度周期分页
    将日期范围按季度分割，确保每个季度的数据独立请求
    例如：3月1日到5月1日 -> [3月1日-3月31日, 4月1日-5月1日]
    """
    all_data = []

    # 获取日期范围
    start_date = params.get('start_date', '20050101')
    end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))

    # 生成季度分割范围
    quarterly_ranges = self._generate_quarterly_ranges(start_date, end_date)

    # 为每个季度范围发起请求
    for idx, (range_start, range_end) in enumerate(quarterly_ranges):
        range_params = params.copy()
        range_params['start_date'] = range_start
        range_params['end_date'] = range_end

        logger.info(f"Downloading dividend data for quarterly range {idx+1}/{len(quarterly_ranges)}: {range_start} - {range_end}")

        # 发起请求
        range_data = self._make_request(interface_config, range_params)

        if range_data:
            all_data.extend(range_data)
            logger.info(f"Downloaded {len(range_data)} records for quarterly range {range_start}-{range_end}")
        else:
            logger.warning(f"No data returned for quarterly range {range_start}-{range_end}")

    return all_data

def _generate_quarterly_ranges(self, start_date: str, end_date: str) -> List[tuple]:
    """
    生成季度分割范围
    将日期范围按季度边界分割
    Q1: 1月1日 - 3月31日
    Q2: 4月1日 - 6月30日  
    Q3: 7月1日 - 9月30日
    Q4: 10月1日 - 12月31日
    """
    from datetime import datetime
    
    start_dt = datetime.strptime(start_date, '%Y%m%d')
    end_dt = datetime.strptime(end_date, '%Y%m%d')
    
    quarterly_ranges = []
    
    current = start_dt
    while current <= end_dt:
        # 确定当前季度的结束日期
        if current.month <= 3:
            # Q1: 1-3月
            quarter_end = datetime(current.year, 3, 31)
        elif current.month <= 6:
            # Q2: 4-6月
            quarter_end = datetime(current.year, 6, 30)
        elif current.month <= 9:
            # Q3: 7-9月
            quarter_end = datetime(current.year, 9, 30)
        else:
            # Q4: 10-12月
            quarter_end = datetime(current.year, 12, 31)
        
        # 如果季度结束日期超过总结束日期，则使用总结束日期
        if quarter_end > end_dt:
            quarter_end = end_dt
            
        # 确定范围开始日期（如果是季度开始，则从当前日期，否则从季度开始）
        if current.month in [1, 4, 7, 10] and current.day == 1:
            # 如果已经在季度开始，使用当前日期
            range_start = current.strftime('%Y%m%d')
        else:
            # 否则从当前季度开始
            if current.month <= 3:
                range_start = datetime(current.year, 1, 1).strftime('%Y%m%d')
            elif current.month <= 6:
                range_start = datetime(current.year, 4, 1).strftime('%Y%m%d')
            elif current.month <= 9:
                range_start = datetime(current.year, 7, 1).strftime('%Y%m%d')
            else:
                range_start = datetime(current.year, 10, 1).strftime('%Y%m%d')
        
        range_end = quarter_end.strftime('%Y%m%d')
        quarterly_ranges.append((range_start, range_end))
        
        # 移动到下一个季度
        if quarter_end.month == 3:
            current = datetime(quarter_end.year, 4, 1)
        elif quarter_end.month == 6:
            current = datetime(quarter_end.year, 7, 1)
        elif quarter_end.month == 9:
            current = datetime(quarter_end.year, 10, 1)
        else:
            current = datetime(quarter_end.year + 1, 1, 1)
    
    return quarterly_ranges
```

### 2. 修改分页执行逻辑

在 `_execute_pagination` 方法中添加季度分页模式支持：

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
        # 新增：季度范围分页
        all_data = self._execute_quarterly_pagination(interface_config, params, pagination_config)
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
  mode: quarterly_range  # 使用季度范围分页模式

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

## 实现效果

通过以上修改，dividend接口将能够：

1. **自动按季度分割日期范围**：当请求跨季度日期时，自动分割为多个季度段
2. **避免数据截断**：每个季度段独立请求，避免单次请求数据量过大
3. **保持数据完整性**：确保所有日期范围内的数据都被获取

例如：
- 请求 2022-03-01 到 2022-05-01
- 自动分割为：[2022-03-01, 2022-03-31] 和 [2022-04-01, 2022-05-01]
- 分别请求两个时间段的数据并合并返回

## 测试验证

修改完成后，需要进行以下测试：

1. **单季度测试**：验证单个季度范围的请求
2. **跨季度测试**：验证跨季度范围的自动分割
3. **大数据量测试**：验证大日期范围（如10年）的数据完整性
4. **性能测试**：确保分页不会显著影响下载性能