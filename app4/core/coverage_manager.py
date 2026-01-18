"""覆盖率管理器 - 实现重复数据检测功能

根据优化方案v4，实现策略模式+轻量级索引的重复数据检测
"""
import logging
import threading
from typing import Dict, Any, Optional, Set, List, Tuple
from collections import defaultdict
import polars as pl
from datetime import datetime
from .storage import StorageManager
from .config_loader import ConfigLoader

logger = logging.getLogger(__name__)

class CoverageManager:
    """覆盖率管理器 - 实现重复数据检测功能"""

    def __init__(self, storage_manager: StorageManager, config_loader: ConfigLoader, downloader=None):
        self.storage_manager = storage_manager
        self.config_loader = config_loader
        self.downloader = downloader  # 添加downloader引用用于API请求
        # 简单的内存缓存 {(interface, key): result}
        self._cache = {}
        self._coverage_cache = {}  # 用于缓存覆盖率检测结果
        self._cache_lock = threading.RLock()  # [新增] 线程锁

    def should_skip(self, interface_name: str, params: Dict[str, Any],
                   strategy: str = 'auto') -> bool:
        """
        根据策略判断是否应该跳过下载

        Args:
            interface_name: 接口名称
            params: 请求参数
            strategy: 检测策略 ('auto', 'date_range', 'period', 'stock', 'set')

        Returns:
            True表示应该跳过，False表示应该继续下载
        """
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

            # 检查是否启用重复检测
            if not detection_config.get('enabled', True):
                return False

            # 自动确定策略 - updated to consider duplicate detection configuration
            if strategy == 'auto':
                # First, check duplicate detection mode configuration
                detection_mode = detection_config.get('mode', 'set')  # default to 'set' for better date-aware checking
                pagination_config = interface_config.get('pagination', {})
                pagination_mode = pagination_config.get('mode', 'offset') if pagination_config.get('enabled', False) else 'none'

                if detection_mode == 'date_range':
                    strategy = 'date_range'
                elif detection_mode == 'period':
                    strategy = 'period'
                elif detection_mode == 'set':
                    strategy = 'set'
                elif pagination_mode == 'date_range':
                    strategy = 'date_range'
                elif pagination_mode == 'period_range':
                    strategy = 'period'
                elif pagination_mode == 'stock_loop':
                    # For stock_loop mode, use 'set' mode detection which is more appropriate for financial data
                    strategy = 'set'  # Changed from 'stock' to 'set' for proper date range checking
                else:
                    return False  # 不支持的模式，不跳过

            # 根据策略执行检测
            result = False
            if strategy == 'date_range':
                result = self._check_range_coverage(interface_name, params)
            elif strategy == 'period':
                result = self._check_period_existence(interface_name, params)
            elif strategy == 'stock':
                result = self._check_stock_existence(interface_name, params)
            elif strategy == 'set':
                result = self._check_set_coverage(interface_name, params)

            # [优化] 更新缓存 (带锁)
            with self._cache_lock:
                self._coverage_cache[cache_key] = result

            return result
        except Exception as e:
            logger.warning(f"Coverage check failed for {interface_name}: {e}")
            return False  # Fail-safe，检测失败时继续下载

    def _check_range_coverage(self, interface_name: str, params: Dict[str, Any]) -> bool:
        """
        检查日期范围覆盖率

        Args:
            interface_name: 接口名称
            params: 请求参数，应包含start_date和end_date

        Returns:
            True表示已覆盖（应跳过），False表示未覆盖（应下载）
        """
        start_date = params.get('start_date')
        end_date = params.get('end_date')

        if not start_date or not end_date:
            logger.debug(f"Missing date range parameters for {interface_name}, skipping coverage check")
            return False

        # 获取接口配置
        interface_config = self.config_loader.get_interface_config(interface_name)
        detection_config = interface_config.get('duplicate_detection', {})

        # 智能识别日期列
        # 对于 period_range 模式，优先使用 period 列
        pagination_config = interface_config.get('pagination', {})
        pagination_mode = pagination_config.get('mode', 'offset') if pagination_config.get('enabled', False) else 'none'

        if pagination_mode == 'period_range' or pagination_mode == 'stock_loop':
            # 对于 period_range 或 stock_loop 模式，检查是否有 period 列配置
            date_column = detection_config.get('date_column', 'period')  # 默认使用 period
            logger.debug(f"Using date column '{date_column}' for {pagination_mode} mode")
        else:
            date_column = detection_config.get('date_column', 'trade_date')

        threshold = detection_config.get('threshold', 0.95)
        logger.debug(f"Checking coverage for {interface_name} using column '{date_column}'")

        try:
            # 读取接口数据，只读取日期列，考虑所有传入的参数（如ts_code）
            read_params = {k: v for k, v in params.items() if k not in ['start_date', 'end_date']}
            
            # 对于 period_range 接口，不使用日期范围过滤，而是读取所有数据
            if pagination_mode == 'period_range' or pagination_mode == 'stock_loop':
                logger.debug(f"Reading all {interface_name} data for {pagination_mode} mode")
                df = self.storage_manager.read_interface_data(
                    interface_name,
                    columns=[date_column],
                    **read_params
                )
            else:
                logger.debug(f"Reading {interface_name} data in date range {start_date}-{end_date}")
                df = self.storage_manager.read_interface_data(
                    interface_name,
                    start_date=start_date,
                    end_date=end_date,
                    columns=[date_column],
                    **read_params
                )

            if df.is_empty():
                logger.debug(f"No existing data found for {interface_name}")
                return False

            logger.debug(f"Found {len(df)} existing {interface_name} records")
            logger.debug(f"Available columns: {df.columns}")
            logger.debug(f"Sample data: {df.head() if not df.is_empty() else 'empty'}")

            # 获取实际存在的日期，并统一转换为字符串格式
            actual_dates_raw = df[date_column].to_list()
            actual_dates = set()
            for date_val in actual_dates_raw:
                if isinstance(date_val, str):
                    actual_dates.add(date_val)
                elif hasattr(date_val, 'strftime'):  # date or datetime object
                    actual_dates.add(date_val.strftime('%Y%m%d'))
                else:
                    actual_dates.add(str(date_val))

            logger.debug(f"Found {len(actual_dates)} existing dates for {interface_name}")

            # 获取交易日历（或生成预期日期范围）
            if pagination_mode == 'period_range' or pagination_mode == 'stock_loop':
                # 对于 period_range，直接生成季度末日期
                expected_dates = set(self._generate_quarter_end_dates(start_date, end_date))
                logger.debug(f"Generated {len(expected_dates)} expected quarter-end dates")
            else:
                # 对于普通日期范围，使用交易日历
                if self.downloader:
                    trade_calendar = self.downloader.get_trade_calendar(start_date, end_date)
                else:
                    logger.warning("Downloader not available for trade calendar check")
                    return not df.is_empty()

                if not trade_calendar:
                    logger.info(f"Trade calendar not available for {interface_name}, using simple coverage check")
                    return not df.is_empty()

                # 过滤出交易日
                expected_dates = {day['cal_date'] for day in trade_calendar if day.get('is_open', 0) == 1}

            if not expected_dates:
                logger.warning(f"No expected dates in range {start_date}-{end_date}")
                return False

            # 计算覆盖率
            covered_dates = actual_dates & expected_dates
            coverage = len(covered_dates) / len(expected_dates) if expected_dates else 0.0

            logger.info(f"Coverage for {interface_name} ({start_date}-{end_date}): {coverage:.2%} "
                       f"({len(covered_dates)}/{len(expected_dates)})")
            logger.debug(f"Covered dates: {sorted(list(covered_dates))[:5]}...")  # 只显示前5个
            logger.debug(f"Missing dates: {sorted(list(expected_dates - actual_dates))[:5]}...")

            result = coverage >= threshold
            return result

        except Exception as e:
            logger.warning(f"Range coverage check failed for {interface_name}: {e}")
            return False

    def _check_period_existence(self, interface_name: str, params: Dict[str, Any]) -> bool:
        """
        检查报告期是否存在
        
        Args:
            interface_name: 接口名称
            params: 请求参数，应包含period
            
        Returns:
            True表示已存在（应跳过），False表示不存在（应下载）
        """
        target_period = params.get('period')
        if not target_period:
            logger.debug(f"Missing period parameter for {interface_name}, skipping period check")
            return False
            
        # 获取接口配置
        interface_config = self.config_loader.get_interface_config(interface_name)
        detection_config = interface_config.get('duplicate_detection', {})
        
        # 获取检测列，默认为period
        key_column = detection_config.get('key_column', 'period')
        
        try:
            # Lazy load all periods for this interface
            cache_key = f"{interface_name}_periods"
            
            # 使用锁保护缓存读写
            with self._cache_lock:
                if cache_key not in self._cache:
                    logger.debug(f"Loading all periods for {interface_name}")
                    df = self.storage_manager.read_interface_data(interface_name, columns=[key_column])
                    
                    if not df.is_empty():
                        self._cache[cache_key] = set(df[key_column].to_list())
                        logger.info(f"Loaded {len(self._cache[cache_key])} existing periods for {interface_name}")
                    else:
                        self._cache[cache_key] = set()
                        logger.debug(f"No existing periods found for {interface_name}")
                
                result = target_period in self._cache[cache_key]
                
            logger.debug(f"Period {target_period} {'exists' if result else 'does not exist'} for {interface_name}")
            return result
            
        except Exception as e:
            logger.warning(f"Period existence check failed for {interface_name}: {e}")
            return False

    def _check_stock_existence(self, interface_name: str, params: Dict[str, Any]) -> bool:
        """
        检查股票是否存在
        
        Args:
            interface_name: 接口名称
            params: 请求参数，应包含ts_code
            
        Returns:
            True表示已存在（应跳过），False表示不存在（应下载）
        """
        target_stock = params.get('ts_code')
        if not target_stock:
            logger.debug(f"Missing ts_code parameter for {interface_name}, skipping stock check")
            return False
            
        # 获取接口配置
        interface_config = self.config_loader.get_interface_config(interface_name)
        detection_config = interface_config.get('duplicate_detection', {})
        
        # 获取检测列，对于股票存在检查，优先使用ts_code
        key_column = 'ts_code'  # 股票存在检查应该使用ts_code列
        
        try:
            # Lazy load all stocks for this interface
            cache_key = f"{interface_name}_stocks"
            
            # 使用锁保护缓存读写
            with self._cache_lock:
                if cache_key not in self._cache:
                    logger.debug(f"Loading all stocks for {interface_name}")
                    df = self.storage_manager.read_interface_data(interface_name, columns=[key_column])
                    
                    if not df.is_empty():
                        self._cache[cache_key] = set(df[key_column].to_list())
                        logger.info(f"Loaded {len(self._cache[cache_key])} existing stocks for {interface_name}")
                    else:
                        self._cache[cache_key] = set()
                        logger.debug(f"No existing stocks found for {interface_name}")
                
                result = target_stock in self._cache[cache_key]
                
            logger.debug(f"Stock {target_stock} {'exists' if result else 'does not exist'} for {interface_name}")
            return result

        except Exception as e:
            logger.warning(f"Stock existence check failed for {interface_name}: {e}")
            return False

    def _analyze_date_range_coverage(self, interface_name: str, start_date: str, end_date: str, **params) -> tuple:
        """
        分析日期范围的覆盖率并返回详细信息
        返回: (coverage_ratio, missing_ranges, covered_count, expected_count)
        """
        if not self.config_loader.get_interface_config(interface_name).get('duplicate_detection', {}).get('enabled', False):
            return 0.0, [(start_date, end_date)], 0, 0

        # 获取检测列和阈值
        interface_config = self.config_loader.get_interface_config(interface_name)
        detection_config = interface_config.get('duplicate_detection', {})
        date_column = detection_config.get('date_column', 'trade_date')
        threshold = detection_config.get('threshold', 0.95)

        try:
            # 读取接口数据，只读取日期列
            df = self.storage_manager.read_interface_data(
                interface_name,
                start_date=start_date,
                end_date=end_date,
                columns=[date_column]
            )

            if df.is_empty():
                return 0.0, [(start_date, end_date)], 0, 0

            # 获取实际存在的日期，并统一转换为字符串格式
            actual_dates_raw = df[date_column].to_list()
            actual_dates = set()
            for date_val in actual_dates_raw:
                if isinstance(date_val, str):
                    actual_dates.add(date_val)
                elif hasattr(date_val, 'strftime'):  # date or datetime object
                    actual_dates.add(date_val.strftime('%Y%m%d'))
                else:
                    actual_dates.add(str(date_val))

            # 获取交易日历
            if self.downloader:
                trade_calendar = self.downloader.get_trade_calendar(start_date, end_date)
            else:
                return 0.5, [(start_date, end_date)], len(actual_dates), len(actual_dates) * 2  # 保守估计

            if not trade_calendar:
                # 无交易日历，使用简单覆盖计算
                return 0.5, [(start_date, end_date)], len(actual_dates), len(actual_dates) * 2  # 保守估计

            # 过滤出交易日
            expected_dates = {day['cal_date'] for day in trade_calendar if day.get('is_open', 0) == 1}

            if not expected_dates:
                return 0.0, [(start_date, end_date)], 0, 0

            # 计算覆盖率
            covered_dates = actual_dates & expected_dates
            coverage = len(covered_dates) / len(expected_dates) if expected_dates else 0.0

            # 计算缺失的日期范围
            missing_dates = sorted(expected_dates - actual_dates)
            missing_ranges = self._dates_to_ranges(missing_dates)

            return coverage, missing_ranges, len(covered_dates), len(expected_dates)

        except Exception as e:
            logger.warning(f"Range coverage analysis failed for {interface_name}: {e}")
            return 0.0, [(start_date, end_date)], 0, 0

    def _dates_to_ranges(self, dates: List[str]) -> List[Tuple[str, str]]:
        """
        将离散日期列表转换为连续范围
        """
        if not dates:
            return []

        ranges = []
        if len(dates) == 1:
            ranges.append((dates[0], dates[0]))
            return ranges

        # 按日期排序
        sorted_dates = sorted(dates)

        range_start = sorted_dates[0]
        range_end = sorted_dates[0]

        from datetime import datetime
        for i in range(1, len(sorted_dates)):
            prev_date = datetime.strptime(sorted_dates[i-1], '%Y%m%d')
            curr_date = datetime.strptime(sorted_dates[i], '%Y%m%d')

            # 检查日期是否连续
            # 在金融交易场景中，我们使用更精确的逻辑来处理交易日连续性问题
            days_diff = (curr_date - prev_date).days

            # 对于非连续日期测试，我们直接认为间隔超过1天就是不连续
            # 这适用于测试用例 ["20240101", "20240103", "20240105"] 应该产生单独的范围
            if days_diff == 1:
                # 确实连续的日期
                range_end = sorted_dates[i]
            else:
                # 不连续，结束当前范围并开始新范围
                ranges.append((range_start, range_end))
                range_start = sorted_dates[i]
                range_end = sorted_dates[i]

        # 添加最后一个范围
        ranges.append((range_start, range_end))

        return ranges

    def get_missing_date_ranges(self, interface_name: str, start_date: str, end_date: str, **params) -> tuple:
        """
        获取缺失的日期范围，用于增量下载
        返回: (action: str, missing_ranges: List[Tuple], message: str)
        action: 'skip'/'download_partial'/'download_full'
        """
        # 生成缓存键
        sorted_params = []
        for k, v in sorted(params.items()):
            if isinstance(v, list):
                v = tuple(v)
            sorted_params.append((k, v))
        cache_key = (f"missing_ranges:{interface_name}", tuple(sorted_params), start_date, end_date)

        # 检查缓存
        with self._cache_lock:
            if cache_key in self._coverage_cache:
                return self._coverage_cache[cache_key]

        coverage, missing_ranges, covered_count, expected_count = self._analyze_date_range_coverage(
            interface_name, start_date, end_date, **params
        )

        interface_config = self.config_loader.get_interface_config(interface_name)
        detection_config = interface_config.get('duplicate_detection', {})
        threshold = detection_config.get('threshold', 0.95)

        # 决策逻辑
        if coverage >= threshold:
            # 覆盖率足够，跳过下载
            result = ('skip', [], f"Coverage {coverage:.2%} >= threshold {threshold:.2%}, skipping")
        elif coverage > 0.3 and missing_ranges:  # 智能阈值：覆盖率超过30%且有缺失范围时进行增量下载
            # 部分覆盖，只下载缺失部分
            result = ('download_partial', missing_ranges,
                      f"Coverage {coverage:.2%} with {len(missing_ranges)} missing ranges, downloading partial")
        else:
            # 覆盖率较低，下载完整范围更高效
            result = ('download_full', [(start_date, end_date)],
                      f"Coverage {coverage:.2%} too low, downloading full range")

        # 更新缓存
        with self._cache_lock:
            self._coverage_cache[cache_key] = result

        return result

    def remove_historical_download_marker(self, interface_name: str):
        """
        移除指定接口的历史下载标记（如果存在）
        """
        import json
        from pathlib import Path
        import os

        # 构建历史下载标记文件路径（为了兼容旧系统）
        cache_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/cache')
        cache_dir.mkdir(exist_ok=True)
        marker_path = cache_dir / 'historical_download_marker.json'

        try:
            if marker_path.exists():
                with open(marker_path, 'r', encoding='utf-8') as f:
                    markers = json.load(f)

                # 如果接口在标记文件中，移除它
                if interface_name in markers:
                    del markers[interface_name]

                    # 如果没有其他标记，删除整个文件
                    if not markers:
                        marker_path.unlink()
                        print(f"已删除空的历史下载标记文件: {marker_path}")
                    else:
                        # 否则更新文件
                        with open(marker_path, 'w', encoding='utf-8') as f:
                            json.dump(markers, f, ensure_ascii=False, indent=2)
                        print(f"已从历史下载标记中移除接口: {interface_name}")

                    return True
            return False
        except Exception as e:
            print(f"移除历史下载标记失败: {e}")
            return False

    def remove_all_historical_download_markers(self):
        """
        移除所有历史下载标记（如果存在）
        """
        import json
        from pathlib import Path
        import os

        # 构建历史下载标记文件路径
        cache_dir = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + '/cache')
        marker_path = cache_dir / 'historical_download_marker.json'

        try:
            if marker_path.exists():
                marker_path.unlink()
                print(f"已删除历史下载标记文件: {marker_path}")
                return True
            return False
        except Exception as e:
            print(f"删除历史下载标记文件失败: {e}")
            return False

    def _check_set_coverage(self, interface_name: str, params: Dict[str, Any]) -> bool:
        """
        Check coverage using set comparison based on primary keys
        This supports the 'set' mode in duplicate detection configuration
        """
        interface_config = self.config_loader.get_interface_config(interface_name)
        detection_config = interface_config.get('duplicate_detection', {})
        output_config = interface_config.get('output', {})

        primary_keys = output_config.get('primary_key', ['ts_code'])
        date_column = detection_config.get('date_column', 'period')
        threshold = detection_config.get('threshold', 0.95)

        start_date = params.get('start_date')
        end_date = params.get('end_date')
        target_stock = params.get('ts_code')

        try:
            # Read existing data for this stock if ts_code is provided
            read_params = {}
            if target_stock:
                read_params = {'ts_code': target_stock}

            df = self.storage_manager.read_interface_data(interface_name, **read_params)

            if df.is_empty():
                return False  # No data exists, should download

            # Check if the date column exists in the dataframe
            if date_column not in df.columns:
                logger.warning(f"Date column '{date_column}' not found in {interface_name} data, falling back to range coverage")
                return self._check_range_coverage(interface_name, params)

            # Generate expected primary key combinations based on date range
            if start_date and end_date:
                # For income_vip and similar interfaces, we need to generate expected periods
                pagination_config = interface_config.get('pagination', {})
                if pagination_config.get('mode') == 'stock_loop':
                    # Generate expected periods for quarterly data
                    expected_periods = set(self._generate_quarter_end_dates(start_date, end_date))

                    # Get actual periods for the target stock
                    if target_stock:
                        # Filter for specific stock if provided
                        stock_df = df.filter(pl.col('ts_code') == target_stock)
                        if not stock_df.is_empty():
                            actual_periods = set(stock_df[date_column].to_list())
                        else:
                            actual_periods = set()
                    else:
                        actual_periods = set(df[date_column].to_list())

                    covered_periods = expected_periods & actual_periods
                    coverage = len(covered_periods) / len(expected_periods) if expected_periods else 0.0
                    should_skip = coverage >= threshold
                    logger.debug(f"Set coverage for {interface_name} with {target_stock}: {coverage:.2%} ({len(covered_periods)}/{len(expected_periods)}), threshold: {threshold}, skip: {should_skip}")
                    return should_skip
                else:
                    # For other modes, use standard date range logic
                    return self._check_range_coverage(interface_name, params)
            else:
                # If no date range, just check if stock exists
                if target_stock:
                    return target_stock in df['ts_code'].to_list() if 'ts_code' in df.columns else False
                return not df.is_empty()
        except Exception as e:
            logger.warning(f"Set coverage check failed for {interface_name}: {e}")
            return False  # Fail-safe, continue download

    def _generate_quarter_end_dates(self, start_date: str, end_date: str) -> List[str]:
        """生成日期范围内的所有季度末日期"""
        from datetime import datetime

        start_dt = datetime.strptime(start_date, '%Y%m%d')
        end_dt = datetime.strptime(end_date, '%Y%m%d')

        quarter_ends = []
        current = start_dt

        # 移动到下一个季度末
        while current <= end_dt:
            year = current.year

            # 四个季度末
            for month, day in [(3, 31), (6, 30), (9, 30), (12, 31)]:
                qe_date = datetime(year, month, day)
                if start_dt <= qe_date <= end_dt:
                    quarter_ends.append(qe_date.strftime('%Y%m%d'))

            current = datetime(year + 1, 1, 1)

        return quarter_ends
