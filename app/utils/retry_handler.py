"""
统一重试处理器
"""
import time
import logging
from typing import Callable, Any


class RetryHandler:
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def execute_with_retry(self, func: Callable, max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0, *args, **kwargs) -> Any:
        """
        执行函数并带重试机制
        """
        for attempt in range(max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if attempt == max_retries:
                    self.logger.error(f"所有 {max_retries + 1} 次尝试都失败了: {e}")
                    raise
                else:
                    self.logger.warning(f"尝试 {attempt + 1} 失败: {e}")
                    wait_time = delay * (backoff ** attempt)
                    self.logger.info(f"等待 {wait_time}s 后重试...")
                    time.sleep(wait_time)