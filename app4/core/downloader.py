import requests
import json
import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from .config_loader import ConfigLoader
from .cache_manager import CacheManager

logger = logging.getLogger(__name__)

class GenericDownloader:
    """通用下载器 - 原子化的执行引擎"""

    def __init__(self, config_loader: ConfigLoader, cache_manager: CacheManager):
        self.config_loader = config_loader
        self.cache_manager = cache_manager
        self.global_config = config_loader.get_global_config()
        self.session = requests.Session()
        # 设置默认请求头
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'aspipe_v4/4.0.0'
        })

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

            # 2. 检查缓存
            cache_key = self._generate_cache_key(interface_name, params)
            cached_data = self.cache_manager.get(cache_key)
            if cached_data is not None:
                logger.info(f"Cache hit for {interface_name} with key: {cache_key}")
                return cached_data
            else:
                logger.info(f"Cache miss for {interface_name} with key: {cache_key}, will fetch from API")

            # 3. 校验参数
            validated_params = self._validate_parameters(interface_config, params)

            # 4. 执行分页/循环逻辑
            all_data = self._execute_pagination(interface_config, validated_params)

            # 5. 写入缓存
            if all_data:
                self.cache_manager.set(cache_key, all_data)
                logger.info(f"Cache set for {interface_name} with key: {cache_key}, {len(all_data)} records")
            else:
                logger.info(f"No data to cache for {interface_name} with key: {cache_key}")

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
            # 添加延迟避免触发限流
            time.sleep(0.1)

        return all_data

    def _execute_date_range_pagination(self, interface_config: Dict[str, Any], params: Dict[str, Any],
                                      pagination_config: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """执行日期范围分页"""
        # 如果没有提供分页配置，从接口配置中获取
        if pagination_config is None:
            pagination_config = interface_config.get('pagination', {})

        all_data = []

        # 获取日期范围
        start_date = params.get('start_date', '20050101')
        end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))

        logger.info(f"[DEBUG] _execute_date_range_pagination called with params: {params}")
        logger.info(f"[DEBUG] start_date: {start_date}, end_date: {end_date}")
        logger.info(f"[DEBUG] ts_code in params: {params.get('ts_code', 'N/A')}")

        logger.info(f"Fetching trade calendar for date range: {start_date} - {end_date}")

        # 获取交易日历
        calendar_params = {
            'start_date': start_date,
            'end_date': end_date,
            'exchange': 'SSE'
        }
        trade_calendar = self._make_request(
            self.config_loader.get_interface_config('trade_cal'),
            calendar_params
        )

        # 如果获取交易日历失败，使用默认的日期范围分页
        if not trade_calendar:
            logger.warning("Failed to get trade calendar, using default date range pagination")
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

            logger.info(f"Downloading data for window {i//window_size + 1}: {window_start} - {window_end}")

            # 下载该窗口的数据
            window_data = self._make_request(interface_config, window_params)
            if window_data:
                all_data.extend(window_data)
                logger.info(f"Downloaded {len(window_data)} records for date range {window_start}-{window_end}")
            else:
                logger.warning(f"No data returned for window {window_start}-{window_end}")

        return all_data

    def _execute_stock_loop_pagination(self, interface_config: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """执行股票循环分页 - 串行版本"""
        all_data = []

        # 获取股票列表（使用增强的缓存方法）
        logger.info("正在获取股票列表...")
        stock_list = self.cache_manager.get_stock_list()

        if stock_list is None:
            logger.info("缓存中未找到股票列表，正在从API获取...")
            stock_params = {'list_status': 'L'}
            stock_list = self._make_request(
                self.config_loader.get_interface_config('stock_basic'),
                stock_params
            )
            if stock_list:
                logger.info(f"从API获取到 {len(stock_list)} 只股票")
                self.cache_manager.set_stock_list(stock_list)
            else:
                logger.warning("未能从API获取股票列表")
        else:
            logger.info(f"从缓存获取到 {len(stock_list)} 只股票")

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

            # 添加延迟避免触发限流
            import time
            time.sleep(0.1)  # 可根据API限制调整

        return all_data

    def download_single_stock(self, interface_config: Dict[str, Any], stock: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """下载单只股票的数据 - 原子化方法供调度器调用

        Args:
            interface_config: 接口配置
            stock: 股票信息字典，包含ts_code等
            params: 基础请求参数

        Returns:
            该股票的数据列表
        """
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

    def _make_request(self, interface_config: Dict[str, Any], params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """发起实际的 API 请求"""
        api_name = interface_config['api_name']
        request_config = interface_config.get('request', {})
        method = request_config.get('method', 'POST')
        timeout = request_config.get('timeout', 30)

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
            token = os.getenv('tushare_token', '')  # 注意这里使用小写
        else:
            token = token_placeholder

        # 调试信息
        logger.info(f"API URL: {api_url}")
        logger.info(f"Request timeout: {timeout}s")

        # 根据TuShare API格式构建请求体
        req_params = {
            'api_name': interface_config['api_name'],
            'token': token,
            'params': params,
            # 如果有字段需要，可以在这里添加fields参数
            'fields': ''  # 可以从配置中读取，这里暂时为空
        }

        # 创建新的params字典用于请求（保持api_name等参数）
        params = req_params

        logger.info(f"Making {method} request to {api_url} with api_name: {interface_config['api_name']}")
        try:
            logger.info(f"Starting request to {api_url}...")
            if method.upper() == 'POST':
                response = self.session.post(api_url, json=params, timeout=timeout)
            else:
                response = self.session.get(api_url, params=params, timeout=timeout)

            logger.info(f"Response status: {response.status_code}")
            response.raise_for_status()
            result = response.json()
            logger.debug(f"API response received, code: {result.get('code', 'unknown')}")

            # 检查 API 返回是否成功
            if result.get('code') != 0:
                logger.error(f"API error: {result.get('msg', 'Unknown error')}")
                return []

            # 将TuShare的字段/数据分离格式转换为字典列表格式
            fields = result.get('data', {}).get('fields', [])
            items = result.get('data', {}).get('items', [])

            # 将二维数组转换为字典列表
            converted_data = []
            for item in items:
                row_dict = {}
                for i, field_name in enumerate(fields):
                    if i < len(item):
                        # 确保字段名是字符串类型
                        field_name = str(field_name) if field_name is not None else f"field_{i}"
                        row_value = item[i]
                        row_dict[field_name] = row_value
                converted_data.append(row_dict)

            return converted_data

        except requests.RequestException as e:
            logger.error(f"Request error: {str(e)}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {str(e)}")
            return []