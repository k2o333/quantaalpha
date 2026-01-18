"""
统一异步下载管理器
整合所有下载模式，实现异步下载和异步存储
"""
import threading
import time
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

from tushare_api import TuShareDownloader
from storage_worker import StorageWorker, StorageTask, submit_data_to_storage
from global_rate_limiter import acquire_tokens
from config_adapter import get_interface_concurrency, get_interface_rate_limit


class AsyncDownloadManager:
    """
    统一异步下载管理器
    支持所有下载模式的异步处理
    """

    def __init__(self,
                 max_download_workers: int = 8,
                 max_storage_workers: int = 2,
                 storage_queue_size: int = 100):
        """
        初始化异步下载管理器

        Args:
            max_download_workers: 最大下载工作线程数
            max_storage_workers: 最大存储工作线程数
            storage_queue_size: 存储队列大小
        """
        self.max_download_workers = max_download_workers
        self.downloader = TuShareDownloader()
        self.storage_worker = StorageWorker(
            max_workers=max_storage_workers,
            queue_size=storage_queue_size
        )
        self.logger = logging.getLogger(__name__)

        # 统计信息
        self.stats_lock = threading.Lock()
        self.stats = {
            'total_downloaded': 0,
            'total_stored': 0,
            'active_downloads': 0,
            'active_storages': 0,
            'failed_downloads': 0,
            'failed_storages': 0,
            'start_time': time.time()
        }

        # 完成事件
        self.completion_event = threading.Event()

    def download_holders_data(self,
                             interfaces: List[str],
                             stock_list: pd.DataFrame,
                             start_date: str = None,
                             end_date: str = None) -> Dict[str, Any]:
        """
        异步下载股东相关数据

        Args:
            interfaces: 接口列表，如 ['stk_rewards', 'top10_holders', 'pledge_detail', 'fina_audit']
            stock_list: 股票列表 DataFrame
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）

        Returns:
            下载结果统计
        """
        self.logger.info(f"开始异步下载股东数据: {interfaces}")

        results = {}
        stock_codes = stock_list['ts_code'].tolist()

        # 为每个接口创建下载任务
        for interface_name in interfaces:
            self.logger.info(f"调度接口 {interface_name} 的下载任务")

            # 使用线程池并发下载
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = {
                    executor.submit(
                        self._download_single_stock_data,
                        interface_name,
                        ts_code,
                        start_date,
                        end_date
                    ): ts_code
                    for ts_code in stock_codes
                }

                # 收集结果
                interface_data = []
                for future in as_completed(futures):
                    ts_code = futures[future]
                    try:
                        df = future.result()
                        if df is not None and not df.empty:
                            interface_data.append(df)
                            with self.stats_lock:
                                self.stats['total_downloaded'] += len(df)
                    except Exception as e:
                        self.logger.error(f"下载 {interface_name} - {ts_code} 失败: {e}")
                        with self.stats_lock:
                            self.stats['failed_downloads'] += 1

                # 合并数据并提交存储
                if interface_data:
                    combined_df = pd.concat(interface_data, ignore_index=True)
                    filename = f"{interface_name}_full_history"
                    subdir = "holders"

                    self.storage_worker.submit_data(
                        data=combined_df,
                        filename=filename,
                        subdir=subdir,
                        callback=self._storage_callback,
                        task_id=interface_name
                    )

                    results[interface_name] = len(combined_df)
                    self.logger.info(f"接口 {interface_name} 下载完成: {len(combined_df)} 条记录")

        return results

    def download_pro_bar(self,
                        stock_list: pd.DataFrame,
                        start_date: str = None,
                        end_date: str = None) -> Dict[str, Any]:
        """
        异步下载复权行情数据

        Args:
            stock_list: 股票列表 DataFrame
            start_date: 开始日期（可选）
            end_date: 结束日期（可选）

        Returns:
            下载结果统计
        """
        self.logger.info("开始异步下载复权行情数据")

        stock_codes = stock_list['ts_code'].tolist()
        all_data = []

        # 使用线程池并发下载
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(
                    self._download_pro_bar_single_stock,
                    ts_code,
                    start_date,
                    end_date
                ): ts_code
                for ts_code in stock_codes
            }

            # 收集结果
            for future in as_completed(futures):
                ts_code = futures[future]
                try:
                    df = future.result()
                    if df is not None and not df.empty:
                        all_data.append(df)
                        with self.stats_lock:
                            self.stats['total_downloaded'] += len(df)
                except Exception as e:
                    self.logger.error(f"下载 pro_bar - {ts_code} 失败: {e}")
                    with self.stats_lock:
                        self.stats['failed_downloads'] += 1

        # 合并数据并提交存储
        results = {}
        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)
            filename = "pro_bar_full_history"
            subdir = "daily"

            self.storage_worker.submit_data(
                data=combined_df,
                filename=filename,
                subdir=subdir,
                callback=self._storage_callback,
                task_id="pro_bar"
            )

            results['pro_bar'] = len(combined_df)
            self.logger.info(f"复权行情下载完成: {len(combined_df)} 条记录")

        return results

    def download_with_legacy(self,
                            start_date: str,
                            end_date: str = None) -> Dict[str, Any]:
        """
        使用传统方式异步下载（改造版）

        Args:
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            下载结果统计
        """
        self.logger.info(f"开始异步下载日期范围数据: {start_date} - {end_date}")

        if end_date is None:
            end_date = datetime.now().strftime('%Y%m%d')

        # 使用现有的 download_scheduler，但确保使用异步存储
        from download_scheduler import DownloadScheduler
        scheduler = DownloadScheduler(start_date, end_date, max_workers=8)

        # 调度下载任务
        scheduler.schedule_download_tasks()

        # 执行下载任务（内部会使用异步存储）
        results = scheduler.execute_scheduled_tasks()

        # 等待所有存储完成
        self.wait_for_completion()

        return results

    def _download_single_stock_data(self,
                                    interface_name: str,
                                    ts_code: str,
                                    start_date: str = None,
                                    end_date: str = None) -> pd.DataFrame:
        """
        下载单个股票的数据

        Args:
            interface_name: 接口名称
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            下载的数据
        """
        try:
            # 申请速率限制令牌
            if not acquire_tokens(interface_name, 1.0, timeout=300):
                raise Exception(f"无法获取 {interface_name} 的速率限制令牌")

            # 根据接口类型调用相应的下载方法
            if interface_name == 'stk_rewards':
                from interfaces.holders_data import HoldersDataDownloader
                downloader = HoldersDataDownloader(self.downloader.pro)
                df = downloader.download_stk_rewards(ts_code)
            elif interface_name == 'top10_holders':
                from interfaces.holders_data import HoldersDataDownloader
                downloader = HoldersDataDownloader(self.downloader.pro)
                df = downloader.download_top10_holders(ts_code)
            elif interface_name == 'pledge_detail':
                from interfaces.holders_data import HoldersDataDownloader
                downloader = HoldersDataDownloader(self.downloader.pro)
                df = downloader.download_pledge_detail(ts_code)
            elif interface_name == 'fina_audit':
                from interfaces.financial_data import FinancialDataDownloader
                downloader = FinancialDataDownloader(self.downloader.pro)
                df = downloader.download_fina_audit(ts_code=ts_code)
            else:
                self.logger.warning(f"未知的接口: {interface_name}")
                return pd.DataFrame()

            return df

        except Exception as e:
            self.logger.error(f"下载 {interface_name} - {ts_code} 失败: {e}")
            return pd.DataFrame()

    def _download_pro_bar_single_stock(self,
                                      ts_code: str,
                                      start_date: str = None,
                                      end_date: str = None) -> pd.DataFrame:
        """
        下载单个股票的复权行情数据

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            下载的数据
        """
        try:
            # 申请速率限制令牌
            if not acquire_tokens('pro_bar', 1.0, timeout=300):
                raise Exception("无法获取 pro_bar 的速率限制令牌")

            from interfaces.daily_data import DailyDataDownloader
            downloader = DailyDataDownloader(self.downloader.pro)
            df = downloader.download_pro_bar_full_history(ts_code)

            return df

        except Exception as e:
            self.logger.error(f"下载 pro_bar - {ts_code} 失败: {e}")
            return pd.DataFrame()

    def _storage_callback(self,
                         task_id: str,
                         file_path: str,
                         success: bool):
        """
        存储回调函数

        Args:
            task_id: 任务ID
            file_path: 文件路径
            success: 是否成功
        """
        if success:
            with self.stats_lock:
                self.stats['total_stored'] += 1
            self.logger.info(f"存储任务 {task_id} 完成: {file_path}")
        else:
            with self.stats_lock:
                self.stats['failed_storages'] += 1
            self.logger.error(f"存储任务 {task_id} 失败")

    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """
        等待所有任务完成

        Args:
            timeout: 超时时间（秒）

        Returns:
            是否在超时前完成
        """
        try:
            # 等待存储队列清空
            result = self.storage_worker.wait_for_completion(timeout=timeout)

            if result:
                self.completion_event.set()
                self.logger.info("所有任务已完成")

            return result
        except Exception as e:
            self.logger.error(f"等待任务完成时出错: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            统计信息字典
        """
        with self.stats_lock:
            stats_copy = self.stats.copy()
            stats_copy['elapsed_time'] = time.time() - stats_copy['start_time']
            stats_copy['storage_queue_size'] = self.storage_worker.task_queue.qsize()
            return stats_copy

    def shutdown(self, wait: bool = True):
        """
        关闭下载管理器

        Args:
            wait: 是否等待当前任务完成
        """
        self.logger.info("正在关闭异步下载管理器...")
        self.storage_worker.shutdown(wait=wait)
        self.logger.info("异步下载管理器已关闭")


def create_async_download_manager(max_download_workers: int = 8,
                                 max_storage_workers: int = 2,
                                 storage_queue_size: int = 100) -> AsyncDownloadManager:
    """
    创建异步下载管理器实例

    Args:
        max_download_workers: 最大下载工作线程数
        max_storage_workers: 最大存储工作线程数
        storage_queue_size: 存储队列大小

    Returns:
        AsyncDownloadManager 实例
    """
    return AsyncDownloadManager(
        max_download_workers=max_download_workers,
        max_storage_workers=max_storage_workers,
        storage_queue_size=storage_queue_size
    )
