"""
分页执行器 - 负责执行分页参数生成器产生的参数
实现"零回调"模式，只执行请求，不生成参数
"""

from typing import Dict, Any, List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from .pagination import ParameterGenerator, PaginationContext
import logging
from datetime import datetime
from collections import OrderedDict, defaultdict, deque

logger = logging.getLogger(__name__)


class PaginationExecutor:
    """分页执行器 - 专门负责执行分页请求，通过回调函数执行具体请求"""

    def execute_offset_pagination(self, interface_config: Dict[str, Any],
                                params: Dict[str, Any],
                                context: PaginationContext,
                                make_request_callback: Callable) -> List[Dict[str, Any]]:
        """执行offset分页，通过回调函数执行请求"""
        all_data = []
        limit = context.pagination_config.get('default_limit', 5000)
        param_gen = ParameterGenerator(context)

        for page_params in param_gen.generate_offset_params(params):
            page_data = make_request_callback(interface_config, page_params)

            if not page_data:
                break
            all_data.extend(page_data)

            if len(page_data) < limit:
                break

        return all_data

    def execute_date_range_pagination(self, interface_config: Dict[str, Any],
                                    params: Dict[str, Any],
                                    context: PaginationContext,
                                    make_request_callback: Callable,
                                    coverage_manager: Optional[Any] = None,
                                    force_download: bool = False,
                                    get_trade_calendar_callback: Optional[Callable] = None) -> List[Dict[str, Any]]:
        """执行日期范围分页（并发），通过回调函数执行请求"""
        interface_name = interface_config['name']

        # 财务接口全量返回
        if interface_name in ['balancesheet_vip', 'income_vip', 'cashflow_vip', 'fina_indicator_vip']:
            logger.info(f"财务接口{interface_name}使用全量请求")
            return make_request_callback(interface_config, params)

        start_date = params.get('start_date', '20050101')
        end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))

        # 获取交易日历
        if hasattr(context, 'trade_calendar') and context.trade_calendar:
            trade_calendar = context.trade_calendar
        else:
            # 如果上下文中没有交易日历，需要通过某种方式获取
            trade_calendar = self._get_trade_calendar(start_date, end_date, get_trade_calendar_callback)
            context.trade_calendar = trade_calendar

        if not trade_calendar:
            logger.warning("Failed to get trade calendar, using offset fallback")
            offset_config = interface_config.get('offset_pagination', {})
            if offset_config.get('enabled', False):
                offset_context = PaginationContext(
                    interface_config=interface_config,
                    force_download=force_download
                )
                return self.execute_offset_pagination(interface_config, params, offset_context, make_request_callback)
            return make_request_callback(interface_config, params)

        # 确定并发数
        if interface_name in ['fina_audit', 'forecast_vip', 'express_vip', 'disclosure_date']:
            max_workers = 1
        elif interface_name in ['top10_holders', 'top10_floatholders', 'pledge_detail', 'dividend']:
            max_workers = 2
        else:
            max_workers = 4

        # 创建参数生成器并收集窗口
        param_gen = ParameterGenerator(context)
        windows = []
        window_params_list = []

        for window_params, window_id in param_gen.generate_date_range_params(params, start_date, end_date):
            windows.append(window_id)
            window_params_list.append(window_params)

        # 并发执行
        all_data = []
        results_by_window = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_window = {}

            for idx, window_params in enumerate(window_params_list):
                window_start, window_end = windows[idx]

                # 覆盖率检查
                should_skip = False
                if coverage_manager and not force_download:
                    should_skip = coverage_manager.should_skip(
                        interface_config['api_name'],
                        window_params,
                        strategy='date_range'
                    )

                if should_skip:
                    logger.info(f"Skipping window {window_start} - {window_end}")
                    results_by_window[(window_start, window_end)] = []
                else:
                    offset_config = interface_config.get('offset_pagination', {})
                    if offset_config.get('enabled', False):
                        future = executor.submit(
                            self._make_request_with_offset_check,
                            interface_config,
                            window_params,
                            make_request_callback,
                            coverage_manager,
                            force_download
                        )
                    else:
                        future = executor.submit(
                            make_request_callback,
                            interface_config,
                            window_params
                        )
                    future_to_window[future] = (window_start, window_end)

            # 收集结果
            for future in as_completed(future_to_window):
                window_start, window_end = future_to_window[future]
                try:
                    result = future.result()
                    results_by_window[(window_start, window_end)] = result
                except Exception as e:
                    logger.error(f"Error fetching window {window_start} to {window_end}: {e}")
                    results_by_window[(window_start, window_end)] = []

        # 合并结果（保持顺序）
        for window_start, window_end in windows:
            window_data = results_by_window.get((window_start, window_end), [])
            all_data.extend(window_data)

        return all_data

    def execute_stock_loop_pagination(self, interface_config: Dict[str, Any],
                                    params: Dict[str, Any],
                                    context: PaginationContext,
                                    make_request_callback: Callable,
                                    get_stock_list_callback: Callable,
                                    coverage_manager: Optional[Any] = None,
                                    force_download: bool = False) -> List[Dict[str, Any]]:
        """执行股票循环分页，通过回调函数执行请求"""
        # 获取股票列表
        logger.info("正在获取股票列表...")
        stock_list = get_stock_list_callback()

        if not stock_list:
            logger.error("Failed to get stock list for stock loop pagination")
            return []

        # 更新上下文
        context.stock_list = stock_list

        # 创建参数生成器
        param_gen = ParameterGenerator(context)

        # 确定并发数
        interface_name = interface_config['name']
        if interface_name in ['fina_audit', 'forecast_vip', 'express_vip', 'disclosure_date']:
            max_workers = 1
        elif interface_name in ['top10_holders', 'top10_floatholders', 'pledge_detail', 'dividend']:
            max_workers = 2
        else:
            max_workers = 4

        all_data = []
        results = []

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}

            for stock_params, stock_info in param_gen.generate_stock_params(
                params,
                existing_stocks_checker=lambda name, code: self._is_stock_data_exists(name, code, coverage_manager)
            ):
                future = executor.submit(
                    make_request_callback,
                    interface_config,
                    stock_params
                )
                futures[future] = (stock_info['ts_code'], stock_params)

            for future in as_completed(futures):
                ts_code, stock_params = futures[future]
                try:
                    data = future.result()
                    if data:
                        all_data.extend(data)
                        logger.info(f"Downloaded {len(data)} records for {ts_code}")
                        results.append((ts_code, data))
                except Exception as e:
                    logger.error(f"Error downloading stock {ts_code}: {e}")

        return all_data

    def execute_period_range_pagination(self, interface_config: Dict[str, Any],
                                      params: Dict[str, Any],
                                      context: PaginationContext,
                                      make_request_callback: Callable,
                                      coverage_manager: Optional[Any] = None,
                                      force_download: bool = False) -> List[Dict[str, Any]]:
        """执行报告期分页"""
        start_date = params.get('start_date', '20050101')
        end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))

        param_gen = ParameterGenerator(context)
        all_data = []

        for period_params, period in param_gen.generate_period_params(params, start_date, end_date):
            # 覆盖率检查
            should_skip = False
            if coverage_manager and not force_download:
                should_skip = coverage_manager.should_skip(
                    interface_config['api_name'],
                    period_params,
                    strategy='period'
                )

            if should_skip:
                logger.info(f"Skipping period {period}")
                continue

            logger.info(f"Fetching data for period {period}")

            period_data = make_request_callback(interface_config, period_params)

            if period_data:
                # 将period参数添加到每条记录中
                for record in period_data:
                    record['period'] = period
                all_data.extend(period_data)

        return all_data

    def execute_quarterly_pagination(self, interface_config: Dict[str, Any],
                                   params: Dict[str, Any],
                                   context: PaginationContext,
                                   make_request_callback: Callable) -> List[Dict[str, Any]]:
        """执行季度范围分页"""
        start_date = params.get('start_date', '20050101')
        end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))

        param_gen = ParameterGenerator(context)
        all_data = []

        for range_params, (range_start, range_end) in param_gen.generate_quarterly_params(params, start_date, end_date):
            logger.info(f"Downloading data for quarterly range {range_start} - {range_end}")

            range_data = make_request_callback(interface_config, range_params)

            if range_data:
                all_data.extend(range_data)

        return all_data

    def execute_periodic_pagination(self, interface_config: Dict[str, Any],
                                  params: Dict[str, Any],
                                  context: PaginationContext,
                                  make_request_callback: Callable) -> List[Dict[str, Any]]:
        """执行周期性时间范围分页"""
        start_date = params.get('start_date', '20050101')
        end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))

        # 获取周期类型，默认为月
        period_type = context.pagination_config.get('period_type', 'month')

        param_gen = ParameterGenerator(context)
        all_data = []

        for range_params, (range_start, range_end) in param_gen.generate_periodic_params(params, start_date, end_date, period_type):
            logger.info(f"Downloading data for {period_type} range {range_start} - {range_end}")

            range_data = make_request_callback(interface_config, range_params)

            if range_data:
                all_data.extend(range_data)

        return all_data

    def _make_request_with_offset_check(self, interface_config: Dict[str, Any], 
                                      params: Dict[str, Any],
                                      make_request_callback: Callable,
                                      coverage_manager: Optional[Any] = None,
                                      force_download: bool = False) -> List[Dict[str, Any]]:
        """内部方法：带偏移检查的请求"""
        # 检查内部偏移分页配置
        offset_config = interface_config.get('offset_pagination', {})
        if offset_config.get('enabled', False):
            context = PaginationContext(
                interface_config=interface_config,
                force_download=force_download
            )
            return self.execute_offset_pagination(interface_config, params, context, make_request_callback)
        else:
            return make_request_callback(interface_config, params)

    def _get_trade_calendar(self, start_date: str, end_date: str, get_trade_calendar_callback: Optional[Callable] = None) -> List[Dict[str, Any]]:
        """内部方法：获取交易日历"""
        if get_trade_calendar_callback:
            return get_trade_calendar_callback(start_date, end_date)
        return []

    def _is_stock_data_exists(self, interface_name: str, ts_code: str, coverage_manager: Optional[Any] = None) -> bool:
        """内部方法：检查股票数据是否存在"""
        if coverage_manager:
            # 使用覆盖率管理器检查
            return coverage_manager.check_stock_coverage(interface_name, ts_code)
        return False