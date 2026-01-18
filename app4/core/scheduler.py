import threading
import time
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Any, List, Dict
import logging

logger = logging.getLogger(__name__)

class TaskScheduler:
    """任务调度器 - 高效的异步模型"""

    def __init__(self, max_workers: int = 8, max_queue_size: int = 1000):
        self.max_workers = max_workers
        self.task_queue = queue.Queue(maxsize=max_queue_size)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.running = False
        self.workers = []

    def submit_task(self, func: Callable, *args, **kwargs) -> Any:
        """
        提交任务到队列

        Args:
            func: 要执行的函数
            *args: 函数的位置参数
            **kwargs: 函数的关键字参数

        Returns:
            任务结果
        """
        future = self.executor.submit(func, *args, **kwargs)
        return future

    def submit_tasks(self, tasks: List[Dict[str, Any]]) -> List[Any]:
        """
        批量提交任务

        Args:
            tasks: 任务列表，每个任务是一个包含 'func', 'args', 'kwargs' 的字典

        Returns:
            所有任务的结果列表
        """
        futures = []
        for task in tasks:
            func = task['func']
            args = task.get('args', ())
            kwargs = task.get('kwargs', {})
            future = self.executor.submit(func, *args, **kwargs)
            futures.append(future)

        # 等待所有任务完成并收集结果
        results = []
        for future in as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.error(f"Task execution error: {str(e)}")
                results.append(None)

        return results

    def start(self):
        """启动调度器"""
        self.running = True
        logger.info(f"Task scheduler started with {self.max_workers} workers")

    def stop(self):
        """停止调度器"""
        self.running = False
        self.executor.shutdown(wait=True)
        logger.info("Task scheduler stopped")

    def get_stats(self) -> Dict[str, Any]:
        """获取调度器统计信息"""
        return {
            'max_workers': self.max_workers,
            'queue_size': self.task_queue.qsize(),
            'running': self.running
        }

class RateLimiter:
    """速率限制器 - 使用令牌桶算法"""

    def __init__(self, rate_limit: int, time_window: int = 60):
        """
        初始化速率限制器

        Args:
            rate_limit: 时间窗口内的最大请求数
            time_window: 时间窗口（秒），默认60秒
        """
        self.rate_limit = rate_limit
        self.time_window = time_window
        self.tokens = rate_limit
        self.last_refill = time.time()
        self.lock = threading.Lock()

    def acquire(self, tokens: int = 1) -> bool:
        """
        获取令牌

        Args:
            tokens: 需要的令牌数

        Returns:
            是否获取成功
        """
        with self.lock:
            now = time.time()
            # 计算需要补充的令牌数
            elapsed = now - self.last_refill
            refill_tokens = int(elapsed * self.rate_limit / self.time_window)

            if refill_tokens > 0:
                self.tokens = min(self.rate_limit, self.tokens + refill_tokens)
                self.last_refill = now

            # 检查是否有足够的令牌
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            else:
                return False

    def wait_for_tokens(self, tokens: int = 1):
        """
        等待直到有足够的令牌

        Args:
            tokens: 需要的令牌数
        """
        import random
        while not self.acquire(tokens):
            # [修改] 添加随机性，避免所有线程同时唤醒
            sleep_time = self.time_window / self.rate_limit
            random_jitter = random.uniform(0, sleep_time * 0.1)  # 添加 0-10% 的随机延迟
            time.sleep(sleep_time + random_jitter)