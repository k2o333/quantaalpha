"""
缓存监控模块 - 跟踪缓存命中率和性能
"""
import time
from datetime import datetime
import json
from pathlib import Path
import logging

class CacheMonitor:
    """
    缓存监控器，跟踪缓存命中率和性能指标
    """

    def __init__(self):
        self.cache_hits = 0
        self.cache_misses = 0
        self.download_count = 0
        self.start_time = time.time()
        self.logger = logging.getLogger(__name__)
        self.stats_file = Path(__file__).parent.parent / 'log' / 'cache_stats.json'

    def record_cache_hit(self, interface_name: str):
        """
        记录缓存命中
        """
        self.cache_hits += 1
        self.logger.info(f"缓存命中: {interface_name}")

    def record_cache_miss(self, interface_name: str):
        """
        记录缓存未命中
        """
        self.cache_misses += 1
        self.logger.info(f"缓存未命中: {interface_name}")

    def record_download(self, interface_name: str, record_count: int):
        """
        记录下载操作
        """
        self.download_count += 1
        self.logger.info(f"执行下载: {interface_name}, 记录数: {record_count}")

    def get_hit_rate(self) -> float:
        """
        计算缓存命中率
        """
        total_requests = self.cache_hits + self.cache_misses
        if total_requests == 0:
            return 0.0
        return self.cache_hits / total_requests

    def get_stats(self) -> dict:
        """
        获取缓存统计信息
        """
        total_requests = self.cache_hits + self.cache_misses
        uptime = time.time() - self.start_time

        stats = {
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'total_requests': total_requests,
            'hit_rate': self.get_hit_rate(),
            'download_count': self.download_count,
            'uptime_seconds': uptime,
            'requests_per_minute': (total_requests / uptime * 60) if uptime > 0 else 0,
            'timestamp': datetime.now().isoformat()
        }

        return stats

    def save_stats(self):
        """
        保存统计信息到文件
        """
        stats = self.get_stats()
        with open(self.stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)

    def load_stats(self):
        """
        从文件加载统计信息
        """
        if self.stats_file.exists():
            with open(self.stats_file, 'r', encoding='utf-8') as f:
                stats = json.load(f)
                self.cache_hits = stats.get('cache_hits', 0)
                self.cache_misses = stats.get('cache_misses', 0)
                self.download_count = stats.get('download_count', 0)
                self.start_time = time.time() - stats.get('uptime_seconds', 0)


# 全局缓存监控器实例
cache_monitor = CacheMonitor()


def get_cache_monitor() -> CacheMonitor:
    """
    获取全局缓存监控器实例
    """
    return cache_monitor


def record_cache_hit(interface_name: str):
    """
    记录缓存命中
    """
    monitor = get_cache_monitor()
    monitor.record_cache_hit(interface_name)


def record_cache_miss(interface_name: str):
    """
    记录缓存未命中
    """
    monitor = get_cache_monitor()
    monitor.record_cache_miss(interface_name)


def record_download(interface_name: str, record_count: int):
    """
    记录下载操作
    """
    monitor = get_cache_monitor()
    monitor.record_download(interface_name, record_count)


def get_cache_hit_rate() -> float:
    """
    获取缓存命中率
    """
    monitor = get_cache_monitor()
    return monitor.get_hit_rate()


def get_cache_monitor_stats() -> dict:
    """
    获取缓存监控统计
    """
    monitor = get_cache_monitor()
    return monitor.get_stats()


def save_cache_monitor_stats():
    """
    保存缓存监控统计
    """
    monitor = get_cache_monitor()
    monitor.save_stats()


def load_cache_monitor_stats():
    """
    加载缓存监控统计
    """
    monitor = get_cache_monitor()
    monitor.load_stats()