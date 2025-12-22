# 全面缓存解决方案

## 概述

本文档描述了为整个aspipe_v4项目实现全面缓存的解决方案。通过分析现有代码结构，我们提出以下缓存实现方案，以避免重复下载并提高系统效率。

## 当前问题分析

1. **生产者-消费者模式缺乏缓存检查**：新的下载调度器不检查数据是否已存在
2. **接口级别的缓存缺失**：对于按股票代码下载的数据没有缓存机制
3. **配置驱动的缓存策略**：需要通过配置文件控制不同接口的缓存行为
4. **集成现有架构**：需要无缝集成到现有的策略模式和调度器中

## 解决方案架构

### 1. 全局缓存管理器 (CacheManager)

创建一个全局缓存管理器，负责：
- 缓存策略配置
- 缓存路径管理
- 缓存状态检查
- 缓存生命周期管理

### 2. 数据存储增强 (data_storage.py)

在现有的 `data_storage.py` 文件基础上增强缓存功能：

```python
class EnhancedDataStorage:
    def __init__(self):
        self.cache_dir = Path("cache") / "downloaded"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get_data_cache_path(self, interface_name: str, **kwargs) -> str:
        """生成基于接口和参数的缓存路径"""
        # 对于不同类型的参数，生成不同的缓存路径
        if 'ts_code' in kwargs:
            ts_code = kwargs['ts_code']
            if 'trade_date' in kwargs:
                # 单日数据: interface/ts_code/trade_date.parquet
                path = self.cache_dir / interface_name / ts_code / f"{kwargs['trade_date']}.parquet"
            elif 'start_date' in kwargs and 'end_date' in kwargs:
                # 日期范围数据: interface/ts_code/start_date_end_date.parquet
                path = self.cache_dir / interface_name / ts_code / f"{kwargs['start_date']}-{kwargs['end_date']}.parquet"
            else:
                # 股票全部历史数据: interface/ts_code/all.parquet
                path = self.cache_dir / interface_name / ts_code / "all.parquet"
        elif 'trade_date' in kwargs:
            # 全市场日度数据: interface/date/yyyy/mm/dd.parquet
            trade_date = kwargs['trade_date']
            year = trade_date[:4]
            month = trade_date[4:6]
            day = trade_date[6:8]
            path = self.cache_dir / interface_name / year / month / f"{day}.parquet"
        else:
            # 其他情况使用参数哈希
            import hashlib
            param_str = str(sorted(kwargs.items()))
            param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]
            path = self.cache_dir / interface_name / f"{param_hash}.parquet"

        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    def is_data_cached(self, interface_name: str, cache_ttl_hours: int = 24, **kwargs) -> bool:
        """检查数据是否已缓存且未过期"""
        cache_path = self.get_data_cache_path(interface_name, **kwargs)
        if not Path(cache_path).exists():
            return False

        # 检查缓存是否过期
        file_mtime = Path(cache_path).stat().st_mtime
        cache_age = datetime.now().timestamp() - file_mtime
        return cache_age < (cache_ttl_hours * 3600)

    def load_cached_data(self, interface_name: str, **kwargs) -> pd.DataFrame:
        """加载缓存数据"""
        cache_path = self.get_data_cache_path(interface_name, **kwargs)
        if Path(cache_path).exists():
            try:
                df = pd.read_parquet(cache_path)
                logger.info(f"从缓存加载数据: {interface_name}, 路径: {cache_path}")
                return df
            except Exception as e:
                logger.warning(f"加载缓存失败: {cache_path}, 错误: {e}")
                return pd.DataFrame()
        return pd.DataFrame()

    def save_data_to_cache(self, df: pd.DataFrame, interface_name: str, **kwargs) -> bool:
        """保存数据到缓存"""
        if df is None or df.empty:
            return False

        cache_path = self.get_data_cache_path(interface_name, **kwargs)
        try:
            df.to_parquet(cache_path, index=False)
            logger.info(f"数据已保存到缓存: {interface_name}, 路径: {cache_path}")
            return True
        except Exception as e:
            logger.error(f"保存缓存失败: {cache_path}, 错误: {e}")
            return False
```

### 3. 基础下载器增强 (base.py)

修改 `BaseDownloader` 类以支持缓存：

```python
class CachingDownloader:
    def __init__(self, pro_api):
        self.pro = pro_api
        self.logger = logging.getLogger(self.__class__.__module__)
        from data_storage import EnhancedDataStorage
        self.cache_manager = EnhancedDataStorage()

    def download_with_cache(self, api_func, interface_name: str, cache_enabled: bool = True,
                           cache_ttl_hours: int = 24, **kwargs) -> pd.DataFrame:
        """带缓存功能的下载方法"""
        if not cache_enabled:
            # 不使用缓存，直接下载
            return self.download_with_retry(api_func, **kwargs)

        # 检查缓存
        if self.cache_manager.is_data_cached(interface_name, cache_ttl_hours=cache_ttl_hours, **kwargs):
            cached_data = self.cache_manager.load_cached_data(interface_name, **kwargs)
            if not cached_data.empty:
                return cached_data

        # 缓存未命中，执行下载
        df = self.download_with_retry(api_func, **kwargs)

        # 保存到缓存
        if not df.empty:
            self.cache_manager.save_data_to_cache(df, interface_name, **kwargs)

        return df
```

### 4. 接口模块缓存增强

在每个接口模块中实现缓存功能：

#### 4.1 股票相关接口 (holders_data.py, basic_data.py)

```python
# 在 holders_data.py 中
def download_stk_rewards_cached(self, ts_code: str, cache_enabled: bool = True, cache_ttl_hours: int = 24) -> pd.DataFrame:
    """带缓存的stk_rewards下载"""
    if cache_enabled:
        # 检查缓存
        cache_path = self._get_cache_path('stk_rewards', ts_code)
        if self._is_cache_valid(cache_path, cache_ttl_hours):
            try:
                df = pd.read_parquet(cache_path)
                self.logger.info(f"从缓存加载stk_rewards数据: {ts_code}")
                return df
            except Exception as e:
                self.logger.warning(f"缓存加载失败: {e}")

    # 执行下载
    df = self.download_stk_rewards(ts_code)

    # 保存到缓存
    if cache_enabled and not df.empty:
        self._save_to_cache(df, 'stk_rewards', ts_code)

    return df

def _get_cache_path(self, interface_name: str, ts_code: str) -> str:
    """生成股票数据缓存路径"""
    cache_dir = Path("cache") / "holders" / interface_name
    cache_dir.mkdir(parents=True, exist_ok=True)
    return str(cache_dir / f"{ts_code}.parquet")

def _is_cache_valid(self, cache_path: str, ttl_hours: int) -> bool:
    """检查缓存是否有效"""
    if not Path(cache_path).exists():
        return False
    file_mtime = datetime.fromtimestamp(Path(cache_path).stat().st_mtime)
    cache_age = datetime.now() - file_mtime
    return cache_age < timedelta(hours=ttl_hours)

def _save_to_cache(self, df: pd.DataFrame, interface_name: str, ts_code: str):
    """保存数据到缓存"""
    cache_path = self._get_cache_path(interface_name, ts_code)
    try:
        df.to_parquet(cache_path, index=False)
        self.logger.info(f"保存{interface_name}数据到缓存: {ts_code}")
    except Exception as e:
        self.logger.error(f"缓存保存失败: {e}")
```

#### 4.2 日度数据接口 (daily_data.py)

```python
# 在 daily_data.py 中
def download_daily_basic_cached(self, trade_date: str, cache_enabled: bool = True, cache_ttl_hours: int = 1) -> pd.DataFrame:
    """带缓存的daily_basic下载（TTL较短，因为是日度数据）"""
    if cache_enabled:
        cache_path = self._get_cache_path('daily_basic', trade_date)
        if self._is_cache_valid(cache_path, cache_ttl_hours):
            try:
                df = pd.read_parquet(cache_path)
                self.logger.info(f"从缓存加载daily_basic数据: {trade_date}")
                return df
            except Exception as e:
                self.logger.warning(f"缓存加载失败: {e}")

    # 执行下载
    df = self.download_daily_basic(trade_date)

    # 保存到缓存
    if cache_enabled and not df.empty:
        self._save_to_cache(df, 'daily_basic', trade_date)

    return df
```

### 5. 下载策略增强 (download_strategies.py)

修改现有的下载策略以支持缓存：

```python
# 在 download_strategies.py 中修改 DownloadStrategy 基类
class DownloadStrategy(ABC):
    def __init__(self, interface_name: str, downloader: TuShareDownloader = None):
        self.interface_name = interface_name
        self.downloader = downloader or TuShareDownloader()
        self.config_adapter = ConfigAdapter()
        self.param_adapter = ParameterAdapterManager()
        self.logger = logging.getLogger(f"{__name__}.{interface_name}")
        self.max_retries = self.config_adapter.get_max_retries(interface_name)
        self.rate_limit = self.config_adapter.get_rate_limit(interface_name)
        self.batch_size = self.config_adapter.get_batch_size(interface_name)

        # 从配置获取缓存设置
        cache_settings = self.config_adapter.get_cache_settings(interface_name)
        self.cache_enabled = cache_settings['cache_enabled']
        self.cache_ttl_hours = cache_settings['cache_ttl_hours']

        # 创建缓存管理器
        from data_storage import EnhancedDataStorage
        self.cache_manager = EnhancedDataStorage()

    def _get_cache_key(self, **kwargs) -> dict:
        """生成缓存键，过滤掉不重要的参数"""
        # 只保留影响数据结果的关键参数
        cache_key = {}
        for key in ['ts_code', 'trade_date', 'start_date', 'end_date', 'period']:
            if key in kwargs and kwargs[key] is not None:
                cache_key[key] = kwargs[key]
        return cache_key

    def _download_with_cache_fallback(self, api_func, **kwargs):
        """带缓存回退的下载方法"""
        cache_key = self._get_cache_key(**kwargs)

        # 如果启用缓存，检查缓存
        if self.cache_enabled and self._can_use_cache(**kwargs):
            cache_result = self.cache_manager.load_cached_data(self.interface_name, **cache_key)
            if not cache_result.empty:
                self.logger.info(f"使用缓存数据: {self.interface_name}")
                return cache_result

        # 执行实际下载
        result = self.download_with_retry(api_func, **kwargs)

        # 保存到缓存
        if self.cache_enabled and not result.empty:
            self.cache_manager.save_data_to_cache(result, self.interface_name, **cache_key)

        return result

    def _can_use_cache(self, **kwargs) -> bool:
        """判断是否可以使用缓存"""
        # 对于某些参数组合，不使用缓存
        if 'ts_code' in kwargs and kwargs.get('ts_code') and self.interface_name in ['stk_rewards', 'top10_holders', 'pledge_detail', 'fina_audit']:
            # 股票特定数据可以缓存
            return True
        elif 'trade_date' in kwargs and self.interface_name in ['daily_basic', 'moneyflow']:
            # 按日期数据可以缓存（短期TTL）
            return True
        elif 'start_date' in kwargs and 'end_date' in kwargs:
            # 按日期范围数据可以缓存
            return True
        elif 'period' in kwargs and self.interface_name in ['income', 'balancesheet', 'cashflow']:
            # 财务报告期数据可以缓存
            return True
        else:
            # 其他情况默认可以缓存
            return True
```

### 6. 配置增强 (enhanced_download_config.py)

在现有配置中增强缓存设置：

```python
# 在 enhanced_download_config.py 的 InterfaceConfig 中
@dataclass
class InterfaceConfig:
    enabled: bool = True
    priority: DataTypePriority = DataTypePriority.MEDIUM
    max_retries: int = 3
    timeout: int = 30
    rate_limit: float = 2.0
    strategy: DownloadStrategy = DownloadStrategy.SEQUENTIAL
    batch_size: int = 100
    concurrency: int = 1
    required_points: int = 0
    api_params: Dict[str, Any] = field(default_factory=dict)
    cache_enabled: bool = True
    cache_ttl_hours: int = 24  # 缓存有效时间（小时）
    cache_strategy: str = 'full'  # 'full', 'incremental', 'none'
```

### 7. 调度器增强 (download_scheduler.py)

修改下载调度器以支持缓存：

```python
# 在 download_scheduler.py 中
def _execute_daily_download(self, **kwargs) -> pd.DataFrame:
    """执行日度数据下载（带缓存检查）"""
    interface_name = kwargs.get('interface_name')
    start_date = kwargs.get('start_date')
    end_date = kwargs.get('end_date')
    trading_days = kwargs.get('trading_days', [])

    # 检查接口配置以确定是否启用缓存
    config = get_interface_config(interface_name)
    cache_enabled = config.cache_enabled if config else True
    cache_ttl = config.cache_ttl_hours if config else 24

    self.logger.info(f"开始下载日度数据: {interface_name}, 日期范围: {start_date} - {end_date}")

    try:
        from download_strategies import get_strategy
        strategy = get_strategy(interface_name, downloader=self.downloader)

        # 更新策略的缓存设置
        if hasattr(strategy, 'cache_enabled'):
            strategy.cache_enabled = cache_enabled
            strategy.cache_ttl_hours = cache_ttl

        # 根据接口类型执行不同的下载逻辑
        if interface_name in ['daily', 'daily_basic', 'moneyflow']:
            # 对于daily_basic等按日期的数据，先检查每个日期的缓存
            if interface_name == 'daily_basic' and cache_enabled:
                all_data = []
                for trade_date in trading_days:
                    # 检查单日缓存
                    if strategy._can_use_cache(trade_date=trade_date):
                        cached_data = strategy.cache_manager.load_cached_data(
                            interface_name, trade_date=trade_date
                        )
                        if not cached_data.empty:
                            all_data.append(cached_data)
                            continue

                    # 没有缓存则下载
                    day_result = strategy.download(trade_date=trade_date)
                    if not day_result.empty:
                        all_data.append(day_result)
                        # 保存到缓存
                        if cache_enabled:
                            strategy.cache_manager.save_data_to_cache(
                                day_result, interface_name, trade_date=trade_date
                            )
                result = pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()
            else:
                # 其他日度数据
                result = strategy.download(start_date=start_date, end_date=end_date)
        else:
            result = strategy.download(start_date=start_date, end_date=end_date)

        with self.stats_lock:
            self.stats['total_downloaded'] += len(result) if result is not None else 0

        self.logger.info(f"完成下载 {interface_name}，获得 {len(result) if result is not None else 0} 条记录")

        # 提交存储任务
        if result is not None and not result.empty:
            filename = f"{interface_name}_{start_date}_{end_date}"
            subdir = f"daily/{start_date[:4]}/{start_date[4:6]}"

            self.task_manager.add_storage_task(
                data=result,
                filename=filename,
                subdir=subdir,
                priority=TaskPriority.MEDIUM
            )

        return result

    except Exception as e:
        self.logger.error(f"下载日度数据 {interface_name} 失败: {e}")
        raise
```

### 8. 任务队列管理器增强 (task_queue_manager.py)

在任务队列管理器中添加缓存检查：

```python
# 在 task_queue_manager.py 中
def add_task(self, task_type: str, target_func, priority: TaskPriority = TaskPriority.MEDIUM,
             args: tuple = (), kwargs: dict = None, max_retries: int = 3,
             wait_for_completion: bool = False, metadata: dict = None) -> str:
    """添加任务时检查缓存"""
    if kwargs is None:
        kwargs = {}

    # 检查是否需要缓存检查
    interface_name = kwargs.get('interface_name')
    if interface_name:
        config = get_interface_config(interface_name)
        if config and config.cache_enabled:
            # 尝试从缓存获取结果
            cache_result = self._check_cache_before_task(interface_name, kwargs)
            if cache_result is not None:
                # 缓存命中，不需要创建任务
                self.logger.info(f"缓存命中: {interface_name}, 跳过任务创建")
                # 直接触发存储任务
                if not cache_result.empty:
                    self.add_storage_task(
                        data=cache_result,
                        filename=f"{interface_name}_{hash(str(kwargs))}",
                        subdir="cached",
                        priority=priority
                    )
                return f"cached_{interface_name}_{hash(str(kwargs))}"

    # 原有任务添加逻辑
    return self._add_task_impl(task_type, target_func, priority, args, kwargs, max_retries, wait_for_completion, metadata)

def _check_cache_before_task(self, interface_name: str, kwargs: dict) -> Optional[pd.DataFrame]:
    """在创建任务前检查缓存"""
    try:
        from data_storage import EnhancedDataStorage
        cache_manager = EnhancedDataStorage()

        # 使用接口配置的TTL
        config = get_interface_config(interface_name)
        ttl_hours = config.cache_ttl_hours if config else 24

        # 检查缓存
        if cache_manager.is_data_cached(interface_name, ttl_hours, **kwargs):
            return cache_manager.load_cached_data(interface_name, **kwargs)
        return None
    except Exception as e:
        self.logger.warning(f"缓存检查失败: {e}")
        return None
```

## 实施步骤

1. **创建 EnhancedDataStorage 类** - 扩展现有 data_storage 模块
2. **修改基础下载器** - 集成缓存功能到 BaseDownloader
3. **更新接口模块** - 为每个接口实现缓存逻辑
4. **增强下载策略** - 修改策略基类和具体策略
5. **更新配置** - 为所有接口添加缓存配置
6. **修改调度器** - 在调度器中集成缓存检查
7. **测试验证** - 验证缓存功能正常工作

## 缓存策略

1. **股票特定数据**（stk_rewards, top10_holders, pledge_detail, fina_audit, pro_bar）：TTL 24小时，按股票代码缓存
2. **日度数据**（daily_basic, moneyflow等）：TTL 1-6小时，按日期缓存
3. **财务数据**（income, balancesheet等）：TTL 24-48小时，按报告期缓存
4. **静态数据**（stock_basic, trade_cal等）：TTL 168小时（1周），全量缓存

## 优势

1. **避免重复下载** - 检查缓存后避免不必要的API调用
2. **提高效率** - 快速返回已下载数据
3. **减少API调用** - 节省积分并避免频率限制
4. **向后兼容** - 不破坏现有架构
5. **配置驱动** - 可通过配置文件控制缓存行为

这个全面的缓存解决方案将集成到现有系统中，为所有接口提供有效的缓存机制，解决重复下载问题。