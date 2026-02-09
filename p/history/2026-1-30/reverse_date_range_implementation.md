# 反向日期范围分页模式实现文档

## 需求概述

实现一个新的分页模式 `reverse_date_range`，支持：
1. 从最近日期往前下载（倒序）
2. 窗口大小可配置（如30天一个窗口）
3. 连续N天无数据时自动终止（默认90天）
4. 支持覆盖率检查，跳过已下载窗口

## 影响范围

需要修改以下文件：
1. `app4/core/pagination_executor.py` - 添加反向分页执行逻辑
2. `app4/core/pagination.py` - 添加反向窗口参数生成
3. `app4/core/downloader.py` - 添加新模式路由
4. `app4/core/coverage_manager.py` - 添加反向模式覆盖率检查（可选）
5. 接口配置文件 - 更新需要反向下载的接口

---

## 第一步：在 pagination_executor.py 添加执行方法

在 `PaginationExecutor` 类中添加新方法：

```python
def execute_reverse_date_range_pagination(
    self,
    interface_config: Dict[str, Any],
    params: Dict[str, Any],
    context: PaginationContext,
    make_request_callback: Callable,
    coverage_manager: Optional[Any] = None,
    force_download: bool = False,
    get_trade_calendar_callback: Optional[Callable] = None
) -> List[Dict[str, Any]]:
    """
    执行反向日期范围分页（从最近日期往前下载）

    特性：
    1. 从end_date往start_date方向下载（倒序）
    2. 支持窗口大小配置
    3. 连续无数据天数达到阈值时自动终止
    4. 支持覆盖率检查

    Args:
        interface_config: 接口配置
        params: 请求参数（包含start_date, end_date）
        context: 分页上下文
        make_request_callback: 请求回调函数
        coverage_manager: 覆盖率管理器
        force_download: 是否强制下载
        get_trade_calendar_callback: 获取交易日历的回调

    Returns:
        下载的数据列表
    """
    interface_name = interface_config['name']
    pagination_config = interface_config.get('pagination', {})

    # 获取配置参数
    window_size_days = pagination_config.get('window_size_days', 30)
    empty_threshold_days = pagination_config.get('empty_threshold_days', 90)

    start_date = params.get('start_date', '20050101')
    end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))

    logger.info(f"Starting reverse date range pagination for {interface_name}")
    logger.info(f"Date range: {start_date} to {end_date}, window size: {window_size_days} days")
    logger.info(f"Empty threshold: {empty_threshold_days} consecutive days without data will stop the download")

    # 获取交易日历
    if hasattr(context, 'trade_calendar') and context.trade_calendar:
        trade_calendar = context.trade_calendar
    else:
        trade_calendar = self._get_trade_calendar(start_date, end_date, get_trade_calendar_callback)
        context.trade_calendar = trade_calendar

    if not trade_calendar:
        logger.warning("Failed to get trade calendar, falling back to regular date_range")
        return self.execute_date_range_pagination(
            interface_config, params, context, make_request_callback,
            coverage_manager, force_download, get_trade_calendar_callback
        )

    # 过滤交易日并按倒序排列（从最近到最远）
    trade_days = [
        day for day in trade_calendar
        if day.get('is_open', 0) == 1 and
           start_date <= day['cal_date'] <= end_date
    ]

    if not trade_days:
        logger.warning(f"No trade days found in range {start_date} - {end_date}")
        return []

    # 按日期倒序排列（从最近到最远）
    trade_days.sort(key=lambda x: x['cal_date'], reverse=True)

    total_days = len(trade_days)
    logger.info(f"Total trade days to process: {total_days}")

    # 生成倒序窗口
    windows = []
    for i in range(0, total_days, window_size_days):
        window_days = trade_days[i:i + window_size_days]
        if not window_days:
            continue

        # 窗口的start和end需要重新排序（因为我们是倒序遍历）
        # 例如：倒序窗口 [20240131, 20240130, ... 20240102]
        # 实际请求的start_date应该是20240102, end_date是20240131
        window_dates = [d['cal_date'] for d in window_days]
        window_start = min(window_dates)  # 窗口内最早的日期
        window_end = max(window_dates)    # 窗口内最晚的日期

        windows.append((window_start, window_end))

    logger.info(f"Generated {len(windows)} windows for reverse download")

    # 顺序执行（从最近到最远）
    all_data = []
    consecutive_empty_days = 0
    processed_windows = 0

    for window_start, window_end in windows:
        processed_windows += 1

        # 构建窗口参数
        window_params = params.copy()
        window_params['start_date'] = window_start
        window_params['end_date'] = window_end

        # 计算当前窗口的天数
        window_days_count = sum(1 for d in trade_days if window_start <= d['cal_date'] <= window_end)

        logger.info(f"[{processed_windows}/{len(windows)}] Processing window {window_start} - {window_end} ({window_days_count} days)")

        # 覆盖率检查
        should_skip = False
        if coverage_manager and not force_download:
            should_skip = coverage_manager.should_skip(
                interface_config['api_name'],
                window_params,
                strategy='date_range'
            )

        if should_skip:
            logger.info(f"  Skipping window {window_start} - {window_end} (already exists)")
            # 重置连续无数据计数（因为数据已存在）
            consecutive_empty_days = 0
            continue

        # 发起请求
        window_data = make_request_callback(interface_config, window_params)

        if window_data:
            all_data.extend(window_data)
            logger.info(f"  Got {len(window_data)} records, reset empty counter")
            # 有数据，重置连续无数据计数
            consecutive_empty_days = 0
        else:
            # 无数据，累加连续无数据天数
            consecutive_empty_days += window_days_count
            logger.info(f"  No data, consecutive empty days: {consecutive_empty_days}")

            # 检查是否达到终止阈值
            if consecutive_empty_days >= empty_threshold_days:
                logger.info(f"Reached empty threshold ({empty_threshold_days} days), stopping download")
                logger.info(f"Total windows processed: {processed_windows}/{len(windows)}")
                break

    logger.info(f"Reverse pagination completed. Total records: {len(all_data)}")
    return all_data
```

---

## 第二步：在 pagination.py 添加参数生成方法

在 `ParameterGenerator` 类中添加新方法：

```python
def generate_reverse_date_range_params(
    self,
    base_params: Dict[str, Any],
    start_date: str,
    end_date: str
) -> Iterator[Tuple[Dict[str, Any], Tuple[str, str]]]:
    """
    生成反向日期范围分页参数（从最近日期往前）

    Args:
        base_params: 基础参数
        start_date: 开始日期 YYYYMMDD（最老的日期）
        end_date: 结束日期 YYYYMMDD（最近的日期）

    Yields:
        (窗口参数, (window_start, window_end)) 元组，按倒序排列
    """
    if not self.context.trade_calendar:
        logger.warning("Trade calendar not provided, yielding single request")
        yield base_params.copy(), (start_date, end_date)
        return

    # 过滤交易日
    trade_days = [
        day for day in self.context.trade_calendar
        if day.get('is_open', 0) == 1 and
           start_date <= day['cal_date'] <= end_date
    ]

    if not trade_days:
        logger.warning(f"No trade days found in range {start_date} - {end_date}")
        return

    # 按日期倒序排列（从最近到最远）
    trade_days.sort(key=lambda x: x['cal_date'], reverse=True)

    # 获取窗口大小
    window_size = get_window_size_for_interface(
        self.context.interface_name,
        self.context.interface_config
    )

    logger.info(f"Generating reverse windows for {len(trade_days)} trade days with window size {window_size}")

    # 生成倒序窗口
    for i in range(0, len(trade_days), window_size):
        window_days = trade_days[i:i + window_size]
        if not window_days:
            continue

        # 窗口内日期重新排序，确保start < end
        window_dates = [d['cal_date'] for d in window_days]
        window_start = min(window_dates)
        window_end = max(window_dates)

        window_params = base_params.copy()
        window_params['start_date'] = window_start
        window_params['end_date'] = window_end

        yield window_params, (window_start, window_end)
```

同时更新 `get_window_size_for_interface` 函数，支持 `reverse_date_range` 模式：

```python
def get_window_size_for_interface(interface_name: str, config: Dict[str, Any] = None) -> int:
    """
    根据接口类型确定窗口大小
    """
    # 如果提供了配置，优先使用配置中的设置
    if config:
        pagination_config = config.get('pagination', {})
        if pagination_config.get('enabled', False):
            mode = pagination_config.get('mode', 'offset')
            if mode == 'date_range_daily':
                return 1
            elif mode == 'reverse_date_range':
                # 反向日期范围模式，默认30天
                return pagination_config.get('window_size_days', 30)
            elif mode == 'stock_loop':
                return pagination_config.get('window_size_days', 30)
            else:
                return pagination_config.get('window_size_days', 365)

    # ... 原有逻辑保持不变 ...
```

---

## 第三步：在 downloader.py 添加模式路由

在 `_execute_pagination` 方法中添加对 `reverse_date_range` 模式的支持：

```python
def _execute_pagination(self, interface_config: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    执行分页/循环逻辑 - 控制器
    """
    pagination_config = interface_config.get('pagination', {})
    if not pagination_config.get('enabled', False):
        return self._make_request(interface_config, params)

    mode = pagination_config.get('mode', 'offset')
    context = PaginationContext(
        interface_config=interface_config,
        force_download=self.force_download
    )

    # 委托给分页执行器
    if mode == 'offset':
        return self.pagination_executor.execute_offset_pagination(...)
    elif mode == 'date_range':
        return self.pagination_executor.execute_date_range_pagination(...)
    elif mode == 'stock_loop':
        return self.pagination_executor.execute_stock_loop_pagination(...)
    elif mode == 'period_range':
        return self.pagination_executor.execute_period_range_pagination(...)
    elif mode == 'quarterly_range':
        return self.pagination_executor.execute_quarterly_pagination(...)
    elif mode == 'periodic_range':
        return self.pagination_executor.execute_periodic_pagination(...)
    elif mode == 'date_range_daily':
        return self.pagination_executor.execute_date_range_daily_pagination(...)
    elif mode == 'reverse_date_range':
        # 新增：反向日期范围分页
        return self.pagination_executor.execute_reverse_date_range_pagination(
            interface_config, params, context, self._make_request,
            coverage_manager=self.coverage_manager, force_download=self.force_download,
            get_trade_calendar_callback=self.get_trade_calendar
        )
    else:
        return self._make_request(interface_config, params)
```

---

## 第四步：更新接口配置文件

### cyq_chips.yaml 示例

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
  mode: reverse_date_range    # 改为反向日期范围模式
  window_size_days: 30        # 每30天一个窗口
  empty_threshold_days: 90    # 连续90天无数据停止
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
    required: true
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

### cyq_perf.yaml 示例

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
  mode: reverse_date_range    # 改为反向日期范围模式
  window_size_days: 1         # 每天一个窗口（该接口适合按天下载）
  empty_threshold_days: 90    # 连续90天无数据停止
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

### daily.yaml 示例（日线行情）

```yaml
api_name: daily
description: 日线行情
derived_fields:
  trade_date_dt:
    description: 日期类型的trade_date
    format: '%Y%m%d'
    source: trade_date
    type: date
duplicate_detection:
  date_column: trade_date
  enabled: true
  mode: range
  threshold: 0.95
name: daily
output:
  dedup_enabled: true
  primary_key:
  - ts_code
  - trade_date
  sort_by:
  - trade_date
pagination:
  enabled: true
  mode: reverse_date_range    # 改为反向日期范围模式
  window_size_days: 30        # 每30天一个窗口
  empty_threshold_days: 90    # 连续90天无数据停止
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
    description: 证券代码
    required: false
    type: string
permissions:
  min_points: 0
  query_limit: 10000
  rate_limit: 120
request:
  extra_path: ''
  method: POST
  timeout: 30
```

---

## 第五步：覆盖率检查支持（可选）

如果需要支持反向模式的覆盖率检查，可以在 `coverage_manager.py` 的 `should_skip` 方法中添加：

```python
def should_skip(self, interface_name: str, params: Dict[str, Any],
               strategy: str = 'auto') -> bool:
    # ... 原有代码 ...

    # 自动确定策略
    if strategy == 'auto':
        pagination_config = interface_config.get('pagination', {})
        pagination_mode = pagination_config.get('mode', 'offset') if pagination_config.get('enabled', False) else 'none'

        if pagination_mode in ['date_range', 'reverse_date_range']:  # 添加reverse_date_range支持
            strategy = 'date_range'
        elif pagination_mode == 'period_range':
            strategy = 'period'
        elif pagination_mode == 'stock_loop':
            strategy = 'stock'
        else:
            return False

    # ... 原有代码 ...
```

---

## 使用示例

### 命令行使用

```bash
# 下载cyq_chips数据，从最近日期往前，每30天一个窗口
python app4/main.py --interface cyq_chips --ts_code 000002.SZ

# 下载cyq_perf数据，从最近日期往前，每天一个窗口
python app4/main.py --interface cyq_perf --start_date 20180101 --end_date 20181231

# 下载daily数据，从最近日期往前
python app4/main.py --interface daily --start_date 20200101 --end_date 20241231
```

### 预期行为

1. **首次运行**：从最近日期开始，按窗口大小往前下载，直到达到起始日期或连续90天无数据
2. **再次运行**：跳过已下载的窗口，只下载缺失的数据
3. **无数据检测**：如果某个窗口返回空数据，累加连续无数据天数，达到90天自动终止

### 日志输出示例

```
INFO - Starting reverse date range pagination for cyq_chips
INFO - Date range: 19910129 to 20260202, window size: 30 days
INFO - Empty threshold: 90 consecutive days without data will stop the download
INFO - Total trade days to process: 8576
INFO - Generated 286 windows for reverse download
INFO - [1/286] Processing window 20260105 - 20260202 (30 days)
INFO -   Got 6000 records, reset empty counter
INFO - [2/286] Processing window 20251202 - 20260104 (30 days)
INFO -   Got 0 records, consecutive empty days: 30
INFO - ...
INFO - [4/286] Processing window 20251001 - 20251103 (30 days)
INFO -   Got 0 records, consecutive empty days: 90
INFO - Reached empty threshold (90 days), stopping download
INFO - Total windows processed: 4/286
INFO - Reverse pagination completed. Total records: 6000
```

---

## 注意事项

1. **窗口大小选择**：
   - 数据量大的接口（如cyq_chips）：建议30天
   - 数据量小的接口（如cyq_perf）：建议1天
   - 普通日线接口（如daily）：建议30天

2. **无数据阈值**：
   - 默认90天适合大多数接口
   - 对于季节性数据，可以适当增大
   - 对于实时性要求高的数据，可以适当减小

3. **与stock_loop模式的区别**：
   - `stock_loop`：按股票循环，每个股票获取全历史
   - `reverse_date_range`：按日期倒序，支持窗口大小和无数据终止

4. **覆盖率检查**：
   - 反向模式复用现有的`date_range`覆盖率检查策略
   - 确保已有数据能被正确识别和跳过
