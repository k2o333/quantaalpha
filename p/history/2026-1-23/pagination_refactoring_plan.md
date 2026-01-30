# 分页代码拆分方案

## 背景

当前 `app4/core/downloader.py` 文件共 1414 行，其中分页相关代码约 837 行，占比约 59%。分页逻辑与核心下载逻辑耦合在一起，导致代码可维护性和可测试性较低。

## 目标

将分页相关代码从 `downloader.py` 中拆分出来，创建独立的 `pagination.py` 模块，实现职责分离，提高代码的可维护性和可测试性。

## 当前分页代码统计

| 方法名 | 起始行 | 结束行 | 行数 |
|--------|--------|--------|------|
| `_execute_pagination` | 183 | 206 | 24 |
| `_execute_offset_pagination` | 207 | 226 | 20 |
| `_execute_date_range_pagination_concurrent` | 227 | 315 | 89 |
| `_make_request_with_offset_check` | 316 | 353 | 38 |
| `_execute_date_range_pagination` | 354 | 408 | 55 |
| `_execute_stock_loop_pagination` | 409 | 564 | 156 |
| `_generate_quarter_end_dates` | 565 | 612 | 48 |
| `_execute_period_range_pagination` | 613 | 667 | 55 |
| `_execute_quarterly_pagination` | 668 | 707 | 40 |
| `_generate_quarterly_ranges` | 708 | 726 | 19 |
| `_execute_periodic_pagination` | 727 | 787 | 61 |
| `_generate_time_ranges` | 788 | 855 | 68 |
| `_get_window_size_for_interface` | 1154 | 1180 | 27 |
| `_is_stock_data_exists` | 1181 | 1196 | 16 |
| **总计** | | | **837** |

## 拆分方案

### 1. 创建新文件 `app4/core/pagination.py`

将所有分页相关方法提取到独立的 `PaginationManager` 类中。

#### 文件结构

```python
"""
分页管理器 - 负责处理各种分页策略
"""
import os
import logging
import threading
import time
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
import polars as pl

logger = logging.getLogger(__name__)


class PaginationManager:
    """分页管理器 - 封装所有分页逻辑"""

    def __init__(
        self,
        config_loader,
        storage_manager=None,
        coverage_manager=None,
        performance_monitor=None,
        force_download=False
    ):
        """
        初始化分页管理器

        Args:
            config_loader: 配置加载器
            storage_manager: 存储管理器
            coverage_manager: 覆盖率管理器
            performance_monitor: 性能监控器
            force_download: 是否强制下载
        """
        self.config_loader = config_loader
        self.global_config = config_loader.get_global_config()
        self.storage_manager = storage_manager
        self.coverage_manager = coverage_manager
        self.performance_monitor = performance_monitor
        self.force_download = force_download

        # 用于获取交易日历和股票列表的回调函数
        self._get_trade_calendar_func: Optional[Callable] = None
        self._make_request_func: Optional[Callable] = None

    def set_trade_calendar_callback(self, callback: Callable):
        """设置获取交易日历的回调函数"""
        self._get_trade_calendar_func = callback

    def set_make_request_callback(self, callback: Callable):
        """设置发起请求的回调函数"""
        self._make_request_func = callback

    def execute_pagination(
        self,
        interface_config: Dict[str, Any],
        params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        执行分页/循环逻辑 - 入口方法

        Args:
            interface_config: 接口配置
            params: 请求参数

        Returns:
            所有分页数据的集合
        """
        pagination_config = interface_config.get('pagination', {})
        if not pagination_config.get('enabled', False):
            # 不分页，直接请求
            return self._make_request_func(interface_config, params)

        mode = pagination_config.get('mode', 'offset')

        if mode == 'offset':
            return self._execute_offset_pagination(interface_config, params, pagination_config)
        elif mode == 'date_range':
            return self._execute_date_range_pagination(interface_config, params, pagination_config)
        elif mode == 'stock_loop':
            return self._execute_stock_loop_pagination(interface_config, params)
        elif mode == 'period_range':
            return self._execute_period_range_pagination(interface_config, params, pagination_config)
        elif mode == 'quarterly_range':
            return self._execute_quarterly_pagination(interface_config, params, pagination_config)
        elif mode == 'periodic_range':
            return self._execute_periodic_pagination(interface_config, params, pagination_config)
        else:
            return self._make_request_func(interface_config, params)

    # ==================== 分页策略方法 ====================

    def _execute_offset_pagination(
        self,
        interface_config: Dict[str, Any],
        params: Dict[str, Any],
        pagination_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """执行 offset 分页"""
        all_data = []
        offset = 0
        limit_key = pagination_config.get('limit_key', 'limit')
        offset_key = pagination_config.get('offset_key', 'offset')
        default_limit = pagination_config.get('default_limit', 5000)

        while True:
            page_params = params.copy()
            page_params[limit_key] = default_limit
            page_params[offset_key] = offset

            page_data = self._make_request_func(interface_config, page_params)
            if not page_data:
                break

            all_data.extend(page_data)

            if len(page_data) < default_limit:
                break

            offset += default_limit

        return all_data

    def _execute_date_range_pagination(
        self,
        interface_config: Dict[str, Any],
        params: Dict[str, Any],
        pagination_config: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """执行日期范围分页 - 支持内部offset分页 - 智能分页策略"""
        if pagination_config is None:
            pagination_config = interface_config.get('pagination', {})

        interface_name = interface_config['name']

        start_date = params.get('start_date', '20050101')
        end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))

        thread_id = threading.get_ident()
        task_id = params.get('ts_code', 'unknown')

        logger.info(f"[Thread-{thread_id}] [Task-{task_id}] _execute_date_range_pagination called")
        logger.info(f"[Thread-{thread_id}] [Task-{task_id}] start_date: {start_date}, end_date: {end_date}")

        # 智能分页：根据接口类型确定窗口大小
        window_size = self._get_window_size_for_interface(interface_name)

        # 根据接口类型调整并发数
        if interface_name in ['fina_audit', 'forecast_vip', 'express_vip', 'disclosure_date']:
            max_workers = 1
        elif interface_name in ['top10_holders', 'top10_floatholders', 'pledge_detail', 'dividend']:
            max_workers = 2
        elif interface_name in ['balancesheet_vip', 'income_vip', 'cashflow_vip', 'fina_indicator_vip']:
            logger.info(f"财务接口{interface_name}使用全量请求模式")
            return self._make_request_func(interface_config, params)
        else:
            max_workers = 4

        logger.info(f"Fetching trade calendar for date range: {start_date} - {end_date}")

        return self._execute_date_range_pagination_concurrent(
            interface_config=interface_config,
            params=params,
            start_date=start_date,
            end_date=end_date,
            window_size=window_size,
            max_workers=max_workers
        )

    def _execute_date_range_pagination_concurrent(
        self,
        interface_config: Dict[str, Any],
        params: Dict[str, Any],
        start_date: str,
        end_date: str,
        window_size: int = 365,
        max_workers: int = 4
    ) -> List[Dict[str, Any]]:
        """并发执行日期范围分页"""
        trade_calendar = self._get_trade_calendar_func(start_date, end_date)

        if not trade_calendar:
            logger.warning("Failed to get trade calendar, using default date range pagination")
            offset_config = interface_config.get('offset_pagination', {})
            if offset_config.get('enabled', False):
                return self._execute_offset_pagination(interface_config, params, offset_config)
            else:
                return self._make_request_func(interface_config, params)

        trade_days = [day for day in trade_calendar if day.get('is_open', 0) == 1]

        if not trade_days:
            logger.warning(f"No trade days found in range {start_date} - {end_date}")
            return []

        trade_days = sorted(trade_days, key=lambda x: x['cal_date'])
        logger.info(f"Found {len(trade_days)} trade days")

        windows = []
        for i in range(0, len(trade_days), window_size):
            window_trade_days = trade_days[i:i+window_size]
            if window_trade_days:
                window_start = window_trade_days[0]['cal_date']
                window_end = window_trade_days[-1]['cal_date']
                windows.append((window_start, window_end))

        all_data = []
        results_by_window = {}

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_window = {}
            for window_start, window_end in windows:
                window_params = params.copy()
                window_params['start_date'] = window_start
                window_params['end_date'] = window_end

                should_skip = False
                if self.coverage_manager and not self.force_download:
                    should_skip = self.coverage_manager.should_skip(
                        interface_config['api_name'],
                        window_params,
                        strategy='date_range'
                    )

                if should_skip:
                    logger.info(f"Skipping window {window_start} - {window_end}")
                    results_by_window[(window_start, window_end)] = []
                else:
                    future = executor.submit(
                        self._make_request_with_offset_check,
                        interface_config,
                        window_params
                    )
                    future_to_window[future] = (window_start, window_end)

            for future in as_completed(future_to_window):
                window_start, window_end = future_to_window[future]
                try:
                    result = future.result()
                    results_by_window[(window_start, window_end)] = result
                except Exception as e:
                    logger.error(f"Error fetching window {window_start} to {window_end}: {e}")
                    results_by_window[(window_start, window_end)] = []

        for window_start, window_end in windows:
            window_data = results_by_window.get((window_start, window_end), [])
            all_data.extend(window_data)

        return all_data

    def _make_request_with_offset_check(
        self,
        interface_config: Dict[str, Any],
        params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """发起请求，支持内部offset分页检查"""
        start_time = time.time()

        offset_config = interface_config.get('offset_pagination', {})
        if offset_config.get('enabled', False):
            logger.debug(f"Using internal offset pagination for window {params.get('start_date')}-{params.get('end_date')}")
            window_data = self._execute_offset_pagination(interface_config, params, offset_config)
        else:
            window_data = self._make_request_func(interface_config, params)

        elapsed_time = time.time() - start_time

        if self.performance_monitor:
            self.performance_monitor.record_request(
                interface=interface_config['name'],
                duration=elapsed_time,
                record_count=len(window_data) if window_data else 0,
                retry_count=0,
                window_start=params.get('start_date'),
                window_end=params.get('end_date')
            )

        if window_data:
            logger.debug(f"Downloaded {len(window_data)} records for {params.get('start_date')}-{params.get('end_date')}")
        else:
            logger.warning(f"No data returned for window {params.get('start_date')}-{params.get('end_date')}")

        return window_data

    def _execute_stock_loop_pagination(
        self,
        interface_config: Dict[str, Any],
        params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """股票循环分页 - 增加前置去重"""
        all_data = []

        logger.info("正在获取股票列表...")
        stock_list = self._get_stock_list_from_memory_cache()

        if stock_list is None:
            logger.info("内存中未找到股票列表，正在从Data目录获取...")
            stock_list = self._get_stock_list_from_data_dir()

        if stock_list is None:
            logger.info("Data目录中未找到股票列表，正在从API获取...")
            stock_params = {'list_status': 'L'}
            stock_list = self._make_request_func(
                self.config_loader.get_interface_config('stock_basic'),
                stock_params
            )
            if stock_list:
                logger.info(f"从API获取到 {len(stock_list)} 只股票")
            else:
                logger.warning("未能从API获取股票列表")
        else:
            logger.info(f"从内存缓存或Data目录获取到 {len(stock_list)} 只股票")

        if not stock_list:
            logger.error("Failed to get stock list for stock loop pagination")
            return all_data

        interface_name = interface_config['name']
        if interface_name in ['fina_audit', 'forecast_vip', 'express_vip', 'disclosure_date']:
            max_workers = 1
        elif interface_name in ['top10_holders', 'top10_floatholders', 'pledge_detail', 'dividend']:
            max_workers = 2
        else:
            max_workers = 4

        total_stocks = len(stock_list)
        logger.info(f"Starting to download data for {total_stocks} stocks...")

        skipped_stocks = 0
        processed_stocks = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for idx, stock in enumerate(stock_list):
                ts_code = stock['ts_code']

                if not self.force_download and self._is_stock_data_exists(interface_name, ts_code):
                    logger.info(f"股票{ts_code}数据已存在，跳过")
                    skipped_stocks += 1
                    continue

                stock_params = params.copy()
                stock_params['ts_code'] = ts_code

                future = executor.submit(
                    self.download_single_stock,
                    interface_config,
                    stock,
                    params
                )
                futures.append(future)

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

    def _execute_period_range_pagination(
        self,
        interface_config: Dict[str, Any],
        params: Dict[str, Any],
        pagination_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """执行报告期范围分页"""
        all_data = []

        start_date = params.get('start_date', '20050101')
        end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))

        logger.info(f"Generating report periods for range: {start_date} - {end_date}")

        periods = self._generate_quarter_end_dates(start_date, end_date)

        if not periods:
            logger.warning(f"No valid report periods found in range {start_date} - {end_date}")
            return []

        logger.info(f"Generated {len(periods)} report periods: {periods}")

        for idx, period in enumerate(periods):
            period_params = params.copy()
            period_params.pop('start_date', None)
            period_params.pop('end_date', None)
            period_params['period'] = period

            should_skip = False
            if self.coverage_manager and not self.force_download:
                should_skip = self.coverage_manager.should_skip(
                    interface_config['api_name'],
                    period_params,
                    strategy='period'
                )
                if should_skip:
                    logger.info(f"Skipping period {period}")
                    continue

            logger.info(f"Fetching data for period {period} ({idx+1}/{len(periods)})")

            period_data = self._make_request_func(interface_config, period_params)

            if period_data and 'period' in period_params:
                for record in period_data:
                    record['period'] = period_params['period']

            if period_data:
                all_data.extend(period_data)
                logger.info(f"Downloaded {len(period_data)} records for period {period}")
            else:
                logger.warning(f"No data returned for period {period}")

        return all_data

    def _execute_quarterly_pagination(
        self,
        interface_config: Dict[str, Any],
        params: Dict[str, Any],
        pagination_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """执行季度周期分页"""
        all_data = []

        start_date = params.get('start_date', '20050101')
        end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))

        quarterly_ranges = self._generate_quarterly_ranges(start_date, end_date)

        for idx, (range_start, range_end) in enumerate(quarterly_ranges):
            range_params = params.copy()
            range_params['start_date'] = range_start
            range_params['end_date'] = range_end

            logger.info(f"Downloading dividend data for quarterly range {idx+1}/{len(quarterly_ranges)}: {range_start} - {range_end}")

            range_data = self._make_request_func(interface_config, range_params)

            if range_data:
                all_data.extend(range_data)
                logger.info(f"Downloaded {len(range_data)} records for quarterly range {range_start}-{range_end}")
            else:
                logger.warning(f"No data returned for quarterly range {range_start}-{range_end}")

        return all_data

    def _execute_periodic_pagination(
        self,
        interface_config: Dict[str, Any],
        params: Dict[str, Any],
        pagination_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """执行周期性时间范围分页"""
        all_data = []

        start_date = params.get('start_date', '20050101')
        end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))

        period_type = pagination_config.get('period_type', 'month')

        time_ranges = self._generate_time_ranges(start_date, end_date, period_type)

        for idx, (range_start, range_end) in enumerate(time_ranges):
            range_params = params.copy()
            range_params['start_date'] = range_start
            range_params['end_date'] = range_end

            logger.info(f"Downloading dividend data for {period_type} range {idx+1}/{len(time_ranges)}: {range_start} - {range_end}")

            range_data = self._make_request_func(interface_config, range_params)

            if range_data:
                all_data.extend(range_data)
                logger.info(f"Downloaded {len(range_data)} records for {period_type} range {range_start}-{range_end}")
            else:
                logger.warning(f"No data returned for {period_type} range {range_start}-{range_end}")

        return all_data

    # ==================== 辅助方法 ====================

    def _generate_quarter_end_dates(self, start_date: str, end_date: str) -> List[str]:
        """生成日期范围内的所有季度末日期"""
        from datetime import datetime, timedelta

        start_dt = datetime.strptime(start_date, '%Y%m%d')
        end_dt = datetime.strptime(end_date, '%Y%m%d')

        quarter_ends = [
            (3, 31), (6, 30), (9, 30), (12, 31)
        ]

        periods = []

        current_year = start_dt.year
        current_quarter_idx = 0

        for q_idx, (month, day) in enumerate(quarter_ends):
            quarter_end = datetime(current_year, month, day)
            if quarter_end >= start_dt:
                current_quarter_idx = q_idx
                break
        else:
            current_year += 1
            current_quarter_idx = 0

        while True:
            month, day = quarter_ends[current_quarter_idx]
            quarter_end = datetime(current_year, month, day)

            if quarter_end > end_dt:
                break

            periods.append(quarter_end.strftime('%Y%m%d'))

            current_quarter_idx += 1
            if current_quarter_idx >= len(quarter_ends):
                current_quarter_idx = 0
                current_year += 1

        return periods

    def _generate_quarterly_ranges(self, start_date: str, end_date: str) -> List[tuple]:
        """生成季度分割范围"""
        from datetime import datetime

        start_dt = datetime.strptime(start_date, '%Y%m%d')
        end_dt = datetime.strptime(end_date, '%Y%m%d')

        quarterly_ranges = []

        current = start_dt
        while current <= end_dt:
            if current.month <= 3:
                quarter_end = datetime(current.year, 3, 31)
            elif current.month <= 6:
                quarter_end = datetime(current.year, 6, 30)
            elif current.month <= 9:
                quarter_end = datetime(current.year, 9, 30)
            else:
                quarter_end = datetime(current.year, 12, 31)

            if quarter_end > end_dt:
                quarter_end = end_dt

            if current.month in [1, 4, 7, 10] and current.day == 1:
                range_start = current.strftime('%Y%m%d')
            else:
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

            if quarter_end.month == 3:
                current = datetime(quarter_end.year, 4, 1)
            elif quarter_end.month == 6:
                current = datetime(quarter_end.year, 7, 1)
            elif quarter_end.month == 9:
                current = datetime(quarter_end.year, 10, 1)
            else:
                current = datetime(quarter_end.year + 1, 1, 1)

        return quarterly_ranges

    def _generate_time_ranges(self, start_date: str, end_date: str, period_type: str) -> List[tuple]:
        """生成时间分割范围"""
        from datetime import datetime, timedelta

        start_dt = datetime.strptime(start_date, '%Y%m%d')
        end_dt = datetime.strptime(end_date, '%Y%m%d')

        time_ranges = []
        current = start_dt

        while current <= end_dt:
            if period_type == 'week':
                days_until_sunday = 6 - current.weekday()
                period_end = current + timedelta(days=days_until_sunday)
            elif period_type == 'month':
                if current.month == 12:
                    period_end = datetime(current.year + 1, 1, 1) - timedelta(days=1)
                else:
                    period_end = datetime(current.year, current.month + 1, 1) - timedelta(days=1)
            elif period_type == 'quarter':
                if current.month <= 3:
                    period_end = datetime(current.year, 3, 31)
                elif current.month <= 6:
                    period_end = datetime(current.year, 6, 30)
                elif current.month <= 9:
                    period_end = datetime(current.year, 9, 30)
                else:
                    period_end = datetime(current.year, 12, 31)
            elif period_type == 'year':
                period_end = datetime(current.year, 12, 31)
            else:
                if current.month == 12:
                    period_end = datetime(current.year + 1, 1, 1) - timedelta(days=1)
                else:
                    period_end = datetime(current.year, current.month + 1, 1) - timedelta(days=1)

            if period_end > end_dt:
                period_end = end_dt

            range_start = current.strftime('%Y%m%d')
            range_end = period_end.strftime('%Y%m%d')
            time_ranges.append((range_start, range_end))

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

    def _get_window_size_for_interface(self, interface_name: str) -> int:
        """根据接口类型确定窗口大小"""
        data_volume_config = {
            'small': ['fina_audit', 'forecast_vip', 'express_vip', 'disclosure_date'],
            'medium': ['top10_holders', 'top10_floatholders', 'pledge_detail', 'dividend',
                      'repurchase', 'concept_detail', 'share_float', 'stk_holdertrade'],
            'large': ['stk_factor', 'stk_factor_pro', 'moneyflow_hsgt', 'moneyflow_north',
                     'moneyflow_stock', 'block_trade', 'stk_rewards', 'pledge_stat'],
            'financial': ['balancesheet_vip', 'income_vip', 'cashflow_vip', 'fina_indicator_vip']
        }

        for typ, interfaces in data_volume_config.items():
            if interface_name in interfaces:
                if typ == 'small':
                    return 3650
                elif typ == 'medium':
                    return 1825
                elif typ == 'financial':
                    return 36500
                else:
                    return 365

        return 365

    def _is_stock_data_exists(self, interface_name: str, ts_code: str, storage_dir: str = None) -> bool:
        """检查股票数据是否已存在"""
        if storage_dir is None:
            storage_dir = self.global_config.get('storage', {}).get('base_dir', '../data')

        dir_path = os.path.join(storage_dir, interface_name)

        if not os.path.exists(dir_path):
            return False

        try:
            df = pl.read_parquet(dir_path)
            return df.filter(pl.col('ts_code') == ts_code).height > 0
        except Exception:
            return False

    def _get_stock_list_from_memory_cache(self) -> Optional[List[Dict[str, Any]]]:
        """从内存缓存获取股票列表"""
        # 这个方法需要从 downloader 传入缓存引用
        return None

    def _get_stock_list_from_data_dir(self) -> Optional[List[Dict[str, Any]]]:
        """从Data目录获取股票列表"""
        try:
            storage_dir = self.global_config.get('storage', {}).get('base_dir', '../data')
            dir_path = os.path.join(storage_dir, 'stock_basic')

            if not os.path.exists(dir_path):
                return None

            df = pl.read_parquet(dir_path)

            if df.is_empty():
                return None

            deduplicated_df = df.unique(subset=['ts_code'], keep='last')

            stock_count = len(deduplicated_df)
            logger.info(f"从本地获取了 {stock_count} 只股票")

            return deduplicated_df.to_dicts()

        except Exception as e:
            logger.warning(f"Failed to read stock list from Data dir: {e}")
            return None

    def download_single_stock(
        self,
        interface_config: Dict[str, Any],
        stock: Dict[str, Any],
        params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """下载单只股票的数据"""
        try:
            stock_params = params.copy()
            stock_params['ts_code'] = stock['ts_code']

            if 'start_date' not in stock_params:
                list_date = stock.get('list_date', '20050101')
                stock_params['start_date'] = list_date
            if 'end_date' not in stock_params:
                from datetime import datetime
                stock_params['end_date'] = datetime.now().strftime('%Y%m%d')

            should_skip = False
            if self.coverage_manager and not self.force_download:
                should_skip = self.coverage_manager.should_skip(
                    interface_config['api_name'],
                    stock_params,
                    strategy='stock'
                )
                if should_skip:
                    logger.info(f"Skipping stock {stock['ts_code']}")
                    return []

            logger.info(f"Downloading data for stock {stock['ts_code']}, date range: {stock_params.get('start_date')} - {stock_params.get('end_date')}")

            stock_data = self._execute_date_range_pagination(interface_config, stock_params)

            if stock_data:
                logger.info(f"Downloaded {len(stock_data)} records for {stock['ts_code']}")

                if hasattr(self, 'storage_manager') and self.storage_manager:
                    self.storage_manager.add_to_buffer(interface_config['api_name'], stock_data)

            return stock_data or []
        except Exception as e:
            logger.error(f"Error downloading stock {stock['ts_code']}: {str(e)}")
            import traceback
            logger.debug(f"Full traceback: {traceback.format_exc()}")
            return []
```

### 2. 修改 `app4/core/downloader.py`

在 `GenericDownloader` 类中集成 `PaginationManager`，删除所有分页相关方法。

#### 修改后的 `GenericDownloader` 类结构

```python
from .config_loader import ConfigLoader
from .coverage_manager import CoverageManager
from .processor import DataProcessor
from .schema_manager import SchemaManager
from .performance_monitor import PerformanceMonitor
from .pagination import PaginationManager  # 新增导入
import polars as pl

class GenericDownloader:
    """通用下载器 - 原子化的执行引擎"""

    def __init__(self, config_loader: ConfigLoader, storage_manager=None,
                 trade_calendar_cache=None, stock_list_cache=None,
                 force_download=False, incremental_mode=False):
        self.config_loader = config_loader
        self.global_config = config_loader.get_global_config()

        self.storage_manager = storage_manager

        self.data_processor = DataProcessor()
        self.schema_manager = SchemaManager()

        self.force_download = force_download
        self.incremental_mode = incremental_mode

        self.performance_monitor = PerformanceMonitor()

        self.session = self._create_session_with_retries()

        self._memory_cache = {
            'trade_cal': LRUCache(maxsize=100),
            'stock_list': None,
            'coverage': LRUCache(maxsize=1000),
            'api_responses': LRUCache(maxsize=500)
        }
        self._cache_lock = threading.RLock()

        if trade_calendar_cache is not None:
            with self._cache_lock:
                self._memory_cache['trade_cal'][('global',)] = trade_calendar_cache

        if stock_list_cache is not None:
            with self._cache_lock:
                self._memory_cache['stock_list'] = stock_list_cache

        if storage_manager:
            self.coverage_manager = CoverageManager(storage_manager, config_loader, downloader=self)
        else:
            self.coverage_manager = None

        # 创建分页管理器
        self.pagination_manager = PaginationManager(
            config_loader=config_loader,
            storage_manager=storage_manager,
            coverage_manager=self.coverage_manager,
            performance_monitor=self.performance_monitor,
            force_download=force_download
        )

        # 设置回调函数
        self.pagination_manager.set_trade_calendar_callback(self.get_trade_calendar)
        self.pagination_manager.set_make_request_callback(self._make_request)

    def download(self, interface_name: str, params: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
        """下载指定接口的数据"""
        try:
            interface_config = self.config_loader.get_interface_config(interface_name)
            validated_params = self._validate_parameters(interface_config, params)

            # 使用分页管理器执行分页
            all_data = self.pagination_manager.execute_pagination(
                interface_config, validated_params
            )

            return all_data
        except Exception as e:
            logger.error(f"Error downloading data from {interface_name}: {str(e)}")
            return None

    # 保留的方法：
    # - _create_session_with_retries
    # - _generate_cache_key
    # - _validate_parameters
    # - get_trade_calendar
    # - _get_trade_calendar_from_data_dir
    # - _make_request
    # - _classify_api_error
    # - download_single_stock (可能需要保留或移到pagination)
    # - verify_trade_calendar_integrity
    # - _after_download

    # 删除的分页相关方法（已移至 pagination.py）：
    # - _execute_pagination
    # - _execute_offset_pagination
    # - _execute_date_range_pagination
    # - _execute_date_range_pagination_concurrent
    # - _make_request_with_offset_check
    # - _execute_stock_loop_pagination
    # - _generate_quarter_end_dates
    # - _execute_period_range_pagination
    # - _execute_quarterly_pagination
    # - _generate_quarterly_ranges
    # - _execute_periodic_pagination
    # - _generate_time_ranges
    # - _get_window_size_for_interface
    # - _is_stock_data_exists
```

## 文件结构对比

### 拆分前

```
app4/core/downloader.py (1414行)
├── 分页相关方法 (837行)
│   ├── _execute_pagination
│   ├── _execute_offset_pagination
│   ├── _execute_date_range_pagination
│   ├── _execute_date_range_pagination_concurrent
│   ├── _make_request_with_offset_check
│   ├── _execute_stock_loop_pagination
│   ├── _execute_period_range_pagination
│   ├── _execute_quarterly_pagination
│   ├── _execute_periodic_pagination
│   ├── 各种辅助方法...
│   └── _get_window_size_for_interface
├── 请求相关 (_make_request等)
├── 缓存相关
└── 其他辅助方法
```

### 拆分后

```
app4/core/
├── downloader.py (~577行)
│   ├── GenericDownloader 类
│   ├── _create_session_with_retries
│   ├── download
│   ├── _validate_parameters
│   ├── get_trade_calendar
│   ├── _make_request
│   └── 其他核心方法
│
└── pagination.py (~837行)
    ├── PaginationManager 类
    ├── execute_pagination (入口)
    ├── 各种分页策略方法
    │   ├── _execute_offset_pagination
    │   ├── _execute_date_range_pagination
    │   ├── _execute_stock_loop_pagination
    │   ├── _execute_period_range_pagination
    │   ├── _execute_quarterly_pagination
    │   └── _execute_periodic_pagination
    └── 辅助方法
```

## 优势

1. **职责分离**: 分页逻辑与下载逻辑解耦，每个模块职责更清晰
2. **易于测试**: 可以独立测试分页策略，无需依赖完整的下载流程
3. **可维护性**: 分页逻辑集中管理，修改和扩展更方便
4. **可扩展性**: 新增分页策略只需修改 `pagination.py`，不影响核心下载逻辑
5. **代码清晰**: `downloader.py` 更简洁，专注于核心下载功能
6. **复用性**: 分页管理器可以被其他模块复用

## 依赖关系

分页管理器需要通过回调函数访问以下功能：

| 功能 | 来源 | 用途 |
|------|------|------|
| `get_trade_calendar()` | GenericDownloader | 获取交易日历 |
| `_make_request()` | GenericDownloader | 发起API请求 |
| `coverage_manager.should_skip()` | CoverageManager | 覆盖率检查 |
| `performance_monitor.record_request()` | PerformanceMonitor | 性能监控 |

## 实施步骤

1. 创建 `app4/core/pagination.py` 文件
2. 将所有分页相关方法从 `downloader.py` 移动到 `pagination.py`
3. 在 `GenericDownloader` 中集成 `PaginationManager`
4. 设置回调函数
5. 删除 `downloader.py` 中的分页方法
6. 运行测试确保功能正常
7. 提交代码

## 注意事项

1. **缓存引用**: `_get_stock_list_from_memory_cache` 需要从 `downloader` 传入缓存引用
2. **线程安全**: 确保回调函数的线程安全性
3. **错误处理**: 保持原有的错误处理逻辑
4. **日志记录**: 保持原有的日志记录级别和格式
5. **向后兼容**: 确保对外接口保持不变

## 测试建议

1. 单元测试：测试各个分页策略方法
2. 集成测试：测试分页管理器与下载器的集成
3. 回归测试：确保所有现有功能正常工作
4. 性能测试：确保拆分后性能不受影响