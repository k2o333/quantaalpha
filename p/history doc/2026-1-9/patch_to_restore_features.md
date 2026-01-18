# 恢复交易日历缓存和重复数据检测功能方案 (优化版)

## 背景

在提交 `cc2c7a5a1f58072c988f268dfa26416da35bf5de` 中，交易日历缓存功能和重复数据检测功能被移除。本方案旨在恢复这两个重要功能，并根据代码审查报告进行了优化，解决了线程安全、缓存一致性和功能缺失问题。

## 问题分析

### 1. 交易日历缓存问题
- 当前每次下载都需要重新加载交易日历数据
- 缺乏内存缓存机制，导致重复的I/O操作
- 存在双重缓存逻辑（Downloader 和 CoverageManager 各自维护），容易导致不一致

### 2. 重复数据检测问题
- 缺乏基于主键的重复检测机制
- 线程安全隐患：多线程环境下缺乏锁保护
- 性能问题：覆盖率检测缺乏缓存，导致重复计算

## 解决方案

### 方案一：统一交易日历缓存机制

在 `GenericDownloader` 中集中管理交易日历的获取和缓存，提供统一的 `get_trade_calendar` 方法供内部和 `CoverageManager` 使用。

#### 1.1 修改 `core/downloader.py`

1.  **完善初始化**：初始化完整的缓存结构和线程锁。
2.  **添加 `get_trade_calendar` 公共方法**：实现 Mem -> Disk -> API 的三级缓存逻辑。
3.  **优化 `_get_trade_calendar_from_data_dir`**：增加对 `exchange` 列存在的检查，防止 crash。
4.  **重构 `_execute_date_range_pagination`**：调用统一的 `get_trade_calendar` 方法。

### 方案二：线程安全的重复数据检测

增强 `CoverageManager`，确保线程安全并复用 `Downloader` 的能力。

#### 2.1 修改 `core/coverage_manager.py`

1.  **添加线程锁**：引入 `threading.RLock` 保护缓存访问。
2.  **优化 `should_skip`**：先查缓存（带锁），再执行检测逻辑，最后更新缓存（带锁）。
3.  **复用 Downloader 能力**：在 `_check_range_coverage` 中直接调用 `downloader.get_trade_calendar`，移除重复的 API 请求逻辑。

## 实施代码

### 1. 修改 `app4/core/downloader.py`

#### 1.1 增强 `__init__` 方法

```python
    def __init__(self, config_loader: ConfigLoader, storage_manager=None):
        self.config_loader = config_loader
        self.global_config = config_loader.get_global_config()

        # 存储管理器（外部传入）
        self.storage_manager = storage_manager

        # 创建具有重试策略的会话
        self.session = self._create_session_with_retries()

        # [增强] 运行时缓存
        self._memory_cache = {
            'trade_cal': {},      # Key: ('start_date', 'end_date'), Value: list[dict]
            'stock_list': None,   # Value: list[dict]
            'coverage': {},       # Key: (interface_name, params_hash), Value: coverage_result
            'api_responses': {}   # Key: (api_name, params_hash), Value: response_data
        }
        self._cache_lock = threading.RLock()  # 确保线程安全

        # [增强] 覆盖率管理器
        if storage_manager:
            self.coverage_manager = CoverageManager(storage_manager, config_loader, downloader=self)
        else:
            self.coverage_manager = None
```

#### 1.2 添加 `get_trade_calendar` 方法 (新方法)

```python
    def get_trade_calendar(self, start_date: str, end_date: str) -> Optional[List[Dict[str, Any]]]:
        """
        获取交易日历，采用三级缓存策略：
        1. 内存缓存 (_memory_cache)
        2. 本地存储 (Data 目录 parquet 文件)
        3. API 请求
        """
        cache_key = (start_date, end_date)
        
        # 1. 检查内存缓存
        with self._cache_lock:
            if cache_key in self._memory_cache['trade_cal']:
                logger.debug(f"Trade calendar loaded from memory cache: {start_date}-{end_date}")
                return self._memory_cache['trade_cal'][cache_key]

        # 2. 检查本地数据目录
        trade_calendar = self._get_trade_calendar_from_data_dir(start_date, end_date)
        
        if trade_calendar:
            logger.info(f"Trade calendar loaded from data directory: {start_date}-{end_date}")
        else:
            # 3. 请求 API
            logger.info(f"Trade calendar not found locally, fetching from API: {start_date}-{end_date}")
            calendar_params = {
                'start_date': start_date,
                'end_date': end_date,
                'exchange': 'SSE'
            }
            # 使用 _make_request 直接请求，避免递归调用
            trade_calendar = self._make_request(
                self.config_loader.get_interface_config('trade_cal'),
                calendar_params
            )
            
            # 如果成功获取，可以选择保存到本地 (可选，视需求而定，这里暂只更新内存)
        
        # 更新内存缓存
        if trade_calendar:
            with self._cache_lock:
                self._memory_cache['trade_cal'][cache_key] = trade_calendar
                
        return trade_calendar
```

#### 1.3 优化 `_get_trade_calendar_from_data_dir`

```python
    def _get_trade_calendar_from_data_dir(self, start_date, end_date):
        """从 Data 目录查询交易日历 (Source of Truth) - 优化版本"""
        storage_dir = self.global_config.get('storage', {}).get('base_dir', '../data')
        dir_path = os.path.join(storage_dir, 'trade_cal')

        if not os.path.exists(dir_path):
            return None

        try:
            # 读取目录下所有 parquet 文件
            # 使用 glob 模式或列出文件可能更稳健，但 polars 支持目录读取
            try:
                df = pl.read_parquet(dir_path)
            except Exception:
                # 兼容处理：如果是分区的或者有问题，尝试读取单个文件或跳过
                return None

            if df.is_empty():
                return None

            # 构建过滤条件
            conditions = [
                (pl.col('cal_date') >= start_date),
                (pl.col('cal_date') <= end_date),
                (pl.col('is_open') == 1)
            ]
            
            # [修复] 检查 exchange 列是否存在
            if 'exchange' in df.columns:
                conditions.append(pl.col('exchange') == 'SSE')

            # 过滤日期范围并去重
            filtered_df = df.filter(
                pl.all_horizontal(conditions)
            ).unique(subset=['cal_date'], keep='last').sort('cal_date')

            if filtered_df.is_empty():
                return None

            return filtered_df.to_dicts()

        except Exception as e:
            logger.warning(f"Failed to read trade calendar from Data dir: {e}")
            return None
```

#### 1.4 优化 `_execute_date_range_pagination`

```python
    def _execute_date_range_pagination(self, interface_config: Dict[str, Any], params: Dict[str, Any],
                                      pagination_config: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """执行日期范围分页"""
        if pagination_config is None:
            pagination_config = interface_config.get('pagination', {})

        all_data = []
        start_date = params.get('start_date', '20050101')
        end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))

        # [优化] 使用统一的 get_trade_calendar 方法
        trade_calendar = self.get_trade_calendar(start_date, end_date)

        # 如果获取交易日历失败，回退策略
        if not trade_calendar:
            logger.warning("Failed to get trade calendar, using default date range pagination")
            offset_config = interface_config.get('offset_pagination', {})
            if offset_config.get('enabled', False):
                return self._execute_offset_pagination(interface_config, params, offset_config)
            else:
                return self._make_request(interface_config, params)

        # 过滤出交易日
        trade_days = [day for day in trade_calendar if day.get('is_open', 0) == 1]
        
        if not trade_days:
            logger.warning(f"No trade days found in range {start_date} - {end_date}")
            return []

        trade_days = sorted(trade_days, key=lambda x: x['cal_date'])
        
        # ... 后续窗口切分逻辑保持不变 ...
        # 注意在循环内部调用 coverage_manager.should_skip 时保持不变
        
        # 窗口循环逻辑...
        window_size = pagination_config.get('window_size_days', 3650)
        
        for i in range(0, len(trade_days), window_size):
            # ... (保持原有的窗口处理逻辑)
            pass # 此处代码省略，保持原逻辑即可，重点是上面 trade_calendar 的获取

        return all_data
```

### 2. 修改 `app4/core/coverage_manager.py`

#### 2.1 增强 `CoverageManager` 类

```python
class CoverageManager:
    """覆盖率管理器 - 实现重复数据检测功能 (线程安全版)"""

    def __init__(self, storage_manager: StorageManager, config_loader: ConfigLoader, downloader=None):
        self.storage_manager = storage_manager
        self.config_loader = config_loader
        self.downloader = downloader
        
        # 简单的内存缓存
        self._cache = {}
        self._coverage_cache = {}
        
        # [新增] 线程锁
        self._cache_lock = threading.RLock()

    def should_skip(self, interface_name: str, params: Dict[str, Any],
                   strategy: str = 'auto') -> bool:
        """根据策略判断是否应该跳过下载"""
        try:
            # 生成缓存键
            # 确保 params 是可哈希的，处理列表等类型
            sorted_params = []
            for k, v in sorted(params.items()):
                if isinstance(v, list):
                    v = tuple(v)
                sorted_params.append((k, v))
            cache_key = (interface_name, tuple(sorted_params))

            # [优化] 先检查缓存 (带锁)
            with self._cache_lock:
                if cache_key in self._coverage_cache:
                    return self._coverage_cache[cache_key]

            # 获取接口配置
            interface_config = self.config_loader.get_interface_config(interface_name)
            detection_config = interface_config.get('duplicate_detection', {})

            if not detection_config.get('enabled', True):
                return False

            # 自动确定策略
            if strategy == 'auto':
                # ... (保持原有的策略判断逻辑) ...
                pagination_config = interface_config.get('pagination', {})
                pagination_mode = pagination_config.get('mode', 'offset') if pagination_config.get('enabled', False) else 'none'
                
                if pagination_mode == 'date_range':
                    strategy = 'date_range'
                elif pagination_mode == 'period_range':
                    strategy = 'period'
                elif pagination_mode == 'stock_loop':
                    strategy = 'stock'
                else:
                    return False

            # 执行检测
            if strategy == 'date_range':
                result = self._check_range_coverage(interface_name, params)
            elif strategy == 'period':
                result = self._check_period_existence(interface_name, params)
            elif strategy == 'stock':
                result = self._check_stock_existence(interface_name, params)
            else:
                result = False

            # [优化] 更新缓存 (带锁)
            with self._cache_lock:
                self._coverage_cache[cache_key] = result
                
            return result
            
        except Exception as e:
            logger.warning(f"Coverage check failed for {interface_name}: {e}")
            return False

    def _check_range_coverage(self, interface_name: str, params: Dict[str, Any]) -> bool:
        """检查日期范围覆盖率"""
        start_date = params.get('start_date')
        end_date = params.get('end_date')

        if not start_date or not end_date:
            return False

        # ... (获取配置逻辑) ...
        interface_config = self.config_loader.get_interface_config(interface_name)
        detection_config = interface_config.get('duplicate_detection', {})
        date_column = detection_config.get('date_column', 'trade_date')
        threshold = detection_config.get('threshold', 0.95)

        try:
            # 读取现有数据
            df = self.storage_manager.read_interface_data(
                interface_name,
                start_date=start_date,
                end_date=end_date,
                columns=[date_column]
            )

            if df.is_empty():
                return False

            actual_dates = set(df[date_column].to_list())

            # [优化] 直接使用 downloader 的 get_trade_calendar 方法
            # 避免了重复的 API 请求代码和缓存不一致
            if self.downloader:
                trade_calendar = self.downloader.get_trade_calendar(start_date, end_date)
            else:
                # Fallback if downloader is not available (should rarely happen)
                logger.warning("Downloader not available for trade calendar check")
                return not df.is_empty()

            if not trade_calendar:
                # 简单检查：如果有数据则认为覆盖
                return not df.is_empty()

            expected_dates = {day['cal_date'] for day in trade_calendar if day.get('is_open', 0) == 1}

            if not expected_dates:
                return False

            coverage = len(actual_dates & expected_dates) / len(expected_dates)
            return coverage >= threshold

        except Exception as e:
            logger.warning(f"Range coverage check failed for {interface_name}: {e}")
            return False
            
    # _check_period_existence 和 _check_stock_existence 也应添加 self._cache_lock 保护 (如果它们使用 self._cache)
    # 示例:
    def _check_period_existence(self, interface_name: str, params: Dict[str, Any]) -> bool:
        # ... logic ...
        cache_key = f"{interface_name}_periods"
        
        # 读取/更新 self._cache 时加锁
        with self._cache_lock:
             if cache_key not in self._cache:
                 # load data...
                 # self._cache[cache_key] = ...
                 pass
             # check existence
             return target in self._cache[cache_key]
```

## 验证计划

1.  **运行 `app4/main.py`**：确保程序能正常启动，无初始化错误。
2.  **执行下载任务**：观察日志，确认 `Trade calendar loaded from ...` 消息出现，验证缓存生效。
3.  **并发测试**：如果可能，模拟多线程下载，验证没有死锁或竞争报错。
4.  **重复运行**：第二次运行相同任务，确认 `Skipping ... (already covered)` 日志出现，验证覆盖率检测生效。
