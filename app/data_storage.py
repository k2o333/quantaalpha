"""
Data storage module for aspipe_v4 - handles saving data in Parquet format with caching support
"""
import os
import pandas as pd
import polars as pl
from pathlib import Path
import logging
from datetime import datetime

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