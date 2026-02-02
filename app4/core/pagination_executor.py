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

    def execute_date_range_daily_pagination(
        self,
        interface_config: Dict[str, Any],
        params: Dict[str, Any],
        context: PaginationContext,
        make_request_callback: Callable,
        coverage_manager=None,
        force_download: bool = False,
        get_trade_calendar_callback: Optional[Callable] = None
    ) -> List[Dict[str, Any]]:
        """
        按日遍历的分页模式 - 适用于cyq_perf等接口
        将日期范围分解为单个交易日，逐日请求
        """
        start_date = params.get('start_date')
        end_date = params.get('end_date')

        if not start_date or not end_date:
            # 如果没有提供日期范围，直接请求
            return make_request_callback(interface_config, params)

        # 获取交易日历
        if get_trade_calendar_callback:
            trade_days = get_trade_calendar_callback(start_date, end_date)
            trade_dates = [day['cal_date'] for day in trade_days if day.get('is_open', 0) == 1]
        else:
            # 如果没有交易日历回调，假设所有日期都是交易日
            from datetime import datetime, timedelta
            start = datetime.strptime(start_date, '%Y%m%d')
            end = datetime.strptime(end_date, '%Y%m%d')
            trade_dates = []
            current = start
            while current <= end:
                trade_dates.append(current.strftime('%Y%m%d'))
                current += timedelta(days=1)

        all_data = []
        for trade_date in trade_dates:
            # 为每一天创建新的参数
            daily_params = params.copy()
            daily_params['trade_date'] = trade_date
            # 移除可能冲突的日期范围参数
            daily_params.pop('start_date', None)
            daily_params.pop('end_date', None)

            # 检查覆盖率，如果已存在则跳过
            if coverage_manager and not force_download:
                should_skip = coverage_manager.should_skip(
                    interface_config['api_name'],
                    daily_params,
                    strategy='daily'
                )
                if should_skip:
                    continue

            # 发起请求
            daily_data = make_request_callback(interface_config, daily_params)
            if daily_data:
                all_data.extend(daily_data)

        return all_data

    def _is_stock_data_exists(self, interface_name: str, ts_code: str, coverage_manager: Optional[Any] = None) -> bool:
        """内部方法：检查股票数据是否存在"""
        if coverage_manager:
            # 使用覆盖率管理器检查
            return coverage_manager.check_stock_coverage(interface_name, ts_code)
        return False

    def execute_reverse_date_range_pagination(
        self,
        interface_config: Dict[str, Any],
        params: Dict[str, Any],
        context: PaginationContext,
        make_request_callback: Callable,
        coverage_manager: Optional[Any] = None,
        force_download: bool = False,
        get_trade_calendar_callback: Optional[Callable] = None
    ) -> List[Dict[str, Any]]:
        """
        执行反向日期范围分页（从最近日期往前下载）

        特性：
        1. 从end_date往start_date方向下载（倒序）
        2. 支持窗口大小配置
        3. 连续无数据天数达到阈值时自动终止
        4. 支持覆盖率检查

        Args:
            interface_config: 接口配置
            params: 请求参数（包含start_date, end_date）
            context: 分页上下文
            make_request_callback: 请求回调函数
            coverage_manager: 覆盖率管理器
            force_download: 是否强制下载
            get_trade_calendar_callback: 获取交易日历的回调

        Returns:
            下载的数据列表
        """
        import logging
        logger = logging.getLogger(__name__)

        interface_name = interface_config['name']
        pagination_config = interface_config.get('pagination', {})

        # 获取配置参数
        window_size_days = pagination_config.get('window_size_days', 30)
        empty_threshold_days = pagination_config.get('empty_threshold_days', 90)

        start_date = params.get('start_date', '20050101')
        end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))

        logger.info(f"Starting reverse date range pagination for {interface_name}")
        logger.info(f"Date range: {start_date} to {end_date}, window size: {window_size_days} days")
        logger.info(f"Empty threshold: {empty_threshold_days} consecutive days without data will stop the download")

        # 获取交易日历
        if hasattr(context, 'trade_calendar') and context.trade_calendar:
            trade_calendar = context.trade_calendar
        else:
            trade_calendar = self._get_trade_calendar(start_date, end_date, get_trade_calendar_callback)
            context.trade_calendar = trade_calendar

        if not trade_calendar:
            logger.warning("Failed to get trade calendar, falling back to regular date_range")
            return self.execute_date_range_pagination(
                interface_config, params, context, make_request_callback,
                coverage_manager, force_download, get_trade_calendar_callback
            )

        # 过滤交易日并按倒序排列（从最近到最远）
        trade_days = [
            day for day in trade_calendar
            if day.get('is_open', 0) == 1 and
               start_date <= day['cal_date'] <= end_date
        ]

        if not trade_days:
            logger.warning(f"No trade days found in range {start_date} - {end_date}")
            return []

        # 按日期倒序排列（从最近到最远）
        trade_days.sort(key=lambda x: x['cal_date'], reverse=True)

        total_days = len(trade_days)
        logger.info(f"Total trade days to process: {total_days}")

        # 生成倒序窗口
        windows = []
        for i in range(0, total_days, window_size_days):
            window_days = trade_days[i:i + window_size_days]
            if not window_days:
                continue

            # 窗口的start和end需要重新排序（因为我们是倒序遍历）
            # 例如：倒序窗口 [20240131, 20240130, ... 20240102]
            # 实际请求的start_date应该是20240102, end_date是20240131
            window_dates = [d['cal_date'] for d in window_days]
            window_start = min(window_dates)  # 窗口内最早的日期
            window_end = max(window_dates)    # 窗口内最晚的日期

            windows.append((window_start, window_end))

        logger.info(f"Generated {len(windows)} windows for reverse download")

        # 顺序执行（从最近到最远）
        all_data = []
        consecutive_empty_days = 0
        processed_windows = 0

        for window_start, window_end in windows:
            processed_windows += 1

            # 构建窗口参数
            window_params = params.copy()
            window_params['start_date'] = window_start
            window_params['end_date'] = window_end

            # 计算当前窗口的天数
            window_days_count = sum(1 for d in trade_days if window_start <= d['cal_date'] <= window_end)

            logger.info(f"[{processed_windows}/{len(windows)}] Processing window {window_start} - {window_end} ({window_days_count} days)")

            # 覆盖率检查
            should_skip = False
            if coverage_manager and not force_download:
                should_skip = coverage_manager.should_skip(
                    interface_config['api_name'],
                    window_params,
                    strategy='date_range'
                )

            if should_skip:
                logger.info(f"  Skipping window {window_start} - {window_end} (already exists)")
                # 重置连续无数据计数（因为数据已存在）
                consecutive_empty_days = 0
                continue

            # 发起请求
            window_data = make_request_callback(interface_config, window_params)

            if window_data:
                all_data.extend(window_data)
                logger.info(f"  Got {len(window_data)} records, reset empty counter")
                # 有数据，重置连续无数据计数
                consecutive_empty_days = 0
            else:
                # 无数据，累加连续无数据天数
                consecutive_empty_days += window_days_count
                logger.info(f"  No data, consecutive empty days: {consecutive_empty_days}")

                # 检查是否达到终止阈值
                if consecutive_empty_days >= empty_threshold_days:
                    logger.info(f"Reached empty threshold ({empty_threshold_days} days), stopping download")
                    logger.info(f"Total windows processed: {processed_windows}/{len(windows)}")
                    break

        logger.info(f"Reverse pagination completed. Total records: {len(all_data)}")
        return all_data