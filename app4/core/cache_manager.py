import os
import pickle
import hashlib
import time
import threading
from typing import Any, Optional
import logging
import pyarrow.parquet as pq
import pyarrow as pa
import pandas as pd
import polars as pl

logger = logging.getLogger(__name__)

class CacheManager:
    """缓存管理器 - 优雅的缓存策略"""

    def __init__(self, cache_dir: str = "../cache", default_ttl: int = 86400):
        self.cache_dir = cache_dir
        self.default_ttl = default_ttl
        os.makedirs(cache_dir, exist_ok=True)

    def _get_cache_path(self, key: str) -> str:
        """获取缓存文件路径"""
        # 使用哈希避免文件名过长的问题
        hash_key = hashlib.md5(key.encode('utf-8')).hexdigest()
        return os.path.join(self.cache_dir, f"{hash_key}.parquet")

    def _is_expired(self, file_path: str, ttl: int) -> bool:
        """检查缓存是否过期"""
        if not os.path.exists(file_path):
            return True

        # 检查修改时间
        mtime = os.path.getmtime(file_path)
        return (time.time() - mtime) > ttl

    def get(self, key: str, ttl: Optional[int] = None) -> Optional[Any]:
        """获取缓存数据"""
        if ttl is None:
            ttl = self.default_ttl

        cache_path = self._get_cache_path(key)

        if self._is_expired(cache_path, ttl):
            logger.debug(f"Cache miss (expired) for key: {key}")
            return None

        try:
            # 读取 Parquet 文件使用Polars
            df = pl.read_parquet(cache_path)
            logger.debug(f"Cache hit for key: {key}")
            return df.to_dicts()
        except Exception as e:
            logger.warning(f"Error reading cache for key {key}: {str(e)}")
            return None

    def set(self, key: str, data: Any, ttl: Optional[int] = None) -> bool:
        """设置缓存数据"""
        if ttl is None:
            ttl = self.default_ttl

        cache_path = self._get_cache_path(key)
        # 使用临时文件确保写入原子性，防止并发写入导致文件损坏
        temp_path = cache_path + f".tmp.{os.getpid()}.{threading.get_ident()}"

        try:
            # 将数据转换为 Polars DataFrame 以便保存为 Parquet
            if isinstance(data, list) and len(data) > 0:
                df = pl.DataFrame(data)
                df.write_parquet(temp_path)
            elif isinstance(data, pd.DataFrame):
                # 如果是pandas DataFrame，转换为Polars
                df = pl.from_pandas(data)
                df.write_parquet(temp_path)
            elif isinstance(data, pl.DataFrame):
                # 如果已经是Polars DataFrame
                data.write_parquet(temp_path)
            else:
                # 如果数据不能转换为 DataFrame，我们仍然需要处理
                logger.warning(f"Cannot cache data of type {type(data)} for key {key}")
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return False

            # 原子重命名
            os.replace(temp_path, cache_path)
            logger.debug(f"Cache set for key: {key}")
            return True
        except Exception as e:
            logger.error(f"Error setting cache for key {key}: {str(e)}")
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            return False

    def get_stock_list(self):
        """获取股票列表缓存"""
        return self.get("stock_list")

    def set_stock_list(self, stock_list):
        """设置股票列表缓存"""
        self.set("stock_list", stock_list, ttl=86400)  # 24小时缓存

    def get_trade_calendar(self, start_date, end_date):
        """获取交易日历缓存"""
        cache_key = f"calendar_{start_date}_{end_date}"
        return self.get(cache_key)

    def set_trade_calendar(self, start_date, end_date, calendar):
        """设置交易日历缓存"""
        cache_key = f"calendar_{start_date}_{end_date}"
        self.set(cache_key, calendar, ttl=86400)  # 24小时缓存

    def delete(self, key: str) -> bool:
        """删除缓存"""
        cache_path = self._get_cache_path(key)

        try:
            if os.path.exists(cache_path):
                os.remove(cache_path)
                logger.debug(f"Cache deleted for key: {key}")
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting cache for key {key}: {str(e)}")
            return False

    def clear_expired(self) -> int:
        """清理过期缓存"""
        count = 0
        for filename in os.listdir(self.cache_dir):
            if filename.endswith('.parquet'):
                file_path = os.path.join(self.cache_dir, filename)
                # 尝试从文件名逆向生成可能的 key 或使用通用 TTL
                if self._is_expired(file_path, self.default_ttl):
                    try:
                        os.remove(file_path)
                        count += 1
                    except Exception as e:
                        logger.error(f"Error removing expired cache file {file_path}: {str(e)}")

        logger.info(f"Cleaned {count} expired cache files")
        return count

    def get_cache_info(self) -> dict:
        """获取缓存信息"""
        files = [f for f in os.listdir(self.cache_dir) if f.endswith('.parquet')]
        total_size = sum(os.path.getsize(os.path.join(self.cache_dir, f)) for f in files)
        return {
            'total_files': len(files),
            'total_size_bytes': total_size,
            'cache_dir': self.cache_dir
        }