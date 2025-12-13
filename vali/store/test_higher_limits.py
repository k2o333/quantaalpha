#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试VIP财务接口的真实上限
"""

import sys
import time
import pandas as pd
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append('/home/quan/testdata/aspipe_v4')

from app.tushare_api import TuShareDownloader
from app.config import TUSHARE_POINTS

def test_higher_limit(interface_name, api_func, base_params, test_limits):
    """
    测试接口的更高限制
    """
    downloader = TuShareDownloader()

    print(f"\n测试 {interface_name} 接口:")

    max_confirmed_limit = 0
    for limit in test_limits:
        try:
            params = base_params.copy()
            params['limit'] = limit

            start_time = time.time()
            result = downloader.download_with_retry(api_func, **params)
            end_time = time.time()
            actual_count = len(result)

            print(f"  limit={limit:>5}: 返回 {actual_count:>5} 条记录, 耗时 {end_time - start_time:.2f}秒")

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

def test_vip_limits():
    """
    测试VIP财务接口的上限
    """
    print("=" * 60)
    print("VIP财务接口真实上限测试")
    print(f"Token积分: {TUSHARE_POINTS}")
    print("=" * 60)

    downloader = TuShareDownloader()

    # 检查积分是否足够
    if TUSHARE_POINTS < 5000:
        print("积分不足，无法测试VIP接口")
        return

    # 测试更高的limit值
    higher_limits = [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000, 11000, 12000]

    results = []

    # 1. balancesheet_vip
    try:
        print("\n测试 balancesheet_vip 接口...")
        result = test_higher_limit(
            "balancesheet_vip",
            downloader.pro.balancesheet_vip,
            {"period": "20240331"},
            higher_limits
        )
        results.append(("balancesheet_vip", result))
    except Exception as e:
        print(f"balancesheet_vip 测试失败: {e}")
        results.append(("balancesheet_vip", "失败"))

    # 2. cashflow_vip
    try:
        print("\n测试 cashflow_vip 接口...")
        result = test_higher_limit(
            "cashflow_vip",
            downloader.pro.cashflow_vip,
            {"period": "20240331"},
            higher_limits
        )
        results.append(("cashflow_vip", result))
    except Exception as e:
        print(f"cashflow_vip 测试失败: {e}")
        results.append(("cashflow_vip", "失败"))

    # 3. fina_indicator_vip
    try:
        print("\n测试 fina_indicator_vip 接口...")
        result = test_higher_limit(
            "fina_indicator_vip",
            downloader.pro.fina_indicator_vip,
            {"period": "20240331"},
            higher_limits
        )
        results.append(("fina_indicator_vip", result))
    except Exception as e:
        print(f"fina_indicator_vip 测试失败: {e}")
        results.append(("fina_indicator_vip", "失败"))

    print("\n" + "=" * 60)
    print("VIP接口真实上限测试结果")
    print("=" * 60)

    for interface, result in results:
        if isinstance(result, int) and result > 0:
            print(f"{interface:<20}: {result} 条记录")
        else:
            print(f"{interface:<20}: {result}")

    print("=" * 60)

if __name__ == "__main__":
    test_vip_limits()