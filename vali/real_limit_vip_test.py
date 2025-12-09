#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试VIP财务接口的真实上限 - 严格按照用户要求的方法
确保limit参数设置大于实际返回记录数才认为找到了真实上限
"""

import sys
import time
import pandas as pd
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append('/home/quan/testdata/aspipe_v4')

from app.tushare_api import TuShareDownloader
from app.config import TUSHARE_POINTS

def test_real_limit(interface_name, api_func, base_params):
    """
    测试接口的真实上限
    只有当limit设置大于实际返回记录数时，才认为找到了真实上限
    """
    downloader = TuShareDownloader()

    print(f"\n测试 {interface_name} 接口真实上限:")

    # 从较小的值开始测试，逐步增加
    test_limits = [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 11000, 12000, 13000, 14000, 15000]

    for limit in test_limits:
        try:
            params = base_params.copy()
            params['limit'] = limit

            start_time = time.time()
            result = downloader.download_with_retry(api_func, **params)
            end_time = time.time()
            actual_count = len(result)

            print(f"  limit={limit:>5}: 返回 {actual_count:>5} 条记录, 耗时 {end_time - start_time:.2f}秒")

            # 关键判断：只有当limit > actual_count时，才认为找到了真实上限
            if limit > actual_count:
                print(f"  → {interface_name} 真实上限确认: {actual_count} 条记录 (limit={limit} > 返回={actual_count})")
                return actual_count

        except Exception as e:
            print(f"  limit={limit}: 错误 - {str(e)[:50]}...")
            break

    print(f"  → {interface_name} 测试完成，未找到明确上限")
    return None

def vip_real_limit_test():
    """
    VIP接口真实上限测试
    """
    print("=" * 70)
    print("VIP财务接口真实上限测试 (严格按照limit>返回值原则)")
    print(f"Token积分: {TUSHARE_POINTS}")
    print("=" * 70)

    downloader = TuShareDownloader()

    # 检查积分是否足够
    if TUSHARE_POINTS < 5000:
        print("积分不足，无法测试VIP接口")
        return

    results = []

    # 1. balancesheet_vip
    try:
        result = test_real_limit(
            "balancesheet_vip",
            downloader.pro.balancesheet_vip,
            {"period": "20240331"}
        )
        results.append(("balancesheet_vip", result))
    except Exception as e:
        print(f"balancesheet_vip 测试失败: {e}")
        results.append(("balancesheet_vip", "失败"))

    # 2. cashflow_vip
    try:
        result = test_real_limit(
            "cashflow_vip",
            downloader.pro.cashflow_vip,
            {"period": "20240331"}
        )
        results.append(("cashflow_vip", result))
    except Exception as e:
        print(f"cashflow_vip 测试失败: {e}")
        results.append(("cashflow_vip", "失败"))

    # 3. fina_indicator_vip
    try:
        result = test_real_limit(
            "fina_indicator_vip",
            downloader.pro.fina_indicator_vip,
            {"period": "20240331"}
        )
        results.append(("fina_indicator_vip", result))
    except Exception as e:
        print(f"fina_indicator_vip 测试失败: {e}")
        results.append(("fina_indicator_vip", "失败"))

    print("\n" + "=" * 70)
    print("VIP接口真实上限测试结果")
    print("=" * 70)

    for interface, result in results:
        if isinstance(result, int) and result > 0:
            print(f"{interface:<20}: {result} 条记录")
        elif result is None:
            print(f"{interface:<20}: 未找到明确上限")
        else:
            print(f"{interface:<20}: {result}")

    print("=" * 70)

    return results

if __name__ == "__main__":
    vip_real_limit_test()