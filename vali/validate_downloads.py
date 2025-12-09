#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TuShare API下载极限验证脚本
用于验证5000积分token可以调用的不同数据接口的下载能力
"""

import sys
import os
import time
import pandas as pd
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append('/home/quan/testdata/aspipe_v4')

from app.tushare_api import TuShareDownloader
from app.config import TUSHARE_POINTS, TUSHARE_TOKEN

def test_api_limit(api_name, api_call_func, *args, **kwargs):
    """
    测试API调用极限
    """
    print(f"\n=== 测试 {api_name} 接口 ===")
    print(f"用户积分: {TUSHARE_POINTS}")

    downloader = TuShareDownloader()

    try:
        start_time = time.time()
        result = api_call_func(downloader, *args, **kwargs)
        end_time = time.time()

        if isinstance(result, pd.DataFrame):
            print(f"✓ 调用成功!")
            print(f"  - 耗时: {end_time - start_time:.2f}秒")
            print(f"  - 返回记录数: {len(result)}")
            if len(result) > 0:
                print(f"  - 字段数: {len(result.columns)}")
                print(f"  - 前3列: {list(result.columns[:3])}")
                print(f"  - 示例数据:")
                print(result.head(3))
            return True, len(result)
        else:
            print(f"? 返回类型未知: {type(result)}")
            return False, 0

    except Exception as e:
        print(f"✗ 调用失败: {e}")
        return False, 0

def main():
    """
    主函数 - 验证各种API接口的下载能力
    """
    print("=" * 60)
    print("TuShare API 下载能力验证工具")
    print(f"Token积分: {TUSHARE_POINTS}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    downloader = TuShareDownloader()

    # 存储测试结果
    test_results = []

    # 1. 测试股票基本信息 (stock_basic)
    success, count = test_api_limit(
        "股票基本信息(stock_basic)",
        lambda d: d.download_stock_basic()
    )
    test_results.append(("stock_basic", success, count))

    # 2. 测试交易日历 (trade_cal)
    success, count = test_api_limit(
        "交易日历(trade_cal)",
        lambda d: d.download_trade_cal(exchange='SSE')
    )
    test_results.append(("trade_cal", success, count))

    # 3. 测试上市公司基本信息 (stock_company)
    success, count = test_api_limit(
        "上市公司基本信息(stock_company)",
        lambda d: d.download_stock_company(exchange='SSE')
    )
    test_results.append(("stock_company", success, count))

    # 4. 测试每日指标 (daily_basic)
    # 先获取一个有效的交易日期
    try:
        trade_cal = downloader.download_trade_cal(exchange='SSE')
        if len(trade_cal) > 0:
            # 获取最近的一个交易日
            recent_trade_date = trade_cal[trade_cal['is_open'] == 1].iloc[-1]['cal_date']
            success, count = test_api_limit(
                "每日指标(daily_basic)",
                lambda d, date: d.download_daily_basic(trade_date=date),
                recent_trade_date
            )
            test_results.append(("daily_basic", success, count))
        else:
            print("无法获取交易日历数据")
            test_results.append(("daily_basic", False, 0))
    except Exception as e:
        print(f"获取交易日历失败: {e}")
        test_results.append(("daily_basic", False, 0))

    # 5. 测试利润表 (income) - 使用VIP接口
    success, count = test_api_limit(
        "利润表(income_vip)",
        lambda d: d.download_income(period='20231231')
    )
    test_results.append(("income_vip", success, count))

    # 6. 测试资产负债表 (balancesheet) - 使用VIP接口
    success, count = test_api_limit(
        "资产负债表(balancesheet_vip)",
        lambda d: d.download_balancesheet(period='20231231')
    )
    test_results.append(("balancesheet_vip", success, count))

    # 7. 测试现金流量表 (cashflow) - 使用VIP接口
    success, count = test_api_limit(
        "现金流量表(cashflow_vip)",
        lambda d: d.download_cashflow(period='20231231')
    )
    test_results.append(("cashflow_vip", success, count))

    # 8. 测试财务指标数据 (fina_indicator) - 使用VIP接口
    success, count = test_api_limit(
        "财务指标(fina_indicator_vip)",
        lambda d: d.download_fina_indicator(period='20231231')
    )
    test_results.append(("fina_indicator_vip", success, count))

    # 9. 测试个股资金流向 (moneyflow)
    try:
        if 'recent_trade_date' in locals():
            success, count = test_api_limit(
                "个股资金流向(moneyflow)",
                lambda d, date: d.download_moneyflow(trade_date=date),
                recent_trade_date
            )
            test_results.append(("moneyflow", success, count))
        else:
            test_results.append(("moneyflow", False, 0))
    except Exception as e:
        print(f"测试资金流向失败: {e}")
        test_results.append(("moneyflow", False, 0))

    # 10. 测试分红送股 (dividend)
    success, count = test_api_limit(
        "分红送股(dividend)",
        lambda d: d.download_dividend()
    )
    test_results.append(("dividend", success, count))

    # 输出汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    print(f"{'接口名称':<25} {'状态':<10} {'记录数':<10}")
    print("-" * 50)

    success_count = 0
    for api_name, success, record_count in test_results:
        status = "✓ 成功" if success else "✗ 失败"
        print(f"{api_name:<25} {status:<10} {record_count:<10}")
        if success:
            success_count += 1

    print("-" * 50)
    print(f"总计: {len(test_results)} 个接口, 成功: {success_count} 个, 失败: {len(test_results) - success_count} 个")
    print(f"完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

if __name__ == "__main__":
    main()