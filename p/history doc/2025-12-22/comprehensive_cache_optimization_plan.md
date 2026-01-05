# 全面缓存优化方案：解决所有接口重复下载数据问题

## 问题概述

在当前系统中，重复下载相同数据时没有命中缓存，导致不必要的API调用和资源浪费。不仅限于stk_rewards等特定接口，而是所有接口都可能存在的缓存键不匹配问题。

## 问题分析

### 1. 根本原因

1. **缓存键不匹配**
   - 下载参数与缓存键生成逻辑不一致
   - 单个股票下载与全量数据缓存之间的不匹配
   - 参数顺序和格式在不同模块中不统一

2. **下载策略与缓存策略不一致**
   - 不同接口使用不同的参数组合进行下载和缓存
   - 缺乏统一的缓存键生成机制

3. **缓存文件命名和组织结构不一致**
   - 不同模块使用不同的缓存路径和文件命名规则

## 解决方案

### 方案一：统一缓存键生成机制

#### 1. 创建缓存键生成器

创建 `cache_key_generator.py` 模块：

```python
"""
缓存键生成器 - 统一管理所有接口的缓存键生成逻辑
"""
import hashlib
from typing import Dict, Any
from pathlib import Path
import pandas as pd

# Data directory configuration - use absolute path from project root
DATA_DIR = Path(__file__).parent.parent / 'data'
DATA_DIR.mkdir(exist_ok=True)

class CacheKeyGenerator:
    """
    统一的缓存键生成器，为所有接口生成标准化的缓存键
    """
    
    @staticmethod
    def generate_cache_path(interface_name: str, **kwargs) -> str:
        """
        生成标准化的缓存路径
        
        Args:
            interface_name: 接口名称
            **kwargs: 接口参数
        
        Returns:
            标准化缓存路径
        """
        # 根据接口类型和参数生成路径
        if interface_name in ['daily', 'daily_basic', 'moneyflow', 'moneyflow_dc', 'moneyflow_ths',
                             'moneyflow_ind_dc', 'moneyflow_mkt_dc', 'moneyflow_cnt_ths',
                             'moneyflow_ind_ths', 'stk_factor', 'stk_factor_pro', 'cyq_perf', 'cyq_chips']:
            # 日度数据接口
            return CacheKeyGenerator._generate_daily_cache_path(interface_name, **kwargs)
        elif interface_name in ['income', 'balancesheet', 'cashflow', 'fina_indicator',
                               'dividend', 'forecast', 'express', 'top10_holders',
                               'top10_floatholders', 'stk_surv']:
            # 财务数据接口
            return CacheKeyGenerator._generate_financial_cache_path(interface_name, **kwargs)
        elif interface_name in ['stock_basic', 'trade_cal', 'new_share', 'stock_company',
                               'stock_st', 'bak_basic', 'namechange', 'stk_rewards',
                               'stk_managers', 'broker_recommend']:
            # 静态数据接口
            return CacheKeyGenerator._generate_static_cache_path(interface_name, **kwargs)
        else:
            # 默认处理
            return CacheKeyGenerator._generate_default_cache_path(interface_name, **kwargs)

    @staticmethod
    def _generate_daily_cache_path(interface_name: str, **kwargs) -> str:
        """
        生成日度数据接口的缓存路径
        """
        if 'ts_code' in kwargs and kwargs['ts_code']:
            ts_code = kwargs['ts_code']
            if 'trade_date' in kwargs and kwargs['trade_date']:
                # 单日数据: data/daily/interface_name/ts_code/yyyy/mm/dd.parquet
                trade_date = kwargs['trade_date']
                year = trade_date[:4]
                month = trade_date[4:6]
                day = trade_date[6:8] if len(trade_date) >= 8 else trade_date[4:8]
                subdir = f"daily/{interface_name}/{ts_code}/{year}/{month}"
                filename = f"{trade_date}.parquet"
            elif 'start_date' in kwargs and 'end_date' in kwargs:
                # 日期范围数据: data/daily/interface_name/ts_code/yyyy/yyyy_start-end.parquet
                start_date = kwargs['start_date']
                end_date = kwargs['end_date']
                year = start_date[:4]
                subdir = f"daily/{interface_name}/{ts_code}/{year}"
                filename = f"{start_date}-{end_date}.parquet"
            else:
                # 单股票全量数据: data/daily/interface_name/ts_code/all.parquet
                subdir = f"daily/{interface_name}/{ts_code}"
                filename = "all.parquet"
        elif 'trade_date' in kwargs and kwargs['trade_date']:
            # 全市场日度数据: data/daily/interface_name/yyyy/mm/dd.parquet
            trade_date = kwargs['trade_date']
            year = trade_date[:4]
            month = trade_date[4:6]
            day = trade_date[6:8] if len(trade_date) >= 8 else trade_date[4:8]
            subdir = f"daily/{interface_name}/{year}/{month}"
            filename = f"{trade_date}.parquet"
        elif 'start_date' in kwargs and 'end_date' in kwargs:
            # 全市场日期范围数据: data/daily/interface_name/yyyy/yyyy_start-end.parquet
            start_date = kwargs['start_date']
            end_date = kwargs['end_date']
            year = start_date[:4]
            subdir = f"daily/{interface_name}/{year}"
            filename = f"{start_date}-{end_date}.parquet"
        else:
            # 全量数据: data/daily/interface_name/all_data.parquet
            subdir = f"daily/{interface_name}"
            filename = "all_data.parquet"

        full_path = DATA_DIR / subdir / filename
        full_path.parent.mkdir(parents=True, exist_ok=True)
        return str(full_path)

    @staticmethod
    def _generate_financial_cache_path(interface_name: str, **kwargs) -> str:
        """
        生成财务数据接口的缓存路径
        """
        if 'ts_code' in kwargs and kwargs['ts_code']:
            ts_code = kwargs['ts_code']
            if 'period' in kwargs and kwargs['period']:
                # 单股票单期数据: data/financial/interface_name/ts_code/yyyy/period.parquet
                period = kwargs['period']
                year = period[:4]
                subdir = f"financial/{interface_name}/{ts_code}/{year}"
                filename = f"{period}.parquet"
            else:
                # 单股票全量数据: data/financial/interface_name/ts_code/all.parquet
                subdir = f"financial/{interface_name}/{ts_code}"
                filename = "all.parquet"
        elif 'period' in kwargs and kwargs['period']:
            # 全市场单期数据: data/financial/interface_name/yyyy/period.parquet
            period = kwargs['period']
            year = period[:4]
            subdir = f"financial/{interface_name}/{year}"
            filename = f"{period}.parquet"
        else:
            # 全量数据: data/financial/interface_name/all_data.parquet
            subdir = f"financial/{interface_name}"
            filename = "all_data.parquet"

        full_path = DATA_DIR / subdir / filename
        full_path.parent.mkdir(parents=True, exist_ok=True)
        return str(full_path)

    @staticmethod
    def _generate_static_cache_path(interface_name: str, **kwargs) -> str:
        """
        生成静态数据接口的缓存路径
        """
        if 'ts_code' in kwargs and kwargs['ts_code']:
            ts_code = kwargs['ts_code']
            subdir = f"static/{interface_name}/{ts_code}"
            filename = "data.parquet"
        else:
            # 全量数据: data/static/interface_name/all_data.parquet
            subdir = f"static/{interface_name}"
            filename = "all_data.parquet"

        full_path = DATA_DIR / subdir / filename
        full_path.parent.mkdir(parents=True, exist_ok=True)
        return str(full_path)

    @staticmethod
    def _generate_default_cache_path(interface_name: str, **kwargs) -> str:
        """
        生成默认缓存路径（使用参数哈希）
        """
        # 使用参数生成哈希作为文件名
        param_str = str(sorted(kwargs.items()))
        param_hash = hashlib.md5(param_str.encode()).hexdigest()[:16]
        subdir = f"misc/{interface_name}"
        filename = f"{param_hash}.parquet"

        full_path = DATA_DIR / subdir / filename
        full_path.parent.mkdir(parents=True, exist_ok=True)
        return str(full_path)

    @staticmethod
    def generate_cache_key(interface_name: str, **kwargs) -> str:
        """
        生成缓存键字符串，用于在缓存系统中标识数据
        """
        # 只保留影响数据结果的关键参数
        cache_key = {'interface': interface_name}
        for key in ['ts_code', 'trade_date', 'start_date', 'end_date', 'period']:
            if key in kwargs and kwargs[key] is not None:
                cache_key[key] = kwargs[key]
        
        # 生成标准化的缓存键
        key_parts = [interface_name]
        for key in sorted(cache_key.keys()):
            if key != 'interface':
                key_parts.append(f"{key}={cache_key[key]}")
        
        return "|".join(key_parts)

    @staticmethod
    def extract_params_from_cache_path(cache_path: str) -> Dict[str, Any]:
        """
        从缓存路径中提取参数（用于缓存匹配）
        """
        path = Path(cache_path)
        parts = path.parts
        
        # 提取接口名称和参数
        params = {}
        
        # 从路径中提取可能的参数
        for i, part in enumerate(parts):
            if part == 'daily':
                if i + 1 < len(parts):
                    params['interface'] = parts[i + 1]
            elif part == 'financial':
                if i + 1 < len(parts):
                    params['interface'] = parts[i + 1]
            elif part == 'static':
                if i + 1 < len(parts):
                    params['interface'] = parts[i + 1]
        
        # 从文件名中提取日期或报告期
        filename = path.stem
        if '-' in filename and len(filename) >= 17:  # 日期范围格式: 20220101-20221231
            start_date, end_date = filename.split('-')
            params['start_date'] = start_date
            params['end_date'] = end_date
        elif len(filename) == 8 and filename.isdigit():  # 日期格式: 20220101
            params['trade_date'] = filename
        elif len(filename) == 8 and filename.isdigit() and int(filename[4:6]) > 0 and int(filename[4:6]) <= 12:  # 报告期格式: 20220331
            params['period'] = filename
        
        return params
```

#### 2. 修改 data_storage.py 使用统一缓存键生成器

```python
def get_interface_cache_path(data_type: str, **kwargs) -> str:
    """
    生成缓存路径 - 使用统一的缓存键生成器
    """
    from cache_key_generator import CacheKeyGenerator
    return CacheKeyGenerator.generate_cache_path(data_type, **kwargs)


def is_interface_data_cached(data_type: str, cache_ttl_hours: int = 24, **kwargs) -> bool:
    """
    检查接口数据是否已缓存且未过期
    增加对全量缓存的检查和智能匹配
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
        from .utils.date_utils import date_range_overlap
        # 实现日期范围重叠检查逻辑

    return False


def load_interface_cached_data(data_type: str, **kwargs) -> pd.DataFrame:
    """
    加载接口的缓存数据
    增加对全量缓存的支持和智能提取
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
    保存接口数据到缓存
    同时更新全量缓存和相关缓存
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
```

### 方案二：增强下载策略中的缓存逻辑

#### 1. 修改 download_strategies.py 中的 DownloadStrategy 基类

```python
def download_with_cache(self, **kwargs):
    """带缓存的下载方法 - 改进的智能缓存逻辑"""
    from cache_key_generator import CacheKeyGenerator
    
    # 生成标准化缓存键
    cache_key = CacheKeyGenerator.generate_cache_key(self.interface_name, **kwargs)

    # 如果启用缓存，检查缓存
    if self.cache_enabled:
        # 使用改进的缓存检查逻辑
        cached_result = self.load_cached(self.interface_name, **kwargs)
        if not cached_result.empty:
            self.logger.info(f"使用缓存数据: {self.interface_name}")
            return cached_result

    # 执行实际下载
    result = self.download(**kwargs)

    # 保存到缓存
    if self.cache_enabled and not result.empty:
        save_success = self.save_cached(result, self.interface_name, **kwargs)
        if save_success:
            self.logger.info(f"数据已保存到缓存: {self.interface_name}")
        else:
            self.logger.warning(f"数据保存到缓存失败: {self.interface_name}")

    return result
```

### 方案三：实现缓存预热和智能清理机制

#### 1. 创建缓存管理器

```python
"""
缓存管理器 - 实现缓存预热、清理和监控功能
"""
import os
import shutil
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import logging

class CacheManager:
    """
    缓存管理器，提供缓存预热、清理和监控功能
    """
    
    def __init__(self):
        self.data_dir = Path(__file__).parent.parent / 'data'
        self.logger = logging.getLogger(__name__)

    def warm_cache(self, interfaces: list, date_range: tuple = None):
        """
        预热缓存 - 提前下载常用数据
        """
        from download_scheduler import DownloadScheduler
        
        if not date_range:
            # 使用最近一个月的数据作为默认预热范围
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
        else:
            start_date, end_date = date_range

        scheduler = DownloadScheduler(start_date, end_date)
        scheduler.schedule_download_tasks(interfaces)
        scheduler.execute_scheduled_tasks(wait_for_completion=True)

    def clean_expired_cache(self, max_age_hours: int = 168):  # 默认保留7天内的缓存
        """
        清理过期缓存文件
        """
        current_time = datetime.now().timestamp()
        cleaned_count = 0
        
        for root, dirs, files in os.walk(self.data_dir):
            for file in files:
                if file.endswith('.parquet'):
                    file_path = Path(root) / file
                    file_mtime = file_path.stat().st_mtime
                    age_hours = (current_time - file_mtime) / 3600
                    
                    if age_hours > max_age_hours:
                        try:
                            file_path.unlink()
                            self.logger.info(f"删除过期缓存: {file_path}, 年龄: {age_hours:.2f}小时")
                            cleaned_count += 1
                        except Exception as e:
                            self.logger.error(f"删除缓存文件失败: {file_path}, 错误: {e}")
        
        self.logger.info(f"缓存清理完成，删除了 {cleaned_count} 个过期文件")
        return cleaned_count

    def get_cache_stats(self):
        """
        获取缓存统计信息
        """
        total_files = 0
        total_size = 0
        daily_cache_count = 0
        financial_cache_count = 0
        static_cache_count = 0
        
        for root, dirs, files in os.walk(self.data_dir):
            for file in files:
                if file.endswith('.parquet'):
                    file_path = Path(root) / file
                    total_files += 1
                    total_size += file_path.stat().st_size
                    
                    # 统计不同类型缓存
                    if 'daily' in str(file_path):
                        daily_cache_count += 1
                    elif 'financial' in str(file_path):
                        financial_cache_count += 1
                    elif 'static' in str(file_path):
                        static_cache_count += 1
        
        return {
            'total_cache_files': total_files,
            'total_cache_size_mb': total_size / (1024 * 1024),
            'daily_cache_count': daily_cache_count,
            'financial_cache_count': financial_cache_count,
            'static_cache_count': static_cache_count,
            'last_updated': datetime.now().isoformat()
        }

    def validate_cache_integrity(self):
        """
        验证缓存文件完整性
        """
        corrupted_files = []
        
        for root, dirs, files in os.walk(self.data_dir):
            for file in files:
                if file.endswith('.parquet'):
                    file_path = Path(root) / file
                    try:
                        # 尝试读取文件验证完整性
                        df = pd.read_parquet(file_path)
                        if df is None or df.empty:
                            corrupted_files.append(str(file_path))
                    except Exception as e:
                        self.logger.warning(f"缓存文件损坏: {file_path}, 错误: {e}")
                        corrupted_files.append(str(file_path))
        
        return corrupted_files
```

### 方案四：实现缓存命中监控和报告

#### 1. 添加缓存监控功能

```python
"""
缓存监控模块 - 跟踪缓存命中率和性能
"""
import time
from datetime import datetime
import json
from pathlib import Path
import logging

class CacheMonitor:
    """
    缓存监控器，跟踪缓存命中率和性能指标
    """
    
    def __init__(self):
        self.cache_hits = 0
        self.cache_misses = 0
        self.download_count = 0
        self.start_time = time.time()
        self.logger = logging.getLogger(__name__)
        self.stats_file = Path(__file__).parent.parent / 'log' / 'cache_stats.json'

    def record_cache_hit(self, interface_name: str):
        """
        记录缓存命中
        """
        self.cache_hits += 1
        self.logger.info(f"缓存命中: {interface_name}")

    def record_cache_miss(self, interface_name: str):
        """
        记录缓存未命中
        """
        self.cache_misses += 1
        self.logger.info(f"缓存未命中: {interface_name}")

    def record_download(self, interface_name: str, record_count: int):
        """
        记录下载操作
        """
        self.download_count += 1
        self.logger.info(f"执行下载: {interface_name}, 记录数: {record_count}")

    def get_hit_rate(self) -> float:
        """
        计算缓存命中率
        """
        total_requests = self.cache_hits + self.cache_misses
        if total_requests == 0:
            return 0.0
        return self.cache_hits / total_requests

    def get_stats(self) -> dict:
        """
        获取缓存统计信息
        """
        total_requests = self.cache_hits + self.cache_misses
        uptime = time.time() - self.start_time
        
        stats = {
            'cache_hits': self.cache_hits,
            'cache_misses': self.cache_misses,
            'total_requests': total_requests,
            'hit_rate': self.get_hit_rate(),
            'download_count': self.download_count,
            'uptime_seconds': uptime,
            'requests_per_minute': (total_requests / uptime * 60) if uptime > 0 else 0,
            'timestamp': datetime.now().isoformat()
        }
        
        return stats

    def save_stats(self):
        """
        保存统计信息到文件
        """
        stats = self.get_stats()
        with open(self.stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)

    def load_stats(self):
        """
        从文件加载统计信息
        """
        if self.stats_file.exists():
            with open(self.stats_file, 'r', encoding='utf-8') as f:
                stats = json.load(f)
                self.cache_hits = stats.get('cache_hits', 0)
                self.cache_misses = stats.get('cache_misses', 0)
                self.download_count = stats.get('download_count', 0)
                self.start_time = time.time() - stats.get('uptime_seconds', 0)
```

## 实施步骤

### 第一步：创建新的缓存键生成器模块
```bash
# 创建 cache_key_generator.py 文件
touch /home/quan/testdata/aspipe_v4/app/cache_key_generator.py
```

### 第二步：修改 data_storage.py
1. 更新 `get_interface_cache_path` 函数
2. 更新 `is_interface_data_cached` 函数
3. 更新 `load_interface_cached_data` 函数
4. 更新 `save_interface_data_to_cache` 函数

### 第三步：更新下载策略
1. 修改 `download_strategies.py` 中的缓存逻辑

### 第四步：创建缓存管理器和监控模块
1. 创建 `cache_manager.py`
2. 创建 `cache_monitor.py`

### 第五步：更新主要调度器
1. 修改 `download_scheduler.py` 集成新的缓存监控

## 预期效果

1. **全面解决缓存命中问题**：通过统一的缓存键生成机制，解决所有接口的缓存不匹配问题
2. **智能缓存匹配**：实现从全量数据中提取特定查询结果的能力
3. **提高缓存效率**：通过缓存预热和智能清理，优化存储使用
4. **可监控性**：通过缓存监控，实时了解缓存性能

## 风险评估

### 低风险
- 缓存逻辑变更不会影响核心下载功能
- 新增模块向后兼容

### 注意事项
- 需要确保现有缓存文件的兼容性
- 需要在多线程环境下确保缓存文件访问的安全性
- 需要充分测试各种参数组合的缓存行为

## 后续优化建议

1. **分布式缓存**：支持Redis等分布式缓存系统
2. **缓存压缩**：对大型缓存文件进行压缩存储
3. **智能预取**：基于使用模式预测可能需要的数据并提前缓存
4. **缓存层级**：实现多级缓存策略（内存+磁盘）