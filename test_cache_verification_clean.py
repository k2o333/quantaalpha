#!/usr/bin/env python3
"""
Test script to verify that the cache is working properly with a clean test case
"""

import sys
from pathlib import Path
import pandas as pd

# Add the app directory to the path so we can import modules
sys.path.insert(0, str(Path(__file__).parent / 'app'))

from app.data_storage import get_cached_or_download_data, get_interface_cache_path
from app.cache_monitor import get_cache_monitor_stats, get_cache_hit_rate
import tushare as ts
from pathlib import Path

def dummy_download_func(**kwargs):
    """模拟下载函数，仅用于测试缓存机制"""
    print(f"执行下载函数，参数: {kwargs}")
    # 返回一些测试数据
    test_data = pd.DataFrame({
        "id": [1, 2, 3],
        "value": [10, 20, 30],
        "param": [str(kwargs)] * 3
    })
    return test_data

def test_cache_mechanism():
    """测试缓存机制是否正常工作"""
    print("测试缓存机制...")

    # 确保使用一个不会与现有缓存冲突的接口名称
    test_interface = "test_cache_interface"
    test_param_value = "test_value_123"

    print(f"测试接口名称: {test_interface}")
    print(f"测试参数值: {test_param_value}")

    print("\n第一次调用 - 应该未命中缓存:")
    result1 = get_cached_or_download_data(
        data_type=test_interface,
        download_func=dummy_download_func,
        test_param=test_param_value
    )
    print(f"第一次结果记录数: {len(result1)}")
    print(f"第一次结果内容: {result1.head()}")

    print("\n第二次调用 - 应该命中缓存:")
    result2 = get_cached_or_download_data(
        data_type=test_interface,
        download_func=dummy_download_func,
        test_param=test_param_value
    )
    print(f"第二次结果记录数: {len(result2)}")
    print(f"第二次结果内容: {result2.head()}")

    # 检查结果是否相同
    if result1.equals(result2):
        print("✓ 两次结果相同 - 缓存机制正常工作")
    else:
        print("✗ 两次结果不同 - 缓存可能未正常工作")

    # 检查缓存文件是否创建
    cache_path = get_interface_cache_path(test_interface, test_param=test_param_value)
    cache_path_obj = Path(cache_path)
    if cache_path_obj.exists():
        print(f"缓存文件已创建: {cache_path}")
    else:
        print(f"缓存文件未找到: {cache_path}")

if __name__ == "__main__":
    test_cache_mechanism()