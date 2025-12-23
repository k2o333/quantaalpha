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
    使用统一的缓存键生成器来保持一致性

    Args:
        data_type: 数据类型 (接口名称)
        **kwargs: 接口参数 (如 ts_code, trade_date, start_date, end_date, period)

    Returns:
        缓存文件路径
    """
    from cache_key_generator import CacheKeyGenerator

    # 使用统一的缓存键生成器
    return CacheKeyGenerator.generate_cache_path(data_type, **kwargs)


def is_interface_data_cached(data_type: str, cache_ttl_hours: int = 24, **kwargs) -> bool:
    """
    检查接口数据是否已缓存且未过期（扩展原有is_data_cached函数）
    增加对全量缓存的检查和智能匹配

    Args:
        data_type: 数据类型 (接口名称)
        cache_ttl_hours: 缓存有效时间（小时）
        **kwargs: 接口参数
    """
    from cache_key_generator import CacheKeyGenerator
    from pathlib import Path
    from datetime import datetime
    import pandas as pd

    # 首先检查标准缓存
    cache_path = CacheKeyGenerator.generate_cache_path(data_type, **kwargs)
    if Path(cache_path).exists():
        file_mtime = Path(cache_path).stat().st_mtime
        cache_age = datetime.now().timestamp() - file_mtime
        if cache_age < (cache_ttl_hours * 3600):
            return True

    # 智能缓存匹配：如果特定参数的缓存不存在，检查是否有更通用的缓存
    # 例如：如果要下载特定股票的数据，但没有找到，检查是否有全量数据
    if 'ts_code' in kwargs:
        # 尝试移除ts_code参数，检查全量数据
        generic_kwargs = {k: v for k, v in kwargs.items() if k != 'ts_code'}
        if generic_kwargs:  # 只有当还有其他参数时才尝试
            generic_cache_path = CacheKeyGenerator.generate_cache_path(data_type, **generic_kwargs)
            if Path(generic_cache_path).exists():
                file_mtime = Path(generic_cache_path).stat().st_mtime
                cache_age = datetime.now().timestamp() - file_mtime
                if cache_age < (cache_ttl_hours * 3600):
                    # 检查全量数据中是否包含所需的股票数据
                    try:
                        df = pd.read_parquet(generic_cache_path)
                        if 'ts_code' in df.columns and kwargs['ts_code'] in df['ts_code'].values:
                            return True
                    except Exception:
                        pass  # 如果读取失败，继续检查其他缓存

    # 对于日期范围数据，检查是否有包含该范围的更大范围数据
    if 'start_date' in kwargs and 'end_date' in kwargs:
        # 检查是否有包含此范围的更大范围数据
        # 实现日期范围重叠检查逻辑（简化版本）
        pass

    return False


def load_interface_cached_data(data_type: str, **kwargs) -> pd.DataFrame:
    """
    加载接口的缓存数据（扩展原有load_from_parquet函数）
    增加对全量缓存的支持和智能提取

    Args:
        data_type: 数据类型 (接口名称)
        **kwargs: 接口参数

    Returns:
        DataFrame或空DataFrame
    """
    from cache_key_generator import CacheKeyGenerator
    from pathlib import Path
    import pandas as pd
    import logging

    logger = logging.getLogger(__name__)

    # 首先尝试加载标准缓存
    cache_path = CacheKeyGenerator.generate_cache_path(data_type, **kwargs)
    if Path(cache_path).exists():
        try:
            df = pd.read_parquet(cache_path)
            logger.info(f"从标准缓存加载数据: {data_type}, 路径: {cache_path}")
            return df
        except Exception as e:
            logger.warning(f"加载标准缓存失败: {cache_path}, 错误: {e}")

    # 智能缓存提取：从更通用的缓存中提取所需数据
    if 'ts_code' in kwargs:
        # 尝试从全量数据中提取特定股票的数据
        ts_code = kwargs['ts_code']
        generic_kwargs = {k: v for k, v in kwargs.items() if k != 'ts_code'}

        # 检查全量缓存文件
        if generic_kwargs:
            generic_cache_path = CacheKeyGenerator.generate_cache_path(data_type, **generic_kwargs)
            if Path(generic_cache_path).exists():
                try:
                    df = pd.read_parquet(generic_cache_path)
                    if 'ts_code' in df.columns:
                        filtered_df = df[df['ts_code'] == ts_code]
                        if not filtered_df.empty:
                            logger.info(f"从全量缓存提取数据: {data_type}, 股票代码: {ts_code}")
                            return filtered_df
                except Exception as e:
                    logger.warning(f"从全量缓存提取数据失败: {generic_cache_path}, 错误: {e}")

    # 对于日期范围数据，从更大范围的数据中提取
    if 'start_date' in kwargs and 'end_date' in kwargs:
        # 实现日期范围数据提取逻辑
        pass

    return pd.DataFrame()


def save_interface_data_to_cache(df: pd.DataFrame, data_type: str, **kwargs) -> bool:
    """
    保存接口数据到缓存（扩展原有save_to_parquet函数）
    同时更新全量缓存和相关缓存

    Args:
        df: 要保存的DataFrame
        data_type: 数据类型 (接口名称)
        **kwargs: 接口参数

    Returns:
        保存是否成功
    """
    from cache_key_generator import CacheKeyGenerator
    from pathlib import Path
    import pandas as pd
    import logging

    logger = logging.getLogger(__name__)

    if df is None or df.empty:
        return False

    try:
        # 保存标准缓存
        cache_path = CacheKeyGenerator.generate_cache_path(data_type, **kwargs)
        df.to_parquet(cache_path, index=False)
        logger.info(f"数据已保存到标准缓存: {data_type}, 路径: {cache_path}")

        # 智能缓存更新：对于特定查询，同时更新更通用的缓存
        if 'ts_code' in kwargs:
            # 如果保存的是单个股票的数据，考虑更新全量缓存
            generic_kwargs = {k: v for k, v in kwargs.items() if k != 'ts_code'}
            if generic_kwargs:
                # 更新全量缓存
                full_cache_path = CacheKeyGenerator.generate_cache_path(data_type, **generic_kwargs)
                if Path(full_cache_path).exists():
                    try:
                        existing_df = pd.read_parquet(full_cache_path)
                        # 合并数据，去重
                        combined_df = pd.concat([existing_df, df], ignore_index=True)
                        if 'ts_code' in combined_df.columns and 'ann_date' in combined_df.columns:
                            # 根据股票代码和公告日期去重
                            combined_df = combined_df.drop_duplicates(subset=['ts_code', 'ann_date'], keep='last')
                        elif 'ts_code' in combined_df.columns:
                            # 根据股票代码去重
                            combined_df = combined_df.drop_duplicates(subset=['ts_code'], keep='last')

                        combined_df.to_parquet(full_cache_path, index=False)
                        logger.info(f"全量缓存已更新: {data_type}")
                    except Exception as e:
                        logger.warning(f"更新全量缓存失败: {full_cache_path}, 错误: {e}")
                else:
                    # 如果全量缓存不存在，创建它
                    df.to_parquet(full_cache_path, index=False)
                    logger.info(f"全量缓存已创建: {data_type}")

        return True
    except Exception as e:
        logger.error(f"保存缓存失败: {e}")
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
    from cache_monitor import record_cache_hit, record_cache_miss, record_download
    from config_adapter import get_interface_cache_settings
    import logging

    logger = logging.getLogger(__name__)

    # 检查是否启用缓存
    cache_settings = get_interface_cache_settings(data_type)

    if cache_settings['enabled']:
        # 检查缓存
        if is_interface_data_cached(data_type, cache_ttl_hours=cache_settings['ttl_hours'],
                                   **kwargs):
            cached_data = load_interface_cached_data(data_type, **kwargs)
            if not cached_data.empty:
                logger.info(f"从缓存获取 {data_type} 数据")
                record_cache_hit(data_type)
                return cached_data
            else:
                record_cache_miss(data_type)
        else:
            record_cache_miss(data_type)
    else:
        record_cache_miss(data_type)

    # 缓存未命中，执行下载
    downloaded_data = download_func(**kwargs)

    # 记录下载操作
    record_download(data_type, len(downloaded_data) if downloaded_data is not None else 0)

    # 保存到缓存（如果启用且数据不为空）
    if cache_settings['enabled'] and not downloaded_data.empty:
        save_interface_data_to_cache(downloaded_data, data_type, **kwargs)

    return downloaded_data