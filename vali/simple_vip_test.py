#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单测试VIP财务接口的真实上限
"""

import sys
import time
import pandas as pd
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append('/home/quan/testdata/aspipe_v4')

from app.tushare_api import TuShareDownloader
from app.config import TUSHARE_POINTS

def simple_vip_test():
    """
    简单测试VIP接口的真实上限
    """
    print("=" * 60)
    print("VIP财务接口真实上限快速测试")
    print(f"Token积分: {TUSHARE_POINTS}")
    print("=" * 60)

    downloader = TuShareDownloader()

    if TUSHARE_POINTS < 5000:
        print("积分不足，无法测试VIP接口")
        return

    # 测试关键的limit值
    key_limits = [1000, 3000, 5000, 7000, 9000, 11000]

    results = []

    # 1. balancesheet_vip
    print("\n测试 balancesheet_vip 接口:")
    try:
        for limit in key_limits:
            result = downloader.download_with_retry(
                downloader.pro.balancesheet_vip,
                period='20240331',
                limit=limit
            )
            actual_count = len(result)
            print(f"  limit={limit:>5}: 返回 {actual_count:>5} 条记录")

            if actual_count != limit:
                print(f"  → balancesheet_vip 极限: {actual_count} 条记录")
                results.append(("balancesheet_vip", actual_count))
                break
        else:
            print(f"  → balancesheet_vip 至少支持: {key_limits[-1]} 条记录")
            results.append(("balancesheet_vip", key_limits[-1]))
    except Exception as e:
        print(f"  balancesheet_vip 测试失败: {e}")
        results.append(("balancesheet_vip", "失败"))

    # 2. cashflow_vip
    print("\n测试 cashflow_vip 接口:")
    try:
        for limit in key_limits:
            result = downloader.download_with_retry(
                downloader.pro.cashflow_vip,
                period='20240331',
                limit=limit
            )
            actual_count = len(result)
            print(f"  limit={limit:>5}: 返回 {actual_count:>5} 条记录")

            if actual_count != limit:
                print(f"  → cashflow_vip 极限: {actual_count} 条记录")
                results.append(("cashflow_vip", actual_count))
                break
        else:
            print(f"  → cashflow_vip 至少支持: {key_limits[-1]} 条记录")
            results.append(("cashflow_vip", key_limits[-1]))
    except Exception as e:
        print(f"  cashflow_vip 测试失败: {e}")
        results.append(("cashflow_vip", "失败"))

    # 3. fina_indicator_vip
    print("\n测试 fina_indicator_vip 接口:")
    try:
        for limit in key_limits:
            result = downloader.download_with_retry(
                downloader.pro.fina_indicator_vip,
                period='20240331',
                limit=limit
            )
            actual_count = len(result)
            print(f"  limit={limit:>5}: 返回 {actual_count:>5} 条记录")

            if actual_count != limit:
                print(f"  → fina_indicator_vip 极限: {actual_count} 条记录")
                results.append(("fina_indicator_vip", actual_count))
                break
        else:
            print(f"  → fina_indicator_vip 至少支持: {key_limits[-1]} 条记录")
            results.append(("fina_indicator_vip", key_limits[-1]))
    except Exception as e:
        print(f"  fina_indicator_vip 测试失败: {e}")
        results.append(("fina_indicator_vip", "失败"))

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    for interface, result in results:
        if isinstance(result, int) and result > 0:
            print(f"{interface:<20}: {result} 条记录")
        else:
            print(f"{interface:<20}: {result}")

    print("=" * 60)

if __name__ == "__main__":
    simple_vip_test()