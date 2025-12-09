#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TuShare API 单次调用记录数限制快速测试
专注于测试各接口单次调用的最大返回记录数
"""

import sys
import time
import pandas as pd
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append('/home/quan/testdata/aspipe_v4')

from app.tushare_api import TuShareDownloader
from app.config import TUSHARE_POINTS

def quick_call_limit_test():
    """
    快速测试各接口单次调用的最大返回记录数
    """
    print("=" * 70)
    print("TuShare API 单次调用记录数限制快速测试")
    print(f"Token积分: {TUSHARE_POINTS}")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    downloader = TuShareDownloader()

    # 测试关键limit值
    test_limits = [100, 500, 1000, 2000, 3000, 5000]

    results = []

    print("\n【支持limit参数的接口测试】")

    # 1. stock_basic 接口
    print("\n1. stock_basic 接口:")
    for limit in test_limits:
        try:
            result = downloader.download_with_retry(
                downloader.pro.stock_basic,
                exchange='',
                list_status='L',
                limit=limit
            )
            actual_count = len(result)
            print(f"   limit={limit:>4}: 返回 {actual_count:>4} 条记录")
            results.append(("stock_basic", limit, actual_count))

            # 如果返回记录数小于limit，说明达到了上限
            if actual_count < limit:
                print(f"   → 最大单次调用记录数: {actual_count}")
                break
        except Exception as e:
            print(f"   limit={limit}: 错误 - {str(e)[:50]}...")
            break

    # 2. income_vip 接口 (VIP)
    print("\n2. income_vip 接口:")
    for limit in test_limits:
        try:
            api_func = downloader.pro.income_vip if TUSHARE_POINTS >= 5000 else downloader.pro.income
            result = downloader.download_with_retry(
                api_func,
                period='20240331',
                limit=limit
            )
            actual_count = len(result)
            print(f"   limit={limit:>4}: 返回 {actual_count:>4} 条记录")
            results.append(("income_vip", limit, actual_count))

            if actual_count < limit:
                print(f"   → 最大单次调用记录数: {actual_count}")
                break
        except Exception as e:
            print(f"   limit={limit}: 错误 - {str(e)[:50]}...")
            break

    # 3. stk_surv 接口
    print("\n3. stk_surv 接口:")
    for limit in test_limits:
        try:
            result = downloader.download_with_retry(
                downloader.pro.stk_surv,
                limit=limit
            )
            actual_count = len(result)
            print(f"   limit={limit:>4}: 返回 {actual_count:>4} 条记录")
            results.append(("stk_surv", limit, actual_count))

            if actual_count < limit:
                print(f"   → 最大单次调用记录数: {actual_count}")
                break
        except Exception as e:
            print(f"   limit={limit}: 错误 - {str(e)[:50]}...")
            break

    print("\n【固定返回记录数的接口测试】")

    # 4. daily_basic 接口 (单日全市场数据)
    print("\n4. daily_basic 接口 (单日数据):")
    try:
        # 获取最近交易日
        trade_cal = downloader.download_with_retry(
            downloader.pro.trade_cal,
            exchange='SSE',
            start_date='20241201',
            end_date='20241231'
        )
        if len(trade_cal) > 0:
            recent_date = trade_cal[trade_cal['is_open'] == 1].iloc[-1]['cal_date']
            result = downloader.download_with_retry(
                downloader.pro.daily_basic,
                trade_date=recent_date
            )
            actual_count = len(result)
            print(f"   {recent_date}: 返回 {actual_count} 条记录 (单日全市场)")
            results.append(("daily_basic", "单日", actual_count))
    except Exception as e:
        print(f"   错误 - {str(e)[:50]}...")

    # 5. moneyflow 接口 (单日全市场数据)
    print("\n5. moneyflow 接口 (单日数据):")
    try:
        if 'recent_date' in locals():
            result = downloader.download_with_retry(
                downloader.pro.moneyflow,
                trade_date=recent_date
            )
            actual_count = len(result)
            print(f"   {recent_date}: 返回 {actual_count} 条记录 (单日全市场)")
            results.append(("moneyflow", "单日", actual_count))
    except Exception as e:
        print(f"   错误 - {str(e)[:50]}...")

    print("\n【固定记录数接口】")

    # 6. top10_holders 接口
    print("\n6. top10_holders 接口:")
    try:
        result = downloader.download_with_retry(
            downloader.pro.top10_holders,
            ts_code='000001.SZ',
            period='20241231'
        )
        actual_count = len(result)
        print(f"   单股票单报告期: 返回 {actual_count} 条记录 (固定10条)")
        results.append(("top10_holders", "固定", actual_count))
    except Exception as e:
        print(f"   错误 - {str(e)[:50]}...")

    # 7. stk_factor 接口
    print("\n7. stk_factor 接口:")
    try:
        if 'recent_date' in locals():
            result = downloader.download_with_retry(
                downloader.pro.stk_factor,
                ts_code='000001.SZ',
                trade_date=recent_date
            )
            actual_count = len(result)
            print(f"   单股票单日: 返回 {actual_count} 条记录 (固定1条)")
            results.append(("stk_factor", "固定", actual_count))
    except Exception as e:
        print(f"   错误 - {str(e)[:50]}...")

    print("\n" + "=" * 70)
    print("单次调用最大记录数总结")
    print("=" * 70)

    # 按接口分组显示结果
    interface_results = {}
    for interface, param, count in results:
        if interface not in interface_results:
            interface_results[interface] = []
        interface_results[interface].append((param, count))

    for interface, data_list in interface_results.items():
        print(f"\n{interface}:")
        for param, count in data_list:
            if param == "固定":
                print(f"  {param}: {count} 条记录")
            elif param == "单日":
                print(f"  {param}: {count} 条记录 (全市场数据)")
            else:
                print(f"  limit={param}: {count} 条记录")

    print("\n" + "=" * 70)
    print("5000积分用户单次调用记录数限制:")
    print("=" * 70)
    print("1. 支持limit参数的接口 (无严格上限限制):")
    print("   - stock_basic: 可通过limit参数控制返回记录数")
    print("   - income_vip等VIP接口: 可通过limit参数控制返回记录数")
    print("   - stk_surv: 可通过limit参数控制返回记录数")

    print("\n2. 固定返回记录数的接口:")
    print("   - daily_basic: 单日全市场数据 (约5000+条)")
    print("   - moneyflow: 单日全市场数据 (约5000+条)")
    print("   - top10_holders: 固定10条记录")
    print("   - stk_factor: 固定1条记录 (单股票单日)")

    print(f"\n测试完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

if __name__ == "__main__":
    quick_call_limit_test()