# 改进的缓存解决方案

## 概述

本文档描述了为aspipe_v4项目实现集成缓存的改进解决方案。基于现有架构，我们提出一个与当前系统深度融合的缓存实现方案，避免重复实现和架构混乱。

## 改进方案特点

### 1. 与现有架构集成
- 充分利用现有的`data_storage.py`缓存机制
- 通过配置适配器统一管理缓存设置
- 保持与现有生产者-消费者模式的兼容性

### 2. 智能缓存检查
- 在任务调度前进行缓存检查，避免不必要的下载
- 根据接口类型和用户积分等级动态调整缓存策略
- 合理的TTL设置避免数据过期问题

## 解决方案架构

### 1. 增强数据存储模块 (data_storage.py)

扩展现有`data_storage.py`模块，增强缓存功能：

```python
from pathlib import Path
import hashlib
from datetime import datetime, timedelta

class CacheManager:
    """统一的缓存管理器"""

    def __init__(self):
        self.cache_dir = Path(__file__).parent.parent / 'cache' / 'downloaded'
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger(__name__)

    def get_cache_path(self, interface_name: str, **kwargs) -> str:
        """生成基于接口和参数的缓存路径"""
        # 对于不同类型的参数，生成不同的缓存路径
        if 'ts_code' in kwargs:
            ts_code = kwargs['ts_code']
            if 'trade_date' in kwargs:
                # 单日数据: cache/interface/ts_code/trade_date.parquet
                path = self.cache_dir / interface_name / ts_code / f"{kwargs['trade_date']}.parquet"
            elif 'start_date' in kwargs and 'end_date' in kwargs:
                # 日期范围数据: cache/interface/ts_code/start_date_end_date.parquet
                path = self.cache_dir / interface_name / ts_code / f"{kwargs['start_date']}-{kwargs['end_date']}.parquet"
            else:
                # 股票全部历史数据: cache/interface/ts_code/all.parquet
                path = self.cache_dir / interface_name / ts_code / "all.parquet"
        elif 'trade_date' in kwargs:
            # 全市场日度数据: cache/interface/date/yyyy/mm/dd.parquet
            trade_date = kwargs['trade_date']
            year = trade_date[:4]
            month = trade_date[4:6]
            day = trade_date[6:8]
            path = self.cache_dir / interface_name / year / month / f"{day}.parquet"
        elif 'period' in kwargs:
            # 财务报告期数据: cache/interface/period/yyyy/period.parquet
            period = kwargs['period']
            year = period[:4]
            path = self.cache_dir / interface_name / year / f"{period}.parquet"
        else:
            # 其他情况使用参数哈希
            param_str = str(sorted(kwargs.items()))
            param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]
            path = self.cache_dir / interface_name / f"{param_hash}.parquet"

        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    def is_data_cached(self, interface_name: str, cache_ttl_hours: int = 24, **kwargs) -> bool:
        """检查数据是否已缓存且未过期"""
        cache_path = self.get_cache_path(interface_name, **kwargs)
        if not Path(cache_path).exists():
            return False

        # 检查缓存是否过期
        file_mtime = Path(cache_path).stat().st_mtime
        cache_age = datetime.now().timestamp() - file_mtime
        return cache_age < (cache_ttl_hours * 3600)

    def load_cached_data(self, interface_name: str, **kwargs) -> pd.DataFrame:
        """加载缓存数据"""
        cache_path = self.get_cache_path(interface_name, **kwargs)
        if Path(cache_path).exists():
            try:
                df = pd.read_parquet(cache_path)
                self.logger.info(f"从缓存加载数据: {interface_name}, 路径: {cache_path}")
                return df
            except Exception as e:
                self.logger.warning(f"加载缓存失败: {cache_path}, 错误: {e}")
                return pd.DataFrame()
        return pd.DataFrame()

    def save_data_to_cache(self, df: pd.DataFrame, interface_name: str, **kwargs) -> bool:
        """保存数据到缓存"""
        if df is None or df.empty:
            return False

        cache_path = self.get_cache_path(interface_name, **kwargs)
        try:
            df.to_parquet(cache_path, index=False)
            self.logger.info(f"数据已保存到缓存: {interface_name}, 路径: {cache_path}")
            return True
        except Exception as e:
            self.logger.error(f"保存缓存失败: {cache_path}, 错误: {e}")
            return False

# 全局缓存管理器实例
_cache_manager = CacheManager()

def get_cache_manager() -> CacheManager:
    """获取全局缓存管理器实例"""
    return _cache_manager
```

### 2. 在任务调度器层面集成缓存检查 (download_scheduler.py)

在任务创建之前检查缓存，避免不必要的下载任务：

```python
# 在 download_scheduler.py 中修改 schedule_download_tasks 方法
def _should_skip_download_task(self, interface_name: str, **task_kwargs) -> tuple[bool, pd.DataFrame]:
    """
    检查是否应该跳过下载任务（因为已有有效缓存）

    Returns:
        (should_skip: bool, cached_data: pd.DataFrame)
    """
    # 获取缓存设置
    from config_adapter import get_interface_cache_settings
    cache_settings = get_interface_cache_settings(interface_name)

    if not cache_settings['enabled']:
        return False, pd.DataFrame()

    # 创建缓存管理器
    from data_storage import get_cache_manager
    cache_manager = get_cache_manager()

    # 提取缓存检查需要的参数
    cache_kwargs = {}
    for key in ['ts_code', 'trade_date', 'start_date', 'end_date', 'period']:
        if key in task_kwargs:
            cache_kwargs[key] = task_kwargs[key]

    # 检查缓存
    if cache_manager.is_data_cached(
        interface_name,
        cache_ttl_hours=cache_settings['ttl_hours'],
        **cache_kwargs
    ):
        # 缓存存在，加载数据
        cached_data = cache_manager.load_cached_data(interface_name, **cache_kwargs)
        if not cached_data.empty:
            self.logger.info(f"使用缓存数据: {interface_name}")
            return True, cached_data

    return False, pd.DataFrame()

def _schedule_daily_interface(self, interface_name: str, priority: TaskPriority) -> str:
    """
    调度日度数据接口下载任务（带缓存检查）
    """
    # 获取交易日列表
    trading_days = self._get_trading_days()

    # 将交易日列表分批，每批处理一段时间范围
    batch_size = 30  # 每批处理30个交易日
    task_ids = []

    for i in range(0, len(trading_days), batch_size):
        batch_days = trading_days[i:i + batch_size]
        batch_start = batch_days[0]
        batch_end = batch_days[-1]

        # 创建任务参数
        task_params = {
            'interface_name': interface_name,
            'start_date': batch_start,
            'end_date': batch_end,
            'trading_days': batch_days
        }

        # 检查是否应该跳过此任务
        should_skip, cached_data = self._should_skip_download_task(interface_name, **task_params)
        if should_skip:
            # 直接创建存储任务
            filename = f"{interface_name}_{batch_start}_{batch_end}"
            subdir = f"daily/{batch_start[:4]}/{batch_start[4:6]}"

            self.task_manager.add_storage_task(
                data=cached_data,
                filename=filename,
                subdir=subdir,
                priority=priority
            )
            continue

        # 提交下载任务
        task_id = self.task_manager.add_task(
            task_type='download',
            target_func=self._execute_daily_download,
            priority=priority,
            kwargs=task_params,
            max_retries=3,
            metadata={
                'interface': interface_name,
                'date_range': f"{batch_start} to {batch_end}"
            }
        )
        if task_id:
            task_ids.append(task_id)

    # 对于有多个批次的接口，创建一个聚合任务ID
    if len(task_ids) == 1:
        return task_ids[0]
    elif len(task_ids) > 1:
        return task_ids[0]
    else:
        return None
```

### 3. 优化下载策略 (download_strategies.py)

在下载策略中集成缓存功能，但保持与现有架构的兼容性：

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
        from data_storage import get_cache_manager
        self.cache_manager = get_cache_manager()

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

### 4. 优化配置管理 (config_adapter.py)

增强配置适配器以更好地支持缓存：

```python
# 在 config_adapter.py 中修改 get_cache_settings 方法
def get_cache_settings(self, interface_name: str) -> Dict[str, Any]:
    """
    获取接口缓存设置
    """
    config = self.get_config(interface_name)

    if isinstance(config, InterfaceConfig):
        return {
            'enabled': config.cache_enabled and self._is_cache_applicable(interface_name),
            'ttl_hours': config.cache_ttl_hours
        }

    # 默认返回启用缓存，24小时TTL
    return {
        'enabled': True,
        'ttl_hours': 24
    }

def _is_cache_applicable(self, interface_name: str) -> bool:
    """
    检查接口是否适合使用缓存
    """
    # 根据接口类型和用户积分等级判断是否适合缓存
    required_points = self.get_required_points(interface_name)

    # 如果用户积分不足，不使用缓存（避免缓存过时数据）
    if self.user_points < required_points:
        return False

    # 某些接口不适合缓存（如实时性要求高的数据）
    non_cache_interfaces = ['realtime_quotes', 'tick_data']  # 示例接口名
    if interface_name in non_cache_interfaces:
        return False

    return True
```

### 5. 优化任务队列管理器 (task_queue_manager.py)

在任务队列管理器中添加缓存检查功能：

```python
# 在 task_queue_manager.py 中添加缓存检查方法
def add_task_with_cache_check(self,
                             task_type: str,
                             target_func: Callable,
                             interface_name: str,
                             priority: TaskPriority = TaskPriority.MEDIUM,
                             args: tuple = None,
                             kwargs: dict = None,
                             max_retries: int = 3,
                             metadata: Dict[str, Any] = None,
                             dependencies: List[str] = None,
                             wait_for_completion: bool = False) -> str:
    """
    添加任务时检查缓存，如果缓存有效则直接处理数据
    """
    if args is None:
        args = ()
    if kwargs is None:
        kwargs = {}
    if metadata is None:
        metadata = {}
    if dependencies is None:
        dependencies = []

    # 检查是否需要缓存检查
    if interface_name:
        from config_adapter import get_interface_cache_settings
        cache_settings = get_interface_cache_settings(interface_name)

        if cache_settings['enabled']:
            # 检查缓存
            from data_storage import get_cache_manager
            cache_manager = get_cache_manager()

            # 提取缓存检查参数
            cache_kwargs = {}
            for key in ['ts_code', 'trade_date', 'start_date', 'end_date', 'period']:
                if key in kwargs:
                    cache_kwargs[key] = kwargs[key]

            if cache_manager.is_data_cached(interface_name, cache_settings['ttl_hours'], **cache_kwargs):
                cached_data = cache_manager.load_cached_data(interface_name, **cache_kwargs)
                if not cached_data.empty:
                    self.logger.info(f"缓存命中: {interface_name}, 跳过任务创建")
                    # 直接创建存储任务
                    if task_type == 'download' and wait_for_completion:
                        # 如果是下载任务并且需要等待完成，直接创建存储任务
                        from storage_worker import submit_data_to_storage
                        filename = f"{interface_name}_{hash(str(cache_kwargs))}"
                        subdir = "cached"
                        submit_data_to_storage(cached_data, filename, subdir)
                        return f"cached_{interface_name}_{hash(str(cache_kwargs))}"

    # 原有任务添加逻辑
    return self.add_task(
        task_type=task_type,
        target_func=target_func,
        priority=priority,
        args=args,
        kwargs=kwargs,
        max_retries=max_retries,
        metadata=metadata,
        dependencies=dependencies,
        wait_for_completion=wait_for_completion
    )
```

## 实施步骤

1. **创建 CacheManager 类** - 扩展现有 data_storage 模块
2. **修改调度器** - 在任务创建前集成缓存检查
3. **更新下载策略** - 集成缓存回退机制
4. **优化配置** - 增强缓存设置管理
5. **测试验证** - 验证缓存功能正常工作

## 缓存策略

1. **股票特定数据**（stk_rewards, top10_holders, pledge_detail, fina_audit, pro_bar）：TTL 24小时，按股票代码缓存
2. **日度数据**（daily_basic, moneyflow等）：TTL 1-6小时，按日期缓存
3. **财务数据**（income, balancesheet等）：TTL 24-48小时，按报告期缓存
4. **静态数据**（stock_basic, trade_cal等）：TTL 168小时（1周），全量缓存

## 优势

1. **与现有架构无缝集成** - 不破坏现有设计模式
2. **避免重复实现** - 基于现有缓存机制扩展
3. **智能缓存策略** - 根据接口类型和用户积分动态调整
4. **性能优化** - 在最合适的时机进行缓存检查
5. **易于维护** - 统一的缓存管理，减少代码复杂度
6. **向后兼容** - 保持与现有接口和配置的兼容性

这个改进的缓存解决方案将与现有系统深度融合，最大化利用现有架构的优势，同时提供有效的缓存功能。