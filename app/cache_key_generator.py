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


# 全局缓存键生成器实例
cache_key_generator = CacheKeyGenerator()


def get_cache_path(interface_name: str, **kwargs) -> str:
    """
    便捷函数：获取缓存路径
    """
    return cache_key_generator.generate_cache_path(interface_name, **kwargs)


def get_cache_key(interface_name: str, **kwargs) -> str:
    """
    便捷函数：获取缓存键
    """
    return cache_key_generator.generate_cache_key(interface_name, **kwargs)