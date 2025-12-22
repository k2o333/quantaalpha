# 分页、分批次和缓存功能实现文档

## 1. 现有功能分析

### 1.1 分页功能
当前项目中已经实现了分页下载功能，主要体现在 `app/api_manager.py` 中的 `download_with_pagination` 方法：

```python
def download_with_pagination(self, api_func, limit_per_call=2000, **base_kwargs):
    """
    分页下载数据的通用函数
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

        # 将DataFrame添加到列表中
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

### 1.2 分页接口实现
为特定接口实现了分页下载方法：
- `download_stk_factor_paginated`
- `download_cyq_perf_paginated`
- `download_cyq_chips_paginated`

### 1.3 缓存功能
缓存功能在 `app/data_storage.py` 中实现：

- `is_data_cached(file_path: str)`: 检查数据是否已缓存
- `get_cache_path(data_type: str, trade_date: str = None, ts_code: str = None)`: 生成标准缓存路径
- `is_data_fresh(file_path: str, max_age_hours: int = 24)`: 检查数据新鲜度

### 1.4 分批处理功能
并行下载功能在 `app/utils/parallel_downloader.py` 中实现：

- `ParallelDownloader` 类支持并行下载特定日度数据类型
- 根据数据类型分配不同线程数（如 daily_basic 使用最多8个线程，其他类型最多4个线程）

## 2. 针对特定接口的增强实现

### 2.1 通用分页处理函数

在 `app/api_manager.py` 中，我们已有的分页函数已经可以很好地处理大多数接口，但可以进一步优化：

```python
def download_with_pagination(self, api_func, limit_per_call=2000, max_retries=3, **base_kwargs):
    """
    分页下载数据的通用函数（增强版）

    Args:
        api_func: API调用函数
        limit_per_call: 每次调用的最大记录数
        max_retries: 每页的重试次数
        **base_kwargs: 传递给API函数的基础参数

    Returns:
        pd.DataFrame: 合并后的所有数据
    """
    all_data = []
    offset = 0
    consecutive_empty_pages = 0  # 连续空页计数，防止无限循环

    # 根据API函数名称优化limit值
    func_name = api_func.__name__ if hasattr(api_func, '__name__') else 'unknown'
    if func_name in ['stk_factor', 'stk_factor_pro']:
        limit_per_call = min(limit_per_call, 10000)  # stk_factor最大支持10000
    elif func_name in ['cyq_perf']:
        limit_per_call = min(limit_per_call, 5000)   # cyq_perf最大支持5000
    elif func_name in ['cyq_chips']:
        limit_per_call = min(limit_per_call, 2000)   # cyq_chips最大支持2000

    while consecutive_empty_pages < 3:  # 连续3次空页则停止
        # 添加分页参数
        kwargs = base_kwargs.copy()
        kwargs['offset'] = offset
        kwargs['limit'] = limit_per_call

        # 带重试的API调用
        attempt = 0
        while attempt <= max_retries:
            try:
                # 实现速率限制
                self._rate_limit(func_name)

                data = api_func(**kwargs)

                if data is None or len(data) == 0:
                    consecutive_empty_pages += 1
                    break  # 本次尝试空数据，但继续下一页

                # 将DataFrame添加到列表中
                all_data.append(data)
                consecutive_empty_pages = 0  # 重置连续空页计数

                # 如果返回数据少于限制数量，说明已到最后一页
                if len(data) < limit_per_call:
                    return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()

                break  # 成功获取数据，跳出重试循环
            except Exception as e:
                attempt += 1
                if attempt > max_retries:
                    self.logger.error(f"分页下载失败, offset={offset}, func={func_name}: {e}")
                    # 如果是认证错误，尝试切换token
                    if "token" in str(e).lower() or "auth" in str(e).lower():
                        self.switch_token()
                    break
                else:
                    self.logger.warning(f"分页下载第 {attempt} 次尝试失败, offset={offset}: {e}")
                    time.sleep(2 ** attempt)  # 指数退避

        offset += limit_per_call

        # 限制最大偏移量，防止无限循环
        if offset > 100000:  # 设定一个合理的最大偏移量
            self.logger.warning(f"达到最大偏移量限制: {offset}")
            break

    return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()
```

### 2.2 针对更多接口的分页实现

```python
# 在 TuShareAPIManager 类中添加以下方法

def download_daily_basic_paginated(self, trade_date: str = None, ts_code: str = None):
    """
    分页下载daily_basic数据
    """
    try:
        kwargs = {}
        if trade_date:
            kwargs['trade_date'] = trade_date
        if ts_code:
            kwargs['ts_code'] = ts_code

        # daily_basic通常数据量较小，使用适中的limit值
        return self.download_with_pagination(
            self.pro.daily_basic,
            limit_per_call=4000,  # daily_basic单次最大支持约4000条
            **kwargs
        )
    except Exception as e:
        self.logger.error(f"分页下载daily_basic失败: {e}")
        # 回退到普通下载方法
        return self.pro.daily_basic(trade_date=trade_date, ts_code=ts_code)

def download_moneyflow_paginated(self, trade_date: str = None, ts_code: str = None):
    """
    分页下载moneyflow数据
    """
    try:
        kwargs = {}
        if trade_date:
            kwargs['trade_date'] = trade_date
        if ts_code:
            kwargs['ts_code'] = ts_code

        # moneyflow数据量适中，使用适中limit值
        return self.download_with_pagination(
            self.pro.moneyflow,
            limit_per_call=3000,  # moneyflow单次最大支持约3000条
            **kwargs
        )
    except Exception as e:
        self.logger.error(f"分页下载moneyflow失败: {e}")
        # 回退到普通下载方法
        return self.pro.moneyflow(trade_date=trade_date, ts_code=ts_code)

def download_bak_basic_paginated(self, trade_date: str = None, ts_code: str = None):
    """
    分页下载bak_basic数据（备用股票列表）
    """
    try:
        kwargs = {}
        if trade_date:
            kwargs['trade_date'] = trade_date
        if ts_code:
            kwargs['ts_code'] = ts_code

        return self.download_with_pagination(
            self.pro.bak_basic,
            limit_per_call=4000,  # bak_basic单次最大支持约4000条
            **kwargs
        )
    except Exception as e:
        self.logger.error(f"分页下载bak_basic失败: {e}")
        # 回退到普通下载方法
        return self.pro.bak_basic(trade_date=trade_date, ts_code=ts_code)

def download_daily_info_paginated(self, trade_date: str = None, ts_code: str = None, type: str = None):
    """
    分页下载daily_info数据（每日详情）
    """
    try:
        kwargs = {}
        if trade_date:
            kwargs['trade_date'] = trade_date
        if ts_code:
            kwargs['ts_code'] = ts_code
        if type:
            kwargs['type'] = type

        return self.download_with_pagination(
            self.pro.daily_info,
            limit_per_call=3000,  # daily_info单次最大支持约3000条
            **kwargs
        )
    except Exception as e:
        self.logger.error(f"分页下载daily_info失败: {e}")
        # 回退到普通下载方法
        return self.pro.daily_info(trade_date=trade_date, ts_code=ts_code, type=type)

def download_hsgt_top10_paginated(self, trade_date: str = None, ts_code: str = None):
    """
    分页下载沪深股通十大成交股数据
    """
    try:
        kwargs = {}
        if trade_date:
            kwargs['trade_date'] = trade_date
        if ts_code:
            kwargs['ts_code'] = ts_code

        return self.download_with_pagination(
            self.pro.hsgt_top10,
            limit_per_call=2000,  # hsgt_top10单次最大支持约2000条
            **kwargs
        )
    except Exception as e:
        self.logger.error(f"分页下载hsgt_top10失败: {e}")
        # 回退到普通下载方法
        return self.pro.hsgt_top10(trade_date=trade_date, ts_code=ts_code)
```

### 2.3 针对范围查询的批量处理

```python
def download_daily_range_batched(self, start_date: str, end_date: str, ts_code: str = None, batch_size: int = 30):
    """
    按日期范围批量下载日线数据（分批处理）

    Args:
        start_date: 开始日期
        end_date: 结束日期
        ts_code: 股票代码
        batch_size: 每批处理的天数
    """
    from utils.date_processor import DateProcessor

    date_processor = DateProcessor()
    all_dates = date_processor.get_trading_days(start_date, end_date)

    all_data = []

    # 按批次处理
    for i in range(0, len(all_dates), batch_size):
        batch_dates = all_dates[i:i+batch_size]
        self.logger.info(f"处理批次: {batch_dates[0]} 到 {batch_dates[-1]}")

        batch_data = []
        for trade_date in batch_dates:
            cache_path = get_cache_path('daily', trade_date)
            if is_data_cached(cache_path) and is_data_fresh(cache_path, max_age_hours=2):
                # 使用缓存数据
                cached_df = pd.read_parquet(cache_path)
                batch_data.append(cached_df)
                self.logger.info(f"使用缓存数据: daily - {trade_date}")
                continue

            try:
                # 分批下载单日数据
                daily_data = self.daily_data.download_daily_data(
                    ts_code=ts_code,
                    start_date=trade_date,
                    end_date=trade_date
                )

                if not daily_data.empty:
                    # 保存到缓存
                    year = trade_date[:4]
                    month = trade_date[4:6]
                    subdir = f"daily/{year}/{month}"
                    filename = f"daily_{trade_date}"
                    save_to_parquet(daily_data, filename, subdir=subdir)

                    batch_data.append(daily_data)
            except Exception as e:
                self.logger.error(f"下载daily数据失败 {trade_date}: {e}")

        if batch_data:
            all_data.extend(batch_data)

        # 批次间短暂休息，避免API限制
        time.sleep(1)

    return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()

def download_daily_basic_range_batched(self, start_date: str, end_date: str, ts_code: str = None, batch_size: int = 30):
    """
    按日期范围批量下载每日基本面数据（分批处理）
    """
    from utils.date_processor import DateProcessor

    date_processor = DateProcessor()
    all_dates = date_processor.get_trading_days(start_date, end_date)

    all_data = []

    # 按批次处理
    for i in range(0, len(all_dates), batch_size):
        batch_dates = all_dates[i:i+batch_size]
        self.logger.info(f"处理基本面数据批次: {batch_dates[0]} 到 {batch_dates[-1]}")

        batch_data = []
        for trade_date in batch_dates:
            cache_path = get_cache_path('daily_basic', trade_date)
            if is_data_cached(cache_path) and is_data_fresh(cache_path, max_age_hours=2):
                # 使用缓存数据
                cached_df = pd.read_parquet(cache_path)
                batch_data.append(cached_df)
                self.logger.info(f"使用缓存数据: daily_basic - {trade_date}")
                continue

            try:
                # 使用分页下载
                daily_basic_data = self.download_daily_basic_paginated(
                    trade_date=trade_date,
                    ts_code=ts_code
                )

                if not daily_basic_data.empty:
                    # 保存到缓存
                    year = trade_date[:4]
                    month = trade_date[4:6]
                    subdir = f"daily/{year}/{month}"
                    filename = f"daily_basic_{trade_date}"
                    save_to_parquet(daily_basic_data, filename, subdir=subdir)

                    batch_data.append(daily_basic_data)
            except Exception as e:
                self.logger.error(f"下载daily_basic数据失败 {trade_date}: {e}")

        if batch_data:
            all_data.extend(batch_data)

        # 批次间短暂休息
        time.sleep(1)

    return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()
```

### 2.4 优化的缓存策略

```python
def get_cache_path_with_hash(data_type: str, **kwargs) -> str:
    """
    生成带参数哈希的缓存路径，避免相同类型不同参数的缓存冲突
    """
    import hashlib

    # 生成参数哈希
    param_str = "_".join([f"{k}_{v}" for k, v in sorted(kwargs.items()) if v is not None])
    param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8] if param_str else ""

    if 'trade_date' in kwargs and kwargs['trade_date']:
        trade_date = kwargs['trade_date']
        year = trade_date[:4]
        month = trade_date[4:6]
        subdir = f"daily/{year}/{month}"
        filename = f"{data_type}_{trade_date}"
        if param_hash:
            filename += f"_{param_hash}"
        return str(DATA_DIR / subdir / f"{filename}.parquet")
    elif 'ts_code' in kwargs and kwargs['ts_code']:
        ts_code = kwargs['ts_code']
        subdir = data_type
        filename = f"{ts_code}"
        if param_hash:
            filename += f"_{param_hash}"
        return str(DATA_DIR / subdir / f"{filename}.parquet")
    else:
        subdir = data_type
        filename = "all_data"
        if param_hash:
            filename += f"_{param_hash}"
        return str(DATA_DIR / subdir / f"{filename}.parquet")

def get_cached_data_or_fetch(self, data_type: str, cache_hours: int = 24, **kwargs):
    """
    获取缓存数据或通过API获取
    """
    cache_path = get_cache_path_with_hash(data_type, **kwargs)

    # 检查缓存是否存在且新鲜
    if is_data_cached(cache_path) and is_data_fresh(cache_path, max_age_hours=cache_hours):
        try:
            df = pd.read_parquet(cache_path)
            self.logger.info(f"使用缓存数据: {data_type}, path: {cache_path}")
            return df
        except Exception as e:
            self.logger.warning(f"读取缓存失败: {cache_path}, 错误: {e}")

    # 缓存不存在或过期，通过API获取
    try:
        # 根据数据类型选择不同的API方法
        if data_type == 'daily':
            df = self.daily_data.download_daily_data(**kwargs)
        elif data_type == 'daily_basic':
            df = self.download_daily_basic_paginated(**kwargs)
        elif data_type == 'moneyflow':
            df = self.download_moneyflow_paginated(**kwargs)
        elif data_type == 'stk_factor':
            df = self.download_stk_factor_paginated(**kwargs)
        elif data_type == 'cyq_perf':
            df = self.download_cyq_perf_paginated(**kwargs)
        elif data_type == 'cyq_chips':
            df = self.download_cyq_chips_paginated(**kwargs)
        else:
            # 使用通用方法
            api_func = getattr(self.pro, data_type)
            df = self.download_with_pagination(api_func, **kwargs)

        if not df.empty:
            # 确定保存路径
            if 'trade_date' in kwargs and kwargs['trade_date']:
                trade_date = kwargs['trade_date']
                year = trade_date[:4]
                month = trade_date[4:6]
                subdir = f"daily/{year}/{month}"
            else:
                subdir = data_type
            filename = f"{data_type}_{'_'.join([f'{k}_{v}' for k, v in kwargs.items() if v is not None])}"
            if len(filename) > 100:  # 文件名过长，使用哈希
                filename = f"{data_type}_{hash(kwargs.__str__()) % 1000000}"

            save_to_parquet(df, filename, subdir=subdir)
            self.logger.info(f"保存新数据到缓存: {cache_path}")

        return df

    except Exception as e:
        self.logger.error(f"获取数据失败 {data_type}: {e}")
        return pd.DataFrame()
```

### 2.5 优化的并行下载器

```python
class EnhancedParallelDownloader(ParallelDownloader):
    """
    增强版并行下载器，支持更多数据类型和更灵活的缓存策略
    """

    def __init__(self, config_manager):
        super().__init__(config_manager)
        self.download_stats = {}  # 下载统计

    def download_daily_type_parallel_with_cache_control(self, data_type: str, trading_days: List[str],
                                                       cache_hours: int = 24, force_refresh: bool = False) -> Dict[str, int]:
        """
        并行下载特定日度数据类型，支持缓存控制
        """
        results = {}
        all_data = []

        # 根据数据类型配置线程数
        thread_config = {
            'daily_basic': {'max_workers': 8, 'limit_per_call': 4000},
            'moneyflow': {'max_workers': 6, 'limit_per_call': 3000},
            'daily': {'max_workers': 10, 'limit_per_call': 8000},
            'stk_factor': {'max_workers': 4, 'limit_per_call': 10000},
            'cyq_perf': {'max_workers': 5, 'limit_per_call': 5000},
            'cyq_chips': {'max_workers': 4, 'limit_per_call': 2000},
            # 其他类型使用默认值
        }

        config = thread_config.get(data_type, {'max_workers': 4, 'limit_per_call': 2000})
        max_workers = min(config['max_workers'], len(trading_days))

        def download_single_day(trade_date):
            try:
                # 检查缓存
                cache_path = get_cache_path(data_type, trade_date)

                if is_data_cached(cache_path) and is_data_fresh(cache_path, max_age_hours=cache_hours) and not force_refresh:
                    df = pd.read_parquet(cache_path)
                    self.logger.info(f"使用缓存数据: {data_type} - {trade_date}")
                    return (trade_date, df, len(df), 'cached')

                # 真实API调用
                api_manager = self.config.api_manager

                # 根据数据类型选择适当的分页下载方法
                if data_type == 'daily':
                    df = api_manager.daily_data.download_daily_data(ts_code=None, start_date=trade_date, end_date=trade_date)
                elif data_type == 'daily_basic':
                    df = api_manager.download_daily_basic_paginated(trade_date=trade_date)
                elif data_type == 'moneyflow':
                    df = api_manager.download_moneyflow_paginated(trade_date=trade_date)
                elif data_type == 'stk_factor':
                    df = api_manager.technical_factors.download_stk_factor_paginated(trade_date=trade_date)
                elif data_type == 'cyq_perf':
                    df = api_manager.market_structure.download_cyq_perf_paginated(trade_date=trade_date)
                elif data_type == 'cyq_chips':
                    df = api_manager.market_structure.download_cyq_chips_paginated(trade_date=trade_date)
                elif data_type == 'moneyflow_dc':
                    df = api_manager.market_flow.download_moneyflow_dc(trade_date=trade_date)
                elif data_type == 'moneyflow_ths':
                    df = api_manager.market_flow.download_moneyflow_ths(trade_date=trade_date)
                else:
                    # 对于其他数据类型，尝试使用通用分页方法
                    api_func = getattr(api_manager.pro, data_type)
                    df = api_manager.download_with_pagination(
                        api_func,
                        limit_per_call=config['limit_per_call'],
                        trade_date=trade_date
                    )

                if not df.empty:
                    # 添加交易日期标记
                    df['trade_date'] = pd.to_datetime(trade_date)

                    # 保存到本地
                    year = trade_date[:4]
                    month = trade_date[4:6]
                    subdir = f"daily/{year}/{month}"
                    filename = f"{data_type}_{trade_date}"

                    with self.download_lock:
                        file_path = save_to_parquet(df, filename, subdir=subdir)

                    self.logger.debug(f"成功下载 {data_type} - {trade_date}: {len(df)} 条记录")
                    return (trade_date, df, len(df), 'downloaded')
                else:
                    self.logger.warning(f"{data_type} - {trade_date} 无数据")
                    return (trade_date, pd.DataFrame(), 0, 'no_data')

            except Exception as e:
                self.logger.error(f"下载 {data_type} - {trade_date} 失败: {e}")
                return (trade_date, pd.DataFrame(), 0, 'error')

        # 记录开始时间
        import time
        start_time = time.time()

        # 并行下载所有日期的数据
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(download_single_day, day): day
                for day in trading_days
            }

            # 收集结果并统计
            completed_count = 0
            cached_count = 0
            downloaded_count = 0
            error_count = 0

            for future in as_completed(futures):
                trade_date, df, record_count, source = future.result()

                if source == 'cached':
                    cached_count += 1
                elif source == 'downloaded':
                    downloaded_count += 1
                elif source == 'error':
                    error_count += 1

                if not df.empty and record_count > 0:
                    all_data.append(df)
                    results[trade_date] = record_count

                completed_count += 1
                self.logger.debug(f"进度: {completed_count}/{len(trading_days)}, "
                                f"缓存:{cached_count}, 下载:{downloaded_count}, 错误:{error_count}")

        # 计算总耗时
        total_time = time.time() - start_time
        self.download_stats[data_type] = {
            'total_days': len(trading_days),
            'cached_count': cached_count,
            'downloaded_count': downloaded_count,
            'error_count': error_count,
            'total_records': sum(results.values()) if results else 0,
            'time_spent': round(total_time, 2)
        }

        # 合并结果
        final_result = {}
        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)
            if 'trade_date' in combined_df.columns:
                date_groups = combined_df.groupby(combined_df['trade_date'].dt.strftime('%Y-%m'))
                for (year_month), group in date_groups:
                    year, month = year_month.split('-')
                    subdir = f"daily/{year}/{month}"
                    filename = f"{data_type}_{year_month}"
                    file_path = save_to_parquet(group, filename, subdir=subdir)
                    final_result[year_month] = len(group)

        self.logger.info(f"{data_type}下载统计: 总天数={len(trading_days)}, "
                        f"缓存={cached_count}, 下载={downloaded_count}, "
                        f"错误={error_count}, 总记录={sum(results.values()) if results else 0}, "
                        f"耗时={total_time:.2f}秒")

        return final_result
```

## 3. 实现建议

### 3.1 集成到现有架构

1. 将增强的分页方法添加到 `app/api_manager.py` 的 `TuShareAPIManager` 类中
2. 创建增强版并行下载器作为 `app/utils/parallel_downloader.py` 的扩展
3. 更新接口模块以使用新的分页方法

### 3.2 性能优化考虑

1. **缓存策略优化**:
   - 根据数据类型设置不同的缓存有效期
   - 实现智能缓存，对于高频更新的数据使用较短的缓存时间

2. **API限频管理**:
   - 基于API类型和调用频率动态调整限频策略
   - 实现token切换机制，有效利用多个API积分

3. **下载策略优化**:
   - 根据数据量和API限制选择合适的分页大小
   - 实现自适应批处理大小

### 3.3 错误处理和恢复

1. 实现更完善的重试机制
2. 添加错误统计和监控
3. 实现断点续传功能

## 4. 测试和验证

### 4.1 功能测试
- 验证分页功能是否能正确处理大数据集
- 确认缓存机制是否正常工作
- 测试并行下载的性能提升

### 4.2 性能测试
- 比较新旧下载方式的性能差异
- 监控API调用频率和响应时间
- 验证缓存命中率

### 4.3 稳定性测试
- 测试长时间运行的稳定性
- 验证在异常情况下的恢复能力
- 确认数据完整性

## 5. 部署说明

1. 将新的方法添加到现有类中
2. 更新配置文件以支持新的参数
3. 修改调用代码以使用新的增强功能
4. 进行回归测试确保向后兼容性