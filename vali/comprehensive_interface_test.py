#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TuShare API 接口完整测试脚本
测试 tudown.md 中提到的所有重要接口的单次调用记录数限制
"""

import sys
import time
import pandas as pd
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append('/home/quan/testdata/aspipe_v4')

from app.tushare_api import TuShareDownloader
from app.config import TUSHARE_POINTS

def comprehensive_interface_test():
    """
    全面测试所有重要接口
    """
    print("=" * 80)
    print("TuShare API 全接口单次调用记录数限制测试")
    print(f"Token积分: {TUSHARE_POINTS}")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    downloader = TuShareDownloader()

    # 测试结果存储
    results = []

    # 定义测试接口列表
    interfaces_to_test = [
        # 基础信息类
        ("stock_basic", lambda: downloader.download_with_retry(
            downloader.pro.stock_basic, exchange='', list_status='L', limit=1000)),
        ("trade_cal", lambda: downloader.download_with_retry(
            downloader.pro.trade_cal, exchange='SSE', start_date='20240101', end_date='20241231')),
        ("stock_company", lambda: downloader.download_with_retry(
            downloader.pro.stock_company, exchange='SSE', limit=500)),

        # 行情数据类
        ("daily_basic", lambda: downloader.download_with_retry(
            downloader.pro.daily_basic, trade_date='20241209')),
        ("moneyflow", lambda: downloader.download_with_retry(
            downloader.pro.moneyflow, trade_date='20241209')),

        # 财务数据类 (VIP)
        ("income_vip", lambda: downloader.download_with_retry(
            downloader.pro.income_vip if TUSHARE_POINTS >= 5000 else downloader.pro.income,
            period='20240331', limit=1000)),
        ("balancesheet_vip", lambda: downloader.download_with_retry(
            downloader.pro.balancesheet_vip if TUSHARE_POINTS >= 5000 else downloader.pro.balancesheet,
            period='20240331', limit=1000)),
        ("cashflow_vip", lambda: downloader.download_with_retry(
            downloader.pro.cashflow_vip if TUSHARE_POINTS >= 5000 else downloader.pro.cashflow,
            period='20240331', limit=1000)),
        ("fina_indicator_vip", lambda: downloader.download_with_retry(
            downloader.pro.fina_indicator_vip if TUSHARE_POINTS >= 5000 else downloader.pro.fina_indicator,
            period='20240331', limit=1000)),

        # 股东数据类
        ("top10_holders", lambda: downloader.download_with_retry(
            downloader.pro.top10_holders, ts_code='000001.SZ', period='20241231')),

        # 技术分析类
        ("stk_factor", lambda: downloader.download_with_retry(
            downloader.pro.stk_factor, ts_code='000001.SZ', trade_date='20241209')),
        ("stk_surv", lambda: downloader.download_with_retry(
            downloader.pro.stk_surv, limit=500)),

        # 其他重要接口
        ("dividend", lambda: downloader.download_with_retry(
            downloader.pro.dividend, ts_code='000001.SZ')),
        ("forecast_vip", lambda: downloader.download_with_retry(
            downloader.pro.forecast_vip if TUSHARE_POINTS >= 5000 else downloader.pro.forecast,
            period='20240331', limit=500)),
    ]

    print("\n开始测试各接口单次调用记录数...")

    for interface_name, test_func in interfaces_to_test:
        try:
            print(f"\n测试 {interface_name}...")
            start_time = time.time()
            result = test_func()
            end_time = time.time()

            if isinstance(result, pd.DataFrame):
                record_count = len(result)
                print(f"  ✓ 成功: {record_count} 条记录, 耗时 {end_time - start_time:.2f}秒")
                results.append((interface_name, record_count, "成功"))
            else:
                print(f"  ? 未知返回类型: {type(result)}")
                results.append((interface_name, 0, "未知类型"))

        except Exception as e:
            print(f"  ✗ 失败: {str(e)[:100]}...")
            results.append((interface_name, 0, f"失败: {str(e)[:50]}"))

    # 输出详细结果
    print("\n" + "=" * 80)
    print("接口测试结果汇总")
    print("=" * 80)
    print(f"{'接口名称':<25} {'记录数':<10} {'状态':<30}")
    print("-" * 80)

    for interface_name, record_count, status in results:
        print(f"{interface_name:<25} {record_count:<10} {status:<30}")

    # 按类别分组显示
    print("\n" + "=" * 80)
    print("按接口类别分组的结果")
    print("=" * 80)

    categories = {
        "基础信息类": ["stock_basic", "trade_cal", "stock_company"],
        "行情数据类": ["daily_basic", "moneyflow"],
        "财务数据类(VIP)": ["income_vip", "balancesheet_vip", "cashflow_vip", "fina_indicator_vip"],
        "股东数据类": ["top10_holders"],
        "技术分析类": ["stk_factor", "stk_surv"],
        "其他重要接口": ["dividend", "forecast_vip"]
    }

    for category, interfaces in categories.items():
        print(f"\n{category}:")
        for interface_name, record_count, status in results:
            if interface_name in interfaces:
                if status == "成功":
                    print(f"  {interface_name}: {record_count} 条记录")
                else:
                    print(f"  {interface_name}: {status}")

    print("\n" + "=" * 80)
    print("单次调用记录数限制总结")
    print("=" * 80)

    # 分析各接口的特点
    limit_free_interfaces = []  # 支持limit参数且无严格限制
    fixed_record_interfaces = []  # 固定记录数
    limited_interfaces = []  # 有硬限制

    for interface_name, record_count, status in results:
        if status == "成功":
            if interface_name in ["stock_basic", "income_vip", "balancesheet_vip", "cashflow_vip", "fina_indicator_vip"]:
                limit_free_interfaces.append((interface_name, record_count))
            elif interface_name in ["daily_basic", "moneyflow"]:
                fixed_record_interfaces.append((interface_name, record_count))
            elif interface_name in ["top10_holders", "stk_factor"]:
                fixed_record_interfaces.append((interface_name, record_count))
            elif interface_name == "stk_surv" and record_count < 500:
                limited_interfaces.append((interface_name, record_count))
            else:
                limit_free_interfaces.append((interface_name, record_count))

    print("\n1. 支持limit参数且无严格限制的接口:")
    for interface, count in limit_free_interfaces:
        print(f"   - {interface}: 可通过limit参数控制返回记录数")

    print("\n2. 固定返回记录数的接口:")
    for interface, count in fixed_record_interfaces:
        print(f"   - {interface}: 固定返回 {count} 条记录")

    print("\n3. 有硬限制的接口:")
    for interface, count in limited_interfaces:
        print(f"   - {interface}: 最大返回 {count} 条记录")

    print(f"\n测试完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

if __name__ == "__main__":
    comprehensive_interface_test()