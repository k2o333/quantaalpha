#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TuShare API 单次调用最大记录数测试
用于测试各接口在单次调用时的最大返回记录数限制
"""

import sys
import time
import pandas as pd
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append('/home/quan/testdata/aspipe_v4')

from app.tushare_api import TuShareDownloader
from app.config import TUSHARE_POINTS

def test_single_call_limit():
    """
    测试各接口单次调用的最大返回记录数
    """
    print("=" * 80)
    print("TuShare API 单次调用最大记录数测试")
    print(f"Token积分: {TUSHARE_POINTS}")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    downloader = TuShareDownloader()

    # 测试不同的limit值来确定单次调用的最大记录数
    limit_values = [100, 500, 1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000]

    results = []

    print("\n1. stock_basic 接口单次调用记录数限制测试")
    print("   (通过设置不同的limit值来测试最大返回记录数)")
    for limit in limit_values:
        try:
            result = downloader.download_with_retry(
                downloader.pro.stock_basic,
                exchange='',
                list_status='L',
                limit=limit
            )
            actual_count = len(result)
            print(f"   limit={limit:>5}: 实际返回 {actual_count:>5} 条记录", end="")
            if actual_count == limit:
                print(" ✓")
            else:
                print(f" (实际返回 {actual_count})")
            results.append(("stock_basic", limit, actual_count))

            # 如果实际返回记录数小于设置的limit，说明已达到API限制
            if actual_count < limit:
                print(f"   → stock_basic 单次调用最大记录数: {actual_count}")
                break
        except Exception as e:
            print(f"   limit={limit}: 错误 - {e}")
            break

    print("\n2. trade_cal 接口单次调用记录数限制测试")
    for limit in limit_values:
        try:
            result = downloader.download_with_retry(
                downloader.pro.trade_cal,
                exchange='SSE',
                start_date='20200101',
                end_date='20241231',
                limit=limit
            )
            actual_count = len(result)
            print(f"   limit={limit:>5}: 实际返回 {actual_count:>5} 条记录", end="")
            if actual_count == limit:
                print(" ✓")
            else:
                print(f" (实际返回 {actual_count})")
            results.append(("trade_cal", limit, actual_count))

            if actual_count < limit:
                print(f"   → trade_cal 单次调用最大记录数: {actual_count}")
                break
        except Exception as e:
            print(f"   limit={limit}: 错误 - {e}")
            break

    print("\n3. stock_company 接口单次调用记录数限制测试")
    for limit in limit_values:
        try:
            result = downloader.download_with_retry(
                downloader.pro.stock_company,
                exchange='SSE',
                limit=limit
            )
            actual_count = len(result)
            print(f"   limit={limit:>5}: 实际返回 {actual_count:>5} 条记录", end="")
            if actual_count == limit:
                print(" ✓")
            else:
                print(f" (实际返回 {actual_count})")
            results.append(("stock_company", limit, actual_count))

            if actual_count < limit:
                print(f"   → stock_company 单次调用最大记录数: {actual_count}")
                break
        except Exception as e:
            print(f"   limit={limit}: 错误 - {e}")
            break

    print("\n4. daily_basic 接口单次调用记录数限制测试")
    # daily_basic 按日期查询，测试单日最大记录数
    try:
        # 获取最近交易日
        trade_cal = downloader.download_with_retry(
            downloader.pro.trade_cal,
            exchange='SSE',
            start_date='20240101',
            end_date='20241231'
        )
        if len(trade_cal) > 0:
            recent_date = trade_cal[trade_cal['is_open'] == 1].iloc[-1]['cal_date']
            result = downloader.download_with_retry(
                downloader.pro.daily_basic,
                trade_date=recent_date
            )
            actual_count = len(result)
            print(f"   daily_basic({recent_date}): 单日返回 {actual_count} 条记录")
            results.append(("daily_basic", "单日", actual_count))
            print(f"   → daily_basic 单次调用最大记录数: {actual_count} (单个交易日)")
    except Exception as e:
        print(f"   daily_basic: 错误 - {e}")

    print("\n5. VIP财务接口单次调用记录数限制测试")
    vip_interfaces = [
        ("income_vip", "20240331"),
        ("balancesheet_vip", "20240331"),
        ("cashflow_vip", "20240331"),
        ("fina_indicator_vip", "20240331")
    ]

    for interface_name, period in vip_interfaces:
        api_func = getattr(downloader.pro, interface_name if TUSHARE_POINTS >= 5000 else interface_name.replace('_vip', ''))
        for limit in limit_values[:5]:  # 只测试较小的limit值，避免超时
            try:
                result = downloader.download_with_retry(
                    api_func,
                    period=period,
                    limit=limit
                )
                actual_count = len(result)
                print(f"   {interface_name}(limit={limit}): 实际返回 {actual_count} 条记录", end="")
                if actual_count == limit:
                    print(" ✓")
                else:
                    print(f" (实际返回 {actual_count})")

                results.append((interface_name, limit, actual_count))

                if actual_count < limit:
                    print(f"   → {interface_name} 单次调用最大记录数: {actual_count}")
                    break
            except Exception as e:
                print(f"   {interface_name}(limit={limit}): 错误 - {e}")
                break

    print("\n6. moneyflow 接口单次调用记录数限制测试")
    try:
        if 'recent_date' in locals():
            result = downloader.download_with_retry(
                downloader.pro.moneyflow,
                trade_date=recent_date
            )
            actual_count = len(result)
            print(f"   moneyflow({recent_date}): 单日返回 {actual_count} 条记录")
            results.append(("moneyflow", "单日", actual_count))
            print(f"   → moneyflow 单次调用最大记录数: {actual_count} (单个交易日)")
    except Exception as e:
        print(f"   moneyflow: 错误 - {e}")

    print("\n7. stk_surv 接口单次调用记录数限制测试")
    for limit in limit_values:
        try:
            result = downloader.download_with_retry(
                downloader.pro.stk_surv,
                limit=limit
            )
            actual_count = len(result)
            print(f"   stk_surv(limit={limit}): 实际返回 {actual_count} 条记录", end="")
            if actual_count == limit:
                print(" ✓")
            else:
                print(f" (实际返回 {actual_count})")

            results.append(("stk_surv", limit, actual_count))

            if actual_count < limit:
                print(f"   → stk_surv 单次调用最大记录数: {actual_count}")
                break
        except Exception as e:
            print(f"   stk_surv(limit={limit}): 错误 - {e}")
            break

    print("\n8. 特殊接口单次调用记录数测试")
    # top10_holders: 固定返回10条
    try:
        result = downloader.download_with_retry(
            downloader.pro.top10_holders,
            ts_code='000001.SZ',
            period='20241231'
        )
        actual_count = len(result)
        print(f"   top10_holders: 固定返回 {actual_count} 条记录")
        results.append(("top10_holders", "固定", actual_count))
    except Exception as e:
        print(f"   top10_holders: 错误 - {e}")

    # stk_factor: 单股票单日返回1条
    try:
        if 'recent_date' in locals():
            result = downloader.download_with_retry(
                downloader.pro.stk_factor,
                ts_code='000001.SZ',
                trade_date=recent_date
            )
            actual_count = len(result)
            print(f"   stk_factor: 单股票单日返回 {actual_count} 条记录")
            results.append(("stk_factor", "单股票单日", actual_count))
    except Exception as e:
        print(f"   stk_factor: 错误 - {e}")

    print("\n" + "=" * 80)
    print("单次调用最大记录数总结")
    print("=" * 80)
    print(f"{'接口名称':<20} {'测试参数':<15} {'实际最大记录数':<15} {'说明':<25}")
    print("-" * 80)

    # 按接口名称分组，取最大值
    interface_max = {}
    for interface, param, count in results:
        if interface not in interface_max:
            interface_max[interface] = count
        else:
            interface_max[interface] = max(interface_max[interface], count)

    for interface, max_count in interface_max.items():
        if interface in ['daily_basic', 'moneyflow', 'top10_holders', 'stk_factor']:
            if interface == 'daily_basic':
                desc = "单日全市场数据"
            elif interface == 'moneyflow':
                desc = "单日全市场数据"
            elif interface == 'top10_holders':
                desc = "固定返回10条"
            elif interface == 'stk_factor':
                desc = "单股票单日数据"
            print(f"{interface:<20} {'单次调用':<15} {max_count:<15} {desc:<25}")
        else:
            print(f"{interface:<20} {'limit参数':<15} {max_count:<15} {'受limit参数控制':<25}")

    print("\n" + "=" * 80)
    print("5000积分用户单次调用限制总结:")
    print("=" * 80)
    print("1. 可分页接口 (支持limit参数):")
    print("   - stock_basic: 无严格限制，取决于实际数据量")
    print("   - stock_company: 无严格限制，取决于实际数据量")
    print("   - stk_surv: 无严格限制，取决于实际数据量")
    print("   - VIP财务接口: 无严格限制，取决于实际数据量")

    print("\n2. 固定返回接口:")
    print("   - daily_basic: 单日全市场数据 (约5000+条)")
    print("   - moneyflow: 单日全市场数据 (约5000+条)")
    print("   - top10_holders: 固定10条记录")
    print("   - stk_factor: 单股票单日1条记录")

    print(f"\n测试完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

if __name__ == "__main__":
    test_single_call_limit()