"""
Enhanced error handling and retry mechanisms for aspipe_v4
"""
import time
import logging
from functools import wraps
from typing import Callable, Any

logger = logging.getLogger(__name__)


def retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Decorator for retrying functions that fail
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            retries = 0
            current_delay = delay
            
            while retries <= max_retries:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    retries += 1
                    if retries > max_retries:
                        logger.error(f"Function {func.__name__} failed after {max_retries + 1} attempts: {e}")
                        raise e
                    
                    logger.warning(f"Attempt {retries} failed for {func.__name__}: {e}. Retrying in {current_delay}s...")
                    time.sleep(current_delay)
                    current_delay *= backoff  # Exponential backoff
            
            return None
        return wrapper
    return decorator


class ErrorHandler:
    """
    Centralized error handling class
    """
    
    @staticmethod
    def handle_api_error(error: Exception, context: str = ""):
        """
        增强的API错误处理，区分错误类型
        """
        error_msg = str(error).lower()

        if "limit" in error_msg or "频次" in error_msg or "frequency" in error_msg:
            logger.error(f"API频率限制超出 in {context}: {error}")
            time.sleep(120)  # 频率限制等待更长时间
        elif "token" in error_msg or "auth" in error_msg:
            logger.error(f"认证错误 in {context}: {error}")
            raise error
        elif any(keyword in error_msg for keyword in ["network", "timeout", "connection", "tushare.xyz"]):
            logger.warning(f"网络错误 in {context}: {error}")
            time.sleep(30)  # 网络错误等待30秒后重试
        elif "指定数据不存在" in str(error):
            logger.warning(f"数据不存在 in {context}: {error}")
            # 数据不存在错误不需要抛出异常，由调用方处理
            pass
        else:
            logger.error(f"未知错误 in {context}: {error}")

        # 对于数据不存在错误，不抛出异常
        if "指定数据不存在" not in str(error):
            raise error


def validate_and_clean_data(df, required_columns=None):
    """
    Basic data validation and cleaning
    """
    if df is None or df.empty:
        logger.warning("Received empty or None dataframe for validation")
        return df
    
    if required_columns:
        missing_cols = [col for col in required_columns if col not in df.columns]
        if missing_cols:
            logger.error(f"Missing required columns: {missing_cols}")
            raise ValueError(f"Missing required columns: {missing_cols}")
    
    initial_rows = len(df)
    
    # Remove completely empty rows
    df = df.dropna(how='all')
    
    # Log data info
    logger.info(f"Data validation: {initial_rows} -> {len(df)} rows after cleaning")
    
    return df