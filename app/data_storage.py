"""
Data storage module for aspipe_v4 - handles saving data in Parquet format with caching support
"""
import os
import pandas as pd
import polars as pl
from pathlib import Path
import logging
from datetime import datetime, timedelta
import hashlib
try:
    from .utils.date_utils import validate_and_convert_datetime
except ImportError:
    from utils.date_utils import validate_and_convert_datetime

logger = logging.getLogger(__name__)

# Data directory configuration - use absolute path from project root
DATA_DIR = Path(__file__).parent.parent / 'data'
DATA_DIR.mkdir(exist_ok=True)

def save_to_parquet(df: pd.DataFrame, filename: str, subdir: str = None) -> str:
    """
    Save a pandas DataFrame to Parquet format

    Args:
        df: DataFrame to save
        filename: Name of the file (without extension)
        subdir: Subdirectory within data directory (optional)

    Returns:
        Path to the saved file
    """
    try:
        # Create subdirectory if specified
        if subdir:
            save_dir = DATA_DIR / subdir
            save_dir.mkdir(parents=True, exist_ok=True)  # Create parent directories if needed
            filepath = save_dir / f"{filename}.parquet"
        else:
            filepath = DATA_DIR / f"{filename}.parquet"

        # Ensure parent directory exists
        filepath.parent.mkdir(parents=True, exist_ok=True)

        # Convert to polars for efficient storage (or stay with pandas)
        # For this implementation, we'll use pandas directly for simplicity
        df.to_parquet(filepath, index=False, engine='pyarrow')

        logger.info(f"Saved {len(df)} records to {filepath}")
        return str(filepath)

    except Exception as e:
        logger.error(f"Failed to save {filename} to parquet: {e}")
        raise


def load_from_parquet(filename: str, subdir: str = None) -> pd.DataFrame:
    """
    Load a DataFrame from Parquet format

    Args:
        filename: Name of the file (with or without .parquet extension)
        subdir: Subdirectory within data directory (optional)

    Returns:
        Loaded DataFrame
    """
    try:
        # Create file path
        if subdir:
            filepath = DATA_DIR / subdir / filename
        else:
            filepath = DATA_DIR / filename

        # Add extension if not present
        if not str(filepath).endswith('.parquet'):
            filepath = filepath.with_suffix('.parquet')

        # Load and return the DataFrame
        df = pd.read_parquet(filepath, engine='pyarrow')
        logger.info(f"Loaded {len(df)} records from {filepath}")

        # 验证并转换日期列（对常见日期列名进行检查）
        for col in df.columns:
            if 'date' in col.lower() or 'trade_date' in col.lower() or 'cal_date' in col.lower() or 'time' in col.lower():
                df = validate_and_convert_datetime(df, col)

        return df

    except Exception as e:
        logger.error(f"Failed to load {filename} from parquet: {e}")
        raise


def is_data_cached(file_path: str) -> bool:
    """
    Check if data is already cached

    Args:
        file_path: Path to the cache file

    Returns:
        True if file exists, False otherwise
    """
    return Path(file_path).exists()


def get_cache_path(data_type: str, trade_date: str = None, ts_code: str = None) -> str:
    """
    Generate standardized cache path

    Args:
        data_type: Type of data (e.g., 'daily_basic', 'moneyflow')
        trade_date: Trading date in YYYYMMDD format (optional)
        ts_code: Stock code (optional)

    Returns:
        Path to the cache file
    """
    if trade_date:
        year = trade_date[:4]
        month = trade_date[4:6]
        subdir = f"daily/{year}/{month}"
        filename = f"{data_type}_{trade_date}"
        return str(DATA_DIR / subdir / f"{filename}.parquet")
    elif ts_code:
        return str(DATA_DIR / data_type / f"{ts_code}.parquet")
    else:
        return str(DATA_DIR / data_type / "all_data.parquet")


def is_data_fresh(file_path: str, max_age_hours: int = 24) -> bool:
    """
    Check if cached data is fresh based on file modification time

    Args:
        file_path: Path to the cache file
        max_age_hours: Maximum age in hours before considering data stale

    Returns:
        True if data is fresh, False otherwise
    """
    try:
        if not Path(file_path).exists():
            return False

        mod_time = Path(file_path).stat().st_mtime
        current_time = datetime.now().timestamp()
        age_hours = (current_time - mod_time) / 3600

        return age_hours <= max_age_hours
    except Exception as e:
        logger.warning(f"Failed to check data freshness for {file_path}: {e}")
        return False


def get_interface_cache_path(data_type: str, **kwargs) -> str:
    """
    Generate cache path based on interface and parameters (扩展原有get_cache_path函数)

    Args:
        data_type: 数据类型 (接口名称)
        **kwargs: 接口参数 (如 ts_code, trade_date, start_date, end_date, period)

    Returns:
        缓存文件路径
    """

    # 使用现有DATA_DIR路径，但支持更多参数组合
    if 'ts_code' in kwargs:
        ts_code = kwargs['ts_code']
        if 'trade_date' in kwargs:
            # 单日数据: data/interface/ts_code/trade_date.parquet
            subdir = f"{data_type}/{ts_code}"
            filename = f"{kwargs['trade_date']}.parquet"
        elif 'start_date' in kwargs and 'end_date' in kwargs:
            # 日期范围数据: data/interface/ts_code/start_date_end_date.parquet
            subdir = f"{data_type}/{ts_code}"
            filename = f"{kwargs['start_date']}-{kwargs['end_date']}.parquet"
        else:
            # 股票全部历史数据: data/interface/ts_code/all.parquet
            subdir = f"{data_type}/{ts_code}"
            filename = "all.parquet"
    elif 'trade_date' in kwargs:
        # 全市场日度数据: data/interface/yyyy/mm/dd.parquet
        trade_date = kwargs['trade_date']
        year = trade_date[:4]
        month = trade_date[4:6]
        subdir = f"{data_type}/{year}/{month}"
        filename = f"{trade_date}.parquet"
    elif 'period' in kwargs:
        # 财务报告期数据: data/interface/yyyy/period.parquet
        period = kwargs['period']
        year = period[:4]
        subdir = f"{data_type}/{year}"
        filename = f"{period}.parquet"
    else:
        # 其他情况使用参数哈希
        param_str = str(sorted(kwargs.items()))
        param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]
        subdir = data_type
        filename = f"{param_hash}.parquet"

    full_path = DATA_DIR / subdir / filename
    full_path.parent.mkdir(parents=True, exist_ok=True)
    return str(full_path)


def is_interface_data_cached(data_type: str, cache_ttl_hours: int = 24, **kwargs) -> bool:
    """
    检查接口数据是否已缓存且未过期（扩展原有is_data_cached函数）

    Args:
        data_type: 数据类型 (接口名称)
        cache_ttl_hours: 缓存有效时间（小时）
        **kwargs: 接口参数
    """
    cache_path = get_interface_cache_path(data_type, **kwargs)
    if not Path(cache_path).exists():
        return False

    # 检查缓存是否过期
    file_mtime = Path(cache_path).stat().st_mtime
    cache_age = datetime.now().timestamp() - file_mtime
    return cache_age < (cache_ttl_hours * 3600)


def load_interface_cached_data(data_type: str, **kwargs) -> pd.DataFrame:
    """
    加载接口的缓存数据（扩展原有load_from_parquet函数）

    Args:
        data_type: 数据类型 (接口名称)
        **kwargs: 接口参数

    Returns:
        DataFrame或空DataFrame
    """
    cache_path = get_interface_cache_path(data_type, **kwargs)
    if Path(cache_path).exists():
        try:
            df = pd.read_parquet(cache_path)
            logger.info(f"从缓存加载数据: {data_type}, 路径: {cache_path}")
            return df
        except Exception as e:
            logger.warning(f"加载缓存失败: {cache_path}, 错误: {e}")
            return pd.DataFrame()
    return pd.DataFrame()


def save_interface_data_to_cache(df: pd.DataFrame, data_type: str, **kwargs) -> bool:
    """
    保存接口数据到缓存（扩展原有save_to_parquet函数）

    Args:
        df: 要保存的DataFrame
        data_type: 数据类型 (接口名称)
        **kwargs: 接口参数

    Returns:
        保存是否成功
    """
    if df is None or df.empty:
        return False

    cache_path = get_interface_cache_path(data_type, **kwargs)
    try:
        df.to_parquet(cache_path, index=False)
        logger.info(f"数据已保存到缓存: {data_type}, 路径: {cache_path}")
        return True
    except Exception as e:
        logger.error(f"保存缓存失败: {cache_path}, 错误: {e}")
        return False


def get_cached_or_download_data(data_type: str, download_func: callable,
                               cache_ttl_hours: int = 24, **kwargs) -> pd.DataFrame:
    """
    统一的缓存获取函数 - 检查缓存，如果未命中则下载并缓存

    Args:
        data_type: 数据类型 (接口名称)
        download_func: 下载函数
        cache_ttl_hours: 缓存TTL
        **kwargs: 传递给下载函数和缓存键的参数

    Returns:
        DataFrame - 来自缓存或下载的数据
    """
    # 检查是否启用缓存
    from config_adapter import get_interface_cache_settings
    cache_settings = get_interface_cache_settings(data_type)

    if cache_settings['enabled']:
        # 检查缓存
        if is_interface_data_cached(data_type, cache_ttl_hours=cache_settings['ttl_hours'],
                                   **kwargs):
            cached_data = load_interface_cached_data(data_type, **kwargs)
            if not cached_data.empty:
                logger.info(f"从缓存获取 {data_type} 数据")
                return cached_data

    # 缓存未命中，执行下载
    downloaded_data = download_func(**kwargs)

    # 保存到缓存（如果启用且数据不为空）
    if cache_settings['enabled'] and not downloaded_data.empty:
        save_interface_data_to_cache(downloaded_data, data_type, **kwargs)

    return downloaded_data