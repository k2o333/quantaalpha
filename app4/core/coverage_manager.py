"""覆盖率管理器 - 实现重复数据检测功能

根据优化方案v4，实现策略模式+轻量级索引的重复数据检测
"""
import logging
from typing import Dict, Any, Optional, Set
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

    def should_skip(self, interface_name: str, params: Dict[str, Any], 
                   strategy: str = 'auto') -> bool:
        """
        根据策略判断是否应该跳过下载
        
        Args:
            interface_name: 接口名称
            params: 请求参数
            strategy: 检测策略 ('auto', 'date_range', 'period', 'stock')
            
        Returns:
            True表示应该跳过，False表示应该继续下载
        """
        try:
            # 获取接口配置
            interface_config = self.config_loader.get_interface_config(interface_name)
            detection_config = interface_config.get('duplicate_detection', {})
            
            # 检查是否启用重复检测
            if not detection_config.get('enabled', True):
                return False
                
            # 自动确定策略
            if strategy == 'auto':
                pagination_config = interface_config.get('pagination', {})
                pagination_mode = pagination_config.get('mode', 'offset') if pagination_config.get('enabled', False) else 'none'
                
                if pagination_mode == 'date_range':
                    strategy = 'date_range'
                elif pagination_mode == 'period_range':
                    strategy = 'period'
                elif pagination_mode == 'stock_loop':
                    strategy = 'stock'
                else:
                    return False  # 不支持的模式，不跳过
            
            # 根据策略执行检测
            if strategy == 'date_range':
                return self._check_range_coverage(interface_name, params)
            elif strategy == 'period':
                return self._check_period_existence(interface_name, params)
            elif strategy == 'stock':
                return self._check_stock_existence(interface_name, params)
            return False
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

        # 获取检测列，默认为trade_date
        date_column = detection_config.get('date_column', 'trade_date')
        threshold = detection_config.get('threshold', 0.95)

        # 检查缓存
        cache_key = f"{interface_name}_{start_date}_{end_date}"
        if cache_key in self._coverage_cache:
            return self._coverage_cache[cache_key]

        try:
            # 读取接口数据，只读取日期列
            df = self.storage_manager.read_interface_data(
                interface_name,
                start_date=start_date,
                end_date=end_date,
                columns=[date_column]
            )

            if df.is_empty():
                logger.debug(f"No existing data found for {interface_name} in range {start_date}-{end_date}")
                self._coverage_cache[cache_key] = False
                return False

            # 获取实际存在的日期
            actual_dates = set(df[date_column].to_list())

            # 获取预期的交易日历（从trade_cal接口获取）
            calendar_params = {
                'start_date': start_date,
                'end_date': end_date,
                'exchange': 'SSE'
            }
            trade_calendar = self._make_request_to_trade_cal(calendar_params)

            if not trade_calendar:
                # 如果无法获取交易日历，使用简单方法：检查日期范围内的数据量
                # 如果实际数据日期在请求范围内，认为已覆盖
                logger.info(f"Trade calendar not available for {interface_name}, using simple coverage check")

                # 简单策略：如果实际数据日期在请求范围内，认为已覆盖
                # 这里我们假设如果存在数据，就认为范围已覆盖
                result = not df.is_empty()
                self._coverage_cache[cache_key] = result
                logger.info(f"Simple coverage check for {interface_name} ({start_date}-{end_date}): {'covered' if result else 'not covered'}")
                return result

            # 过滤出交易日
            expected_dates = {day['cal_date'] for day in trade_calendar if day.get('is_open', 0) == 1}

            if not expected_dates:
                logger.warning(f"No expected trade days in range {start_date}-{end_date}")
                self._coverage_cache[cache_key] = False
                return False

            # 计算覆盖率
            coverage = len(actual_dates & expected_dates) / len(expected_dates)
            logger.info(f"Coverage for {interface_name} ({start_date}-{end_date}): {coverage:.2%} ({len(actual_dates & expected_dates)}/{len(expected_dates)})")

            result = coverage >= threshold
            self._coverage_cache[cache_key] = result

            return result

        except Exception as e:
            logger.warning(f"Range coverage check failed for {interface_name}: {e}")
            self._coverage_cache[cache_key] = False
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
        
        # 获取检测列，默认为ts_code
        key_column = detection_config.get('key_column', 'ts_code')
        
        try:
            # Lazy load all stocks for this interface
            cache_key = f"{interface_name}_stocks"
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

    def _make_request_to_trade_cal(self, params: Dict[str, Any]) -> Optional[list]:
        """
        内部方法：请求交易日历数据
        优先从本地存储读取，如果不存在则从API获取并缓存
        """
        try:
            # 尝试从storage读取交易日历 - 不使用日期过滤，因为文件名可能不包含日期范围
            df = self.storage_manager.read_interface_data('trade_cal', columns=['cal_date', 'is_open', 'exchange'])
            if not df.is_empty():
                # 过滤出指定日期范围内的数据
                filtered_df = df.filter(
                    (pl.col('cal_date') >= params['start_date']) &
                    (pl.col('cal_date') <= params['end_date']) &
                    (pl.col('exchange') == params['exchange'])
                )
                if not filtered_df.is_empty():
                    logger.info(f"Loaded {len(filtered_df)} trade days from local storage for range {params['start_date']}-{params['end_date']}")
                    return filtered_df.to_dicts()

            logger.info(f"No trade calendar data found in local storage for range {params['start_date']}-{params['end_date']}, fetching from API...")

            # 如果本地没有数据，尝试从API获取
            # 从downloader获取trade_cal接口配置
            try:
                trade_cal_config = self.config_loader.get_interface_config('trade_cal')

                # 创建下载器实例来获取数据（但需要避免循环依赖）
                # 这里我们直接使用storage_manager的downloader引用（如果存在）
                if hasattr(self, 'downloader') and self.downloader:
                    # 通过downloader请求API
                    calendar_params = {
                        'start_date': params['start_date'],
                        'end_date': params['end_date'],
                        'exchange': params['exchange']
                    }
                    trade_calendar = self.downloader._make_request(trade_cal_config, calendar_params)

                    if trade_calendar:
                        # 将新获取的数据保存到存储中以供后续使用
                        self.storage_manager.save_data('trade_cal', trade_calendar, async_write=True)
                        logger.info(f"Fetched and cached {len(trade_calendar)} trade days from API for range {params['start_date']}-{params['end_date']}")
                        return trade_calendar
            except Exception as api_error:
                logger.warning(f"Failed to fetch trade calendar from API: {api_error}")

            return None
        except Exception as e:
            # 如果读取失败，返回None，外部会处理
            logger.debug(f"Failed to read trade calendar from storage: {e}")
            return None