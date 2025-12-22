# 优化的缓存解决方案

## 概述

本文档描述了为aspipe_v4项目实现的优化缓存解决方案。该方案完全基于现有架构进行优化，避免重复实现和架构混乱，充分利用现有的`data_storage.py`模块和配置系统。

## 优化方案特点

### 1. 基于现有架构
- 扩展现有的`data_storage.py`缓存机制，而非重新实现
- 利用现有的缓存路径结构(`data/`目录)
- 通过配置适配器统一管理缓存设置
- 保持与现有生产者-消费者模式的兼容性

### 2. 智能缓存检查
- 在任务调度前进行缓存检查，避免不必要的下载
- 根据接口类型和用户积分等级动态调整缓存策略
- 合理的TTL设置避免数据过期问题

## 解决方案架构

### 1. 扩展现有数据存储模块 (data_storage.py)

扩展现有`data_storage.py`模块，增强缓存功能而不用创建新的类：

```python
from pathlib import Path
import hashlib
from datetime import datetime, timedelta

def get_interface_cache_path(data_type: str, **kwargs) -> str:
    """
    生成基于接口和参数的缓存路径（扩展原有get_cache_path函数）

    Args:
        data_type: 数据类型 (接口名称)
        **kwargs: 接口参数 (如 ts_code, trade_date, start_date, end_date, period)

    Returns:
        缓存文件路径
    """
    # 使用现有DATA_DIR路径，但支持更多参数组合
    if 'ts_code' in kwargs:
        ts_code = kwargs['ts_code']
        if 'trade_date' in kwargs:
            # 单日数据: data/interface/ts_code/trade_date.parquet
            subdir = f"{data_type}/{ts_code}"
            filename = f"{kwargs['trade_date']}.parquet"
        elif 'start_date' in kwargs and 'end_date' in kwargs:
            # 日期范围数据: data/interface/ts_code/start_date_end_date.parquet
            subdir = f"{data_type}/{ts_code}"
            filename = f"{kwargs['start_date']}-{kwargs['end_date']}.parquet"
        else:
            # 股票全部历史数据: data/interface/ts_code/all.parquet
            subdir = f"{data_type}/{ts_code}"
            filename = "all.parquet"
    elif 'trade_date' in kwargs:
        # 全市场日度数据: data/interface/yyyy/mm/dd.parquet
        trade_date = kwargs['trade_date']
        year = trade_date[:4]
        month = trade_date[4:6]
        subdir = f"{data_type}/{year}/{month}"
        filename = f"{trade_date}.parquet"
    elif 'period' in kwargs:
        # 财务报告期数据: data/interface/yyyy/period.parquet
        period = kwargs['period']
        year = period[:4]
        subdir = f"{data_type}/{year}"
        filename = f"{period}.parquet"
    else:
        # 其他情况使用参数哈希
        param_str = str(sorted(kwargs.items()))
        param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]
        subdir = data_type
        filename = f"{param_hash}.parquet"

    full_path = DATA_DIR / subdir / filename
    full_path.parent.mkdir(parents=True, exist_ok=True)
    return str(full_path)

def is_interface_data_cached(data_type: str, cache_ttl_hours: int = 24, **kwargs) -> bool:
    """
    检查接口数据是否已缓存且未过期（扩展原有is_data_cached函数）

    Args:
        data_type: 数据类型 (接口名称)
        cache_ttl_hours: 缓存有效时间（小时）
        **kwargs: 接口参数
    """
    cache_path = get_interface_cache_path(data_type, **kwargs)
    if not Path(cache_path).exists():
        return False

    # 检查缓存是否过期
    file_mtime = Path(cache_path).stat().st_mtime
    cache_age = datetime.now().timestamp() - file_mtime
    return cache_age < (cache_ttl_hours * 3600)

def load_interface_cached_data(data_type: str, **kwargs) -> pd.DataFrame:
    """
    加载接口的缓存数据（扩展原有load_from_parquet函数）

    Args:
        data_type: 数据类型 (接口名称)
        **kwargs: 接口参数

    Returns:
        DataFrame或空DataFrame
    """
    cache_path = get_interface_cache_path(data_type, **kwargs)
    if Path(cache_path).exists():
        try:
            df = pd.read_parquet(cache_path)
            logger.info(f"从缓存加载数据: {data_type}, 路径: {cache_path}")
            return df
        except Exception as e:
            logger.warning(f"加载缓存失败: {cache_path}, 错误: {e}")
            return pd.DataFrame()
    return pd.DataFrame()

def save_interface_data_to_cache(df: pd.DataFrame, data_type: str, **kwargs) -> bool:
    """
    保存接口数据到缓存（扩展原有save_to_parquet函数）

    Args:
        df: 要保存的DataFrame
        data_type: 数据类型 (接口名称)
        **kwargs: 接口参数

    Returns:
        保存是否成功
    """
    if df is None or df.empty:
        return False

    cache_path = get_interface_cache_path(data_type, **kwargs)
    try:
        df.to_parquet(cache_path, index=False)
        logger.info(f"数据已保存到缓存: {data_type}, 路径: {cache_path}")
        return True
    except Exception as e:
        logger.error(f"保存缓存失败: {cache_path}, 错误: {e}")
        return False

# 保留原有函数以保持向后兼容性
# is_data_cached, get_cache_path, is_data_fresh, save_to_parquet, load_from_parquet
```

### 2. 在任务调度器层面集成缓存检查 (download_scheduler.py)

在任务创建之前检查缓存，避免不必要的下载任务：

```python
# 在 download_scheduler.py 中修改 schedule_download_tasks 方法
def _should_skip_download_task(self, interface_name: str, **task_kwargs) -> tuple[bool, pd.DataFrame]:
    """
    检查是否应该跳过下载任务（因为已有有效缓存）
    基于现有配置系统和数据存储模块

    Returns:
        (should_skip: bool, cached_data: pd.DataFrame)
    """
    # 获取缓存设置 - 利用现有配置系统
    from config_adapter import get_interface_cache_settings
    cache_settings = get_interface_cache_settings(interface_name)

    if not cache_settings['enabled']:
        return False, pd.DataFrame()

    # 使用扩展现有的数据存储功能
    from data_storage import is_interface_data_cached, load_interface_cached_data

    # 提取缓存检查需要的参数
    cache_kwargs = {}
    for key in ['ts_code', 'trade_date', 'start_date', 'end_date', 'period']:
        if key in task_kwargs:
            cache_kwargs[key] = task_kwargs[key]

    # 检查缓存
    if is_interface_data_cached(
        interface_name,
        cache_ttl_hours=cache_settings['ttl_hours'],
        **cache_kwargs
    ):
        # 缓存存在，加载数据
        cached_data = load_interface_cached_data(interface_name, **cache_kwargs)
        if not cached_data.empty:
            self.logger.info(f"使用缓存数据: {interface_name}")
            return True, cached_data

    return False, pd.DataFrame()

def _schedule_daily_interface(self, interface_name: str, priority: TaskPriority) -> str:
    """
    调度日度数据接口下载任务（带缓存检查）
    基于现有架构进行优化
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

        # 检查是否应该跳过此任务（使用扩展的缓存功能）
        should_skip, cached_data = self._should_skip_download_task(interface_name, **task_params)
        if should_skip:
            # 直接创建存储任务，使用现有存储功能
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

def _execute_daily_download(self, **kwargs) -> pd.DataFrame:
    """
    执行日度数据下载（集成缓存逻辑）
    """
    interface_name = kwargs.get('interface_name')
    start_date = kwargs.get('start_date')
    end_date = kwargs.get('end_date')
    trading_days = kwargs.get('trading_days', [])

    self.logger.info(f"开始下载日度数据: {interface_name}, 日期范围: {start_date} - {end_date}")

    try:
        from download_strategies import get_strategy
        strategy = get_strategy(interface_name, downloader=self.downloader)

        # 申请速率限制令牌
        if not acquire_tokens(interface_name, 1.0, timeout=300):
            raise Exception(f"无法获取 {interface_name} 的速率限制令牌")

        # 在策略中集成缓存检查
        if interface_name in ['daily', 'daily_basic', 'moneyflow']:
            if interface_name == 'daily_basic':
                # daily_basic 按单日下载，集成缓存检查
                all_data = []
                for trade_date in trading_days:
                    # 检查单日数据缓存
                    from config_adapter import get_interface_cache_settings
                    from data_storage import is_interface_data_cached, load_interface_cached_data, save_interface_data_to_cache

                    cache_settings = get_interface_cache_settings(interface_name)
                    if cache_settings['enabled'] and is_interface_data_cached(
                        interface_name,
                        cache_ttl_hours=cache_settings['ttl_hours'],
                        trade_date=trade_date
                    ):
                        cached_result = load_interface_cached_data(interface_name, trade_date=trade_date)
                        if not cached_result.empty:
                            all_data.append(cached_result)
                            self.logger.info(f"使用缓存数据: {interface_name}, 日期: {trade_date}")
                            continue

                    # 未命中缓存，执行下载
                    day_result = strategy.download(trade_date=trade_date)
                    if not day_result.empty:
                        all_data.append(day_result)
                        # 保存到缓存
                        if cache_settings['enabled']:
                            save_interface_data_to_cache(day_result, interface_name, trade_date=trade_date)
                    time.sleep(0.5)  # 应用速率限制
                result = pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()
            else:
                # 对于其他支持日期范围的接口，首先检查整个范围的缓存
                from config_adapter import get_interface_cache_settings
                from data_storage import is_interface_data_cached, load_interface_cached_data, save_interface_data_to_cache

                cache_settings = get_interface_cache_settings(interface_name)
                if cache_settings['enabled'] and is_interface_data_cached(
                    interface_name,
                    cache_ttl_hours=cache_settings['ttl_hours'],
                    start_date=start_date,
                    end_date=end_date
                ):
                    result = load_interface_cached_data(interface_name, start_date=start_date, end_date=end_date)
                    if not result.empty:
                        self.logger.info(f"使用缓存数据: {interface_name}, 范围: {start_date} - {end_date}")
                    else:
                        result = strategy.download(start_date=start_date, end_date=end_date)
                        # 保存到缓存
                        if cache_settings['enabled'] and not result.empty:
                            save_interface_data_to_cache(result, interface_name, start_date=start_date, end_date=end_date)
                else:
                    result = strategy.download(start_date=start_date, end_date=end_date)
                    # 保存到缓存
                    if cache_settings['enabled'] and not result.empty:
                        save_interface_data_to_cache(result, interface_name, start_date=start_date, end_date=end_date)
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

### 3. 优化下载策略 (download_strategies.py)

在下载策略中集成缓存功能，但基于现有架构：

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

        # 从现有配置获取缓存设置
        cache_settings = self.config_adapter.get_cache_settings(interface_name)
        self.cache_enabled = cache_settings['cache_enabled']
        self.cache_ttl_hours = cache_settings['cache_ttl_hours']

        # 使用扩展现有的数据存储模块
        from data_storage import (
            is_interface_data_cached,
            load_interface_cached_data,
            save_interface_data_to_cache
        )
        self.is_cached = is_interface_data_cached
        self.load_cached = load_interface_cached_data
        self.save_cached = save_interface_data_to_cache

    def _get_cache_key(self, **kwargs) -> dict:
        """生成缓存键，过滤掉不重要的参数"""
        # 只保留影响数据结果的关键参数
        cache_key = {}
        for key in ['ts_code', 'trade_date', 'start_date', 'end_date', 'period']:
            if key in kwargs and kwargs[key] is not None:
                cache_key[key] = kwargs[key]
        return cache_key

    def download_with_cache(self, **kwargs):
        """带缓存的下载方法 - 基于现有架构扩展"""
        cache_key = self._get_cache_key(**kwargs)

        # 如果启用缓存，检查缓存
        if self.cache_enabled and self._can_use_cache(**kwargs):
            cache_result = self.load_cached(self.interface_name, **cache_key)
            if not cache_result.empty:
                self.logger.info(f"使用缓存数据: {self.interface_name}")
                return cache_result

        # 执行实际下载
        result = self.download(**kwargs)

        # 保存到缓存
        if self.cache_enabled and not result.empty:
            self.save_cached(result, self.interface_name, **cache_key)

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

利用现有配置系统，无需重复实现：

```python
# 在 config_adapter.py 中的 get_cache_settings 方法已经完善
# 保持原有实现，无需修改
def get_cache_settings(self, interface_name: str) -> Dict[str, Any]:
    """
    获取接口缓存设置 - 利用现有配置结构
    """
    config = self.get_config(interface_name)

    if isinstance(config, InterfaceConfig):
        return {
            'enabled': config.cache_enabled,
            'ttl_hours': config.cache_ttl_hours
        }

    # 默认返回启用缓存，24小时TTL
    return {
        'enabled': True,
        'ttl_hours': 24
    }
```

## 实施步骤

1. **扩展现有 data_storage.py** - 添加新的缓存辅助函数，保持路径一致
2. **修改调度器** - 在任务创建前集成缓存检查
3. **更新下载策略** - 集成缓存回退机制，基于现有架构
4. **保持配置** - 利用现有配置系统无需更改
5. **测试验证** - 验证缓存功能正常工作

## 缓存策略

1. **股票特定数据**（stk_rewards, top10_holders, pledge_detail, fina_audit, pro_bar）：TTL 24小时，按股票代码缓存
2. **日度数据**（daily_basic, moneyflow等）：TTL 1-6小时，按日期缓存
3. **财务数据**（income, balancesheet等）：TTL 24-48小时，按报告期缓存
4. **静态数据**（stock_basic, trade_cal等）：TTL 168小时（1周），全量缓存

## 优势

1. **避免重复实现** - 完全基于现有架构，扩展现有功能
2. **路径一致性** - 使用现有数据路径结构，保持一致性
3. **配置统一** - 利用现有配置系统，无需重复实现
4. **性能优化** - 在最合适的时机进行缓存检查
5. **易于维护** - 扩展而非重建现有模块，降低复杂度
6. **向后兼容** - 保持与现有接口和配置的兼容性

这个优化的缓存解决方案完全基于现有系统架构，避免了重复实现问题，同时提供了有效的缓存功能。