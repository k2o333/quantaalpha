#!/usr/bin/env python3
"""
分析main.py中pro_bar调用逻辑的问题
"""

import sys
import os
sys.path.append('/home/quan/testdata/aspipe_v4')

import argparse
from datetime import datetime
import time

def simulate_main_pro_bar_call():
    """
    模拟main.py中pro_bar_only参数的调用逻辑
    """
    print("=" * 60)
    print("模拟main.py中pro_bar_only参数的调用逻辑")
    print("=" * 60)

    # 模拟命令行参数
    args = argparse.Namespace(
        start_date='20230101',
        end_date=None,
        use_legacy=False,
        holders_data=False,
        pro_bar_only=True,
        tscode_historical=True
    )

    print(f"模拟参数: {args}")

    # 模拟main.py中的逻辑
    print("\n1. 分析调用模式...")
    is_date_range_mode = not args.tscode_historical and not args.holders_data and not args.pro_bar_only
    effective_tscode_historical = args.tscode_historical or args.pro_bar_only

    print(f"is_date_range_mode: {is_date_range_mode}")
    print(f"effective_tscode_historical: {effective_tscode_historical}")
    print(f"pro_bar_only: {args.pro_bar_only}")

    # 模拟下载逻辑
    print("\n2. 模拟下载逻辑...")

    if args.pro_bar_only or (effective_tscode_historical and not (args.holders_data or args.pro_bar_only)):
        print("进入pro_bar下载逻辑...")

        if effective_tscode_historical:
            print("使用 DownloadScheduler (tscode-historical 模式)")

            # 模拟导入
            try:
                from app.download_scheduler import run_download_schedule
                print("✓ 成功导入run_download_schedule")

                # 模拟调用（不实际执行，只是分析参数）
                print("模拟调用参数:")
                print("  start_date: '20230101' (忽略)")
                print("  end_date: 当前日期 (忽略)")
                print("  interfaces: ['pro_bar']")
                print("  mode: 'tscode_historical'")

            except Exception as e:
                print(f"✗ 导入run_download_schedule失败: {e}")
                import traceback
                traceback.print_exc()
        else:
            print("使用传统下载方式")

def analyze_main_logic():
    """
    分析main.py中的关键逻辑分支
    """
    print("\n" + "=" * 60)
    print("分析main.py中的关键逻辑分支")
    print("=" * 60)

    # 分析条件判断
    print("关键条件判断分析:")

    # 条件1: is_date_range_mode
    print("\n1. is_date_range_mode = not tscode_historical and not holders_data and not pro_bar_only")
    test_cases = [
        {"tscode_historical": False, "holders_data": False, "pro_bar_only": False, "expected": True},
        {"tscode_historical": True, "holders_data": False, "pro_bar_only": False, "expected": False},
        {"tscode_historical": False, "holders_data": True, "pro_bar_only": False, "expected": False},
        {"tscode_historical": False, "holders_data": False, "pro_bar_only": True, "expected": False},
    ]

    for i, case in enumerate(test_cases):
        result = not case["tscode_historical"] and not case["holders_data"] and not case["pro_bar_only"]
        status = "✓" if result == case["expected"] else "✗"
        print(f"  测试{i+1}: {case} => {result} {status}")

    # 条件2: effective_tscode_historical
    print("\n2. effective_tscode_historical = tscode_historical or pro_bar_only")
    test_cases = [
        {"tscode_historical": False, "pro_bar_only": False, "expected": False},
        {"tscode_historical": True, "pro_bar_only": False, "expected": True},
        {"tscode_historical": False, "pro_bar_only": True, "expected": True},
        {"tscode_historical": True, "pro_bar_only": True, "expected": True},
    ]

    for i, case in enumerate(test_cases):
        result = case["tscode_historical"] or case["pro_bar_only"]
        status = "✓" if result == case["expected"] else "✗"
        print(f"  测试{i+1}: {case} => {result} {status}")

    # 条件3: download_pro_bar_only
    print("\n3. download_pro_bar_only = pro_bar_only or (effective_tscode_historical and not (holders_data or pro_bar_only))")

    # 这里的逻辑有点复杂，让我们仔细分析
    print("  注意：这个条件中的'and not (holders_data or pro_bar_only)'部分可能存在问题")
    print("  当pro_bar_only=True时，'(holders_data or pro_bar_only)'也为True，所以整个表达式为False")

def check_imports():
    """
    检查关键导入是否正常
    """
    print("\n" + "=" * 60)
    print("检查关键导入是否正常")
    print("=" * 60)

    imports_to_check = [
        "app.download_scheduler",
        "app.tushare_api",
        "app.download_strategies",
        "app.data_storage",
        "app.cache_key_generator",
        "app.config_adapter"
    ]

    for imp in imports_to_check:
        try:
            if imp == "app.download_scheduler":
                from app.download_scheduler import run_download_schedule
                print(f"✓ {imp} - 成功导入run_download_schedule")
            elif imp == "app.tushare_api":
                from app.tushare_api import TuShareDownloader
                print(f"✓ {imp} - 成功导入TuShareDownloader")
            elif imp == "app.download_strategies":
                from app.download_strategies import DailyDataStrategy
                print(f"✓ {imp} - 成功导入DailyDataStrategy")
            elif imp == "app.data_storage":
                from app.data_storage import is_interface_data_cached
                print(f"✓ {imp} - 成功导入is_interface_data_cached")
            elif imp == "app.cache_key_generator":
                from app.cache_key_generator import CacheKeyGenerator
                print(f"✓ {imp} - 成功导入CacheKeyGenerator")
            elif imp == "app.config_adapter":
                from app.config_adapter import get_interface_cache_settings
                print(f"✓ {imp} - 成功导入get_interface_cache_settings")
        except Exception as e:
            print(f"✗ {imp} - 导入失败: {e}")

def simulate_download_scheduler_call():
    """
    模拟download_scheduler中的调用
    """
    print("\n" + "=" * 60)
    print("模拟download_scheduler中的调用")
    print("=" * 60)

    try:
        from app.download_scheduler import DownloadScheduler

        # 创建调度器实例
        scheduler = DownloadScheduler('20230101', '20230110')
        print("✓ 成功创建DownloadScheduler实例")

        # 检查是否识别pro_bar为ts_code接口
        is_tscode = scheduler._is_tscode_interface('pro_bar')
        print(f"pro_bar是否为ts_code接口: {is_tscode}")

        # 检查接口配置
        from app.enhanced_download_config import DOWNLOAD_PIPELINE_CONFIG
        pro_bar_config = DOWNLOAD_PIPELINE_CONFIG.get('pro_bar')
        if pro_bar_config:
            print(f"pro_bar配置:")
            print(f"  enabled: {pro_bar_config.enabled}")
            print(f"  requires_tscode: {getattr(pro_bar_config, 'requires_tscode', False)}")
            print(f"  cache_enabled: {pro_bar_config.cache_enabled}")
            print(f"  cache_ttl_hours: {pro_bar_config.cache_ttl_hours}")
        else:
            print("✗ 未找到pro_bar配置")

    except Exception as e:
        print(f"✗ 模拟download_scheduler调用失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("开始分析main.py中pro_bar调用逻辑...")

    # 运行各项分析
    analyze_main_logic()
    check_imports()
    simulate_main_pro_bar_call()
    simulate_download_scheduler_call()

    print("\n" + "=" * 60)
    print("分析结论:")
    print("1. 检查main.py中的逻辑条件判断")
    print("2. 验证关键模块导入是否正常")
    print("3. 确认download_scheduler是否正确处理pro_bar")
    print("=" * 60)