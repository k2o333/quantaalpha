"""
存储工作者
实现数据存储的消费者逻辑，线程安全的数据写入，错误处理和重试机制
"""
import threading
import queue
import time
import logging
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from pathlib import Path
import pandas as pd
from datetime import datetime
import json

from data_storage import save_to_parquet
from error_handler import ErrorHandler


@dataclass
class StorageTask:
    """
    存储任务数据类
    """
    data: pd.DataFrame
    filename: str
    subdir: str = "default"
    callback: Optional[Callable] = None  # 完成后回调函数
    task_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None  # 额外元数据
    retry_count: int = 0
    max_retries: int = 3


class StorageWorker:
    """
    存储工作者，处理数据存储的消费者逻辑
    """

    def __init__(self,
                 max_workers: int = 1,
                 queue_size: int = 100,
                 storage_path: str = "data"):
        """
        初始化存储工作者

        Args:
            max_workers: 最大工作线程数
            queue_size: 任务队列大小
            storage_path: 存储路径
        """
        self.max_workers = max_workers
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)

        self.task_queue = queue.Queue(maxsize=queue_size)
        self.workers = []
        self.shutdown_event = threading.Event()
        self.logger = logging.getLogger(__name__)

        # 统计信息
        self.stats_lock = threading.Lock()
        self.stats = {
            'processed_tasks': 0,
            'failed_tasks': 0,
            'total_size': 0,
            'start_time': time.time()
        }

        self._start_workers()

    def _start_workers(self):
        """
        启动工作线程
        """
        for i in range(self.max_workers):
            worker_thread = threading.Thread(
                target=self._worker_loop,
                name=f"StorageWorker-{i}",
                daemon=True
            )
            worker_thread.start()
            self.workers.append(worker_thread)
            self.logger.info(f"启动存储工作线程: StorageWorker-{i}")

    def _worker_loop(self):
        """
        工作线程主循环
        """
        while not self.shutdown_event.is_set():
            try:
                # 从队列获取任务，带超时
                task = self.task_queue.get(timeout=1.0)

                if task is None:  # 退出信号
                    break

                self._process_task(task)
                self.task_queue.task_done()

            except queue.Empty:
                continue  # 超时继续循环
            except Exception as e:
                self.logger.error(f"工作线程错误: {e}")

        self.logger.info("存储工作线程退出")

    def _process_task(self, task: StorageTask):
        """
        处理单个存储任务

        Args:
            task: 存储任务
        """
        max_retries = task.max_retries
        current_retry = 0

        while current_retry <= max_retries:
            try:
                # 执行存储操作
                file_path = self._save_data(task.data, task.filename, task.subdir)

                # 更新统计信息
                with self.stats_lock:
                    self.stats['processed_tasks'] += 1
                    if not task.data.empty:
                        self.stats['total_size'] += task.data.memory_usage(deep=True).sum()

                self.logger.info(f"成功存储数据: {file_path}, 记录数: {len(task.data)}")

                # 如果有回调函数，执行回调
                if task.callback:
                    try:
                        task.callback(task.task_id, file_path, True)
                    except Exception as e:
                        self.logger.error(f"执行回调函数失败: {e}")

                # 成功后退出重试循环
                return

            except Exception as e:
                current_retry += 1
                self.logger.warning(f"存储任务失败 (尝试 {current_retry}/{max_retries}): {e}")

                if current_retry <= max_retries:
                    # 等待后重试
                    time.sleep(2 ** current_retry)  # 指数退避
                    continue
                else:
                    # 达到最大重试次数
                    self.logger.error(f"存储任务最终失败: {task.filename}")

                    with self.stats_lock:
                        self.stats['failed_tasks'] += 1

                    # 即使失败也执行回调（通知失败）
                    if task.callback:
                        try:
                            task.callback(task.task_id, None, False)
                        except Exception as callback_error:
                            self.logger.error(f"执行失败回调函数失败: {callback_error}")

    def _save_data(self, data: pd.DataFrame, filename: str, subdir: str) -> str:
        """
        保存数据到指定位置

        Args:
            data: 要保存的数据
            filename: 文件名
            subdir: 子目录

        Returns:
            保存的文件路径
        """
        # 确保子目录存在
        subdir_path = self.storage_path / subdir
        subdir_path.mkdir(parents=True, exist_ok=True)

        # 生成带时间戳的文件名（避免冲突）
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')[:-3]  # 包含毫秒
        final_filename = f"{filename}_{timestamp}"

        # 保存为Parquet格式
        file_path = save_to_parquet(data, final_filename, subdir=subdir)

        return file_path

    def submit_task(self, task: StorageTask) -> bool:
        """
        提交存储任务

        Args:
            task: 存储任务

        Returns:
            是否成功提交任务
        """
        if self.shutdown_event.is_set():
            self.logger.warning("存储工作者已关闭，拒绝新任务")
            return False

        try:
            self.task_queue.put(task, timeout=5.0)  # 5秒超时
            self.logger.debug(f"提交存储任务: {task.filename}")
            return True
        except queue.Full:
            self.logger.error(f"存储任务队列已满，无法提交: {task.filename}")
            return False

    def submit_data(self,
                   data: pd.DataFrame,
                   filename: str,
                   subdir: str = "default",
                   callback: Optional[Callable] = None,
                   task_id: Optional[str] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        直接提交数据进行存储

        Args:
            data: 要存储的数据
            filename: 文件名
            subdir: 子目录
            callback: 完成回调
            task_id: 任务ID
            metadata: 元数据

        Returns:
            是否成功提交
        """
        task = StorageTask(
            data=data,
            filename=filename,
            subdir=subdir,
            callback=callback,
            task_id=task_id,
            metadata=metadata
        )
        return self.submit_task(task)

    def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """
        等待所有任务完成

        Args:
            timeout: 超时时间

        Returns:
            是否在超时前完成
        """
        try:
            self.task_queue.join()  # 等待所有任务完成
            return True
        except:
            return False

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息
        """
        with self.stats_lock:
            stats_copy = self.stats.copy()
            stats_copy['active_tasks'] = self.task_queue.qsize()
            stats_copy['uptime'] = time.time() - stats_copy['start_time']
            return stats_copy

    def shutdown(self, wait: bool = True):
        """
        关闭存储工作者

        Args:
            wait: 是否等待当前任务完成
        """
        self.logger.info("正在关闭存储工作者...")
        self.shutdown_event.set()

        # 发送退出信号给所有工作线程
        for _ in range(len(self.workers)):
            try:
                self.task_queue.put(None, timeout=1.0)
            except queue.Full:
                pass  # 队列可能已满，但没关系

        if wait:
            # 等待所有工作线程结束
            for worker in self.workers:
                worker.join(timeout=10.0)  # 10秒超时

        self.logger.info("存储工作者已关闭")

    def is_alive(self) -> bool:
        """
        检查是否还有活跃的工作线程
        """
        return any(worker.is_alive() for worker in self.workers)


class BatchStorageWorker(StorageWorker):
    """
    批量存储工作者，支持批量操作以提高效率
    """

    def __init__(self,
                 max_workers: int = 1,
                 queue_size: int = 100,
                 storage_path: str = "data",
                 batch_size: int = 10,
                 batch_timeout: float = 5.0):
        """
        初始化批量存储工作者

        Args:
            batch_size: 批处理大小
            batch_timeout: 批处理超时时间
        """
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        super().__init__(max_workers, queue_size, storage_path)

    def _worker_loop(self):
        """
        重写工作循环以支持批量处理
        """
        batch = []

        while not self.shutdown_event.is_set():
            try:
                # 等待第一个任务
                try:
                    task = self.task_queue.get(timeout=self.batch_timeout)
                except queue.Empty:
                    # 即使超时也要处理现有的批量
                    if batch:
                        self._process_batch(batch)
                        batch = []
                    continue

                if task is None:  # 退出信号
                    # 处理剩余的批量
                    if batch:
                        self._process_batch(batch)
                    break

                batch.append(task)

                # 收集足够的任务或超时后处理
                while len(batch) < self.batch_size and not self.shutdown_event.is_set():
                    try:
                        additional_task = self.task_queue.get(timeout=self.batch_timeout)
                        if additional_task is None:  # 退出信号
                            break
                        batch.append(additional_task)
                    except queue.Empty:
                        break

                if batch:
                    self._process_batch(batch)
                    batch = []

            except Exception as e:
                self.logger.error(f"批量工作线程错误: {e}")
                # 清空当前批次以避免任务丢失
                batch = []

        # 关闭时处理剩余任务
        if batch:
            self._process_batch(batch)
        self.logger.info("批量存储工作线程退出")

    def _process_batch(self, batch: list):
        """
        处理任务批次
        """
        for task in batch:
            try:
                self._process_task(task)
            finally:
                self.task_queue.task_done()


class StorageWorkerManager:
    """
    存储工作者管理器，提供对多个存储工作者的统一管理
    """

    def __init__(self):
        self.workers: Dict[str, StorageWorker] = {}
        self.logger = logging.getLogger(__name__)

    def create_worker(self,
                     name: str,
                     max_workers: int = 1,
                     queue_size: int = 100,
                     storage_path: str = "data",
                     batch_mode: bool = False) -> StorageWorker:
        """
        创建存储工作者

        Args:
            name: 工作者名称
            max_workers: 最大工作线程数
            queue_size: 队列大小
            storage_path: 存储路径
            batch_mode: 是否启用批量模式

        Returns:
            存储工作者实例
        """
        if batch_mode:
            worker = BatchStorageWorker(max_workers, queue_size, storage_path)
        else:
            worker = StorageWorker(max_workers, queue_size, storage_path)

        self.workers[name] = worker
        self.logger.info(f"创建存储工作者: {name}")
        return worker

    def get_worker(self, name: str) -> Optional[StorageWorker]:
        """
        获取存储工作者
        """
        return self.workers.get(name)

    def submit_to_worker(self,
                        worker_name: str,
                        data: pd.DataFrame,
                        filename: str,
                        subdir: str = "default",
                        callback: Optional[Callable] = None,
                        task_id: Optional[str] = None,
                        metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        向指定的工作者提交任务
        """
        worker = self.get_worker(worker_name)
        if worker:
            return worker.submit_data(data, filename, subdir, callback, task_id, metadata)
        else:
            self.logger.error(f"未找到存储工作者: {worker_name}")
            return False

    def shutdown_all(self, wait: bool = True):
        """
        关闭所有存储工作者
        """
        for name, worker in self.workers.items():
            self.logger.info(f"关闭存储工作者: {name}")
            worker.shutdown(wait)

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有工作者的统计信息
        """
        stats = {}
        for name, worker in self.workers.items():
            stats[name] = worker.get_stats()
        return stats


# 全局存储工作者管理器
_global_storage_manager = StorageWorkerManager()


def get_storage_manager() -> StorageWorkerManager:
    """
    获取全局存储管理器
    """
    return _global_storage_manager


def get_default_storage_worker() -> StorageWorker:
    """
    获取默认存储工作者
    """
    manager = get_storage_manager()
    worker = manager.get_worker("default")
    if worker is None:
        # 如果不存在默认工作者，创建一个
        worker = manager.create_worker("default", max_workers=2)
    return worker


def submit_data_to_storage(data: pd.DataFrame,
                          filename: str,
                          subdir: str = "default",
                          callback: Optional[Callable] = None,
                          task_id: Optional[str] = None) -> bool:
    """
    向默认存储工作者提交数据
    """
    worker = get_default_storage_worker()
    return worker.submit_data(data, filename, subdir, callback, task_id)


def wait_for_storage_completion(timeout: Optional[float] = None) -> bool:
    """
    等待默认存储工作者完成所有任务
    """
    worker = get_default_storage_worker()
    return worker.wait_for_completion(timeout)


def get_storage_stats() -> Dict[str, Any]:
    """
    获取存储工作者统计信息
    """
    worker = get_default_storage_worker()
    return worker.get_stats()


def shutdown_storage_worker():
    """
    关闭默认存储工作者
    """
    manager = get_storage_manager()
    manager.shutdown_all()