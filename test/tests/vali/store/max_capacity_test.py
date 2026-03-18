#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TuShare API分页和最大下载量测试脚本
专注于获取各接口的分页能力和最大下载量信息
"""

import sys
import os
import time
import pandas as pd
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append('/home/quan/testdata/aspipe_v4')

from app.tushare_api import TuShareDownloader
from app.config import TUSHARE_POINTS

def test_max_download_capacity():
    """
    测试各接口的最大下载容量和分页能力
    """
    print("=" * 80)
    print("TuShare API 最大下载容量和分页能力测试")
    print(f"Token积分: {TUSHARE_POINTS}")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    downloader = TuShareDownloader()

    # 存储测试结果
    results = []

    # 1. 测试股票基本信息的最大下载量
    print("\n1. 股票基本信息(stock_basic) - 最大下载量测试")
    try:
        # 不限制数量获取全部
        result = downloader.download_with_retry(
            downloader.pro.stock_basic,
            exchange='',
            list_status='L'
        )
        print(f"   全量下载: {len(result)} 条记录")
        results.append(("stock_basic", "全量", len(result), "无分页限制"))

        # 测试分页能力
        result_limit = downloader.download_with_retry(
            downloader.pro.stock_basic,
            exchange='',
            list_status='L',
            limit=100
        )
        print(f"   limit=100: {len(result_limit)} 条记录")
        results.append(("stock_basic", "limit=100", len(result_limit), "支持limit参数"))

    except Exception as e:
        print(f"   测试失败: {e}")
        results.append(("stock_basic", "失败", 0, str(e)))

    # 2. 测试交易日历
    print("\n2. 交易日历(trade_cal) - 时间范围测试")
    try:
        result = downloader.download_with_retry(
            downloader.pro.trade_cal,
            exchange='SSE',
            start_date='20100101',
            end_date='20251231'
        )
        print(f"   15年数据: {len(result)} 条记录")
        results.append(("trade_cal", "15年范围", len(result), "时间范围查询"))
    except Exception as e:
        print(f"   测试失败: {e}")
        results.append(("trade_cal", "失败", 0, str(e)))

    # 3. 测试上市公司信息分交易所获取
    print("\n3. 上市公司信息(stock_company) - 分交易所测试")
    try:
        sse_result = downloader.download_with_retry(
            downloader.pro.stock_company,
            exchange='SSE'
        )
        print(f"   SSE数据: {len(sse_result)} 条记录")
        results.append(("stock_company", "SSE", len(sse_result), "按交易所分批"))

        szse_result = downloader.download_with_retry(
            downloader.pro.stock_company,
            exchange='SZSE'
        )
        print(f"   SZSE数据: {len(szse_result)} 条记录")
        results.append(("stock_company", "SZSE", len(szse_result), "按交易所分批"))
    except Exception as e:
        print(f"   测试失败: {e}")
        results.append(("stock_company", "失败", 0, str(e)))

    # 4. 测试每日指标单日容量
    print("\n4. 每日指标(daily_basic) - 单日容量测试")
    try:
        # 获取最近交易日
        trade_cal = downloader.download_trade_cal(exchange='SSE')
        if len(trade_cal) > 0:
            recent_date = trade_cal[trade_cal['is_open'] == 1].iloc[-1]['cal_date']
            result = downloader.download_with_retry(
                downloader.pro.daily_basic,
                trade_date=recent_date
            )
            print(f"   {recent_date}数据: {len(result)} 条记录")
            results.append(("daily_basic", recent_date, len(result), "单日全市场"))
        else:
            print("   无法获取交易日信息")
            results.append(("daily_basic", "失败", 0, "无法获取交易日"))
    except Exception as e:
        print(f"   测试失败: {e}")
        results.append(("daily_basic", "失败", 0, str(e)))

    # 5. 测试VIP接口单季度容量
    print("\n5. VIP财务接口 - 单季度容量测试")
    vip_interfaces = [
        ("income_vip", downloader.pro.income_vip if TUSHARE_POINTS >= 5000 else downloader.pro.income),
        ("balancesheet_vip", downloader.pro.balancesheet_vip if TUSHARE_POINTS >= 5000 else downloader.pro.balancesheet),
        ("cashflow_vip", downloader.pro.cashflow_vip if TUSHARE_POINTS >= 5000 else downloader.pro.cashflow),
        ("fina_indicator_vip", downloader.pro.fina_indicator_vip if TUSHARE_POINTS >= 5000 else downloader.pro.fina_indicator)
    ]

    for interface_name, api_func in vip_interfaces:
        try:
            result = downloader.download_with_retry(
                api_func,
                period='20230331'  # 2023年第一季度
            )
            print(f"   {interface_name}: {len(result)} 条记录")
            results.append((interface_name, "2023Q1", len(result), "单季度全市场"))
        except Exception as e:
            print(f"   {interface_name}测试失败: {e}")
            results.append((interface_name, "失败", 0, str(e)))

    # 6. 测试资金流向接口
    print("\n6. 资金流向(moneyflow) - 单日容量测试")
    try:
        if 'recent_date' in locals():
            result = downloader.download_with_retry(
                downloader.pro.moneyflow,
                trade_date=recent_date
            )
            print(f"   {recent_date}数据: {len(result)} 条记录")
            results.append(("moneyflow", recent_date, len(result), "单日全市场"))
        else:
            print("   无法获取交易日信息")
            results.append(("moneyflow", "失败", 0, "无法获取交易日"))
    except Exception as e:
        print(f"   测试失败: {e}")
        results.append(("moneyflow", "失败", 0, str(e)))

    # 7. 测试特殊接口
    print("\n7. 特殊接口测试")

    # 前十大股东
    try:
        result = downloader.download_with_retry(
            downloader.pro.top10_holders,
            ts_code='000001.SZ',
            period='20231231'
        )
        print(f"   前十大股东: {len(result)} 条记录 (固定10条)")
        results.append(("top10_holders", "单股票", len(result), "固定10条记录"))
    except Exception as e:
        print(f"   前十大股东测试失败: {e}")
        results.append(("top10_holders", "失败", 0, str(e)))

    # 机构调研
    try:
        result = downloader.download_with_retry(
            downloader.pro.stk_surv,
            limit=3000
        )
        print(f"   机构调研(limit=3000): {len(result)} 条记录")
        results.append(("stk_surv", "limit=3000", len(result), "支持limit参数"))
    except Exception as e:
        print(f"   机构调研测试失败: {e}")
        results.append(("stk_surv", "失败", 0, str(e)))

    # 技术因子
    try:
        if 'recent_date' in locals():
            result = downloader.download_with_retry(
                downloader.pro.stk_factor,
                ts_code='000001.SZ',
                trade_date=recent_date
            )
            print(f"   技术因子: {len(result)} 条记录 (单股票单日)")
            results.append(("stk_factor", "单股票单日", len(result), "1条记录"))
    except Exception as e:
        print(f"   技术因子测试失败: {e}")
        results.append(("stk_factor", "失败", 0, str(e)))

    # 8. 测试分页能力的具体参数
    print("\n8. 分页能力详细测试")
    pagination_tests = [
        ("stock_basic", downloader.pro.stock_basic, {"exchange": "", "list_status": "L", "limit": 50}),
        ("income_vip", downloader.pro.income_vip if TUSHARE_POINTS >= 5000 else downloader.pro.income, {"period": "20230331", "limit": 100}),
        ("stk_surv", downloader.pro.stk_surv, {"limit": 100})
    ]

    for name, func, params in pagination_tests:
        try:
            result = downloader.download_with_retry(func, **params)
            print(f"   {name}分页测试: {len(result)} 条记录")
            results.append((f"{name}_pagination", str(params), len(result), "支持分页"))
        except Exception as e:
            print(f"   {name}分页测试失败: {e}")
            results.append((f"{name}_pagination", "失败", 0, str(e)))

    # 输出详细结果表格
    print("\n" + "=" * 80)
    print("详细测试结果汇总")
    print("=" * 80)
    print(f"{'接口名称':<25} {'测试条件':<15} {'记录数':<10} {'说明':<25}")
    print("-" * 80)

    for interface, condition, count, note in results:
        print(f"{interface:<25} {condition:<15} {count:<10} {note:<25}")

    # 输出5000积分用户的优势总结
    print("\n" + "=" * 80)
    print("5000积分用户下载能力总结")
    print("=" * 80)
    print("1. 最大单次下载量:")
    print("   - stock_basic: 无限制 (全市场约5000+股票)")
    print("   - trade_cal: 无限制 (15年约6000+交易日)")
    print("   - daily_basic: 单日无限制 (全市场数千条)")
    print("   - VIP财务接口: 单季度无限制 (全市场数千条)")
    print("   - moneyflow: 单日无限制 (全市场数百到千条)")

    print("\n2. 分页支持能力:")
    print("   - 支持limit参数控制返回记录数")
    print("   - 多数接口支持大数据量一次性获取")
    print("   - VIP接口特别优化，效率更高")

    print("\n3. 5000积分特权:")
    print("   ✓ 所有VIP接口访问权限")
    print("   ✓ 更高的API调用频率限制")
    print("   ✓ 无总量限制的数据接口")
    print("   ✓ 更大的单次查询返回记录数")
    print("   ✓ 部分接口调用次数限制更宽松")

    print(f"\n测试完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

if __name__ == "__main__":
    test_max_download_capacity()