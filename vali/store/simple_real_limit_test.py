#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TuShare API 接口真实极限简单测试
快速测试几个关键接口的真实极限
"""

import sys
import time
import pandas as pd
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append('/home/quan/testdata/aspipe_v4')

from app.tushare_api import TuShareDownloader
from app.config import TUSHARE_POINTS

def test_interface_limit(interface_name, api_func, base_params, test_limits):
    """
    测试单个接口的极限
    """
    downloader = TuShareDownloader()

    print(f"\n测试 {interface_name} 接口:")

    max_confirmed_limit = 0
    for limit in test_limits:
        try:
            params = base_params.copy()
            params['limit'] = limit

            result = downloader.download_with_retry(api_func, **params)
            actual_count = len(result)

            print(f"  limit={limit:>5}: 返回 {actual_count:>5} 条记录")

            if actual_count == limit:
                max_confirmed_limit = limit
            else:
                print(f"  → {interface_name} 极限确认: {actual_count} 条记录")
                return actual_count

        except Exception as e:
            print(f"  limit={limit}: 错误 - {str(e)[:50]}...")
            break

    if max_confirmed_limit > 0:
        print(f"  → {interface_name} 至少支持: {max_confirmed_limit} 条记录")
        return max_confirmed_limit
    else:
        print(f"  → {interface_name} 测试失败")
        return 0

def simple_real_limit_test():
    """
    简单测试真实极限
    """
    print("=" * 60)
    print("TuShare API 接口真实极限快速测试")
    print(f"Token积分: {TUSHARE_POINTS}")
    print("=" * 60)

    downloader = TuShareDownloader()

    # 关键测试值
    key_limits = [1000, 3000, 5000, 8000, 10000]

    results = []

    # 测试几个最重要的接口
    print("\n【支持limit参数的关键接口测试】")

    # 1. stock_basic
    try:
        limit = test_interface_limit(
            "stock_basic",
            downloader.pro.stock_basic,
            {"exchange": "", "list_status": "L"},
            key_limits
        )
        results.append(("stock_basic", limit))
    except Exception as e:
        print(f"stock_basic 测试失败: {e}")
        results.append(("stock_basic", "失败"))

    # 2. income_vip
    try:
        api_func = downloader.pro.income_vip if TUSHARE_POINTS >= 5000 else downloader.pro.income
        limit = test_interface_limit(
            "income_vip",
            api_func,
            {"period": "20240331"},
            key_limits
        )
        results.append(("income_vip", limit))
    except Exception as e:
        print(f"income_vip 测试失败: {e}")
        results.append(("income_vip", "失败"))

    # 3. stk_surv
    try:
        limit = test_interface_limit(
            "stk_surv",
            downloader.pro.stk_surv,
            {},
            [100, 200, 300, 400, 500]
        )
        results.append(("stk_surv", limit))
    except Exception as e:
        print(f"stk_surv 测试失败: {e}")
        results.append(("stk_surv", "失败"))

    print("\n【固定记录数接口测试】")

    # 4. daily_basic
    try:
        print("\n测试 daily_basic 接口:")
        result = downloader.download_with_retry(downloader.pro.daily_basic, trade_date='20241209')
        count = len(result)
        print(f"  daily_basic: 固定返回 {count} 条记录")
        results.append(("daily_basic", f"固定{count}"))
    except Exception as e:
        print(f"daily_basic 测试失败: {e}")
        results.append(("daily_basic", "失败"))

    # 5. moneyflow
    try:
        print("\n测试 moneyflow 接口:")
        result = downloader.download_with_retry(downloader.pro.moneyflow, trade_date='20241209')
        count = len(result)
        print(f"  moneyflow: 固定返回 {count} 条记录")
        results.append(("moneyflow", f"固定{count}"))
    except Exception as e:
        print(f"moneyflow 测试失败: {e}")
        results.append(("moneyflow", "失败"))

    # 6. top10_holders
    try:
        print("\n测试 top10_holders 接口:")
        result = downloader.download_with_retry(downloader.pro.top10_holders, ts_code='000001.SZ', period='20241231')
        count = len(result)
        print(f"  top10_holders: 固定返回 {count} 条记录")
        results.append(("top10_holders", f"固定{count}"))
    except Exception as e:
        print(f"top10_holders 测试失败: {e}")
        results.append(("top10_holders", "失败"))

    # 输出结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    for interface, result in results:
        if isinstance(result, int):
            if result > 0:
                print(f"{interface:<20}: {result} 条记录")
            else:
                print(f"{interface:<20}: 测试失败")
        elif "固定" in str(result):
            print(f"{interface:<20}: {result}")
        else:
            print(f"{interface:<20}: {result}")

    print("=" * 60)

if __name__ == "__main__":
    simple_real_limit_test()