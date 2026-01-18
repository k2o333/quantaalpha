"""
StockListManager - 股票列表管理器
用于解决stock_basic数据重复下载问题的单例管理器
"""

import os
import pandas as pd
import logging
from pathlib import Path
from datetime import datetime, timedelta
import threading
from typing import Optional

logger = logging.getLogger(__name__)


class StockListManager:
    """股票列表管理器 - 单例模式"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, downloader=None, cache_dir="cache", max_cache_age_hours=24):
        """
        实现单例模式

        Args:
            downloader: Tushare下载器实例
            cache_dir: 缓存目录
            max_cache_age_hours: 缓存最大有效时间（小时）
        """
        if cls._instance is None:
            with cls._lock:
                # Double-check locking pattern
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, downloader=None, cache_dir="cache", max_cache_age_hours=24):
        """
        初始化StockListManager

        Args:
            downloader: Tushare下载器实例
            cache_dir: 缓存目录
            max_cache_age_hours: 缓存最大有效时间（小时）
        """
        if self._initialized:
            return

        self.downloader = downloader
        self.cache_dir = Path(cache_dir)
        self.max_cache_age_hours = max_cache_age_hours
        self.cache_file = self.cache_dir / "stock_basic.parquet"

        # 创建缓存目录
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # 缓存数据
        self._stock_df = None
        self._last_updated = None

        self._initialized = True
        logger.info(f"StockListManager initialized with cache dir: {self.cache_dir}")

    def _is_cache_valid(self) -> bool:
        """
        检查缓存是否有效

        Returns:
            bool: 缓存是否有效
        """
        if not self.cache_file.exists():
            logger.debug("Cache file does not exist")
            return False

        # 检查文件修改时间
        file_mtime = datetime.fromtimestamp(self.cache_file.stat().st_mtime)
        cache_age = datetime.now() - file_mtime

        is_valid = cache_age < timedelta(hours=self.max_cache_age_hours)
        logger.debug(f"Cache age: {cache_age}, max age: {timedelta(hours=self.max_cache_age_hours)}, valid: {is_valid}")

        return is_valid

    def _load_from_cache(self) -> Optional[pd.DataFrame]:
        """
        从缓存加载数据

        Returns:
            pd.DataFrame: 股票数据，如果加载失败返回None
        """
        try:
            if self.cache_file.exists():
                df = pd.read_parquet(self.cache_file)
                logger.info(f"Loaded stock data from cache: {len(df)} records")
                return df
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")
        return None

    def _save_to_cache(self, df: pd.DataFrame) -> bool:
        """
        保存数据到缓存

        Args:
            df: 要保存的DataFrame

        Returns:
            bool: 是否保存成功
        """
        try:
            df.to_parquet(self.cache_file, index=False)
            logger.info(f"Saved stock data to cache: {len(df)} records")
            return True
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")
            return False

    def _download_stock_basic(self) -> pd.DataFrame:
        """
        下载股票基本信息

        Returns:
            pd.DataFrame: 股票数据
        """
        if self.downloader is None:
            raise ValueError("Downloader not initialized")

        logger.info("Downloading stock basic data from Tushare API")
        df = self.downloader.download_stock_basic()
        return df

    def get_stock_basic(self, force_refresh: bool = False) -> pd.DataFrame:
        """
        获取股票基本信息，优先使用缓存

        Args:
            force_refresh: 是否强制刷新缓存

        Returns:
            pd.DataFrame: 股票数据
        """
        with self._lock:
            # 如果强制刷新，清除缓存
            if force_refresh:
                logger.info("Force refresh requested, clearing cache")
                self.clear_cache()
                self._stock_df = None
                self._last_updated = None

            # 如果已经有缓存数据且不需要强制刷新，直接返回
            if self._stock_df is not None and not force_refresh:
                logger.debug("Using in-memory cached stock data")
                return self._stock_df.copy()

            # 检查磁盘缓存
            if not force_refresh and self._is_cache_valid():
                logger.info("Using disk cached stock data")
                self._stock_df = self._load_from_cache()
                if self._stock_df is not None:
                    return self._stock_df.copy()

            # 下载新数据
            logger.info("Downloading fresh stock data")
            try:
                df = self._download_stock_basic()
                if not df.empty:
                    # 保存到缓存
                    self._save_to_cache(df)
                    self._stock_df = df.copy()
                    self._last_updated = datetime.now()
                    logger.info(f"Successfully downloaded and cached stock data: {len(df)} records")
                    return df.copy()
                else:
                    logger.warning("Downloaded empty stock data")
                    # 如果下载失败但有缓存，使用缓存
                    if self._stock_df is not None:
                        logger.info("Using previous cached data due to download failure")
                        return self._stock_df.copy()
                    # 如果完全没有数据，返回空DataFrame
                    return pd.DataFrame()
            except Exception as e:
                logger.error(f"Failed to download stock data: {e}")
                # 如果下载失败但有缓存，使用缓存
                if self._stock_df is not None:
                    logger.info("Using cached data due to download failure")
                    return self._stock_df.copy()
                # 如果完全没有数据，返回空DataFrame
                return pd.DataFrame()

    def clear_cache(self) -> bool:
        """
        清除缓存文件

        Returns:
            bool: 是否清除成功
        """
        try:
            if self.cache_file.exists():
                self.cache_file.unlink()
                logger.info("Cache file cleared")
            return True
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return False

    def refresh_cache(self) -> pd.DataFrame:
        """
        强制刷新缓存

        Returns:
            pd.DataFrame: 刷新后的股票数据
        """
        return self.get_stock_basic(force_refresh=True)

    def get_cache_status(self) -> dict:
        """
        获取缓存状态信息

        Returns:
            dict: 缓存状态信息
        """
        status = {
            "cache_file": str(self.cache_file),
            "cache_exists": self.cache_file.exists(),
            "last_updated": self._last_updated,
            "in_memory_cached": self._stock_df is not None,
            "records_count": len(self._stock_df) if self._stock_df is not None else 0
        }

        if self.cache_file.exists():
            file_mtime = datetime.fromtimestamp(self.cache_file.stat().st_mtime)
            status["file_modified_time"] = file_mtime
            status["cache_age"] = datetime.now() - file_mtime

        return status


def init_stock_manager(downloader, cache_dir="cache", max_cache_age_hours=24) -> StockListManager:
    """
    初始化StockListManager实例

    Args:
        downloader: Tushare下载器实例
        cache_dir: 缓存目录
        max_cache_age_hours: 缓存最大有效时间（小时）

    Returns:
        StockListManager: 初始化的实例
    """
    manager = StockListManager(downloader, cache_dir, max_cache_age_hours)
    return manager