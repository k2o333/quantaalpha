#!/usr/bin/env python3
"""
Test script to verify that the cache is working properly
"""

import sys
from pathlib import Path
import pandas as pd

# Add the app directory to the path so we can import modules
sys.path.insert(0, str(Path(__file__).parent / 'app'))

from app.data_storage import get_cached_or_download_data
from app.cache_monitor import get_cache_monitor_stats, get_cache_hit_rate
import tushare as ts

def dummy_download_func(**kwargs):
    """模拟下载函数，仅用于测试缓存机制"""
    print(f"执行下载函数: {kwargs}")
    import pandas as pd
    return pd.DataFrame({"test": [1, 2, 3]})

def test_cache_mechanism():
    """测试缓存机制是否正常工作"""
    print("测试缓存机制...")

    print("第一次调用 - 应该未命中缓存:")
    result1 = get_cached_or_download_data(
        data_type='stock_basic',
        download_func=dummy_download_func,
        test_param='value'
    )
    print(f"第一次结果: {len(result1)} records")

    print("\n第二次调用 - 应该命中缓存:")
    result2 = get_cached_or_download_data(
        data_type='stock_basic',
        download_func=dummy_download_func,
        test_param='value'
    )
    print(f"第二次结果: {len(result2)} records")

    # 检查缓存统计
    stats = get_cache_monitor_stats()
    print(f"\n缓存统计: {stats}")
    print(f"缓存命中率: {get_cache_hit_rate():.2%}")

if __name__ == "__main__":
    test_cache_mechanism()