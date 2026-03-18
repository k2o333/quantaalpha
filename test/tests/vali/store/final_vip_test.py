#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
最终测试剩余VIP接口的真实上限
"""

import sys
import time
import pandas as pd
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append('/home/quan/testdata/aspipe_v4')

from app.tushare_api import TuShareDownloader
from app.config import TUSHARE_POINTS

def final_vip_test():
    """
    最终测试剩余VIP接口的真实上限
    """
    print("=" * 70)
    print("剩余VIP财务接口真实上限测试")
    print(f"Token积分: {TUSHARE_POINTS}")
    print("=" * 70)

    downloader = TuShareDownloader()

    if TUSHARE_POINTS < 5000:
        print("积分不足，无法测试VIP接口")
        return

    # 测试更高的limit值，直到找到真实上限
    test_limits = [5000, 7000, 9000, 11000, 13000, 15000]

    results = []

    # 1. balancesheet_vip
    print("\n测试 balancesheet_vip 接口真实上限:")
    try:
        max_limit_reached = 0
        for limit in test_limits:
            start_time = time.time()
            result = downloader.download_with_retry(
                downloader.pro.balancesheet_vip,
                period='20240331',
                limit=limit
            )
            end_time = time.time()
            actual_count = len(result)

            print(f"  limit={limit:>5}: 返回 {actual_count:>5} 条记录, 耗时 {end_time - start_time:.2f}秒")

            if actual_count == limit:
                max_limit_reached = limit
            else:
                print(f"  → balancesheet_vip 真实上限: {actual_count} 条记录")
                results.append(("balancesheet_vip", actual_count))
                break
        else:
            if max_limit_reached > 0:
                print(f"  → balancesheet_vip 至少支持: {max_limit_reached} 条记录")
                results.append(("balancesheet_vip", f"至少{max_limit_reached}"))
    except Exception as e:
        print(f"  balancesheet_vip 测试失败: {e}")
        results.append(("balancesheet_vip", "测试失败"))

    # 2. cashflow_vip
    print("\n测试 cashflow_vip 接口真实上限:")
    try:
        max_limit_reached = 0
        for limit in test_limits:
            start_time = time.time()
            result = downloader.download_with_retry(
                downloader.pro.cashflow_vip,
                period='20240331',
                limit=limit
            )
            end_time = time.time()
            actual_count = len(result)

            print(f"  limit={limit:>5}: 返回 {actual_count:>5} 条记录, 耗时 {end_time - start_time:.2f}秒")

            if actual_count == limit:
                max_limit_reached = limit
            else:
                print(f"  → cashflow_vip 真实上限: {actual_count} 条记录")
                results.append(("cashflow_vip", actual_count))
                break
        else:
            if max_limit_reached > 0:
                print(f"  → cashflow_vip 至少支持: {max_limit_reached} 条记录")
                results.append(("cashflow_vip", f"至少{max_limit_reached}"))
    except Exception as e:
        print(f"  cashflow_vip 测试失败: {e}")
        results.append(("cashflow_vip", "测试失败"))

    # 3. fina_indicator_vip
    print("\n测试 fina_indicator_vip 接口真实上限:")
    try:
        max_limit_reached = 0
        for limit in test_limits:
            start_time = time.time()
            result = downloader.download_with_retry(
                downloader.pro.fina_indicator_vip,
                period='20240331',
                limit=limit
            )
            end_time = time.time()
            actual_count = len(result)

            print(f"  limit={limit:>5}: 返回 {actual_count:>5} 条记录, 耗时 {end_time - start_time:.2f}秒")

            if actual_count == limit:
                max_limit_reached = limit
            else:
                print(f"  → fina_indicator_vip 真实上限: {actual_count} 条记录")
                results.append(("fina_indicator_vip", actual_count))
                break
        else:
            if max_limit_reached > 0:
                print(f"  → fina_indicator_vip 至少支持: {max_limit_reached} 条记录")
                results.append(("fina_indicator_vip", f"至少{max_limit_reached}"))
    except Exception as e:
        print(f"  fina_indicator_vip 测试失败: {e}")
        results.append(("fina_indicator_vip", "测试失败"))

    print("\n" + "=" * 70)
    print("最终测试结果汇总")
    print("=" * 70)

    for interface, result in results:
        if isinstance(result, int) and result > 0:
            print(f"{interface:<20}: {result} 条记录")
        else:
            print(f"{interface:<20}: {result}")

    print("=" * 70)

    return results

def update_documentation(results):
    """
    根据测试结果更新文档
    """
    print("\n准备更新文档...")
    # 这里可以添加更新文档的逻辑

if __name__ == "__main__":
    results = final_vip_test()
    # update_documentation(results)