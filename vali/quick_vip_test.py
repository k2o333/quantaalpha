#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速测试剩余VIP接口的真实上限
"""

import sys
import time
import pandas as pd
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append('/home/quan/testdata/aspipe_v4')

from app.tushare_api import TuShareDownloader
from app.config import TUSHARE_POINTS

def quick_vip_test():
    """
    快速测试剩余VIP接口的真实上限
    """
    print("=" * 60)
    print("剩余VIP财务接口快速测试")
    print(f"Token积分: {TUSHARE_POINTS}")
    print("=" * 60)

    downloader = TuShareDownloader()

    if TUSHARE_POINTS < 5000:
        print("积分不足，无法测试VIP接口")
        return

    # 快速测试关键limit值
    quick_limits = [5000, 9000, 11000]

    results = []

    interfaces = [
        ("balancesheet_vip", downloader.pro.balancesheet_vip),
        ("cashflow_vip", downloader.pro.cashflow_vip),
        ("fina_indicator_vip", downloader.pro.fina_indicator_vip)
    ]

    for interface_name, api_func in interfaces:
        print(f"\n测试 {interface_name} 接口:")
        try:
            for limit in quick_limits:
                start_time = time.time()
                result = downloader.download_with_retry(
                    api_func,
                    period='20240331',
                    limit=limit
                )
                end_time = time.time()
                actual_count = len(result)

                print(f"  limit={limit:>5}: 返回 {actual_count:>5} 条记录, 耗时 {end_time - start_time:.2f}秒")

                if actual_count != limit:
                    print(f"  → {interface_name} 真实上限: {actual_count} 条记录")
                    results.append((interface_name, actual_count))
                    break
            else:
                print(f"  → {interface_name} 至少支持: {quick_limits[-1]} 条记录")
                results.append((interface_name, f"至少{quick_limits[-1]}"))
        except Exception as e:
            print(f"  {interface_name} 测试失败: {str(e)[:50]}...")
            results.append((interface_name, "测试失败"))

    print("\n" + "=" * 60)
    print("快速测试结果汇总")
    print("=" * 60)

    for interface, result in results:
        print(f"{interface:<20}: {result}")

    print("=" * 60)

    return results

if __name__ == "__main__":
    quick_vip_test()