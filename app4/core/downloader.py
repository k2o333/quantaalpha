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
from typing import Dict, Any, Optional, List
from collections import defaultdict, deque
from .config_loader import ConfigLoader
import polars as pl

logger = logging.getLogger(__name__)

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

class GenericDownloader:
    """通用下载器 - 原子化的执行引擎"""

    def __init__(self, config_loader: ConfigLoader):
        self.config_loader = config_loader
        self.global_config = config_loader.get_global_config()

        # 创建具有重试策略的会话
        self.session = self._create_session_with_retries()

        # [新增] 运行时简易缓存，替代原有的 CacheManager
        self._memory_cache = {
            'trade_cal': {},      # Key: ('start_date', 'end_date'), Value: list[dict]
            'stock_list': None    # Value: list[dict]
        }
        self._cache_lock = threading.RLock()  # 确保线程安全

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

    def _execute_date_range_pagination(self, interface_config: Dict[str, Any], params: Dict[str, Any],
                                      pagination_config: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """执行日期范围分页 - 支持内部offset分页"""
        # 如果没有提供分页配置，从接口配置中获取
        if pagination_config is None:
            pagination_config = interface_config.get('pagination', {})

        all_data = []

        # 获取日期范围
        start_date = params.get('start_date', '20050101')
        end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))

        # [新增] 获取线程 ID 和任务 ID
        thread_id = threading.get_ident()
        task_id = params.get('ts_code', 'unknown')

        logger.info(f"[Thread-{thread_id}] [Task-{task_id}] [DEBUG] _execute_date_range_pagination called with params: {params}")
        logger.info(f"[Thread-{thread_id}] [Task-{task_id}] [DEBUG] start_date: {start_date}, end_date: {end_date}")
        logger.info(f"[Thread-{thread_id}] [Task-{task_id}] [DEBUG] ts_code in params: {params.get('ts_code', 'N/A')}")

        logger.info(f"Fetching trade calendar for date range: {start_date} - {end_date}")

        # [修改] 先查内存缓存，再查Data目录，最后请求 API
        with self._cache_lock:
            cache_key = (start_date, end_date)
            trade_calendar = self._memory_cache['trade_cal'].get(cache_key)

        # 如果内存缓存未命中，查询Data目录
        if trade_calendar is None:
            trade_calendar = self._get_trade_calendar_from_data_dir(start_date, end_date)

        # 如果Data目录未命中，请求 API
        if trade_calendar is None:
            logger.info(f"Trade calendar not found in memory cache or data directory, fetching from API")
            calendar_params = {
                'start_date': start_date,
                'end_date': end_date,
                'exchange': 'SSE'
            }
            trade_calendar = self._make_request(
                self.config_loader.get_interface_config('trade_cal'),
                calendar_params
            )
            # 更新内存缓存
            if trade_calendar:
                with self._cache_lock:
                    self._memory_cache['trade_cal'][cache_key] = trade_calendar
        else:
            logger.info(f"Trade calendar loaded from data directory: {start_date}-{end_date}")

        # 如果获取交易日历失败，使用默认的日期范围分页
        if not trade_calendar:
            logger.warning("Failed to get trade calendar, using default date range pagination")
            # 检查是否配置了内部offset分页
            offset_config = interface_config.get('offset_pagination', {})
            if offset_config.get('enabled', False):
                return self._execute_offset_pagination(interface_config, params, offset_config)
            else:
                return self._make_request(interface_config, params)

        # 过滤出交易日
        trade_days = [day for day in trade_calendar if day.get('is_open', 0) == 1]

        # 如果没有交易日，直接返回
        if not trade_days:
            logger.warning(f"No trade days found in range {start_date} - {end_date}")
            return []

        # 按日期升序排序（从旧到新）
        trade_days = sorted(trade_days, key=lambda x: x['cal_date'])

        logger.info(f"Found {len(trade_days)} trade days")

        # 按窗口分割日期范围
        window_size = pagination_config.get('window_size_days', 3650)  # 默认10年窗口
        logger.info(f"Using window size: {window_size} days")

        for i in range(0, len(trade_days), window_size):
            window_trade_days = trade_days[i:i+window_size]
            if not window_trade_days:
                continue
            window_start = window_trade_days[0]['cal_date']
            window_end = window_trade_days[-1]['cal_date']

            window_params = params.copy()
            window_params['start_date'] = window_start
            window_params['end_date'] = window_end

            # 记录开始时间
            start_time = time.time()

            logger.info(f"Downloading data for window {i//window_size + 1}: {window_start} - {window_end}")

            # 检查是否配置了内部offset分页
            offset_config = interface_config.get('offset_pagination', {})
            if offset_config.get('enabled', False):
                # 使用内部offset分页下载窗口数据
                logger.info(f"Using internal offset pagination for window {window_start}-{window_end}")
                window_data = self._execute_offset_pagination(interface_config, window_params, offset_config)
            else:
                # 直接下载窗口数据
                window_data = self._make_request(interface_config, window_params)

            # 记录并检查性能指标
            elapsed_time = time.time() - start_time
            performance_monitor.record_metric('request_time', elapsed_time, {
                'interface': interface_config['api_name'],
                'window': f"{window_start}-{window_end}",
                'ts_code': params.get('ts_code', 'unknown')
            })
            performance_monitor.check_alerts('request_time', elapsed_time, {
                'interface': interface_config['api_name'],
                'window': f"{window_start}-{window_end}",
                'ts_code': params.get('ts_code', 'unknown')
            })

            if window_data:
                # 检查数据完整性
                query_limit = interface_config.get('permissions', {}).get('query_limit', 6000)

                # 记录数据量指标
                performance_monitor.record_metric('data_size', len(window_data), {
                    'interface': interface_config['api_name'],
                    'window': f"{window_start}-{window_end}",
                    'ts_code': params.get('ts_code', 'unknown')
                })

                if len(window_data) >= query_limit:
                    logger.warning(f"Window {window_start}-{window_end} returned {len(window_data)} records, which may be truncated (API limit: {query_limit})")
                    performance_monitor.check_alerts('data_size', len(window_data), {
                        'interface': interface_config['api_name'],
                        'window': f"{window_start}-{window_end}",
                        'ts_code': params.get('ts_code', 'unknown')
                    })

                all_data.extend(window_data)
                logger.info(f"Downloaded {len(window_data)} records for date range {window_start}-{window_end}")
            else:
                logger.warning(f"No data returned for window {window_start}-{window_end}")

        return all_data

    def _execute_stock_loop_pagination(self, interface_config: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """执行股票循环分页 - 串行版本"""
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

        # 为每个股票下载数据
        total_stocks = len(stock_list)
        logger.info(f"Starting to download data for {total_stocks} stocks...")

        log_interval = 100  # 每100个股票输出一次进度
        for idx, stock in enumerate(stock_list):
            # 使用原子化的单股票下载方法
            stock_data = self.download_single_stock(interface_config, stock, params)

            if stock_data:
                all_data.extend(stock_data)

            # 只在特定间隔输出日志
            if (idx + 1) % log_interval == 0 or idx == 0:
                logger.info(f"Processed stock {stock['ts_code']} ({idx+1}/{total_stocks}), got {len(stock_data)} records")

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

            return df.to_dicts()

        except Exception as e:
            logger.warning(f"Failed to read stock list from Data dir: {e}")
            return None

    def _get_trade_calendar_from_data_dir(self, start_date, end_date):
        """从 Data 目录查询交易日历 (Source of Truth)"""
        # 假设存储目录为 data/trade_cal/
        storage_dir = self.global_config.get('storage', {}).get('base_dir', '../data')
        dir_path = os.path.join(storage_dir, 'trade_cal')

        if not os.path.exists(dir_path):
            return None

        try:
            # 读取目录下所有 parquet 文件 (Dataset 模式)
            df = pl.read_parquet(dir_path)

            if df.is_empty():
                return None

            # 过滤日期范围并去重
            # 必须去重，因为 Dataset 模式下可能有重复数据
            filtered_df = df.filter(
                (pl.col('cal_date') >= start_date) &
                (pl.col('cal_date') <= end_date) &
                (pl.col('is_open') == 1)
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

            logger.info(f"Fetching data for period {period} ({idx+1}/{len(periods)})")

            # 记录开始时间
            start_time = time.time()
            
            # 发起请求
            period_data = self._make_request(interface_config, period_params)
            
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

            logger.info(f"Downloading data for stock {stock['ts_code']}, date range: {stock_params.get('start_date')} - {stock_params.get('end_date')}")

            # 执行日期范围分页下载
            stock_data = self._execute_date_range_pagination(interface_config, stock_params)

            if stock_data:
                logger.info(f"Downloaded {len(stock_data)} records for {stock['ts_code']}")

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

                # 从配置中读取字段列表
                output_config = interface_config.get('output', {})
                columns_config = output_config.get('columns', {})

                # 构建fields参数：排除内部字段（以_开头的）
                if columns_config:
                    fields_list = [col for col in columns_config.keys() if not col.startswith('_')]
                    fields_str = ','.join(fields_list)
                else:
                    fields_str = ''

                # 根据TuShare API格式构建请求体
                req_params = {
                    'api_name': interface_config['api_name'],
                    'token': token,
                    'params': params,
                    'fields': fields_str
                }

                # 调试日志：记录发送的fields参数
                logger.debug(f"Sending request to {api_name} with {len(fields_str.split(',')) if fields_str else 0} fields")
                if fields_str and len(fields_str) < 200:
                    logger.debug(f"Fields: {fields_str}")
                else:
                    logger.debug(f"Fields length: {len(fields_str)} chars, preview: {fields_str[:200]}...{fields_str[-200:]}")

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

        return []