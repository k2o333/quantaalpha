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
        Handle API-specific errors
        """
        error_msg = str(error).lower()
        
        if "limit" in error_msg or "频次" in error_msg or "frequency" in error_msg:
            logger.error(f"API frequency limit exceeded in {context}: {error}")
            # In a real system, we might want to wait longer or reduce concurrent requests
            time.sleep(60)  # Wait a minute before retrying
        elif "token" in error_msg or "auth" in error_msg:
            logger.error(f"Authentication error in {context}: {error}")
            # This is likely a permanent error
            raise error
        elif "network" in error_msg or "timeout" in error_msg or "connection" in error_msg:
            logger.warning(f"Network error in {context}: {error}")
            # This might be temporary, handled by retry mechanism
        else:
            logger.error(f"Unknown error in {context}: {error}")
        
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