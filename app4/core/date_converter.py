"""
日期转换器 - 提供内存缓存的日期转换功能
支持高性能日期格式转换，避免重复解析
"""
import polars as pl
from datetime import datetime, date
import threading
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

class DateConverter:
    """
    日期转换器，提供内存缓存功能

    使用场景：
    - 生产环境/服务：使用内存缓存（启动时预加载）
    - 脚本/单次任务：使用惰性加载（第一次调用时加载）
    - 简单测试：可直接使用CPU计算
    """

    def __init__(self, use_cache: bool = True):
        self.use_cache = use_cache
        self._date_map: Optional[Dict[str, date]] = None
        self._cache_loaded = False
        self._cache_lock = threading.RLock()

    def convert(self, date_str: str, date_format: str = '%Y%m%d') -> Optional[date]:
        """
        转换日期字符串为date对象

        Args:
            date_str: 日期字符串，格式如'20240101'
            date_format: 日期格式，默认'%Y%m%d'

        Returns:
            转换后的date对象，如果输入无效则返回None
        """
        if not date_str:
            return None

        if self.use_cache and self._load_calendar_cache():
            # 尝试从缓存获取
            cached_result = self._date_map.get(date_str)
            if cached_result is not None:
                return cached_result

        # 降级方案：直接解析
        try:
            result = datetime.strptime(date_str, date_format).date()
            # 如果缓存可用，也更新缓存
            if self.use_cache and self._date_map is not None:
                self._date_map[date_str] = result
            return result
        except ValueError:
            logger.warning(f"Cannot parse date string: {date_str}")
            return None

    def _load_calendar_cache(self) -> bool:
        """加载交易日历到内存缓存 - 惰性加载"""
        if self._cache_loaded:
            return True

        with self._cache_lock:
            if self._cache_loaded:
                return True

            try:
                # 尝试从数据目录加载trade_cal
                import os
                from .config_loader import ConfigLoader

                config_loader = ConfigLoader()
                global_config = config_loader.get_global_config()
                storage_dir = global_config.get('storage', {}).get('base_dir', '../data')

                trade_cal_path = os.path.join(storage_dir, 'trade_cal', '*.parquet')

                # 读取trade_cal数据
                import polars as pl
                df = pl.read_parquet(trade_cal_path)

                # 创建日期映射
                self._date_map = {}
                for row in df.to_dicts():
                    cal_date = row.get('cal_date')
                    # 确保cal_date存在且为字符串
                    if cal_date and isinstance(cal_date, str):
                        # 优先使用已转换的date类型，否则转换
                        if 'cal_date_dt' in row and row['cal_date_dt'] is not None:
                            self._date_map[cal_date] = row['cal_date_dt']
                        else:
                            try:
                                parsed_date = datetime.strptime(cal_date, '%Y%m%d').date()
                                self._date_map[cal_date] = parsed_date
                            except ValueError:
                                continue

                self._cache_loaded = True
                logger.info(f"DateConverter cache loaded: {len(self._date_map)} dates")
                return True

            except Exception as e:
                # 如果无法从存储加载，则使用空缓存
                logger.warning(f"Could not load trade calendar cache: {e}")
                self._date_map = {}
                self._cache_loaded = True
                return False

# 全局转换器实例
_date_converter = None
_converter_lock = threading.Lock()

def get_default_converter() -> DateConverter:
    """获取默认的日期转换器实例 - 单例模式"""
    global _date_converter

    if _date_converter is None:
        with _converter_lock:
            if _date_converter is None:
                _date_converter = DateConverter()

    return _date_converter

def convert_date(date_str: str) -> Optional[date]:
    """便捷函数：转换日期字符串为date对象"""
    return get_default_converter().convert(date_str)

def convert_trade_date(date_str: str) -> Optional[date]:
    """便捷函数：转换交易日期字符串为date对象"""
    return get_default_converter().convert(date_str, '%Y%m%d')