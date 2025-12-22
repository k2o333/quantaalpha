# Main分支功能实现详细说明

## 1. 缓存功能实现

### 1.1 缓存检查机制
在 `app/data_storage.py` 中实现了缓存检查功能：

```python
def is_data_cached(file_path: str) -> bool:
    """
    检查数据是否已经缓存

    Args:
        file_path: 路径到缓存文件

    Returns:
        如果文件存在返回True，否则返回False
    """
    return Path(file_path).exists()
```

### 1.2 缓存路径生成
```python
def get_cache_path(data_type: str, trade_date: str = None, ts_code: str = None) -> str:
    """
    生成标准的缓存路径

    Args:
        data_type: 数据类型 (例如 'daily_basic', 'moneyflow')
        trade_date: 交易日期，格式 YYYYMMDD (可选)
        ts_code: 股票代码 (可选)

    Returns:
        缓存文件的路径
    """
    if trade_date:
        year = trade_date[:4]
        month = trade_date[4:6]
        subdir = f"daily/{year}/{month}"
        filename = f"{data_type}_{trade_date}"
        return str(DATA_DIR / subdir / f"{filename}.parquet")
    elif ts_code:
        return str(DATA_DIR / data_type / f"{ts_code}.parquet")
    else:
        return str(DATA_DIR / data_type / "all_data.parquet")
```

### 1.3 数据新鲜度检查
```python
def is_data_fresh(file_path: str, max_age_hours: int = 24) -> bool:
    """
    检查缓存的数据是否新鲜，基于文件修改时间

    Args:
        file_path: 缓存文件路径
        max_age_hours: 最大年龄（小时），超过此值则认为数据过时

    Returns:
        数据是否新鲜的布尔值
    """
    try:
        if not Path(file_path).exists():
            return False

        mod_time = Path(file_path).stat().st_mtime
        current_time = datetime.now().timestamp()
        age_hours = (current_time - mod_time) / 3600

        return age_hours <= max_age_hours
    except Exception as e:
        logger.warning(f"Failed to check data freshness for {file_path}: {e}")
        return False
```

### 1.4 缓存使用示例
在 `app/utils/parallel_downloader.py` 中：

```python
def download_single_day(trade_date):
    # 检查缓存
    cache_path = get_cache_path(data_type, trade_date)
    if is_data_cached(cache_path):
        self.logger.info(f"使用缓存数据: {data_type} - {trade_date}")
        df = pd.read_parquet(cache_path)
        return (trade_date, df, len(df))
```

## 2. 分页功能实现

### 2.1 分页下载通用函数
在 `app/api_manager.py` 中定义了通用的分页下载函数：

```python
def download_with_pagination(self, api_func, limit_per_call=2000, **base_kwargs):
    """
    分页下载数据的通用函数

    Args:
        api_func: API调用函数
        limit_per_call: 每次调用的最大记录数
        **base_kwargs: 传递给API函数的基础参数

    Returns:
        pd.DataFrame: 合并后的所有数据
    """
    all_data = []
    offset = 0

    while True:
        # 添加分页参数
        kwargs = base_kwargs.copy()
        kwargs['offset'] = offset
        kwargs['limit'] = limit_per_call

        try:
            data = api_func(**kwargs)
        except Exception as e:
            self.logger.error(f"分页下载失败, offset={offset}: {e}")
            break

        if data is None or len(data) == 0:
            break

        # 将DataFrame添加到列表中，而不是扩展DataFrame
        all_data.append(data)

        # 如果返回数据少于限制数量，说明已到最后一页
        if len(data) < limit_per_call:
            break

        offset += limit_per_call

    # 将所有数据合并成一个DataFrame
    if all_data:
        return pd.concat(all_data, ignore_index=True)
    else:
        return pd.DataFrame()
```

### 2.2 针对不同接口的分页下载
```python
def download_stk_factor_paginated(self, trade_date: str = None, ts_code: str = None):
    """
    分页下载stk_factor数据
    """
    try:
        # 使用分页下载方法
        kwargs = {}
        if trade_date:
            kwargs['trade_date'] = trade_date
        if ts_code:
            kwargs['ts_code'] = ts_code

        # 使用最大支持的limit值
        return self.download_with_pagination(
            self.pro.stk_factor,
            limit_per_call=10000,  # stk_factor单次最大10000条
            **kwargs
        )
    except Exception as e:
        self.logger.error(f"分页下载stk_factor失败: {e}")
        # 回退到普通下载方法
        return self.pro.stk_factor(trade_date=trade_date, ts_code=ts_code)

def download_cyq_perf_paginated(self, trade_date: str = None, ts_code: str = None):
    """
    分页下载cyq_perf数据
    """
    try:
        # 使用分页下载方法
        kwargs = {}
        if trade_date:
            kwargs['trade_date'] = trade_date
        if ts_code:
            kwargs['ts_code'] = ts_code

        # 使用最大支持的limit值
        return self.download_with_pagination(
            self.pro.cyq_perf,
            limit_per_call=5000,  # cyq_perf单次最大5000条
            **kwargs
        )
    except Exception as e:
        self.logger.error(f"分页下载cyq_perf失败: {e}")
        # 回退到普通下载方法
        return self.pro.cyq_perf(trade_date=trade_date, ts_code=ts_code)

def download_cyq_chips_paginated(self, trade_date: str = None, ts_code: str = None):
    """
    分页下载cyq_chips数据
    """
    try:
        # 使用分页下载方法
        kwargs = {}
        if trade_date:
            kwargs['trade_date'] = trade_date
        if ts_code:
            kwargs['ts_code'] = ts_code

        # 使用最大支持的limit值
        return self.download_with_pagination(
            self.pro.cyq_chips,
            limit_per_call=2000,  # cyq_chips单次最大2000条
            **kwargs
        )
    except Exception as e:
        self.logger.error(f"分页下载cyq_chips失败: {e}")
        # 回退到普通下载方法
        return self.pro.cyq_chips(trade_date=trade_date, ts_code=ts_code)
```

### 2.3 接口实现中的分页处理
在 `app/interfaces/technical_factors.py` 中：

```python
def download_cyq_perf_paginated(self, trade_date=None, ts_code=None):
    """下载每日筹码及胜率(分页)"""
    return self.download_cyq_perf(trade_date=trade_date, ts_code=ts_code)

def download_cyq_chips_paginated(self, trade_date=None, ts_code=None):
    """下载每日筹码分布(分页)"""
    return self.download_cyq_chips(trade_date=trade_date, ts_code=ts_code)
```

## 3. 批次处理功能实现

### 3.1 并行下载器实现
在 `app/utils/parallel_downloader.py` 中：

```python
class ParallelDownloader:
    def __init__(self, config_manager):
        self.config = config_manager
        self.logger = logging.getLogger(__name__)
        self.download_lock = threading.Lock()
```

### 3.2 日期分片处理
```python
def download_daily_type_parallel(self, data_type: str, trading_days: List[str]) -> Dict[str, int]:
    """
    并行下载特定日度数据类型
    """
    results = {}
    all_data = []

    # 为不同数据类型分配不同数量的线程
    if data_type == 'daily_basic':
        # daily_basic最慢，可用更多线程
        max_workers = min(8, len(trading_days))
    else:
        # 其他类型使用适度的线程数
        max_workers = min(4, len(trading_days))
```

### 3.3 单日下载处理
```python
def download_single_day(trade_date):
    try:
        # 检查缓存
        cache_path = get_cache_path(data_type, trade_date)
        if is_data_cached(cache_path):
            self.logger.info(f"使用缓存数据: {data_type} - {trade_date}")
            df = pd.read_parquet(cache_path)
            return (trade_date, df, len(df))

        # 真实API调用
        api_manager = self.config.api_manager  # 假设config中有api_manager
        if data_type == 'daily':
            df = api_manager.daily_data.download_daily_data(ts_code=None, start_date=trade_date, end_date=trade_date)
        elif data_type == 'daily_basic':
            df = api_manager.daily_data.download_daily_basic(trade_date=trade_date)
        elif data_type == 'moneyflow':
            df = api_manager.market_flow.download_moneyflow(trade_date=trade_date)
        # ... 其他数据类型处理
```

### 3.4 并行执行机制
```python
# 并行下载所有日期的数据
with ThreadPoolExecutor(max_workers=max_workers) as executor:
    # 提交所有任务
    futures = {
        executor.submit(download_single_day, day): day
        for day in trading_days
    }

    # 收集结果
    for future in as_completed(futures):
        trade_date, df, record_count = future.result()
        if not df.empty and record_count > 0:
            all_data.append(df)
            results[trade_date] = record_count
```

### 3.5 数据分组和存储
```python
# 合并结果
final_result = {}
if all_data:
    # 按月分组数据(如果需要进一步组织存储)
    combined_df = pd.concat(all_data, ignore_index=True)
    if 'trade_date' in combined_df.columns:
        date_groups = combined_df.groupby(combined_df['trade_date'].dt.strftime('%Y-%m'))
        for (year_month), group in date_groups:
            year, month = year_month.split('-')
            subdir = f"daily/{year}/{month}"
            filename = f"{data_type}_{year_month}"
            file_path = save_to_parquet(group, filename, subdir=subdir)
            final_result[year_month] = len(group)

return final_result
```

### 3.6 在下载管理器中的任务组织
在 `app/download_manager.py` 中：

```python
def _create_download_task_list(self, start_date: str, end_date: str) -> List[Tuple[str, callable, int]]:
    """创建下载任务列表"""
    tasks = []

    # 日度数据 - 高优先级
    daily_types = self._get_daily_types()
    for data_type in daily_types:
        if self._is_data_type_available(data_type):
            tasks.append((data_type,
                         lambda dt=data_type: self._download_daily_type_for_range(dt, start_date, end_date),
                         3))

    # 静态数据 - 高优先级
    static_types = self._get_static_types()
    for data_type in static_types:
        if self._is_data_type_available(data_type):
            tasks.append((data_type,
                         lambda dt=data_type: self._download_static_type(dt),
                         3))

    # 财务数据 - 中等优先级
    financial_types = self._get_financial_types()
    for data_type in financial_types:
        if self._is_data_type_available(data_type):
            tasks.append((data_type,
                         lambda dt=data_type: self._download_financial_type_for_range(dt, start_date, end_date),
                         3))

    return tasks
```

### 3.7 API限频实现
在 `app/api_manager.py` 中：

```python
def _rate_limit(self, api_name: str) -> None:
    """实现速率限制"""
    current_time = time.perf_counter()

    # 获取此API的速率限制
    api_config = self.api_limits.get(api_name, {'calls_per_minute': 200})
    calls_per_minute = api_config['calls_per_minute']

    # 添加随机性以避免被识别为自动化脚本
    min_interval = (60.0 / calls_per_minute) * random.uniform(0.8, 1.2)

    # 检查是否最近调用过此API
    if api_name in self.last_call_times:
        elapsed = current_time - self.last_call_times[api_name]
        if elapsed < min_interval:
            sleep_time = min_interval - elapsed
            self.logger.debug(f"Rate limiting {api_name}, sleeping for {sleep_time:.2f}s")
            time.sleep(min_interval)

    self.last_call_times[api_name] = current_time
```

## 总结

Main分支实现了以下关键功能：

### 缓存功能
- 基于文件路径的缓存检查
- 标准化的缓存路径生成
- 数据新鲜度验证机制
- 在下载过程中自动使用缓存

### 分页功能
- 通用的分页下载框架
- 针对不同API的分页下载实现
- 自动处理offset和limit参数
- 完整的错误处理和回退机制

### 批次处理功能
- 灵活的并行下载机制
- 按数据类型分配不同线程数
- 任务组织和优先级管理
- API限频控制
- 数据分组和存储优化

这些功能使得Main分支在处理大规模数据时具有更高的效率和更好的资源利用率。