#!/usr/bin/env python3
"""
测试download_strategies中pro_bar的缓存调用
"""

import sys
import os
sys.path.append('/home/quan/testdata/aspipe_v4')

def test_strategy_cache_mechanism():
    """
    测试策略的缓存机制
    """
    print("=" * 60)
    print("测试策略的缓存机制")
    print("=" * 60)

    try:
        from app.download_strategies import DailyDataStrategy
        from app.tushare_api import TuShareDownloader
        from app.parameter_adapters import ParameterAdapterManager

        downloader = TuShareDownloader()
        strategy = DailyDataStrategy('pro_bar', downloader)

        print(f"策略类型: {type(strategy)}")
        print(f"接口名称: {strategy.interface_name}")
        print(f"缓存启用状态: {strategy.cache_enabled}")
        print(f"缓存TTL小时: {strategy.cache_ttl_hours}")

        # 测试参数适配
        params = {
            'ts_code': '000001.SZ',
            'start_date': '20230101',
            'end_date': '20230110',
            'adj': 'qfq',
            'freq': 'D'
        }
        print(f"原始参数: {params}")

        adapted_params = strategy.validate_and_adapt_params(params)
        print(f"适配后参数: {adapted_params}")

        # 检查缓存状态
        from app.data_storage import is_interface_data_cached
        is_cached = is_interface_data_cached('pro_bar', **params)
        print(f"调用前缓存状态: {is_cached}")

        # 测试download_with_cache调用
        print("\n测试download_with_cache方法...")
        result = strategy.download_with_cache(**params)
        print(f"返回结果类型: {type(result)}")
        if result is not None:
            print(f"返回数据条数: {len(result)}")

        # 检查调用后缓存状态
        is_cached_after = is_interface_data_cached('pro_bar', **params)
        print(f"调用后缓存状态: {is_cached_after}")

    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()

def test_can_use_cache_logic():
    """
    测试_can_use_cache方法的逻辑
    """
    print("\n" + "=" * 60)
    print("测试_can_use_cache方法的逻辑")
    print("=" * 60)

    try:
        from app.download_strategies import DailyDataStrategy
        from app.tushare_api import TuShareDownloader

        downloader = TuShareDownloader()
        strategy = DailyDataStrategy('pro_bar', downloader)

        test_cases = [
            {'ts_code': '000001.SZ', 'trade_date': '20230101'},
            {'ts_code': '000001.SZ', 'start_date': '20230101', 'end_date': '20230110'},
            {'ts_code': '000001.SZ', 'period': '20231231'},
            {'start_date': '20230101', 'end_date': '20230110'}
        ]

        for i, params in enumerate(test_cases):
            result = strategy._can_use_cache(**params)
            print(f"测试用例{i+1}: {params}")
            print(f"结果: {result}")
            print()

    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()

def check_cache_imports():
    """
    检查缓存相关导入
    """
    print("\n" + "=" * 60)
    print("检查缓存相关导入")
    print("=" * 60)

    try:
        from app.download_strategies import DownloadStrategy

        strategy = DownloadStrategy('test')
        print(f"策略缓存启用: {strategy.cache_enabled}")
        print(f"策略缓存TTL小时: {strategy.cache_ttl_hours}")

        # 检查具体缓存函数导入
        from app.download_strategies import (
            is_interface_data_cached,
            load_interface_cached_data,
            save_interface_data_to_cache
        )
        print("✓ 成功导入缓存相关函数")

        # 测试函数调用
        params = {'ts_code': '000001.SZ'}
        result = is_interface_data_cached('test_interface', **params)
        print(f"缓存检查结果: {result}")

    except Exception as e:
        print(f"检查失败: {e}")
        import traceback
        traceback.print_exc()

def analyze_pro_bar_download_method():
    """
    分析pro_bar接口在download方法中的处理
    """
    print("\n" + "=" * 60)
    print("分析pro_bar接口在download方法中的处理")
    print("=" * 60)

    try:
        from app.download_strategies import DailyDataStrategy
        from app.tushare_api import TuShareDownloader

        downloader = TuShareDownloader()
        strategy = DailyDataStrategy('pro_bar', downloader)

        # 手动调用download方法来检查逻辑
        ts_code = '000001.SZ'
        start_date = '20230101'
        end_date = '20230110'
        adj = 'qfq'
        freq = 'D'

        print(f"接口名称: {strategy.interface_name}")
        print(f"start_date: {start_date}")
        print(f"adj: {adj}")
        print(f"freq: {freq}")

        if ts_code:
            print("✓ 有ts_code参数，可以调用下载方法")
        else:
            print("✗ 缺少ts_code参数")

        # 验证downloader是否支持pro_bar方法
        if hasattr(downloader, 'download_pro_bar'):
            print("✓ 下载器支持download_pro_bar方法")
        else:
            print("✗ 下载器不支持download_pro_bar方法")

    except Exception as e:
        print(f"分析失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("测试download_strategies中pro_bar的缓存调用...")

    # 运行各项测试
    check_cache_imports()
    test_can_use_cache_logic()
    test_strategy_cache_mechanism()
    analyze_pro_bar_download_method()

    print("\n" + "=" * 60)
    print("测试总结:")
    print("1. 检查策略缓存机制是否正常")
    print("2. 验证_can_use_cache逻辑")
    print("3. 分析download方法处理")
    print("=" * 60)