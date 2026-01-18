# 分页、分批次和缓存功能实现文档 (V4 - 修复版)

## 1. 现有架构分析

### 1.1 模块化设计架构
项目采用模块化设计，功能分散在不同的接口类中：
- `app/interfaces/daily_data.py` - 日度数据接口
- `app/interfaces/technical_factors.py` - 技术因子接口
- `app/interfaces/market_structure.py` - 市场结构接口
- `app/interfaces/financial_data.py` - 财务数据接口
- `app/utils/parallel_downloader.py` - 并行下载器

### 1.2 现有分页功能
项目中的分页功能在各个接口类和API管理器中实现：
- `TechnicalFactorsDownloader.download_stk_factor_paginated`
- `MarketStructureDownloader.download_cyq_perf_paginated`
- `MarketStructureDownloader.download_cyq_chips_paginated`
- `TuShareAPIManager.download_with_pagination` - 通用分页下载方法

### 1.3 现有缓存功能
缓存功能在 `app/data_storage.py` 中实现：
- `is_data_cached(file_path: str)` - 检查数据是否已缓存
- `get_cache_path(data_type: str, trade_date: str = None, ts_code: str = None)` - 生成标准缓存路径
- `is_data_fresh(file_path: str, max_age_hours: int = 24)` - 检查数据新鲜度

## 2. 基于现有架构的增强实现

### 2.1 各接口类的分页功能增强

在 `app/interfaces/daily_data.py` 中扩展分页功能：

```python
from .base import BaseDownloader
import pandas as pd


class DailyDataDownloader(BaseDownloader):
    def __init__(self, pro_api, config_manager):
        super().__init__(pro_api, config_manager)

    def download_daily_data(self, ts_code=None, start_date=None, end_date=None):
        """下载日线数据"""
        # 检查积分要求
        if not self.check_points_requirement(2000):
            self.logger.warning("daily requires 2000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'daily')
        return self.safe_download(
            api_func,
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date
        )

    def download_daily_basic(self, trade_date=None, ts_code=None, start_date=None, end_date=None):
        """下载每日指标数据"""
        # 检查积分要求
        if not self.check_points_requirement(2000):
            self.logger.warning("daily_basic requires 2000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'daily_basic')
        return self.safe_download(
            api_func,
            trade_date=trade_date,
            ts_code=ts_code,
            start_date=start_date,
            end_date=end_date
        )

    def download_daily_basic_paginated(self, trade_date=None, ts_code=None, start_date=None, end_date=None):
        """分页下载每日指标数据 - 根据TuShare文档限制: 单次最大6000条"""
        if not self.check_points_requirement(2000):
            self.logger.warning("daily_basic requires 2000+ points, skipping download")
            return pd.DataFrame()

        # 通过API管理器的分页功能
        try:
            # 使用传入的config_manager中的API管理器
            # 注意：这通常由API管理器处理，这里提供直接分页实现作为参考
            api_func = getattr(self.pro, 'daily_basic')

            # 分页下载实现
            all_data = []
            offset = 0
            limit = 6000  # daily_basic最大支持6000条

            while True:
                try:
                    # 使用API管理器的速率限制
                    if hasattr(self.config, 'api_manager'):
                        self.config.api_manager._rate_limit('daily_basic')

                    kwargs = {}
                    if trade_date:
                        kwargs['trade_date'] = trade_date
                    if ts_code:
                        kwargs['ts_code'] = ts_code
                    if start_date:
                        kwargs['start_date'] = start_date
                    if end_date:
                        kwargs['end_date'] = end_date
                    kwargs['offset'] = offset
                    kwargs['limit'] = limit

                    data = api_func(**kwargs)

                    if data is None or len(data) == 0:
                        break

                    all_data.append(data)

                    # 如果返回数据少于限制数量，说明已到最后一页
                    if len(data) < limit:
                        break

                    offset += limit

                    # 防止无限循环
                    if offset > 100000:
                        self.logger.warning(f"daily_basic pagination reached max offset: {offset}")
                        break

                except Exception as e:
                    self.logger.error(f"Pagination download failed for daily_basic, offset={offset}: {e}")
                    break

            return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()
        except Exception as e:
            self.logger.error(f"Failed to download daily_basic paginated: {e}")
            # 回退到非分页下载
            return self.download_daily_basic(
                trade_date=trade_date, 
                ts_code=ts_code, 
                start_date=start_date, 
                end_date=end_date
            )
```

在 `app/interfaces/market_flow.py` 中添加分页功能：

```python
from .base import BaseDownloader
import pandas as pd


class MarketFlowDownloader(BaseDownloader):
    def __init__(self, pro_api, config_manager):
        super().__init__(pro_api, config_manager)

    def download_moneyflow(self, trade_date=None, ts_code=None):
        """下载资金流数据"""
        # 检查积分要求
        if not self.check_points_requirement(2000):
            self.logger.warning("moneyflow requires 2000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'moneyflow')
        return self.safe_download(
            api_func,
            trade_date=trade_date,
            ts_code=ts_code
        )

    def download_moneyflow_paginated(self, trade_date=None, ts_code=None):
        """分页下载资金流数据 - 根据TuShare文档限制: 单次最大6000条"""
        if not self.check_points_requirement(2000):
            self.logger.warning("moneyflow requires 2000+ points, skipping download")
            return pd.DataFrame()

        # 分页下载实现
        all_data = []
        offset = 0
        limit = 6000  # moneyflow最大支持6000条

        while True:
            try:
                # 使用API管理器的速率限制
                if hasattr(self.config, 'api_manager'):
                    self.config.api_manager._rate_limit('moneyflow')

                kwargs = {}
                if trade_date:
                    kwargs['trade_date'] = trade_date
                if ts_code:
                    kwargs['ts_code'] = ts_code
                kwargs['offset'] = offset
                kwargs['limit'] = limit

                data = self.pro.moneyflow(**kwargs)

                if data is None or len(data) == 0:
                    break

                all_data.append(data)

                # 如果返回数据少于限制数量，说明已到最后一页
                if len(data) < limit:
                    break

                offset += limit

                if offset > 100000:
                    self.logger.warning(f"moneyflow pagination reached max offset: {offset}")
                    break

            except Exception as e:
                self.logger.error(f"Pagination download failed for moneyflow, offset={offset}: {e}")
                break

        return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()
```

在 `app/interfaces/financial_data.py` 中添加财务数据分页功能：

```python
from .base import BaseDownloader
import pandas as pd


class FinancialDataDownloader(BaseDownloader):
    def __init__(self, pro_api, config_manager):
        super().__init__(pro_api, config_manager)

    def download_income(self, period=None, ts_code=None):
        """下载利润表数据"""
        # 检查积分要求
        if not self.check_points_requirement(5000):
            self.logger.warning("income requires 5000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'income')
        return self.safe_download(
            api_func,
            period=period,
            ts_code=ts_code
        )

    def download_balancesheet(self, period=None, ts_code=None):
        """下载资产负债表数据"""
        # 检查积分要求
        if not self.check_points_requirement(9000):
            self.logger.warning("balancesheet requires 9000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'balancesheet')
        return self.safe_download(
            api_func,
            period=period,
            ts_code=ts_code
        )

    def download_cashflow(self, period=None, ts_code=None):
        """下载现金流量表数据"""
        # 检查积分要求
        if not self.check_points_requirement(9000):
            self.logger.warning("cashflow requires 9000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'cashflow')
        return self.safe_download(
            api_func,
            period=period,
            ts_code=ts_code
        )

    def download_fina_indicator(self, period=None, ts_code=None):
        """下载财务指标数据"""
        # 检查积分要求
        if not self.check_points_requirement(2000):
            self.logger.warning("fina_indicator requires 2000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'fina_indicator')
        return self.safe_download(
            api_func,
            period=period,
            ts_code=ts_code
        )

    def download_income_paginated(self, period=None, ts_code=None):
        """分页下载利润表数据 - 根据TuShare文档限制: 单次最大3000条"""
        if not self.check_points_requirement(5000):
            self.logger.warning("income requires 5000+ points, skipping download")
            return pd.DataFrame()

        all_data = []
        offset = 0
        limit = 3000  # income最大支持3000条

        while True:
            try:
                # 使用API管理器的速率限制
                if hasattr(self.config, 'api_manager'):
                    self.config.api_manager._rate_limit('income')

                kwargs = {}
                if period:
                    kwargs['period'] = period
                if ts_code:
                    kwargs['ts_code'] = ts_code
                kwargs['offset'] = offset
                kwargs['limit'] = limit

                data = self.pro.income(**kwargs)

                if data is None or len(data) == 0:
                    break

                all_data.append(data)

                # 如果返回数据少于限制数量，说明已到最后一页
                if len(data) < limit:
                    break

                offset += limit

                if offset > 50000:
                    self.logger.warning(f"income pagination reached max offset: {offset}")
                    break

            except Exception as e:
                self.logger.error(f"Pagination download failed for income, offset={offset}: {e}")
                break

        return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()

    def download_fina_indicator_paginated(self, period=None, ts_code=None):
        """分页下载财务指标数据 - 根据TuShare文档限制: 单次最大3000条"""
        if not self.check_points_requirement(2000):
            self.logger.warning("fina_indicator requires 2000+ points, skipping download")
            return pd.DataFrame()

        all_data = []
        offset = 0
        limit = 3000  # fina_indicator最大支持3000条

        while True:
            try:
                # 使用API管理器的速率限制
                if hasattr(self.config, 'api_manager'):
                    self.config.api_manager._rate_limit('fina_indicator')

                kwargs = {}
                if period:
                    kwargs['period'] = period
                if ts_code:
                    kwargs['ts_code'] = ts_code
                kwargs['offset'] = offset
                kwargs['limit'] = limit

                data = self.pro.fina_indicator(**kwargs)

                if data is None or len(data) == 0:
                    break

                all_data.append(data)

                # 如果返回数据少于限制数量，说明已到最后一页
                if len(data) < limit:
                    break

                offset += limit

                if offset > 50000:
                    self.logger.warning(f"fina_indicator pagination reached max offset: {offset}")
                    break

            except Exception as e:
                self.logger.error(f"Pagination download failed for fina_indicator, offset={offset}: {e}")
                break

        return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()


class MarketStructureDownloader(BaseDownloader):
    def __init__(self, pro_api, config_manager):
        super().__init__(pro_api, config_manager)

    def download_cyq_perf(self, trade_date=None, ts_code=None):
        """下载每日筹码及胜率"""
        # 检查积分要求
        if not self.check_points_requirement(5000):
            self.logger.warning("cyq_perf requires 5000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'cyq_perf')
        return self.safe_download(
            api_func,
            trade_date=trade_date,
            ts_code=ts_code
        )

    def download_cyq_chips(self, trade_date=None, ts_code=None):
        """下载每日筹码分布"""
        # 检查积分要求
        if not self.check_points_requirement(5000):
            self.logger.warning("cyq_chips requires 5000+ points, skipping download")
            return pd.DataFrame()

        api_func = getattr(self.pro, 'cyq_chips')
        return self.safe_download(
            api_func,
            trade_date=trade_date,
            ts_code=ts_code
        )

    def download_cyq_perf_paginated(self, trade_date=None, ts_code=None):
        """下载每日筹码及胜率(分页) - 使用API管理器的分页功能"""
        if not self.check_points_requirement(5000):
            self.logger.warning("cyq_perf requires 5000+ points, skipping download")
            return pd.DataFrame()

        # 使用API管理器的分页功能，避免重复实现
        try:
            if hasattr(self.config, 'api_manager'):
                return self.config.api_manager.download_cyq_perf_paginated(
                    trade_date=trade_date,
                    ts_code=ts_code
                )
            else:
                # 如果没有API管理器，使用基本分页下载
                all_data = []
                offset = 0
                limit = 5000  # cyq_perf单次最大5000条

                while True:
                    try:
                        # 使用API管理器的速率限制（如果可用）
                        if hasattr(self.config, 'api_manager'):
                            self.config.api_manager._rate_limit('cyq_perf')

                        kwargs = {}
                        if trade_date:
                            kwargs['trade_date'] = trade_date
                        if ts_code:
                            kwargs['ts_code'] = ts_code
                        kwargs['offset'] = offset
                        kwargs['limit'] = limit

                        data = self.pro.cyq_perf(**kwargs)

                        if data is None or len(data) == 0:
                            break

                        all_data.append(data)

                        # 如果返回数据少于限制数量，说明已到最后一页
                        if len(data) < limit:
                            break

                        offset += limit

                        if offset > 50000:
                            self.logger.warning(f"cyq_perf pagination reached max offset: {offset}")
                            break

                    except Exception as e:
                        self.logger.error(f"Pagination download failed for cyq_perf, offset={offset}: {e}")
                        break

                return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()
        except Exception as e:
            self.logger.error(f"分页下载cyq_perf失败: {e}")
            # 回退到普通下载方法
            return self.download_cyq_perf(trade_date=trade_date, ts_code=ts_code)

    def download_cyq_chips_paginated(self, trade_date=None, ts_code=None):
        """下载每日筹码分布(分页) - 使用API管理器的分页功能"""
        if not self.check_points_requirement(5000):
            self.logger.warning("cyq_chips requires 5000+ points, skipping download")
            return pd.DataFrame()

        # 使用API管理器的分页功能，避免重复实现
        try:
            if hasattr(self.config, 'api_manager'):
                return self.config.api_manager.download_cyq_chips_paginated(
                    trade_date=trade_date,
                    ts_code=ts_code
                )
            else:
                # 如果没有API管理器，使用基本分页下载
                all_data = []
                offset = 0
                limit = 2000  # cyq_chips单次最大2000条

                while True:
                    try:
                        # 使用API管理器的速率限制（如果可用）
                        if hasattr(self.config, 'api_manager'):
                            self.config.api_manager._rate_limit('cyq_chips')

                        kwargs = {}
                        if trade_date:
                            kwargs['trade_date'] = trade_date
                        if ts_code:
                            kwargs['ts_code'] = ts_code
                        kwargs['offset'] = offset
                        kwargs['limit'] = limit

                        data = self.pro.cyq_chips(**kwargs)

                        if data is None or len(data) == 0:
                            break

                        all_data.append(data)

                        # 如果返回数据少于限制数量，说明已到最后一页
                        if len(data) < limit:
                            break

                        offset += limit

                        if offset > 50000:
                            self.logger.warning(f"cyq_chips pagination reached max offset: {offset}")
                            break

                    except Exception as e:
                        self.logger.error(f"Pagination download failed for cyq_chips, offset={offset}: {e}")
                        break

                return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()
        except Exception as e:
            self.logger.error(f"分页下载cyq_chips失败: {e}")
            # 回退到普通下载方法
            return self.download_cyq_chips(trade_date=trade_date, ts_code=ts_code)
```

### 2.2 缓存策略优化到现有架构

修改 `app/data_storage.py` 以添加更灵活的缓存策略（在现有基础上）：

```python
"""
Data storage module for aspipe_v4 - handles saving data in Parquet format with caching support
"""
import os
import pandas as pd
import polars as pl
from pathlib import Path
import logging
from datetime import datetime
import hashlib

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

def get_cache_path_with_params(data_type: str, **kwargs) -> str:
    """
    根据参数生成缓存路径 - 替代原始文档中的get_cache_path_with_custom_params
    这个函数会根据参数组合生成唯一的缓存路径
    """
    # 过滤出有效的参数
    valid_params = {k: v for k, v in kwargs.items() if v is not None}
    
    if not valid_params:
        return str(DATA_DIR / data_type / "all_data.parquet")
    
    # 按参数名称排序以确保生成相同的路径
    sorted_params = sorted(valid_params.items())
    
    # 创建参数标识符
    param_str = "_".join([f"{k}_{v}" for k, v in sorted_params])
    # 使用MD5哈希避免文件名太长的问题
    param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]
    
    # 根据主要参数确定子目录
    if 'trade_date' in valid_params and valid_params['trade_date']:
        trade_date = valid_params['trade_date']
        year = trade_date[:4]
        month = trade_date[4:6]
        subdir = f"daily/{year}/{month}"
        filename = f"{data_type}_{trade_date}_{param_hash}"
        return str(DATA_DIR / subdir / f"{filename}.parquet")
    elif 'ts_code' in valid_params and valid_params['ts_code']:
        ts_code = valid_params['ts_code']
        subdir = data_type
        filename = f"{ts_code}_{param_hash}"
        return str(DATA_DIR / subdir / f"{filename}.parquet")
    else:
        subdir = data_type
        filename = f"custom_{param_hash}"
        return str(DATA_DIR / subdir / f"{filename}.parquet")

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

def get_data_with_cache_fallback(data_type: str, cache_hours: int = 24, **kwargs):
    """
    通用缓存获取函数，适用于各接口模块
    """
    cache_path = get_cache_path_with_params(data_type, **kwargs)

    # 检查缓存是否存在且新鲜
    if is_data_cached(cache_path) and is_data_fresh(cache_path, max_age_hours=cache_hours):
        try:
            df = pd.read_parquet(cache_path)
            logger.info(f"Using cached data: {data_type}, path: {cache_path}")
            return df
        except Exception as e:
            logger.warning(f"Failed to read cache: {cache_path}, error: {e}")

    # 缓存不存在或过期，返回None表示需要从API获取
    return None
```

### 2.3 并行下载器的适配

修改 `app/utils/parallel_downloader.py` 以适配现有的分页方法：

```python
"""
并行下载管理器
"""
import logging
from typing import List, Dict
import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data_storage import save_to_parquet, get_cache_path, get_cache_path_with_params, is_data_cached


class ParallelDownloader:
    def __init__(self, config_manager):
        self.config = config_manager
        self.logger = logging.getLogger(__name__)
        self.download_lock = threading.Lock()

    def download_daily_type_parallel(self, data_type: str, trading_days: List[str]) -> Dict[str, int]:
        """
        并行下载特定日度数据类型
        """
        results = {}
        all_data = []

        # 为不同数据类型分配不同数量的线程
        if data_type == 'daily_basic':
            # daily_basic最慢，可用更多线程
            max_workers = min(8, len(trading_days))
        else:
            # 其他类型使用适度的线程数
            max_workers = min(4, len(trading_days))

        # 函数：下载单个日期的指定数据类型
        def download_single_day(trade_date):
            try:
                # 检查缓存
                cache_path = get_cache_path(data_type, trade_date)
                if is_data_cached(cache_path):
                    self.logger.info(f"使用缓存数据: {data_type} - {trade_date}")
                    df = pd.read_parquet(cache_path)
                    return (trade_date, df, len(df))

                # 获取API管理器
                api_manager = self.config.api_manager
                
                # 根据数据类型调用相应接口的分页方法
                if data_type == 'daily':
                    df = api_manager.daily_data.download_daily_data(ts_code=None, start_date=trade_date, end_date=trade_date)
                elif data_type == 'daily_basic':
                    # 使用分页下载
                    df = api_manager.daily_data.download_daily_basic_paginated(trade_date=trade_date)
                elif data_type == 'moneyflow':
                    # 使用分页下载
                    df = api_manager.market_flow.download_moneyflow_paginated(trade_date=trade_date)
                elif data_type == 'moneyflow_dc':
                    df = api_manager.market_flow.download_moneyflow_dc(trade_date=trade_date)
                elif data_type == 'moneyflow_ths':
                    df = api_manager.market_flow.download_moneyflow_ths(trade_date=trade_date)
                elif data_type == 'moneyflow_ind_dc':
                    df = api_manager.market_flow.download_moneyflow_ind_dc(trade_date=trade_date)
                elif data_type == 'moneyflow_mkt_dc':
                    df = api_manager.market_flow.download_moneyflow_mkt_dc(trade_date=trade_date)
                elif data_type == 'moneyflow_cnt_ths':
                    df = api_manager.market_flow.download_moneyflow_cnt_ths(trade_date=trade_date)
                elif data_type == 'moneyflow_ind_ths':
                    df = api_manager.market_flow.download_moneyflow_ind_ths(trade_date=trade_date)
                elif data_type == 'stk_factor':
                    # 使用API管理器的分页下载
                    df = api_manager.download_stk_factor_paginated(trade_date=trade_date)
                elif data_type == 'stk_factor_pro':
                    df = api_manager.technical_factors.download_stk_factor_pro(trade_date=trade_date)
                elif data_type == 'cyq_perf':
                    # 使用API管理器的分页下载
                    df = api_manager.download_cyq_perf_paginated(trade_date=trade_date)
                elif data_type == 'cyq_chips':
                    # 使用API管理器的分页下载
                    df = api_manager.download_cyq_chips_paginated(trade_date=trade_date)
                else:
                    # 默认处理方式
                    try:
                        # 尝试动态调用接口
                        if data_type in ['income', 'balancesheet', 'cashflow', 'fina_indicator']:
                            # 使用财务数据接口
                            df = getattr(api_manager.financial_data, f'download_{data_type}')(trade_date=trade_date)
                        elif data_type in [dt.replace('_', '') for dt in api_manager.get_available_data_types()]:
                            # 尝试日度数据接口
                            df = getattr(api_manager.daily_data, f'download_{data_type}')(trade_date=trade_date)
                        else:
                            # 尝试使用API管理器的通用方法
                            try:
                                api_func = getattr(api_manager.pro, data_type)
                                df = api_manager.download_with_pagination(api_func, limit_per_call=6000, trade_date=trade_date)
                            except AttributeError:
                                self.logger.warning(f"未知的数据类型: {data_type}")
                                return (trade_date, pd.DataFrame(), 0)
                    except AttributeError:
                        self.logger.warning(f"未知的数据类型: {data_type}")
                        return (trade_date, pd.DataFrame(), 0)

                if not df.empty:
                    # 添加交易日期标记
                    if 'trade_date' not in df.columns:
                        df['trade_date'] = pd.to_datetime(trade_date)
                    else:
                        # 如果列已存在，确保其是datetime格式
                        df['trade_date'] = pd.to_datetime(df['trade_date'])

                    # 保存到本地
                    year = trade_date[:4]
                    month = trade_date[4:6]
                    subdir = f"daily/{year}/{month}"
                    filename = f"{data_type}_{trade_date}"

                    with self.download_lock:
                        file_path = save_to_parquet(df, filename, subdir=subdir)

                    self.logger.debug(f"成功下载 {data_type} - {trade_date}: {len(df)} 条记录")
                    return (trade_date, df, len(df))
                else:
                    self.logger.warning(f"{data_type} - {trade_date} 无数据")
                    return (trade_date, pd.DataFrame(), 0)

            except Exception as e:
                self.logger.error(f"下载 {data_type} - {trade_date} 失败: {e}")
                return (trade_date, pd.DataFrame(), 0)

        # 并行下载所有日期的数据
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有任务
            futures = {
                executor.submit(download_single_day, day): day
                for day in trading_days
            }

            # 收集结果
            for future in as_completed(futures):
                trade_date, df, record_count = future.result()
                if not df.empty and record_count > 0:
                    all_data.append(df)
                    results[trade_date] = record_count

        # 合并结果
        final_result = {}
        if all_data:
            # 按月分组数据(如果需要进一步组织存储)
            combined_df = pd.concat(all_data, ignore_index=True)
            if 'trade_date' in combined_df.columns:
                date_groups = combined_df.groupby(combined_df['trade_date'].dt.strftime('%Y-%m'))
                for (year_month), group in date_groups:
                    year, month = year_month.split('-')
                    subdir = f"daily/{year}/{month}"
                    filename = f"{data_type}_{year_month}"
                    file_path = save_to_parquet(group, filename, subdir=subdir)
                    final_result[year_month] = len(group)

        return final_result
```

## 3. 实现建议

### 3.1 分布式架构适配
- 将分页功能添加到相应的接口类中，而不是集中在API管理器
- 遵循现有的继承结构和基类设计

### 3.2 渐进式增强
- 保持现有接口兼容性
- 逐步添加分页功能到现有接口
- 确保不影响现有功能

### 3.3 配置化分页参数
基于不同接口的API限制设置合适的分页参数：

```python
# 在配置管理器中添加分页参数配置
PAGINATION_LIMITS = {
    'stk_factor': 10000,
    'stk_factor_pro': 10000,
    'cyq_perf': 5000,
    'cyq_chips': 2000,
    'daily_basic': 6000,
    'moneyflow': 6000,
    'daily': 8000,
    'income': 3000,
    'balancesheet': 3000,
    'cashflow': 3000,
    'fina_indicator': 3000
}
```

## 4. 部署和集成

### 4.1 模块化集成
- 将新功能添加到现有的接口模块中
- 保持与现有架构的一致性
- 确保向后兼容性

### 4.2 测试策略
- 为每个接口类的分页功能编写单元测试
- 验证缓存策略的有效性
- 测试并行下载的性能提升

### 4.3 渐进式部署
- 逐步启用各接口的分页功能
- 监控性能和稳定性
- 根据积分等级动态调整分页参数

## 5. 总结

这个修正版文档解决了以下原始文档中的问题：

1. **导入路径**：改为相对导入 `from .base import BaseDownloader`
2. **API调用方式**：通过接口类的适当方法，利用API管理器的速率限制
3. **缓存函数**：使用 `get_cache_path_with_params` 替代不存在的 `get_cache_path_with_custom_params`
4. **错误处理和日志**：增加了适当的错误处理和日志记录
5. **与现有分页兼容**：考虑到API管理器中已有的分页功能，避免重复实现

这个版本更好地与现有项目架构兼容，并提供了可实施的解决方案。