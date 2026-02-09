# stock_hsgt 接口 Window Size 配置方案

## 问题背景

`stock_hsgt` 接口使用 `type_split` 分页模式，按类型（HK_SZ, SZ_HK, HK_SH, SH_HK）分别请求数据。但每个类型在一年内的数据可能超过 2000 条限制，导致数据被截断。

例如：
```bash
python app4/main.py --start_date 20180101 --end_date 20181231 --interface stock_hsgt
```

由于每个分类只有 2000 条的上限，2018 年全年的数据可能超过 2000 条，导致部分记录下载不到。

## 解决方案

给 `type_split` 模式添加 `window_size_days` 配置支持，让每个类型的请求也能按指定的日期窗口分批请求。

## 实现步骤

### 1. 修改接口配置文件

文件：`app4/config/interfaces/stock_hsgt.yaml`

在 `pagination` 部分添加 `window_size_days: 1`：

```yaml
pagination:
  enabled: true
  mode: type_split
  window_size_days: 1  # 每天每个分类请求一次，确保不超过 2000 条限制
```

### 2. 修改分页执行器

文件：`app4/core/pagination_executor.py`

修改 `execute_type_split_pagination` 方法：

```python
def execute_type_split_pagination(
    self,
    interface_config: Dict[str, Any],
    params: Dict[str, Any],
    context: PaginationContext,
    make_request_callback: Callable,
    get_trade_calendar_callback: Optional[Callable] = None  # 新增参数
) -> List[Dict[str, Any]]:
    """
    执行按类型分割的分页模式（适用于stock_hsgt等接口）

    特性：
    1. 按接口支持的不同类型分别请求
    2. 支持 window_size_days 配置，可按日期窗口分批请求
    3. 避免因数据量超限导致的截断问题
    """
    import logging
    logger = logging.getLogger(__name__)

    interface_name = interface_config['name']
    pagination_config = interface_config.get('pagination', {})

    # 获取窗口大小配置，默认 None（不分窗）
    window_size_days = pagination_config.get('window_size_days')

    logger.info(f"Starting type split pagination for {interface_name}")
    if window_size_days:
        logger.info(f"Using window size: {window_size_days} days")

    # 获取接口配置中定义的类型选项
    type_values = interface_config.get('type_values', ['HK_SZ', 'SZ_HK', 'HK_SH', 'SH_HK'])
    logger.info(f"Type values to iterate: {type_values}")

    # 获取日期范围
    start_date = params.get('start_date')
    end_date = params.get('end_date')

    all_data = []
    successful_requests = 0

    for type_val in type_values:
        logger.info(f"Processing type: {type_val}")

        # 创建带有特定type值的参数
        type_params = params.copy()
        type_params['type'] = type_val

        if window_size_days and start_date and end_date:
            # 需要按日期窗口分批请求
            # 获取交易日历
            trade_calendar = self._get_trade_calendar(start_date, end_date, get_trade_calendar_callback)

            if trade_calendar:
                # 过滤交易日
                trade_days = [
                    day for day in trade_calendar
                    if day.get('is_open', 0) == 1 and
                       start_date <= day['cal_date'] <= end_date
                ]
                trade_days.sort(key=lambda x: x['cal_date'])

                # 按窗口大小分批
                for i in range(0, len(trade_days), window_size_days):
                    window_days = trade_days[i:i + window_size_days]
                    if not window_days:
                        continue

                    window_start = window_days[0]['cal_date']
                    window_end = window_days[-1]['cal_date']

                    window_params = type_params.copy()
                    window_params['start_date'] = window_start
                    window_params['end_date'] = window_end

                    logger.info(f"Making request for {interface_name} with type={type_val}, window={window_start}-{window_end}")
                    window_data = make_request_callback(interface_config, window_params)

                    if window_data:
                        all_data.extend(window_data)
                        successful_requests += 1
                        logger.info(f"Got {len(window_data)} records for type {type_val}, window {window_start}-{window_end}")
            else:
                # 没有交易日历，直接请求
                logger.info(f"Making request for {interface_name} with type={type_val}")
                type_data = make_request_callback(interface_config, type_params)

                if type_data:
                    all_data.extend(type_data)
                    successful_requests += 1
                    logger.info(f"Got {len(type_data)} records for type {type_val}")
        else:
            # 不需要分窗，直接请求
            logger.info(f"Making request for {interface_name} with type={type_val}")
            type_data = make_request_callback(interface_config, type_params)

            if type_data:
                all_data.extend(type_data)
                successful_requests += 1
                logger.info(f"Got {len(type_data)} records for type {type_val}")

    logger.info(f"Type split pagination completed. Total records: {len(all_data)}, Successful requests: {successful_requests}")
    return all_data
```

### 3. 修改 Downloader 中的调用

文件：`app4/core/downloader.py`

在 `_execute_pagination` 方法中，修改 `type_split` 模式的调用：

```python
elif mode == 'type_split':
    # 按类型分割分页（适用于stock_hsgt等接口）
    return self.pagination_executor.execute_type_split_pagination(
        interface_config, params, context, self._make_request,
        get_trade_calendar_callback=self.get_trade_calendar  # 新增参数
    )
```

## 配置示例

### stock_hsgt.yaml 完整配置

```yaml
api_name: stock_hsgt
description: 沪深港通股票列表
name: stock_hsgt

pagination:
  enabled: true
  mode: type_split
  window_size_days: 1  # 每天每个分类请求一次

type_values: ['HK_SZ', 'SZ_HK', 'HK_SH', 'SH_HK']

parameters:
  end_date:
    description: 结束时间
    required: false
    type: string
  start_date:
    description: 开始时间
    required: false
    type: string
  trade_date:
    description: 交易日期（格式：YYYYMMDD）
    required: false
    type: string
  ts_code:
    description: 股票代码
    required: false
    type: string
  type:
    description: 类型（HK_SZ深股通, SZ_HK港股通(深), HK_SH沪股通, SH_HK港股通(沪)）
    required: true
    type: string

permissions:
  min_points: 3000
  query_limit: 2000
  rate_limit: 120

output:
  primary_key:
  - ts_code
  - trade_date
  - type
  sort_by:
  - trade_date
  - ts_code

derived_fields:
  trade_date_dt:
    description: 日期类型的trade_date
    format: '%Y%m%d'
    source: trade_date
    type: date

request:
  extra_path: ''
  method: POST
  timeout: 30
```

## 使用方式

配置完成后，使用方式不变：

```bash
# 下载 2018 年全年数据，每天每个分类单独请求
python app4/main.py --start_date 20180101 --end_date 20181231 --interface stock_hsgt
```

由于配置了 `window_size_days: 1`，程序会自动：
1. 获取 2018 年的所有交易日
2. 对每个交易日，分别请求 4 个类型（HK_SZ, SZ_HK, HK_SH, SH_HK）
3. 每天每个类型的数据量都会远小于 2000 条，确保数据完整

## 扩展性

此方案具有良好的扩展性：

1. **其他接口复用**：任何使用 `type_split` 模式的接口都可以通过添加 `window_size_days` 配置来启用日期窗口分批
2. **灵活配置**：可以根据接口的数据密度调整窗口大小，例如：
   - `window_size_days: 1` - 每天请求一次（适合数据量大的接口）
   - `window_size_days: 7` - 每周请求一次（适合数据量中等的接口）
   - `window_size_days: 30` - 每月请求一次（适合数据量小的接口）
3. **向后兼容**：不配置 `window_size_days` 时，保持原有行为不变

## 注意事项

1. **请求次数增加**：使用 `window_size_days: 1` 会显著增加请求次数（交易日数量 × 类型数量），请确保积分和频率限制足够
2. **性能考虑**：可以根据实际数据量调整窗口大小，在数据完整性和请求效率之间取得平衡
3. **交易日历依赖**：此方案需要交易日历数据，确保 `trade_cal` 接口数据已下载或可以正常获取
