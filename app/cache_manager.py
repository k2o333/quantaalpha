"""
缓存管理器 - 实现缓存预热、清理和监控功能
"""
import os
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import logging

class CacheManager:
    """
    缓存管理器，提供缓存预热、清理和监控功能
    """

    def __init__(self):
        self.data_dir = Path(__file__).parent.parent / 'data'
        self.logger = logging.getLogger(__name__)

    def warm_cache(self, interfaces: list, date_range: tuple = None):
        """
        预热缓存 - 提前下载常用数据
        """
        from download_scheduler import DownloadScheduler

        if not date_range:
            # 使用最近一个月的数据作为默认预热范围
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
        else:
            start_date, end_date = date_range

        scheduler = DownloadScheduler(start_date, end_date)
        scheduler.schedule_download_tasks(interfaces)
        scheduler.execute_scheduled_tasks(wait_for_completion=True)

    def clean_expired_cache(self, max_age_hours: int = 168):  # 默认保留7天内的缓存
        """
        清理过期缓存文件
        """
        current_time = datetime.now().timestamp()
        cleaned_count = 0

        for root, dirs, files in os.walk(self.data_dir):
            for file in files:
                if file.endswith('.parquet'):
                    file_path = Path(root) / file
                    file_mtime = file_path.stat().st_mtime
                    age_hours = (current_time - file_mtime) / 3600

                    if age_hours > max_age_hours:
                        try:
                            file_path.unlink()
                            self.logger.info(f"删除过期缓存: {file_path}, 年龄: {age_hours:.2f}小时")
                            cleaned_count += 1
                        except Exception as e:
                            self.logger.error(f"删除缓存文件失败: {file_path}, 错误: {e}")

        self.logger.info(f"缓存清理完成，删除了 {cleaned_count} 个过期文件")
        return cleaned_count

    def get_cache_stats(self):
        """
        获取缓存统计信息
        """
        total_files = 0
        total_size = 0
        daily_cache_count = 0
        financial_cache_count = 0
        static_cache_count = 0

        for root, dirs, files in os.walk(self.data_dir):
            for file in files:
                if file.endswith('.parquet'):
                    file_path = Path(root) / file
                    total_files += 1
                    total_size += file_path.stat().st_size

                    # 统计不同类型缓存
                    if 'daily' in str(file_path):
                        daily_cache_count += 1
                    elif 'financial' in str(file_path):
                        financial_cache_count += 1
                    elif 'static' in str(file_path):
                        static_cache_count += 1

        return {
            'total_cache_files': total_files,
            'total_cache_size_mb': total_size / (1024 * 1024),
            'daily_cache_count': daily_cache_count,
            'financial_cache_count': financial_cache_count,
            'static_cache_count': static_cache_count,
            'last_updated': datetime.now().isoformat()
        }

    def validate_cache_integrity(self):
        """
        验证缓存文件完整性
        """
        corrupted_files = []

        for root, dirs, files in os.walk(self.data_dir):
            for file in files:
                if file.endswith('.parquet'):
                    file_path = Path(root) / file
                    try:
                        # 尝试读取文件验证完整性
                        df = pd.read_parquet(file_path)
                        if df is None or df.empty:
                            corrupted_files.append(str(file_path))
                    except Exception as e:
                        self.logger.warning(f"缓存文件损坏: {file_path}, 错误: {e}")
                        corrupted_files.append(str(file_path))

        return corrupted_files


# 全局缓存管理器实例
cache_manager = CacheManager()


def get_cache_manager() -> CacheManager:
    """
    获取全局缓存管理器实例
    """
    return cache_manager


def clean_cache(max_age_hours: int = 168):
    """
    清理过期缓存
    """
    manager = get_cache_manager()
    return manager.clean_expired_cache(max_age_hours)


def get_cache_statistics():
    """
    获取缓存统计信息
    """
    manager = get_cache_manager()
    return manager.get_cache_stats()


def validate_cache():
    """
    验证缓存完整性
    """
    manager = get_cache_manager()
    return manager.validate_cache_integrity()