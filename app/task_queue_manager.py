"""
任务队列管理器
管理下载任务队列，任务优先级管理，任务状态跟踪
"""
import queue
import threading
import time
import logging
from typing import Dict, Any, Optional, Callable, List, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import uuid
import heapq
import json


class TaskPriority(Enum):
    """任务优先级枚举"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """任务数据类"""
    task_id: str
    task_type: str  # 任务类型，如 'download', 'storage', 'process' 等
    priority: TaskPriority
    target_func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict = field(default_factory=dict)
    callback: Optional[Callable] = None
    timeout: Optional[float] = None
    retry_count: int = 0
    max_retries: int = 3
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Any = None
    error: Optional[Exception] = None
    status: TaskStatus = TaskStatus.PENDING
    metadata: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)  # 依赖任务ID列表
    wait_for_completion: bool = False  # 是否等待完成

    def __lt__(self, other):
        """用于优先级队列排序，优先级高的任务优先级数值小"""
        return self.priority.value > other.priority.value


class TaskQueueManager:
    """
    任务队列管理器，提供优先级队列、任务状态跟踪等功能
    """

    def __init__(self, max_queue_size: int = 1000):
        """
        初始化任务队列管理器

        Args:
            max_queue_size: 最大队列大小
        """
        self.max_queue_size = max_queue_size
        self.task_queue = queue.PriorityQueue(maxsize=max_queue_size)
        self.tasks: Dict[str, Task] = {}
        self.task_lock = threading.Lock()
        self.logger = logging.getLogger(__name__)
        self.shutdown_event = threading.Event()

        # 统计信息
        self.stats_lock = threading.Lock()
        self.stats = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'pending_tasks': 0,
            'processing_tasks': 0,
            'start_time': time.time()
        }

    def create_task_id(self) -> str:
        """
        创建唯一任务ID
        """
        return str(uuid.uuid4())

    def add_task(self,
                task_type: str,
                target_func: Callable,
                priority: TaskPriority = TaskPriority.MEDIUM,
                args: tuple = None,
                kwargs: dict = None,
                callback: Optional[Callable] = None,
                timeout: Optional[float] = None,
                max_retries: int = 3,
                task_id: Optional[str] = None,
                metadata: Dict[str, Any] = None,
                dependencies: List[str] = None,
                wait_for_completion: bool = False) -> str:
        """
        添加任务到队列

        Args:
            task_type: 任务类型
            target_func: 目标函数
            priority: 任务优先级
            args: 函数参数
            kwargs: 函数关键字参数
            callback: 完成回调函数
            timeout: 超时时间
            max_retries: 最大重试次数
            task_id: 任务ID（如果不提供则自动生成）
            metadata: 任务元数据
            dependencies: 依赖的任务ID列表
            wait_for_completion: 是否等待任务完成

        Returns:
            任务ID
        """
        if args is None:
            args = ()
        if kwargs is None:
            kwargs = {}
        if metadata is None:
            metadata = {}
        if dependencies is None:
            dependencies = []

        # 检查依赖任务是否都已完成
        if dependencies:
            for dep_id in dependencies:
                if dep_id not in self.tasks:
                    self.logger.warning(f"任务依赖的任务不存在: {dep_id}")
                elif self.tasks[dep_id].status != TaskStatus.COMPLETED:
                    self.logger.warning(f"任务依赖的任务尚未完成: {dep_id}")

        task_id = task_id or self.create_task_id()

        task = Task(
            task_id=task_id,
            task_type=task_type,
            priority=priority,
            target_func=target_func,
            args=args,
            kwargs=kwargs,
            callback=callback,
            timeout=timeout,
            max_retries=max_retries,
            metadata=metadata,
            dependencies=dependencies,
            wait_for_completion=wait_for_completion
        )

        with self.task_lock:
            self.tasks[task_id] = task

            # 更新统计
            with self.stats_lock:
                self.stats['total_tasks'] += 1
                self.stats['pending_tasks'] += 1

        try:
            # 将任务添加到优先级队列
            self.task_queue.put((priority.value, task), timeout=5.0)
            task.status = TaskStatus.QUEUED
            self.logger.debug(f"添加任务到队列: {task_id}, 优先级: {priority.name}")
            return task_id
        except queue.Full:
            self.logger.error(f"任务队列已满，无法添加任务: {task_id}")
            task.status = TaskStatus.FAILED
            task.error = Exception("任务队列已满")
            return None

    def get_next_task(self, timeout: float = None) -> Optional[Task]:
        """
        获取下一个任务

        Args:
            timeout: 超时时间

        Returns:
            任务对象或None
        """
        try:
            if timeout is None:
                priority, task = self.task_queue.get_nowait()
            else:
                priority, task = self.task_queue.get(timeout=timeout)

            with self.task_lock:
                # 检查依赖是否都已完成
                if task.dependencies:
                    all_dependencies_completed = True
                    for dep_id in task.dependencies:
                        if dep_id not in self.tasks or self.tasks[dep_id].status != TaskStatus.COMPLETED:
                            all_dependencies_completed = False
                            break

                    if not all_dependencies_completed:
                        # 如果依赖未完成，重新放入队列
                        self.task_queue.put((task.priority.value, task))
                        return None

                task.started_at = datetime.now()
                task.status = TaskStatus.PROCESSING

                with self.stats_lock:
                    self.stats['pending_tasks'] -= 1
                    self.stats['processing_tasks'] += 1

            return task
        except queue.Empty:
            return None

    def complete_task(self, task_id: str, result: Any = None, success: bool = True):
        """
        完成任务

        Args:
            task_id: 任务ID
            result: 任务结果
            success: 是否成功
        """
        with self.task_lock:
            if task_id not in self.tasks:
                self.logger.warning(f"尝试完成不存在的任务: {task_id}")
                return

            task = self.tasks[task_id]
            task.completed_at = datetime.now()
            task.result = result

            if success:
                task.status = TaskStatus.COMPLETED
                self.logger.info(f"任务完成: {task_id}")
            else:
                task.status = TaskStatus.FAILED
                self.logger.warning(f"任务失败: {task_id}")

            # 更新统计
            with self.stats_lock:
                self.stats['processing_tasks'] -= 1
                if success:
                    self.stats['completed_tasks'] += 1
                else:
                    self.stats['failed_tasks'] += 1

            # 执行回调
            if task.callback:
                try:
                    task.callback(task_id, result, success)
                except Exception as e:
                    self.logger.error(f"执行任务回调失败: {e}")

    def retry_task(self, task: Task) -> bool:
        """
        重试任务

        Args:
            task: 任务对象

        Returns:
            是否可以重试
        """
        if task.retry_count < task.max_retries:
            task.retry_count += 1
            task.status = TaskStatus.PENDING  # 重新进入待处理状态

            # 重新加入队列
            try:
                self.task_queue.put((task.priority.value, task), timeout=5.0)
                self.logger.info(f"重试任务: {task.task_id} (第 {task.retry_count} 次)")

                # 更新统计
                with self.stats_lock:
                    self.stats['failed_tasks'] -= 1  # 之前算作失败的要减回去
                    self.stats['processing_tasks'] -= 1 # 之前在处理的要减回去
                    self.stats['pending_tasks'] += 1 # 重新加入待处理

                return True
            except queue.Full:
                self.logger.error(f"重试任务失败，队列已满: {task.task_id}")
                return False
        else:
            self.logger.error(f"任务已达到最大重试次数: {task.task_id}")
            return False

    def cancel_task(self, task_id: str) -> bool:
        """
        取消任务

        Args:
            task_id: 任务ID

        Returns:
            是否成功取消
        """
        with self.task_lock:
            if task_id not in self.tasks:
                return False

            task = self.tasks[task_id]
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                return False  # 已完成的任务不能取消

            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.now()

            with self.stats_lock:
                if task.status == TaskStatus.PENDING:
                    self.stats['pending_tasks'] -= 1
                elif task.status == TaskStatus.PROCESSING:
                    self.stats['processing_tasks'] -= 1

            self.logger.info(f"任务已取消: {task_id}")
            return True

    def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """
        获取任务状态

        Args:
            task_id: 任务ID

        Returns:
            任务状态或None
        """
        with self.task_lock:
            if task_id in self.tasks:
                return self.tasks[task_id].status
            return None

    def get_task_result(self, task_id: str) -> Any:
        """
        获取任务结果

        Args:
            task_id: 任务ID

        Returns:
            任务结果
        """
        with self.task_lock:
            if task_id in self.tasks:
                task = self.tasks[task_id]
                if task.status == TaskStatus.COMPLETED:
                    return task.result
                elif task.status == TaskStatus.FAILED:
                    return task.error
        return None

    def get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务详细信息

        Args:
            task_id: 任务ID

        Returns:
            任务信息字典
        """
        with self.task_lock:
            if task_id not in self.tasks:
                return None

            task = self.tasks[task_id]
            return {
                'task_id': task.task_id,
                'task_type': task.task_type,
                'priority': task.priority.name,
                'status': task.status.name,
                'retry_count': task.retry_count,
                'max_retries': task.max_retries,
                'created_at': task.created_at.isoformat() if task.created_at else None,
                'started_at': task.started_at.isoformat() if task.started_at else None,
                'completed_at': task.completed_at.isoformat() if task.completed_at else None,
                'dependencies': task.dependencies,
                'metadata': task.metadata
            }

    def get_all_tasks(self) -> List[Dict[str, Any]]:
        """
        获取所有任务信息

        Returns:
            任务信息列表
        """
        with self.task_lock:
            tasks_info = []
            for task_id in self.tasks:
                info = self.get_task_info(task_id)
                if info:
                    tasks_info.append(info)
            return tasks_info

    def get_tasks_by_status(self, status: TaskStatus) -> List[str]:
        """
        根据状态获取任务ID列表

        Args:
            status: 任务状态

        Returns:
            任务ID列表
        """
        with self.task_lock:
            task_ids = []
            for task_id, task in self.tasks.items():
                if task.status == status:
                    task_ids.append(task_id)
            return task_ids

    def get_tasks_by_type(self, task_type: str) -> List[str]:
        """
        根据类型获取任务ID列表

        Args:
            task_type: 任务类型

        Returns:
            任务ID列表
        """
        with self.task_lock:
            task_ids = []
            for task_id, task in self.tasks.items():
                if task.task_type == task_type:
                    task_ids.append(task_id)
            return task_ids

    def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息
        """
        with self.stats_lock:
            stats_copy = self.stats.copy()
            stats_copy['queue_size'] = self.task_queue.qsize()
            stats_copy['active_tasks'] = len(self.tasks)
            stats_copy['uptime'] = time.time() - stats_copy['start_time']
            return stats_copy

    def wait_for_task(self, task_id: str, timeout: float = None) -> bool:
        """
        等待任务完成

        Args:
            task_id: 任务ID
            timeout: 超时时间

        Returns:
            任务是否完成
        """
        start_time = time.time()
        while True:
            status = self.get_task_status(task_id)
            if status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                return True

            if timeout and (time.time() - start_time) > timeout:
                return False

            time.sleep(0.1)  # 短暂休眠避免过度占用CPU

    def wait_for_all_tasks(self, timeout: float = None) -> bool:
        """
        等待所有任务完成

        Args:
            timeout: 超时时间

        Returns:
            是否在超时前完成
        """
        start_time = time.time()
        while True:
            with self.task_lock:
                pending_task_ids = [
                    task_id for task_id, task in self.tasks.items()
                    if task.status not in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
                ]

            if not pending_task_ids:
                return True

            if timeout and (time.time() - start_time) > timeout:
                return False

            time.sleep(0.5)  # 短暂休眠

    def clear_completed_tasks(self):
        """
        清除已完成的任务（从内存中移除）
        """
        with self.task_lock:
            completed_task_ids = [
                task_id for task_id, task in self.tasks.items()
                if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]
            ]

            for task_id in completed_task_ids:
                del self.tasks[task_id]

            self.logger.info(f"清除 {len(completed_task_ids)} 个已完成的任务")

    def shutdown(self):
        """
        关闭队列管理器
        """
        self.logger.info("关闭任务队列管理器...")
        self.shutdown_event.set()

        # 等待队列中的任务处理完成
        with self.task_lock:
            pending_task_ids = self.get_tasks_by_status(TaskStatus.PENDING)
            queued_task_ids = self.get_tasks_by_status(TaskStatus.QUEUED)
            processing_task_ids = self.get_tasks_by_status(TaskStatus.PROCESSING)

        # 尝试等待所有任务完成
        all_task_ids = pending_task_ids + queued_task_ids + processing_task_ids
        for task_id in all_task_ids:
            self.wait_for_task(task_id, timeout=5.0)  # 最多等待5秒

        self.logger.info("任务队列管理器已关闭")


class DownloadTaskQueueManager(TaskQueueManager):
    """
    专门用于下载任务的队列管理器
    """

    def __init__(self, max_queue_size: int = 1000):
        super().__init__(max_queue_size)
        self.logger = logging.getLogger(f"{__name__}.download")

    def add_download_task(self,
                         interface_name: str,
                         strategy_func: Callable,
                         start_date: str,
                         end_date: str,
                         priority: TaskPriority = TaskPriority.MEDIUM,
                         max_retries: int = 3,
                         metadata: Dict[str, Any] = None) -> str:
        """
        添加下载任务

        Args:
            interface_name: 接口名称
            strategy_func: 下载策略函数
            start_date: 开始日期
            end_date: 结束日期
            priority: 优先级
            max_retries: 最大重试次数
            metadata: 元数据

        Returns:
            任务ID
        """
        kwargs = {
            'start_date': start_date,
            'end_date': end_date
        }

        if metadata is None:
            metadata = {}
        metadata.update({
            'interface_name': interface_name,
            'start_date': start_date,
            'end_date': end_date
        })

        task_id = self.create_task_id()
        self.logger.info(f"添加下载任务: {interface_name}, 日期范围: {start_date} - {end_date}, ID: {task_id}")

        return self.add_task(
            task_type='download',
            target_func=strategy_func,
            priority=priority,
            kwargs=kwargs,
            max_retries=max_retries,
            task_id=task_id,
            metadata=metadata
        )

    def add_storage_task(self,
                        data: object,  # 使用object类型避免循环导入
                        filename: str,
                        subdir: str = "default",
                        priority: TaskPriority = TaskPriority.MEDIUM,
                        max_retries: int = 3,
                        metadata: Dict[str, Any] = None) -> str:
        """
        添加存储任务

        Args:
            data: 要存储的数据
            filename: 文件名
            subdir: 子目录
            priority: 优先级
            max_retries: 最大重试次数
            metadata: 元数据

        Returns:
            任务ID
        """
        if metadata is None:
            metadata = {}
        metadata.update({
            'filename': filename,
            'subdir': subdir
        })

        task_id = self.create_task_id()
        self.logger.info(f"添加存储任务: {filename}, ID: {task_id}")

        return self.add_task(
            task_type='storage',
            target_func=lambda data=data, filename=filename, subdir=subdir: self._execute_storage(data, filename, subdir),
            priority=priority,
            max_retries=max_retries,
            task_id=task_id,
            metadata=metadata
        )

    def _execute_storage(self, data, filename: str, subdir: str):
        """
        执行存储操作（内部方法）
        """
        # 这里需要导入storage_worker，避免循环导入
        from storage_worker import submit_data_to_storage
        return submit_data_to_storage(data, filename, subdir)


# 全局任务队列管理器实例
_global_task_manager = TaskQueueManager()


def get_task_manager() -> TaskQueueManager:
    """
    获取全局任务管理器
    """
    return _global_task_manager


def get_download_task_manager() -> DownloadTaskQueueManager:
    """
    获取下载任务管理器
    """
    # 创建一个新的下载任务管理器实例
    return DownloadTaskQueueManager()


def add_task_nowait(task_type: str,
                   target_func: Callable,
                   priority: TaskPriority = TaskPriority.MEDIUM,
                   args: tuple = None,
                   kwargs: dict = None,
                   callback: Optional[Callable] = None,
                   timeout: Optional[float] = None,
                   max_retries: int = 3,
                   metadata: Dict[str, Any] = None,
                   dependencies: List[str] = None) -> str:
    """
    向全局任务管理器添加任务（非阻塞）
    """
    manager = get_task_manager()
    return manager.add_task(
        task_type=task_type,
        target_func=target_func,
        priority=priority,
        args=args,
        kwargs=kwargs,
        callback=callback,
        timeout=timeout,
        max_retries=max_retries,
        metadata=metadata,
        dependencies=dependencies
    )


def wait_for_task_completion(task_id: str, timeout: float = None) -> bool:
    """
    等待指定任务完成
    """
    manager = get_task_manager()
    return manager.wait_for_task(task_id, timeout)


def get_task_status(task_id: str) -> Optional[TaskStatus]:
    """
    获取任务状态
    """
    manager = get_task_manager()
    return manager.get_task_status(task_id)


def get_task_result(task_id: str) -> Any:
    """
    获取任务结果
    """
    manager = get_task_manager()
    return manager.get_task_result(task_id)


def get_all_task_stats() -> Dict[str, Any]:
    """
    获取所有任务统计信息
    """
    manager = get_task_manager()
    return manager.get_stats()