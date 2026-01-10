"""覆盖率管理器 - 实现重复数据检测功能

根据优化方案v4，实现策略模式+轻量级索引的重复数据检测
"""
import logging
import threading
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
        self._cache_lock = threading.RLock()  # [新增] 线程锁

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
            result = False
            if strategy == 'date_range':
                result = self._check_range_coverage(interface_name, params)
            elif strategy == 'period':
                result = self._check_period_existence(interface_name, params)
            elif strategy == 'stock':
                result = self._check_stock_existence(interface_name, params)
            
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

        # 获取检测列，默认为trade_date
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
                logger.debug(f"No existing data found for {interface_name} in range {start_date}-{end_date}")
                return False

            # 获取实际存在的日期
            actual_dates = set(df[date_column].to_list())

            # [优化] 直接使用 downloader 的 get_trade_calendar 方法
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
                logger.warning(f"No expected trade days in range {start_date}-{end_date}")
                return False

            # 计算覆盖率
            coverage = len(actual_dates & expected_dates) / len(expected_dates)
            logger.info(f"Coverage for {interface_name} ({start_date}-{end_date}): {coverage:.2%} ({len(actual_dates & expected_dates)}/{len(expected_dates)})")

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
        
        # 获取检测列，默认为ts_code
        key_column = detection_config.get('key_column', 'ts_code')
        
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
