"""
并行下载器
实现基本的并行下载框架，集成策略模式，处理并发控制和资源管理
"""
from typing import Dict, Any, List, Tuple, Callable
import pandas as pd
import logging
from datetime import datetime
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Semaphore, Lock
from tushare_api import TuShareDownloader
# We import inside the functions to avoid circular import issues
from config_adapter import get_interface_concurrency, get_interface_rate_limit
from data_storage import save_to_parquet


class ParallelDownloader:
    """
    并行下载器，支持多个接口的并发下载
    """

    def __init__(self, max_workers: int = None, downloader: TuShareDownloader = None):
        """
        初始化并行下载器

        Args:
            max_workers: 最大工作线程数
            downloader: TuShareDownloader实例
        """
        self.max_workers = max_workers
        self.downloader = downloader or TuShareDownloader()
        self.interface_semaphores = {}
        self.interface_results = {}
        self.download_lock = Lock()
        self.logger = logging.getLogger(__name__)

    def _get_interface_semaphore(self, interface_name: str) -> Semaphore:
        """
        获取接口的信号量，用于控制并发数
        """
        if interface_name not in self.interface_semaphores:
            concurrency = get_interface_concurrency(interface_name)
            self.interface_semaphores[interface_name] = Semaphore(concurrency)
            self.logger.info(f"为接口 {interface_name} 创建信号量，最大并发数: {concurrency}")

        return self.interface_semaphores[interface_name]

    def _download_single_task(self, interface_name: str, task_params: Dict[str, Any]) -> Tuple[str, Dict[str, Any], pd.DataFrame]:
        """
        下载单个任务

        Args:
            interface_name: 接口名称
            task_params: 任务参数

        Returns:
            (interface_name, task_params, result_dataframe)
        """
        # 获取接口信号量
        semaphore = self._get_interface_semaphore(interface_name)

        with semaphore:  # 控制并发数
            try:
                # 获取对应的下载策略（延迟导入避免循环依赖）
                from download_strategies import get_strategy
                strategy = get_strategy(interface_name, downloader=self.downloader)

                # 应用速率限制
                rate_limit = get_interface_rate_limit(interface_name)
                time.sleep(1.0 / rate_limit)  # 简单的速率限制

                # 验证并适配参数
                adapted_params = strategy.validate_and_adapt_params(task_params)

                # 执行下载
                result_df = strategy.download_with_cache(**adapted_params)

                # 记录下载信息
                record_count = len(result_df) if result_df is not None else 0
                self.logger.info(f"✅ {interface_name} 下载完成: {record_count} 条记录")

                return (interface_name, task_params, result_df)

            except Exception as e:
                self.logger.error(f"❌ {interface_name} 下载失败: {e}")
                return (interface_name, task_params, pd.DataFrame())

    def download_interfaces_parallel(self,
                                   interface_configs: Dict[str, Dict[str, Any]],
                                   shared_params: Dict[str, Any] = None) -> Dict[str, pd.DataFrame]:
        """
        并行下载多个接口的数据

        Args:
            interface_configs: 接口配置字典，格式为 {interface_name: params_dict}
            shared_params: 所有接口共享的参数（如日期范围等）

        Returns:
            接口名称到结果DataFrame的映射
        """
        if not interface_configs:
            self.logger.warning("没有配置的接口需要下载")
            return {}

        # 确定最大工作线程数
        if self.max_workers is None:
            # 根据所有接口的最高并发数来确定总工作线程数
            from config_adapter import get_all_available_interfaces, DataTypePriority
            available_interfaces = get_all_available_interfaces()
            total_concurrency = sum(
                config.concurrency
                for config in available_interfaces.values()
            )
            self.max_workers = max(4, min(total_concurrency, 32))  # 限制在合理范围内

        self.logger.info(f"开始并行下载 {len(interface_configs)} 个接口，最大工作线程数: {self.max_workers}")
        results = {}

        # 准备下载任务
        download_tasks = []
        for interface_name, interface_params in interface_configs.items():
            # 检查接口是否启用且对当前用户可用
            from config_adapter import config_adapter
            if not config_adapter.interface_available_for_user(interface_name):
                self.logger.info(f"接口 {interface_name} 对当前用户不可用，跳过下载")
                continue

            # 合并共享参数和接口特定参数
            final_params = {}
            if shared_params:
                final_params.update(shared_params)
            if interface_params:
                final_params.update(interface_params)

            download_tasks.append((interface_name, final_params))

        # 使用线程池并行下载
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有下载任务
            future_to_task = {
                executor.submit(self._download_single_task, interface_name, params): (interface_name, params)
                for interface_name, params in download_tasks
            }

            # 收集结果
            for future in as_completed(future_to_task):
                interface_name, params = future_to_task[future]
                try:
                    _, _, result_df = future.result()
                    results[interface_name] = result_df
                except Exception as e:
                    self.logger.error(f"处理 {interface_name} 结果时出错: {e}")
                    results[interface_name] = pd.DataFrame()

        self.logger.info(f"并行下载完成，共处理 {len(results)} 个接口")
        return results

    def download_interface_batches(self,
                                  interface_name: str,
                                  batch_params_list: List[Dict[str, Any]]) -> Dict[str, pd.DataFrame]:
        """
        对单个接口进行批处理下载

        Args:
            interface_name: 接口名称
            batch_params_list: 批处理参数列表

        Returns:
            批处理标识到结果DataFrame的映射
        """
        if not batch_params_list:
            self.logger.warning(f"接口 {interface_name} 没有批处理参数")
            return {}

        # 获取接口的最大并发数
        max_concurrency = get_interface_concurrency(interface_name)

        self.logger.info(f"开始批处理下载接口 {interface_name}，共 {len(batch_params_list)} 个任务，最大并发数: {max_concurrency}")
        results = {}

        # 使用线程池进行批处理下载
        with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
            # 提交所有批处理任务
            future_to_batch_id = {}
            for i, params in enumerate(batch_params_list):
                batch_id = f"{interface_name}_batch_{i}"
                future = executor.submit(self._download_single_task, interface_name, params)
                future_to_batch_id[future] = batch_id

            # 收集结果
            for future in as_completed(future_to_batch_id):
                batch_id = future_to_batch_id[future]
                try:
                    _, _, result_df = future.result()
                    results[batch_id] = result_df
                except Exception as e:
                    self.logger.error(f"处理批处理 {batch_id} 结果时出错: {e}")
                    results[batch_id] = pd.DataFrame()

        self.logger.info(f"接口 {interface_name} 批处理下载完成，共处理 {len(results)} 个批处理任务")
        return results

    def download_with_callback(self,
                              interface_configs: Dict[str, Dict[str, Any]],
                              callback: Callable[[str, pd.DataFrame], None] = None,
                              shared_params: Dict[str, Any] = None) -> Dict[str, pd.DataFrame]:
        """
        并行下载并支持回调函数处理结果

        Args:
            interface_configs: 接口配置字典
            callback: 回调函数，接受接口名和结果DataFrame作为参数
            shared_params: 共享参数

        Returns:
            接口名称到结果DataFrame的映射
        """
        # 执行并行下载
        results = self.download_interfaces_parallel(interface_configs, shared_params)

        # 如果提供了回调函数，则处理每个结果
        if callback:
            for interface_name, result_df in results.items():
                try:
                    callback(interface_name, result_df)
                except Exception as e:
                    self.logger.error(f"执行回调函数处理 {interface_name} 结果时出错: {e}")
        return results

    def get_download_progress(self) -> Dict[str, int]:
        """
        获取下载进度统计

        Returns:
            接口名称到记录数的映射
        """
        progress = {}
        with self.download_lock:
            for interface_name, df in self.interface_results.items():
                progress[interface_name] = len(df) if df is not None else 0
        return progress

    def save_results(self, results: Dict[str, pd.DataFrame], base_subdir: str = "parallel") -> Dict[str, str]:
        """
        保存下载结果到Parquet文件

        Args:
            results: 接口名称到结果DataFrame的映射
            base_subdir: 基础子目录

        Returns:
            接口名称到文件路径的映射
        """
        saved_files = {}

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        for interface_name, df in results.items():
            if df is not None and not df.empty:
                try:
                    subdir = f"{base_subdir}/{interface_name}"
                    filename = f"{interface_name}_{timestamp}"
                    file_path = save_to_parquet(df, filename, subdir=subdir)
                    saved_files[interface_name] = file_path
                    self.logger.info(f"保存 {interface_name} 数据到: {file_path}")
                except Exception as e:
                    self.logger.error(f"保存 {interface_name} 数据失败: {e}")
            else:
                self.logger.info(f"接口 {interface_name} 无数据需要保存")

        return saved_files

    def clear_results(self):
        """
        清除下载结果缓存
        """
        with self.download_lock:
            self.interface_results.clear()
        self.logger.info("下载结果缓存已清除")


class ConcurrentDownloadManager:
    """
    并发下载管理器，提供更高级的并发控制功能
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.active_downloads = {}
        self.download_lock = Lock()

    def schedule_download(self,
                          downloader: ParallelDownloader,
                          interface_configs: Dict[str, Dict[str, Any]],
                          shared_params: Dict[str, Any] = None,
                          priority: int = 0) -> str:
        """
        安排下载任务

        Args:
            downloader: 并行下载器实例
            interface_configs: 接口配置
            shared_params: 共享参数
            priority: 优先级

        Returns:
            任务ID
        """
        task_id = f"task_{int(time.time() * 1000000)}"
        with self.download_lock:
            self.active_downloads[task_id] = {
                'downloader': downloader,
                'configs': interface_configs,
                'shared_params': shared_params,
                'priority': priority,
                'status': 'scheduled',
                'start_time': None,
                'end_time': None
            }

        self.logger.info(f"安排下载任务 {task_id}，优先级: {priority}")
        return task_id

    def execute_download(self, task_id: str) -> Dict[str, pd.DataFrame]:
        """
        执行指定的下载任务

        Args:
            task_id: 任务ID

        Returns:
            下载结果
        """
        with self.download_lock:
            if task_id not in self.active_downloads:
                raise ValueError(f"未找到下载任务: {task_id}")
            task_info = self.active_downloads[task_id]
            task_info['status'] = 'running'
            task_info['start_time'] = datetime.now()

        try:
            downloader = task_info['downloader']
            configs = task_info['configs']
            shared_params = task_info['shared_params']

            results = downloader.download_interfaces_parallel(configs, shared_params)

            with self.download_lock:
                task_info['status'] = 'completed'
                task_info['end_time'] = datetime.now()
                task_info['results'] = results

            self.logger.info(f"下载任务 {task_id} 完成")
            return results

        except Exception as e:
            with self.download_lock:
                task_info['status'] = 'failed'
                task_info['end_time'] = datetime.now()
                task_info['error'] = str(e)

            self.logger.error(f"下载任务 {task_id} 失败: {e}")
            raise

    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            任务状态信息
        """
        with self.download_lock:
            if task_id not in self.active_downloads:
                return {'status': 'not_found'}

            return self.active_downloads[task_id].copy()


# 全局并发管理器实例
_global_concurrent_manager = ConcurrentDownloadManager()


def get_concurrent_manager() -> ConcurrentDownloadManager:
    """
    获取全局并发管理器实例
    """
    return _global_concurrent_manager


def create_parallel_downloader(max_workers: int = None) -> ParallelDownloader:
    """
    创建并行下载器实例

    Args:
        max_workers: 最大工作线程数

    Returns:
        ParallelDownloader实例
    """
    return ParallelDownloader(max_workers)


def schedule_and_execute_download(interface_configs: Dict[str, Dict[str, Any]],
                                 shared_params: Dict[str, Any] = None,
                                 priority: int = 0) -> Dict[str, pd.DataFrame]:
    """
    安排并执行下载任务

    Args:
        interface_configs: 接口配置
        shared_params: 共享参数
        priority: 优先级

    Returns:
        下载结果
    """
    downloader = create_parallel_downloader()
    manager = get_concurrent_manager()

    task_id = manager.schedule_download(downloader, interface_configs, shared_params, priority)
    return manager.execute_download(task_id)