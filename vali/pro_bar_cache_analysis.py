#!/usr/bin/env python3
"""
分析pro_bar接口缓存不激活的问题
"""

import sys
import os
sys.path.append('/home/quan/testdata/aspipe_v4')

from app.strategy_factory import get_strategy
from app.tushare_api import TuShareDownloader
from app.download_strategies import DailyDataStrategy
from app.data_storage import get_interface_cache_path, is_interface_data_cached, load_interface_cached_data
from app.cache_key_generator import CacheKeyGenerator
import time
import logging

# 设置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_pro_bar_cache_mechanism():
    """
    测试pro_bar接口的缓存机制
    """
    print("=" * 60)
    print("测试pro_bar接口缓存机制")
    print("=" * 60)

    # 初始化下载器和策略
    downloader = TuShareDownloader()
    strategy = DailyDataStrategy('pro_bar', downloader)

    # 测试参数
    test_params = {
        'ts_code': '000001.SZ',
        'start_date': '20230101',
        'end_date': '20230110',
        'adj': 'qfq',
        'freq': 'D'
    }

    print(f"测试参数: {test_params}")

    # 1. 检查缓存键生成
    print("\n1. 检查缓存键生成...")
    cache_path = CacheKeyGenerator.generate_cache_path('pro_bar', **test_params)
    print(f"生成的缓存路径: {cache_path}")

    # 2. 检查缓存是否已存在
    print("\n2. 检查缓存是否存在...")
    is_cached = is_interface_data_cached('pro_bar', **test_params)
    print(f"缓存状态: {is_cached}")

    if is_cached:
        cached_data = load_interface_cached_data('pro_bar', **test_params)
        print(f"缓存数据条数: {len(cached_data)}")

    # 3. 检查策略是否使用缓存
    print("\n3. 检查策略的缓存设置...")
    print(f"策略是否启用缓存: {strategy.cache_enabled}")
    print(f"策略缓存TTL: {strategy.cache_ttl_hours}")
    print(f"策略接口名称: {strategy.interface_name}")

    # 4. 尝试调用download_with_cache方法
    print("\n4. 尝试调用download_with_cache方法...")
    try:
        start_time = time.time()
        result = strategy.download_with_cache(**test_params)
        duration = time.time() - start_time

        print(f"调用耗时: {duration:.2f}秒")
        print(f"返回数据条数: {len(result) if result is not None else 0}")

        # 根据耗时判断是否使用了缓存
        if duration < 1.0:  # 假设1秒内完成的是从缓存读取
            print("✓ 可能使用了缓存")
        else:
            print("✗ 可能进行了实际下载")

    except Exception as e:
        print(f"调用download_with_cache失败: {e}")
        import traceback
        traceback.print_exc()

    # 5. 对比：直接调用download方法
    print("\n5. 直接调用download方法...")
    try:
        start_time = time.time()
        result_direct = strategy.download(**test_params)
        duration_direct = time.time() - start_time

        print(f"直接调用耗时: {duration_direct:.2f}秒")
        print(f"直接调用数据条数: {len(result_direct) if result_direct is not None else 0}")

    except Exception as e:
        print(f"调用download失败: {e}")
        import traceback
        traceback.print_exc()

def test_strategy_factory():
    """
    测试策略工厂创建的pro_bar策略
    """
    print("\n" + "=" * 60)
    print("测试策略工厂创建的pro_bar策略")
    print("=" * 60)

    try:
        strategy = get_strategy('pro_bar')
        print(f"策略类型: {type(strategy)}")
        print(f"接口名称: {strategy.interface_name}")
        print(f"是否启用缓存: {strategy.cache_enabled}")
        print(f"缓存TTL: {strategy.cache_ttl_hours}")

        # 测试缓存相关方法
        test_params = {
            'ts_code': '000001.SZ',
            'start_date': '20230101',
            'end_date': '20230110',
            'adj': 'qfq',
            'freq': 'D'
        }

        # 检查是否可以使用缓存
        can_use = strategy._can_use_cache(**test_params)
        print(f"是否可以使用缓存: {can_use}")

    except Exception as e:
        print(f"获取pro_bar策略失败: {e}")
        import traceback
        traceback.print_exc()

def test_cache_paths():
    """
    测试不同参数组合的缓存路径
    """
    print("\n" + "=" * 60)
    print("测试不同参数组合的缓存路径")
    print("=" * 60)

    test_cases = [
        {
            'ts_code': '000001.SZ',
            'start_date': '20230101',
            'end_date': '20230110',
            'adj': 'qfq',
            'freq': 'D'
        },
        {
            'ts_code': '000001.SZ',
            'start_date': '20230101',
            'end_date': '20230110',
            'adj': 'qfq',
            'freq': 'D'
        },
        {
            'ts_code': '000002.SZ',  # 不同股票
            'start_date': '20230101',
            'end_date': '20230110',
            'adj': 'qfq',
            'freq': 'D'
        }
    ]

    paths = []
    for i, params in enumerate(test_cases):
        path = CacheKeyGenerator.generate_cache_path('pro_bar', **params)
        paths.append(path)
        print(f"测试用例 {i+1}: {params}")
        print(f"  缓存路径: {path}")
        print(f"  路径存在: {os.path.exists(path)}")
        print()

    # 检查路径是否一致
    all_same = all(p == paths[0] for p in paths)
    print(f"前两个参数相同的测试用例是否生成相同路径: {all_same}")

    if not all_same:
        print("⚠️  相同参数生成了不同路径，这会导致缓存问题！")

def compare_with_daily():
    """
    对比pro_bar接口与daily接口的缓存行为
    """
    print("\n" + "=" * 60)
    print("对比pro_bar接口与daily接口的缓存行为")
    print("=" * 60)

    downloader = TuShareDownloader()

    # 测试daily接口
    print("测试daily接口...")
    daily_strategy = DailyDataStrategy('daily', downloader)
    print(f"daily策略缓存设置: enabled={daily_strategy.cache_enabled}, ttl={daily_strategy.cache_ttl_hours}")

    daily_params = {
        'start_date': '20230101',
        'end_date': '20230110'
    }

    daily_cache_path = CacheKeyGenerator.generate_cache_path('daily', **daily_params)
    print(f"daily缓存路径: {daily_cache_path}")

    # 测试pro_bar接口
    print("\n测试pro_bar接口...")
    pro_bar_strategy = DailyDataStrategy('pro_bar', downloader)
    print(f"pro_bar策略缓存设置: enabled={pro_bar_strategy.cache_enabled}, ttl={pro_bar_strategy.cache_ttl_hours}")

    pro_bar_params = {
        'ts_code': '000001.SZ',
        'start_date': '20230101',
        'end_date': '20230110',
        'adj': 'qfq',
        'freq': 'D'
    }

    pro_bar_cache_path = CacheKeyGenerator.generate_cache_path('pro_bar', **pro_bar_params)
    print(f"pro_bar缓存路径: {pro_bar_cache_path}")

    # 检查配置
    from app.config_adapter import get_interface_cache_settings
    daily_cache_config = get_interface_cache_settings('daily')
    pro_bar_cache_config = get_interface_cache_settings('pro_bar')

    print(f"\ndaily缓存配置: {daily_cache_config}")
    print(f"pro_bar缓存配置: {pro_bar_cache_config}")

if __name__ == "__main__":
    print("开始分析pro_bar接口缓存问题...")

    # 运行各项测试
    test_cache_paths()
    test_strategy_factory()
    test_pro_bar_cache_mechanism()
    compare_with_daily()

    print("\n" + "=" * 60)
    print("分析总结:")
    print("1. 检查缓存键生成是否一致")
    print("2. 检查策略是否正确启用缓存")
    print("3. 比较不同接口的缓存行为")
    print("=" * 60)