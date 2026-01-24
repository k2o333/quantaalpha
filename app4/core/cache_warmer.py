import os
import polars as pl
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

class CacheWarmer:
    """全局缓存预热器 - 在程序启动时加载常用数据到内存"""

    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.trade_calendar_cache = None
        self.stock_list_cache = None

    def preload_trade_calendar(self) -> Optional[List[Dict[str, Any]]]:
        """预加载交易日历到内存"""
        if self.trade_calendar_cache is not None:
            return self.trade_calendar_cache

        trade_cal_dir = os.path.join(self.data_dir, 'trade_cal')

        if not os.path.exists(trade_cal_dir):
            logger.warning(f"交易日历目录不存在: {trade_cal_dir}")
            return None

        try:
            # 读取所有交易日历文件
            df = pl.read_parquet(trade_cal_dir)

            # 过滤有效交易日
            df = df.filter(
                (pl.col('is_open') == 1) &
                (pl.col('exchange') == 'SSE')
            ).select(['cal_date', 'is_open', 'exchange'])

            # 去重并排序
            df = df.unique(subset=['cal_date'], keep='last').sort('cal_date')

            # 转换为字典列表
            self.trade_calendar_cache = df.to_dicts()

            logger.info(f"预加载交易日历成功: {len(self.trade_calendar_cache)}条记录")

            return self.trade_calendar_cache

        except Exception as e:
            logger.error(f"预加载交易日历失败: {str(e)}")
            return None

    def preload_stock_list(self) -> Optional[List[Dict[str, Any]]]:
        """预加载股票列表到内存"""
        if self.stock_list_cache is not None:
            return self.stock_list_cache

        stock_basic_dir = os.path.join(self.data_dir, 'stock_basic')

        if not os.path.exists(stock_basic_dir):
            logger.warning(f"股票列表目录不存在: {stock_basic_dir}")
            return None

        try:
            # 读取股票列表
            df = pl.read_parquet(stock_basic_dir)

            # 过滤有效股票
            df = df.filter(pl.col('status') == 'L')  # 只保留上市股票

            # 转换为字典列表
            self.stock_list_cache = df.to_dicts()

            logger.info(f"预加载股票列表成功: {len(self.stock_list_cache)}只股票")

            return self.stock_list_cache

        except Exception as e:
            logger.error(f"预加载股票列表失败: {str(e)}")
            return None

    def get_trade_calendar(self, start_date: str, end_date: str) -> Optional[List[Dict[str, Any]]]:
        """从缓存获取指定日期范围的交易日历"""
        if self.trade_calendar_cache is None:
            return None

        # 过滤日期范围
        filtered = [
            day for day in self.trade_calendar_cache
            if start_date <= day['cal_date'] <= end_date
        ]

        return filtered if filtered else None

    def get_stock_list(self) -> Optional[List[Dict[str, Any]]]:
        """从缓存获取股票列表"""
        return self.stock_list_cache