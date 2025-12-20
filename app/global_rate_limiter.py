"""
全局速率限制器
实现基于令牌桶算法的速率限制，确保API调用不会超频
"""
import time
import threading
from typing import Dict, Optional
from dataclasses import dataclass
from enum import Enum
import logging


class RateLimitType(Enum):
    """速率限制类型枚举"""
    GLOBAL = "global"           # 全局限制
    INTERFACE = "interface"     # 接口限制
    IP = "ip"                   # IP限制
    USER = "user"               # 用户限制


@dataclass
class RateLimitConfig:
    """速率限制配置"""
    max_tokens: float          # 最大令牌数
    refill_rate: float        # 令牌填充速率（个/秒）
    current_tokens: float     # 当前令牌数
    last_refill_time: float   # 上次填充时间
    lock: threading.Lock      # 线程锁


class GlobalRateLimiter:
    """
    全局速率限制器，基于令牌桶算法的线程安全实现
    """

    def __init__(self):
        self.rate_limits: Dict[str, RateLimitConfig] = {}
        self.logger = logging.getLogger(__name__)
        self._setup_default_limits()

    def _setup_default_limits(self):
        """
        设置默认速率限制
        """
        # 全局限制：根据TuShare API限制设置
        self.set_rate_limit("global", max_tokens=500, refill_rate=180)  # 每30分钟500次请求

        # 常见接口限制
        self.set_rate_limit("daily", max_tokens=200, refill_rate=20)      # 日度数据
        self.set_rate_limit("daily_basic", max_tokens=100, refill_rate=10) # 日频基本面
        self.set_rate_limit("moneyflow", max_tokens=150, refill_rate=15)   # 资金流
        self.set_rate_limit("financial", max_tokens=50, refill_rate=5)     # 财务数据
        self.set_rate_limit("other", max_tokens=100, refill_rate=10)       # 其他接口

    def set_rate_limit(self, key: str, max_tokens: float, refill_rate: float):
        """
        设置指定键的速率限制

        Args:
            key: 限制键（如 'global', 'daily', 'income' 等）
            max_tokens: 最大令牌数
            refill_rate: 令牌填充速率（个/秒）
        """
        config = RateLimitConfig(
            max_tokens=max_tokens,
            refill_rate=refill_rate,
            current_tokens=max_tokens,  # 初始时令牌桶满
            last_refill_time=time.time(),
            lock=threading.Lock()
        )
        self.rate_limits[key] = config
        self.logger.info(f"设置速率限制 - {key}: 最大 {max_tokens} 令牌, 填充速率 {refill_rate}/秒")

    def _refill_tokens(self, config: RateLimitConfig):
        """
        填充令牌
        """
        current_time = time.time()
        time_passed = current_time - config.last_refill_time

        # 计算应填充的令牌数
        tokens_to_add = time_passed * config.refill_rate
        config.current_tokens = min(config.max_tokens, config.current_tokens + tokens_to_add)
        config.last_refill_time = current_time

    def acquire(self, key: str, tokens: float = 1.0, block: bool = True, timeout: float = None) -> bool:
        """
        获取指定数量的令牌

        Args:
            key: 限制键
            tokens: 需要的令牌数
            block: 是否阻塞等待
            timeout: 等待超时时间（秒）

        Returns:
            是否成功获取令牌
        """
        if key not in self.rate_limits:
            self.logger.warning(f"未找到速率限制配置: {key}，使用默认配置")
            # 对于未配置的接口，使用其他接口的默认限制
            self.set_rate_limit(key, max_tokens=100, refill_rate=10)

        config = self.rate_limits[key]

        with config.lock:
            self._refill_tokens(config)

            if config.current_tokens >= tokens:
                # 有足够的令牌
                config.current_tokens -= tokens
                self.logger.debug(f"获取 {tokens} 个令牌成功 - {key}，剩余: {config.current_tokens:.2f}")
                return True
            elif not block:
                # 不阻塞，直接返回失败
                self.logger.debug(f"获取 {tokens} 个令牌失败 - {key}，当前: {config.current_tokens:.2f}，需要: {tokens}")
                return False
            else:
                # 需要阻塞等待
                start_time = time.time()
                while config.current_tokens < tokens:
                    # 计算需要等待的时间
                    tokens_needed = tokens - config.current_tokens
                    wait_time = tokens_needed / config.refill_rate

                    # 如果设置了超时且等待时间超过超时，则返回失败
                    if timeout is not None:
                        elapsed = time.time() - start_time
                        if elapsed >= timeout:
                            self.logger.debug(f"获取令牌超时 - {key}")
                            return False
                        wait_time = min(wait_time, timeout - elapsed)

                    # 等待一段时间再检查
                    time.sleep(wait_time)
                    self._refill_tokens(config)

                # 有足够的令牌
                config.current_tokens -= tokens
                self.logger.debug(f"获取 {tokens} 个令牌成功（等待后） - {key}，剩余: {config.current_tokens:.2f}")
                return True

    def try_acquire(self, key: str, tokens: float = 1.0) -> bool:
        """
        尝试获取令牌，不阻塞

        Args:
            key: 限制键
            tokens: 需要的令牌数

        Returns:
            是否成功获取令牌
        """
        return self.acquire(key, tokens, block=False)

    def wait_for_tokens(self, key: str, tokens: float = 1.0, timeout: float = None) -> bool:
        """
        等待直到有足够的令牌

        Args:
            key: 限制键
            tokens: 需要的令牌数
            timeout: 最大等待时间

        Returns:
            是否成功等待到令牌
        """
        return self.acquire(key, tokens, block=True, timeout=timeout)

    def get_available_tokens(self, key: str) -> float:
        """
        获取指定键的可用令牌数
        """
        if key not in self.rate_limits:
            return 0.0

        config = self.rate_limits[key]
        with config.lock:
            self._refill_tokens(config)
            return config.current_tokens

    def get_rate_limit_info(self, key: str) -> Dict[str, float]:
        """
        获取速率限制信息
        """
        if key not in self.rate_limits:
            return {}

        config = self.rate_limits[key]
        with config.lock:
            self._refill_tokens(config)
            return {
                'max_tokens': config.max_tokens,
                'refill_rate': config.refill_rate,
                'current_tokens': config.current_tokens,
                'last_refill_time': config.last_refill_time
            }

    def reset_tokens(self, key: str):
        """
        重置指定键的令牌数到最大值
        """
        if key in self.rate_limits:
            config = self.rate_limits[key]
            with config.lock:
                config.current_tokens = config.max_tokens
                config.last_refill_time = time.time()
                self.logger.info(f"重置 {key} 令牌数到最大值: {config.max_tokens}")

    def acquire_multiple(self, requirements: Dict[str, float], block: bool = True, timeout: float = None) -> bool:
        """
        同时获取多个限制键的令牌

        Args:
            requirements: {key: tokens} 字典
            block: 是否阻塞等待
            timeout: 等待超时时间

        Returns:
            是否成功获取所有令牌
        """
        # 首先检查是否所有键都有足够的令牌（非阻塞方式）
        for key, tokens in requirements.items():
            if not self.try_acquire(key, tokens):
                if not block:
                    return False
                # 如果需要阻塞，按顺序获取
                for req_key, req_tokens in requirements.items():
                    if not self.wait_for_tokens(req_key, req_tokens, timeout):
                        # 如果获取失败，释放已经获取的令牌
                        for acquired_key, acquired_tokens in requirements.items():
                            if acquired_key == req_key:
                                break
                            self._release_tokens(acquired_key, acquired_tokens)
                        return False
                return True

        # 所有令牌都获取成功
        return True

    def _release_tokens(self, key: str, tokens: float):
        """
        释放令牌（内部方法，不带锁）
        """
        if key in self.rate_limits:
            config = self.rate_limits[key]
            config.current_tokens = min(config.max_tokens, config.current_tokens + tokens)
            self.logger.debug(f"释放 {tokens} 个令牌 - {key}，当前: {config.current_tokens:.2f}")


# 全局速率限制器实例
_global_rate_limiter = GlobalRateLimiter()


def get_global_rate_limiter() -> GlobalRateLimiter:
    """
    获取全局速率限制器实例
    """
    return _global_rate_limiter


def acquire_tokens(key: str, tokens: float = 1.0, block: bool = True, timeout: float = None) -> bool:
    """
    获取令牌
    """
    limiter = get_global_rate_limiter()
    return limiter.acquire(key, tokens, block, timeout)


def try_acquire_tokens(key: str, tokens: float = 1.0) -> bool:
    """
    尝试获取令牌（不阻塞）
    """
    limiter = get_global_rate_limiter()
    return limiter.try_acquire(key, tokens)


def wait_for_tokens(key: str, tokens: float = 1.0, timeout: float = None) -> bool:
    """
    等待令牌
    """
    limiter = get_global_rate_limiter()
    return limiter.wait_for_tokens(key, tokens, timeout)


def get_available_tokens(key: str) -> float:
    """
    获取可用令牌数
    """
    limiter = get_global_rate_limiter()
    return limiter.get_available_tokens(key)


def get_rate_limit_info(key: str) -> Dict[str, float]:
    """
    获取速率限制信息
    """
    limiter = get_global_rate_limiter()
    return limiter.get_rate_limit_info(key)


def reset_tokens(key: str):
    """
    重置令牌
    """
    limiter = get_global_rate_limiter()
    limiter.reset_tokens(key)


def acquire_multiple_tokens(requirements: Dict[str, float], block: bool = True, timeout: float = None) -> bool:
    """
    同时获取多个令牌
    """
    limiter = get_global_rate_limiter()
    return limiter.acquire_multiple(requirements, block, timeout)


class RateLimitedSession:
    """
    速率限制会话，用于简化速率限制的使用
    """

    def __init__(self, default_key: str = "global"):
        self.default_key = default_key
        self.limiter = get_global_rate_limiter()
        self.logger = logging.getLogger(__name__)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def acquire(self, key: str = None, tokens: float = 1.0, timeout: float = None) -> bool:
        """
        获取令牌
        """
        use_key = key or self.default_key
        return self.limiter.acquire(use_key, tokens, timeout=timeout)

    def execute_with_rate_limit(self,
                               func,
                               key: str = None,
                               tokens: float = 1.0,
                               timeout: float = 300) -> Optional[any]:
        """
        在速率限制下执行函数

        Args:
            func: 要执行的函数
            key: 速率限制键
            tokens: 需要的令牌数
            timeout: 等待超时时间

        Returns:
            函数执行结果，如果获取令牌失败则返回None
        """
        use_key = key or self.default_key

        if self.acquire(use_key, tokens, timeout):
            try:
                result = func()
                return result
            except Exception as e:
                self.logger.error(f"执行函数时出错: {e}")
                raise
        else:
            self.logger.warning(f"获取速率限制令牌失败 - {use_key}, 令牌数: {tokens}")
            return None


def with_rate_limit(key: str = "global", tokens: float = 1.0, timeout: float = 300):
    """
    速率限制装饰器

    Args:
        key: 速率限制键
        tokens: 需要的令牌数
        timeout: 等待超时时间
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            limiter = get_global_rate_limiter()
            if limiter.acquire(key, tokens, timeout=timeout):
                return func(*args, **kwargs)
            else:
                logging.getLogger(__name__).warning(f"无法获取速率限制令牌 - {key}, 跳过函数执行: {func.__name__}")
                return None
        return wrapper
    return decorator