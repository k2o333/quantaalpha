#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TuShare API 接口真实极限测试脚本
用于找出各接口支持limit参数时的真实最大返回记录数
"""

import sys
import time
import pandas as pd
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append('/home/quan/testdata/aspipe_v4')

from app.tushare_api import TuShareDownloader
from app.config import TUSHARE_POINTS

def find_real_limit(interface_name, api_func, base_params=None):
    """
    找出接口的真实极限
    """
    if base_params is None:
        base_params = {}

    downloader = TuShareDownloader()

    # 测试不同的limit值，从较小值开始逐步增加
    test_limits = [100, 500, 1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 15000, 20000]

    print(f"\n测试 {interface_name} 接口真实极限...")

    max_success_limit = 0
    for limit in test_limits:
        try:
            params = base_params.copy()
            params['limit'] = limit

            start_time = time.time()
            result = downloader.download_with_retry(api_func, **params)
            end_time = time.time()

            actual_count = len(result)
            print(f"  limit={limit:>5}: 实际返回 {actual_count:>5} 条记录, 耗时 {end_time - start_time:.2f}秒")

            if actual_count == limit:
                max_success_limit = limit
            else:
                # 如果返回记录数小于limit，说明达到了上限
                print(f"  → {interface_name} 接口真实极限: {actual_count} 条记录")
                return actual_count

        except Exception as e:
            print(f"  limit={limit}: 错误 - {str(e)[:100]}...")
            break

    if max_success_limit > 0:
        print(f"  → {interface_name} 接口至少支持 limit={max_success_limit}")
    else:
        print(f"  → {interface_name} 接口测试失败")

    return max_success_limit

def find_real_limits():
    """
    找出所有支持limit参数接口的真实极限
    """
    print("=" * 80)
    print("TuShare API 接口真实极限测试")
    print(f"Token积分: {TUSHARE_POINTS}")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    downloader = TuShareDownloader()

    # 存储测试结果
    results = []

    # 测试支持limit参数的接口
    interfaces_to_test = [
        ("stock_basic", downloader.pro.stock_basic, {"exchange": "", "list_status": "L"}),
        ("stock_company", downloader.pro.stock_company, {"exchange": "SSE"}),
        ("income_vip", downloader.pro.income_vip if TUSHARE_POINTS >= 5000 else downloader.pro.income, {"period": "20240331"}),
        ("balancesheet_vip", downloader.pro.balancesheet_vip if TUSHARE_POINTS >= 5000 else downloader.pro.balancesheet, {"period": "20240331"}),
        ("cashflow_vip", downloader.pro.cashflow_vip if TUSHARE_POINTS >= 5000 else downloader.pro.cashflow, {"period": "20240331"}),
        ("fina_indicator_vip", downloader.pro.fina_indicator_vip if TUSHARE_POINTS >= 5000 else downloader.pro.fina_indicator, {"period": "20240331"}),
        ("forecast_vip", downloader.pro.forecast_vip if TUSHARE_POINTS >= 5000 else downloader.pro.forecast, {"period": "20240331"}),
        ("stk_surv", downloader.pro.stk_surv, {}),
        ("dividend", downloader.pro.dividend, {}),  # 注意：dividend接口可能需要ts_code参数
    ]

    print("\n开始测试支持limit参数的接口...")

    for interface_name, api_func, base_params in interfaces_to_test:
        try:
            real_limit = find_real_limit(interface_name, api_func, base_params)
            results.append((interface_name, real_limit))
        except Exception as e:
            print(f"测试 {interface_name} 失败: {e}")
            results.append((interface_name, "测试失败"))

    # 测试固定返回记录数的接口
    print("\n\n测试固定返回记录数的接口...")

    fixed_interfaces = [
        ("daily_basic", lambda: downloader.download_with_retry(downloader.pro.daily_basic, trade_date='20241209')),
        ("moneyflow", lambda: downloader.download_with_retry(downloader.pro.moneyflow, trade_date='20241209')),
        ("top10_holders", lambda: downloader.download_with_retry(downloader.pro.top10_holders, ts_code='000001.SZ', period='20241231')),
        ("stk_factor", lambda: downloader.download_with_retry(downloader.pro.stk_factor, ts_code='000001.SZ', trade_date='20241209')),
    ]

    for interface_name, test_func in fixed_interfaces:
        try:
            print(f"\n测试 {interface_name} 接口...")
            result = test_func()
            actual_count = len(result)
            print(f"  {interface_name}: 固定返回 {actual_count} 条记录")
            results.append((interface_name, f"固定{actual_count}"))
        except Exception as e:
            print(f"测试 {interface_name} 失败: {e}")
            results.append((interface_name, "测试失败"))

    # 输出最终结果
    print("\n" + "=" * 80)
    print("接口真实极限测试结果汇总")
    print("=" * 80)
    print(f"{'接口名称':<25} {'真实极限':<20} {'说明':<30}")
    print("-" * 80)

    for interface_name, real_limit in results:
        if isinstance(real_limit, int):
            if real_limit > 0:
                print(f"{interface_name:<25} {real_limit:<20} {'支持limit参数'}")
            else:
                print(f"{interface_name:<25} {'测试失败':<20} {'测试过程中出现错误'}")
        elif "固定" in str(real_limit):
            print(f"{interface_name:<25} {real_limit:<20} {'固定返回记录数'}")
        else:
            print(f"{interface_name:<25} {real_limit:<20} {'未知'}")

    print(f"\n测试完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

if __name__ == "__main__":
    find_real_limits()