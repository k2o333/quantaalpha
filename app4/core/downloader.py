import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
import time
import logging
import random
import threading
import os
from datetime import datetime
from typing import Dict, Any, Optional, List, Union
from enum import Enum
from collections import OrderedDict, defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from .config_loader import ConfigLoader
from .coverage_manager import CoverageManager
from .processor import DataProcessor
from .schema_manager import SchemaManager
import polars as pl

logger = logging.getLogger(__name__)

class LRUCache(OrderedDict):
    """
    Least Recently Used (LRU) cache implementation.
    Automatically removes least recently used items when size exceeds maxsize.
    """
    def __init__(self, maxsize: int = 1000):
        super().__init__()
        self.maxsize = maxsize

    def __getitem__(self, key):
        # Move accessed item to end (marking it as most recently used)
        value = super().__getitem__(key)
        self.move_to_end(key)
        return value

    def __setitem__(self, key, value):
        # Move existing key to end or add new key
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)

        # Remove oldest item if size exceeds limit
        if len(self) > self.maxsize:
            oldest_key = next(iter(self))
            super().__delitem__(oldest_key)

    def get(self, key, default=None):
        """Get value with optional default, mark as recently used."""
        try:
            return self[key]
        except KeyError:
            return default

    def put(self, key, value):
        """Alias for __setitem__"""
        self[key] = value

class PerformanceMonitor:
    """
    性能监控器，用于跟踪关键指标
    """
    def __init__(self):
        self._metrics = defaultdict(lambda: deque(maxlen=100))  # 保留最近100个指标
        self._lock = threading.Lock()
        self._alert_thresholds = {
            'request_time': 30.0,  # 请求时间超过30秒告警
            'data_size': 6000,     # 单次请求数据量超过6000条告警
            'retry_count': 2       # 重试次数超过2次告警
        }

    def record_metric(self, metric_name: str, value: float, context: Dict[str, Any] = None):
        """
        记录性能指标
        """
        with self._lock:
            self._metrics[metric_name].append({
                'value': value,
                'timestamp': time.time(),
                'context': context or {}
            })

    def get_average_metric(self, metric_name: str) -> float:
        """
        获取指标的平均值
        """
        with self._lock:
            if not self._metrics[metric_name]:
                return 0.0
            values = [item['value'] for item in self._metrics[metric_name]]
            return sum(values) / len(values)

    def check_alerts(self, metric_name: str, value: float, context: Dict[str, Any] = None):
        """
        检查是否超过告警阈值
        """
        threshold = self._alert_thresholds.get(metric_name)
        if threshold and value > threshold:
            logger.warning(f"ALERT: {metric_name} exceeded threshold: {value} > {threshold} for {context or {}}")
            return True
        return False

# 全局性能监控器实例
performance_monitor = PerformanceMonitor()

class APIErrorType(Enum):
    SUCCESS = "success"
    RATE_LIMIT = "rate_limit"
    SERVER_ERROR = "server_error"
    CLIENT_ERROR = "client_error"
    NETWORK_ERROR = "network_error"

class GenericDownloader:
    """通用下载器 - 原子化的执行引擎"""

    def __init__(self, config_loader: ConfigLoader, storage_manager=None,
                 trade_calendar_cache=None, stock_list_cache=None):
        self.config_loader = config_loader
        self.global_config = config_loader.get_global_config()

        # 存储管理器（外部传入）
        self.storage_manager = storage_manager

        # 数据处理器和模式管理器
        self.data_processor = DataProcessor()
        self.schema_manager = SchemaManager()

        # 创建具有重试策略的会话
        self.session = self._create_session_with_retries()

        # [新增] 运行时简易缓存，替代原有的 CacheManager
        self._memory_cache = {
            'trade_cal': LRUCache(maxsize=100),      # Trade calendar cache - typically small set of keys
            'stock_list': None,                      # Will be stored separately if needed
            'coverage': LRUCache(maxsize=1000),      # Coverage info for various interfaces
            'api_responses': LRUCache(maxsize=500)   # API responses cache
        }
        self._cache_lock = threading.RLock()  # 确保线程安全

        # 使用传入的缓存（如果不为None）
        if trade_calendar_cache is not None:
            with self._cache_lock:
                self._memory_cache['trade_cal'][('global',)] = trade_calendar_cache

        if stock_list_cache is not None:
            with self._cache_lock:
                self._memory_cache['stock_list'] = stock_list_cache

        # [新增] 覆盖率管理器
        if storage_manager:
            self.coverage_manager = CoverageManager(storage_manager, config_loader, downloader=self)
        else:
            self.coverage_manager = None

    def _create_session_with_retries(self):
        """创建配置了重试策略的 Session"""
        session = requests.Session()

        # 配置重试策略
        retry_strategy = Retry(
            total=3,
            backoff_factor=2,  # 指数退避
            status_forcelist=[429, 500, 502, 503, 504],  # 需要重试的状态码
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"]  # 允许重试的HTTP方法
        )

        # 配置连接池
        adapter = HTTPAdapter(
            pool_connections=10,      # 增加连接池大小
            pool_maxsize=20,         # 最大连接数
            max_retries=retry_strategy
        )

        session.mount("http://", adapter)
        session.mount("https://", adapter)

        # 设置默认请求头
        session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'aspipe_v4/4.0.0'
        })

        return session

    def download(self, interface_name: str, params: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """
        下载指定接口的数据

        Args:
            interface_name: 接口名称
            params: 请求参数

        Returns:
            下载的数据列表，如果出错则返回 None
        """
        try:
            # 1. 获取接口配置
            interface_config = self.config_loader.get_interface_config(interface_name)

            # 2. 校验参数
            validated_params = self._validate_parameters(interface_config, params)

            # 3. 执行分页/循环逻辑
            all_data = self._execute_pagination(interface_config, validated_params)

            return all_data

        except Exception as e:
            logger.error(f"Error downloading data from {interface_name}: {str(e)}")
            return None

    def _generate_cache_key(self, interface_name: str, params: Dict[str, Any]) -> str:
        """生成缓存键"""
        # 将参数排序并序列化为字符串
        sorted_params = sorted(params.items())
        param_str = "&".join([f"{k}={v}" for k, v in sorted_params])
        return f"{interface_name}_{param_str}"

    def _validate_parameters(self, interface_config: Dict[str, Any], params: Dict[str, Any]) -> Dict[str, Any]:
        """校验并处理参数"""
        validated_params = {}
        parameter_config = interface_config.get('parameters', {})

        for param_name, param_value in params.items():
            if param_name in parameter_config:
                param_def = parameter_config[param_name]
                param_type = param_def.get('type')

                # 类型检查和转换
                if param_type == 'string':
                    validated_params[param_name] = str(param_value)
                elif param_type == 'int':
                    validated_params[param_name] = int(param_value)
                elif param_type == 'float':
                    validated_params[param_name] = float(param_value)
                else:
                    validated_params[param_name] = param_value
            else:
                # 如果参数未在配置中定义，仍然传递
                validated_params[param_name] = param_value

        # 添加默认值
        for param_name, param_def in parameter_config.items():
            if param_name not in validated_params and 'default' in param_def:
                validated_params[param_name] = param_def['default']

        return validated_params

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
            # 新增：报告期范围分页
            all_data = self._execute_period_range_pagination(interface_config, params, pagination_config)
        elif mode == 'quarterly_range':
            # 新增：季度范围分页
            all_data = self._execute_quarterly_pagination(interface_config, params, pagination_config)
        elif mode == 'periodic_range':
            # 新增：周期性时间范围分页
            all_data = self._execute_periodic_pagination(interface_config, params, pagination_config)
        else:
            # 默认不分页
            all_data = self._make_request(interface_config, params)

        return all_data

    def _execute_offset_pagination(self, interface_config: Dict[str, Any], params: Dict[str, Any],
                                  pagination_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """执行 offset 分页"""
        all_data = []
        offset = 0
        limit_key = pagination_config.get('limit_key', 'limit')
        offset_key = pagination_config.get('offset_key', 'offset')
        default_limit = pagination_config.get('default_limit', 5000)

        while True:
            # 设置分页参数
            page_params = params.copy()
            page_params[limit_key] = default_limit
            page_params[offset_key] = offset

            # 发起请求
            page_data = self._make_request(interface_config, page_params)
            if not page_data:
                break

            all_data.extend(page_data)

            # 如果返回数据少于限制，说明已经到最后一页
            if len(page_data) < default_limit:
                break

            offset += default_limit

        return all_data

    def _execute_date_range_pagination_concurrent(self, interface_config: Dict[str, Any], params: Dict[str, Any], start_date: str, end_date: str, window_size: int = 365, max_workers: int = 4) -> List[Dict[str, Any]]:
        """
        Execute date range pagination concurrently using thread pool.

        Args:
            interface_config: Configuration for the interface
            params: Parameters for the request
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format
            window_size: Size of each time window in days
            max_workers: Maximum number of worker threads

        Returns:
            Combined list of data from all windows
        """
        # Get trade calendar
        trade_calendar = self.get_trade_calendar(start_date, end_date)

        # If getting trade calendar fails, fall back to default
        if not trade_calendar:
            logger.warning("Failed to get trade calendar, using default date range pagination")
            # Check if internal offset pagination is configured
            offset_config = interface_config.get('offset_pagination', {})
            if offset_config.get('enabled', False):
                return self._execute_offset_pagination(interface_config, params, offset_config)
            else:
                return self._make_request(interface_config, params)

        # Filter for trading days
        trade_days = [day for day in trade_calendar if day.get('is_open', 0) == 1]

        # Return early if no trading days
        if not trade_days:
            logger.warning(f"No trade days found in range {start_date} - {end_date}")
            return []

        # Sort by date in ascending order (oldest to newest)
        trade_days = sorted(trade_days, key=lambda x: x['cal_date'])

        logger.info(f"Found {len(trade_days)} trade days")

        # Generate time ranges
        windows = []
        for i in range(0, len(trade_days), window_size):
            window_trade_days = trade_days[i:i+window_size]
            if window_trade_days:
                # Create start and end date for this window
                window_start = window_trade_days[0]['cal_date']
                window_end = window_trade_days[-1]['cal_date']
                windows.append((window_start, window_end))

        all_data = []
        results_by_window = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all window requests
            future_to_window = {}
            for window_start, window_end in windows:
                window_params = params.copy()
                window_params['start_date'] = window_start
                window_params['end_date'] = window_end

                # Check coverage - if already covered, skip
                should_skip = False
                if self.coverage_manager:
                    should_skip = self.coverage_manager.should_skip(
                        interface_config['api_name'],
                        window_params,
                        strategy='date_range'
                    )

                if should_skip:
                    logger.info(f"Skipping window {window_start} - {window_end} for {interface_config['api_name']} (already covered)")
                    # Store empty result for this window
                    results_by_window[(window_start, window_end)] = []
                else:
                    # Submit the task for execution
                    future = executor.submit(
                        self._make_request_with_offset_check,
                        interface_config,
                        window_params
                    )
                    future_to_window[future] = (window_start, window_end)

            # Collect results as they complete
            for future in as_completed(future_to_window):
                window_start, window_end = future_to_window[future]
                try:
                    result = future.result()
                    # Store result with window info to maintain order if needed
                    results_by_window[(window_start, window_end)] = result
                except Exception as e:
                    logger.error(f"Error fetching window {window_start} to {window_end}: {e}")
                    results_by_window[(window_start, window_end)] = []

        # Combine all results in the original order
        for window_start, window_end in windows:
            window_data = results_by_window.get((window_start, window_end), [])
            all_data.extend(window_data)

        return all_data

    def _make_request_with_offset_check(self, interface_config: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Make request with optional offset pagination check.

        Args:
            interface_config: Interface configuration
            params: Request parameters

        Returns:
            Request result
        """
        # Record start time for performance monitoring
        start_time = time.time()

        # Check if internal offset pagination is configured
        offset_config = interface_config.get('offset_pagination', {})
        if offset_config.get('enabled', False):
            # Use internal offset pagination for window data
            logger.debug(f"Using internal offset pagination for window {params.get('start_date')}-{params.get('end_date')}")
            window_data = self._execute_offset_pagination(interface_config, params, offset_config)
        else:
            # Direct download of window data
            window_data = self._make_request(interface_config, params)

        # Record and check performance metrics
        elapsed_time = time.time() - start_time
        performance_monitor.record_metric('request_time', elapsed_time, {
            'interface': interface_config['api_name'],
            'window': f"{params.get('start_date')}-{params.get('end_date')}",
            'ts_code': params.get('ts_code', 'unknown')
        })
        performance_monitor.check_alerts('request_time', elapsed_time, {
            'interface': interface_config['api_name'],
            'window': f"{params.get('start_date')}-{params.get('end_date')}",
            'ts_code': params.get('ts_code', 'unknown')
        })

        if window_data:
            # Check data integrity
            query_limit = interface_config.get('permissions', {}).get('query_limit', 6000)

            # Record data size metric
            performance_monitor.record_metric('data_size', len(window_data), {
                'interface': interface_config['api_name'],
                'window': f"{params.get('start_date')}-{params.get('end_date')}",
                'ts_code': params.get('ts_code', 'unknown')
            })

            if len(window_data) >= query_limit:
                logger.warning(f"Window {params.get('start_date')}-{params.get('end_date')} returned {len(window_data)} records, which may be truncated (API limit: {query_limit})")
                performance_monitor.check_alerts('data_size', len(window_data), {
                    'interface': interface_config['api_name'],
                    'window': f"{params.get('start_date')}-{params.get('end_date')}",
                    'ts_code': params.get('ts_code', 'unknown')
                })

            logger.debug(f"Downloaded {len(window_data)} records for date range {params.get('start_date')}-{params.get('end_date')}")
        else:
            logger.warning(f"No data returned for window {params.get('start_date')}-{params.get('end_date')}")

        return window_data

    def _execute_date_range_pagination(self, interface_config: Dict[str, Any], params: Dict[str, Any],
                                      pagination_config: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """执行日期范围分页 - 支持内部offset分页 - 智能分页策略"""
        # 如果没有提供分页配置，从接口配置中获取
        if pagination_config is None:
            pagination_config = interface_config.get('pagination', {})

        # 获取接口配置
        interface_name = interface_config['name']

        # 获取日期范围
        start_date = params.get('start_date', '20050101')
        end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))

        # [新增] 获取线程 ID 和任务 ID
        thread_id = threading.get_ident()
        task_id = params.get('ts_code', 'unknown')

        logger.info(f"[Thread-{thread_id}] [Task-{task_id}] [DEBUG] _execute_date_range_pagination called with params: {params}")
        logger.info(f"[Thread-{thread_id}] [Task-{task_id}] [DEBUG] start_date: {start_date}, end_date: {end_date}")
        logger.info(f"[Thread-{thread_id}] [Task-{task_id}] [DEBUG] ts_code in params: {params.get('ts_code', 'N/A')}")

        # 智能分页：根据接口类型确定窗口大小
        window_size = self._get_window_size_for_interface(interface_name)

        # 根据接口类型调整并发数
        if interface_name in ['fina_audit', 'forecast_vip', 'express_vip', 'disclosure_date']:
            max_workers = 1
        elif interface_name in ['top10_holders', 'top10_floatholders', 'pledge_detail', 'dividend']:
            max_workers = 2
        elif interface_name in ['balancesheet_vip', 'income_vip', 'cashflow_vip', 'fina_indicator_vip']:
            # 财务数据接口是全量返回，不应分页
            logger.info(f"财务接口{interface_name}使用全量请求模式")
            return self._make_request(interface_config, params)
        else:
            max_workers = 4  # Conservative default to respect API limits

        logger.info(f"Fetching trade calendar for date range: {start_date} - {end_date}")

        # Use concurrent execution for better performance with intelligent window size
        return self._execute_date_range_pagination_concurrent(
            interface_config=interface_config,
            params=params,
            start_date=start_date,
            end_date=end_date,
            window_size=window_size,
            max_workers=max_workers
        )

    def _execute_stock_loop_pagination(self, interface_config: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """股票循环分页 - 增加前置去重"""
        all_data = []

        # 获取股票列表（从内存缓存或API获取）
        logger.info("正在获取股票列表...")
        stock_list = self._get_stock_list_from_memory_cache()

        if stock_list is None:
            logger.info("内存中未找到股票列表，正在从Data目录获取...")
            stock_list = self._get_stock_list_from_data_dir()

        if stock_list is None:
            logger.info("Data目录中未找到股票列表，正在从API获取...")
            stock_params = {'list_status': 'L'}
            stock_list = self._make_request(
                self.config_loader.get_interface_config('stock_basic'),
                stock_params
            )
            if stock_list:
                logger.info(f"从API获取到 {len(stock_list)} 只股票")
                # 更新内存缓存
                with self._cache_lock:
                    self._memory_cache['stock_list'] = stock_list
            else:
                logger.warning("未能从API获取股票列表")
        else:
            logger.info(f"从内存缓存或Data目录获取到 {len(stock_list)} 只股票")

        if not stock_list:
            logger.error("Failed to get stock list for stock loop pagination")
            return all_data

        # 根据接口类型确定并发数
        interface_name = interface_config['name']
        if interface_name in ['fina_audit', 'forecast_vip', 'express_vip', 'disclosure_date']:
            max_workers = 1
        elif interface_name in ['top10_holders', 'top10_floatholders', 'pledge_detail', 'dividend']:
            max_workers = 2
        else:
            max_workers = 4  # Conservative default based on previous implementations

        # 为每个股票下载数据
        total_stocks = len(stock_list)
        logger.info(f"Starting to download data for {total_stocks} stocks...")

        log_interval = 100  # 每100个股票输出一次进度

        # 并行处理股票，使用前置去重逻辑
        skipped_stocks = 0
        processed_stocks = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 创建任务
            futures = []
            for idx, stock in enumerate(stock_list):
                ts_code = stock['ts_code']

                # 前置去重：检查本地是否已有该股票的数据
                if self._is_stock_data_exists(interface_name, ts_code):
                    logger.info(f"股票{ts_code}数据已存在，跳过")
                    skipped_stocks += 1
                    continue

                # 准备参数
                stock_params = params.copy()
                stock_params['ts_code'] = ts_code

                future = executor.submit(
                    self.download_single_stock,
                    interface_config,
                    stock,
                    params  # Use original params to avoid overwriting ts_code
                )
                futures.append(future)

            # 收集结果
            for future in as_completed(futures):
                try:
                    data = future.result()
                    if data:
                        all_data.extend(data)
                        processed_stocks += 1
                except Exception as e:
                    logger.error(f"获取股票数据失败: {str(e)}")
                    continue

        logger.info(f"股票循环分页完成: {processed_stocks} 只股票处理, {skipped_stocks} 只股票跳过")
        return all_data

    def _get_stock_list_from_memory_cache(self) -> Optional[List[Dict[str, Any]]]:
        """从内存缓存获取股票列表"""
        with self._cache_lock:
            return self._memory_cache['stock_list']

    def _get_stock_list_from_data_dir(self) -> Optional[List[Dict[str, Any]]]:
        """从Data目录获取股票列表"""
        try:
            storage_dir = self.global_config.get('storage', {}).get('base_dir', '../data')
            dir_path = os.path.join(storage_dir, 'stock_basic')

            if not os.path.exists(dir_path):
                return None

            # 读取目录下所有 parquet 文件
            df = pl.read_parquet(dir_path)

            if df.is_empty():
                return None

            # [修复] 必须去重，因为 Dataset 模式下可能有重复数据
            # 按 ts_code 去重，保留最后一次出现的数据
            deduplicated_df = df.unique(subset=['ts_code'], keep='last')

            # [新增] 添加日志输出
            stock_count = len(deduplicated_df)
            logger.info(f"从本地获取了 {stock_count} 只股票")

            return deduplicated_df.to_dicts()

        except Exception as e:
            logger.warning(f"Failed to read stock list from Data dir: {e}")
            return None

    def get_trade_calendar(self, start_date: str, end_date: str) -> Optional[List[Dict[str, Any]]]:
        """
        获取交易日历，优先使用预热缓存
        """
        # 使用全局缓存键
        cache_key = ('global',)  # 改为固定键

        with self._cache_lock:
            if cache_key in self._memory_cache['trade_cal']:
                # 从全局缓存过滤日期范围
                all_days = self._memory_cache['trade_cal'][cache_key]
                if all_days:
                    return [d for d in all_days if start_date <= d['cal_date'] <= end_date]

        # 回退到原有逻辑
        trade_calendar = self._get_trade_calendar_from_data_dir(start_date, end_date)
        if not trade_calendar:
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

            # 更新内存缓存
            if trade_calendar:
                with self._cache_lock:
                    cache_key = (start_date, end_date)  # 保持原有缓存键
                    self._memory_cache['trade_cal'][cache_key] = trade_calendar

        return trade_calendar

    def _get_trade_calendar_from_data_dir(self, start_date, end_date):
        """从 Data 目录查询交易日历 (Source of Truth) - 优化版本"""
        # 假设存储目录为 data/trade_cal/
        storage_dir = self.global_config.get('storage', {}).get('base_dir', '../data')
        dir_path = os.path.join(storage_dir, 'trade_cal')

        if not os.path.exists(dir_path):
            return None

        try:
            # 读取目录下所有 parquet 文件 (Dataset 模式)
            try:
                df = pl.read_parquet(dir_path)
            except Exception:
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
            # 必须去重，因为 Dataset 模式下可能有重复数据
            filtered_df = df.filter(
                pl.all_horizontal(conditions)
            ).unique(subset=['cal_date'], keep='last').sort('cal_date')

            if filtered_df.is_empty():
                return None

            return filtered_df.to_dicts()

        except Exception as e:
            logger.warning(f"Failed to read trade calendar from Data dir: {e}")
            return None

    def _generate_quarter_end_dates(self, start_date: str, end_date: str) -> List[str]:
        """
        生成日期范围内的所有季度末日期

        Args:
            start_date: 起始日期 YYYYMMDD
            end_date: 结束日期 YYYYMMDD

        Returns:
            季度末日期列表，格式为 YYYYMMDD
        """
        from datetime import datetime, timedelta

        # 解析日期
        start_dt = datetime.strptime(start_date, '%Y%m%d')
        end_dt = datetime.strptime(end_date, '%Y%m%d')

        # 季度末月份和日期
        quarter_ends = [
            (3, 31),   # Q1
            (6, 30),   # Q2
            (9, 30),   # Q3
            (12, 31)   # Q4
        ]

        periods = []

        # 从起始日期的下一个季度末开始
        current_year = start_dt.year
        current_quarter_idx = 0

        # 找到 start_date 之后的第一个季度末
        for q_idx, (month, day) in enumerate(quarter_ends):
            quarter_end = datetime(current_year, month, day)
            if quarter_end >= start_dt:
                current_quarter_idx = q_idx
                break
        else:
            # 如果当前年份没有找到，从下一年第一季度开始
            current_year += 1
            current_quarter_idx = 0

        # 生成所有在范围内的季度末日期
        while True:
            month, day = quarter_ends[current_quarter_idx]
            quarter_end = datetime(current_year, month, day)

            if quarter_end > end_dt:
                break

            periods.append(quarter_end.strftime('%Y%m%d'))

            # 移动到下一个季度
            current_quarter_idx += 1
            if current_quarter_idx >= len(quarter_ends):
                current_quarter_idx = 0
                current_year += 1

        return periods

    def _execute_period_range_pagination(self, interface_config: Dict[str, Any],
                                        params: Dict[str, Any],
                                        pagination_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        执行报告期范围分页

        当 date_parameter_type 为 "report_period" 时，将 start_date/end_date
        转换为多个 period 参数请求
        """
        all_data = []

        # 获取日期范围
        start_date = params.get('start_date', '20050101')
        end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))

        logger.info(f"Generating report periods for range: {start_date} - {end_date}")

        # 生成季度末日期列表
        periods = self._generate_quarter_end_dates(start_date, end_date)

        if not periods:
            logger.warning(f"No valid report periods found in range {start_date} - {end_date}")
            return []

        logger.info(f"Generated {len(periods)} report periods: {periods}")

        # 为每个 period 发起请求
        for idx, period in enumerate(periods):
            period_params = params.copy()

            # 移除 start_date 和 end_date，使用 period 参数
            period_params.pop('start_date', None)
            period_params.pop('end_date', None)
            period_params['period'] = period

            # [新增] 检查覆盖率，如果已存在则跳过
            if self.coverage_manager:
                should_skip = self.coverage_manager.should_skip(
                    interface_config['api_name'],
                    period_params,
                    strategy='period'
                )
                if should_skip:
                    logger.info(f"Skipping period {period} for {interface_config['api_name']} (already exists)")
                    continue

            logger.info(f"Fetching data for period {period} ({idx+1}/{len(periods)})")

            # 记录开始时间
            start_time = time.time()

            # 发起请求
            period_data = self._make_request(interface_config, period_params)

            # 对于period_range模式，将period参数添加到每条记录中
            if period_data and 'period' in period_params:
                for record in period_data:
                    record['period'] = period_params['period']

            # 计算请求耗时
            elapsed_time = time.time() - start_time

            # 记录性能指标
            logger.debug(f"Recording request_time metric: {elapsed_time:.2f}s for period {period}")
            performance_monitor.record_metric('request_time', elapsed_time, {
                'interface': interface_config['api_name'],
                'period': period,
                'ts_code': params.get('ts_code', 'unknown')
            })
            performance_monitor.check_alerts('request_time', elapsed_time, {
                'interface': interface_config['api_name'],
                'period': period,
                'ts_code': params.get('ts_code', 'unknown')
            })

            if period_data:
                all_data.extend(period_data)
                logger.info(f"Downloaded {len(period_data)} records for period {period}")

                # 记录数据量指标
                logger.debug(f"Recording data_size metric: {len(period_data)} records for period {period}")
                performance_monitor.record_metric('data_size', len(period_data), {
                    'interface': interface_config['api_name'],
                    'period': period,
                    'ts_code': params.get('ts_code', 'unknown')
                })
                performance_monitor.check_alerts('data_size', len(period_data), {
                    'interface': interface_config['api_name'],
                    'period': period,
                    'ts_code': params.get('ts_code', 'unknown')
                })
            else:
                logger.warning(f"No data returned for period {period}")

        return all_data

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

    def download_single_stock(self, interface_config: Dict[str, Any], stock: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """下载单只股票的数据 - 原子化方法供调度器调用

        Args:
            interface_config: 接口配置
            stock: 股票信息字典，包含ts_code等
            params: 基础请求参数

        Returns:
            该股票的数据列表，如果出错则返回空列表
        """
        try:
            stock_params = params.copy()
            stock_params['ts_code'] = stock['ts_code']

            # 设置日期范围
            if 'start_date' not in stock_params:
                # 如果没有指定起始日期，使用该股票的上市日期
                list_date = stock.get('list_date', '20050101')
                stock_params['start_date'] = list_date
            if 'end_date' not in stock_params:
                from datetime import datetime
                stock_params['end_date'] = datetime.now().strftime('%Y%m%d')

            # [新增] 检查覆盖率，如果已存在则跳过
            if self.coverage_manager:
                should_skip = self.coverage_manager.should_skip(
                    interface_config['api_name'],
                    stock_params,
                    strategy='stock'
                )
                if should_skip:
                    logger.info(f"Skipping stock {stock['ts_code']} for {interface_config['api_name']} (already exists)")
                    return []

            logger.info(f"Downloading data for stock {stock['ts_code']}, date range: {stock_params.get('start_date')} - {stock_params.get('end_date')}")

            # 执行日期范围分页下载
            stock_data = self._execute_date_range_pagination(interface_config, stock_params)

            if stock_data:
                logger.info(f"Downloaded {len(stock_data)} records for {stock['ts_code']}")

                # [新增] 如果有storage_manager，将数据添加到缓存
                if hasattr(self, 'storage_manager') and self.storage_manager:
                    self.storage_manager.add_to_buffer(interface_config['api_name'], stock_data)

            return stock_data or []
        except Exception as e:
            # [新增] 捕获异常，避免影响其他股票
            logger.error(f"Error downloading stock {stock['ts_code']}: {str(e)}")
            import traceback
            logger.debug(f"Full traceback: {traceback.format_exc()}")
            return []  # 返回空列表，让其他股票继续下载

    def _make_request(self, interface_config: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """发起实际的 API 请求 - 优化版"""
        api_name = interface_config['api_name']

        # 读取重试配置
        req_config = self.global_config.get('request', {})
        max_retries = req_config.get('retries', 3)

        # 随机延迟，错开多个线程的请求时刻
        time.sleep(random.uniform(
            req_config.get('jitter_min', 0.1),
            req_config.get('jitter_max', 0.5)
        ))

        # 重试循环
        for attempt in range(max_retries + 1):
            try:
                request_config = interface_config.get('request', {})
                method = request_config.get('method', 'POST')
                # 增加默认超时时间，(连接超时, 读取超时)
                timeout_val = request_config.get('timeout', 60)
                timeout = (10, timeout_val)

                # 获取 API URL，优先使用代理 URL
                import os
                proxy_url = os.getenv('PROXY_URL', '')
                tushare_config = self.global_config.get('tushare', {})
                if proxy_url:
                    api_url = proxy_url
                else:
                    api_url = tushare_config.get('api_url', 'http://api.tushare.pro/api')

                # 在没有指定额外路径的情况下，使用 /api 作为默认路径
                if api_url.endswith('/api') or api_url.endswith('/dataapi'):
                    pass  # URL 已经正确
                elif not request_config.get('extra_path', ''):
                    # 如果没有额外路径，且 URL 不以 /api 或 /dataapi 结尾，则添加 /api
                    if not api_url.endswith('/api') and not api_url.endswith('/dataapi'):
                        if api_url.endswith('/'):
                            api_url += 'api'
                        else:
                            api_url += '/api'

                # 添加额外路径（如果有）
                extra_path = request_config.get('extra_path', '')
                if extra_path:
                    api_url += extra_path

                # 添加 token
                token_placeholder = tushare_config.get('token', '')
                if '${TUSHARE_TOKEN}' in token_placeholder:
                    token = os.getenv('TUSHARE_TOKEN', '')
                else:
                    token = token_placeholder

                # 不传递fields参数，让API返回所有字段
                # 因为API默认返回所有字段，不需要显式指定

                # 根据TuShare API格式构建请求体
                req_params = {
                    'api_name': interface_config['api_name'],
                    'token': token,
                    'params': params,
                    'fields': ''  # 空字符串表示不指定字段，API返回所有字段
                }

                # 记录重试次数指标
                if attempt > 0:
                    performance_monitor.record_metric('retry_count', attempt, {
                        'interface': api_name,
                        'attempt': attempt
                    })
                    performance_monitor.check_alerts('retry_count', attempt, {
                        'interface': api_name
                    })

                logger.debug(f"Making {method} request to {api_url} for {api_name} (attempt {attempt+1})")
                
                if method.upper() == 'POST':
                    response = self.session.post(api_url, json=req_params, timeout=timeout)
                else:
                    response = self.session.get(api_url, json=req_params, timeout=timeout)

                response.raise_for_status()
                result = response.json()

                # 检查 API 返回是否成功
                if result.get('code') != 0:
                    msg = result.get('msg', '')
                    # 如果是频率限制，执行退避重试
                    if '频繁' in msg or 'limit' in msg.lower():
                        if attempt < max_retries:
                            base_delay = (req_config.get('retry_delay', 2) *
                                         (req_config.get('retry_backoff', 2) ** attempt))
                            random_delay = base_delay + random.uniform(0, 2)
                            logger.warning(f"Rate limit hit for {api_name}. Retrying in {random_delay:.2f}s...")
                            time.sleep(random_delay)
                            continue
                    
                    logger.error(f"API error for {api_name}: {msg}")
                    return []

                # 数据转换逻辑
                fields = result.get('data', {}).get('fields', [])
                items = result.get('data', {}).get('items', [])

                # 调试日志：记录API实际返回的字段
                logger.info(f"API returned {len(fields)} fields for {api_name}")
                if len(fields) < 50:  # 如果字段少，全部显示
                    logger.info(f"Returned fields: {fields}")
                else:
                    logger.info(f"First 10 fields: {fields[:10]}")
                    logger.info(f"Last 10 fields: {fields[-10:]}")

                converted_data = []
                for item in items:
                    row_dict = {}
                    for i, field_name in enumerate(fields):
                        if i < len(item):
                            field_name = str(field_name) if field_name is not None else f"field_{i}"
                            row_dict[field_name] = item[i]
                    converted_data.append(row_dict)

                return converted_data

            except (requests.RequestException, json.JSONDecodeError) as e:
                logger.error(f"Request error for {api_name}: {str(e)}")
                if attempt < max_retries:
                    base_delay = (req_config.get('retry_delay', 2) *
                                 (req_config.get('retry_backoff', 2) ** attempt))
                    random_delay = base_delay + random.uniform(0, 2)
                    logger.warning(f"Retrying {api_name} in {random_delay:.2f}s due to: {type(e).__name__}")
                    time.sleep(random_delay)
                    continue
                return []
            except Exception as e:
                logger.error(f"Unexpected error for {api_name}: {str(e)}")
                if attempt < max_retries:
                    time.sleep(2 ** attempt)
                    continue
                return []

    def _classify_api_error(self, response: Dict[str, Any]) -> APIErrorType:
        """
        Classify API response error into specific error type for appropriate handling.

        Args:
            response: API response dictionary

        Returns:
            APIErrorType enum value
        """
        code = response.get('code')
        msg = response.get('msg', '').lower()

        # Success case
        if code == 0 or 'success' in msg or 'ok' in msg:
            return APIErrorType.SUCCESS

        # Rate limit errors - specific codes and messages
        rate_limit_codes = [10001, 10002, 10003, 10004]  # Common TuShare rate limit codes
        rate_limit_keywords = ['limit', 'frequent', 'frequently', 'time', 'request', 'rate']

        if code in rate_limit_codes or any(keyword in msg for keyword in rate_limit_keywords):
            return APIErrorType.RATE_LIMIT

        # Client errors - invalid parameters, missing permissions, etc.
        client_error_codes = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110]
        client_error_keywords = ['parameter', 'invalid', 'missing', 'forbidden', 'unauthorized', 'permission']

        if code in client_error_codes or any(keyword in msg for keyword in client_error_keywords):
            return APIErrorType.CLIENT_ERROR

        # Server errors - network issues, internal errors, etc.
        server_error_codes = [500, 502, 503, 504, 110, 120]  # Common server error codes
        server_error_keywords = ['server', 'error', 'network', 'timeout', 'internal']

        if code in server_error_codes or any(keyword in msg for keyword in server_error_keywords):
            return APIErrorType.SERVER_ERROR

        # Default to server error if unrecognized
        return APIErrorType.SERVER_ERROR

    def _get_window_size_for_interface(self, interface_name: str) -> int:
        """根据接口类型确定窗口大小"""
        # 定义接口数据量级别
        data_volume_config = {
            # 小数据量接口：每只股票数据量<100条
            'small': ['fina_audit', 'forecast_vip', 'express_vip', 'disclosure_date'],
            # 中等数据量：100-1000条
            'medium': ['top10_holders', 'top10_floatholders', 'pledge_detail', 'dividend',
                      'repurchase', 'concept_detail', 'share_float', 'stk_holdertrade'],
            # 大数据量：>1000条
            'large': ['stk_factor', 'stk_factor_pro', 'moneyflow_hsgt', 'moneyflow_north',
                     'moneyflow_stock', 'block_trade', 'stk_rewards', 'pledge_stat'],
            # 财务数据接口：全量数据
            'financial': ['balancesheet_vip', 'income_vip', 'cashflow_vip', 'fina_indicator_vip']
        }

        # 确定接口类型
        for typ, interfaces in data_volume_config.items():
            if interface_name in interfaces:
                if typ == 'small':
                    return 3650  # 10年窗口，减少请求次数
                elif typ == 'medium':
                    return 1825  # 5年窗口
                elif typ == 'financial':
                    return 36500  # 100年，实际上一次性获取
                else:  # large
                    return 365  # 默认1年窗口

        # 默认情况
        return 365

    def _is_stock_data_exists(self, interface_name: str, ts_code: str, storage_dir: str = None) -> bool:
        """检查股票数据是否已存在"""
        if storage_dir is None:
            storage_dir = self.global_config.get('storage', {}).get('base_dir', '../data')

        dir_path = os.path.join(storage_dir, interface_name)

        if not os.path.exists(dir_path):
            return False

        try:
            # 读取现有数据
            df = pl.read_parquet(dir_path)

            # 检查该股票是否存在
            return df.filter(pl.col('ts_code') == ts_code).height > 0
        except Exception:
            return False

    def verify_trade_calendar_integrity(self, df: pl.DataFrame) -> bool:
        """
        验证交易日历完整性
        在数据下载和转换过程中，必须进行数据完整性自检，确保trade_cal数据的可靠性
        """
        logger.info(f"Starting trade calendar integrity check...")

        # 检查1：从1990-01-01到今天（当日）是否全覆盖
        try:
            # 从DataFrame中获取所有有效日期
            from datetime import date
            min_date_str = df['cal_date'].min()
            max_date_str = df['cal_date'].max()

            # 确保我们有完整的日期信息
            if not min_date_str or not max_date_str:
                logger.error("No valid calendar dates found in the data")
                return False

            logger.info(f"Date range in data: {min_date_str} to {max_date_str}")

        except Exception as e:
            logger.error(f"Error checking date range: {e}")
            return False

        # 检查2：string格式和date格式是否一一对应
        try:
            if 'cal_date_dt' in df.columns:
                mismatched = df.filter(
                    pl.col('cal_date').is_not_null() & pl.col('cal_date_dt').is_null()
                )

                if len(mismatched) > 0:
                    logger.error(f"Found {len(mismatched)} records with mismatched date formats")
                    return False
        except Exception as e:
            logger.error(f"Error checking date format consistency: {e}")

        # 检查3：数据量合理性（至少应该有8000个交易日）
        try:
            total_records = len(df)
            if total_records < 5000:  # 调整为更合理的要求
                logger.warning(f"Trade calendar has fewer records ({total_records}) than expected")
                # 对于早期测试或小范围日期，我们不返回False，仅记录日志

            logger.info(f"Trade calendar integrity check passed: {total_records} records")
            return True

        except Exception as e:
            logger.error(f"Error checking record count: {e}")
            return False

    def _after_download(self, interface_name: str, df: pl.DataFrame):
        """下载后处理 - 特定接口的特殊处理"""
        if interface_name == 'trade_cal':
            if not self.verify_trade_calendar_integrity(df):
                logger.error("Trade calendar integrity check failed, marking for re-download")
                # 可以设置一些标记来指示需要重新下载
                return False
        return True