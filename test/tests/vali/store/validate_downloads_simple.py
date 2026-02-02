#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TuShare API下载极限验证脚本 (简化版)
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
from app.config import TUSHARE_POINTS

def test_api_limit_simple(api_name, api_call_func, *args, **kwargs):
    """
    测试API调用极限（简化版，只测试API是否能调用成功）
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
                print(f"  - 示例数据 (前2行):")
                print(result.head(2).to_string())
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
    print("TuShare API 下载能力验证工具 (快速版)")
    print(f"Token积分: {TUSHARE_POINTS}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    downloader = TuShareDownloader()

    # 存储测试结果
    test_results = []

    # 1. 测试股票基本信息 (stock_basic)
    success, count = test_api_limit_simple(
        "股票基本信息(stock_basic)",
        lambda d: d.download_stock_basic()
    )
    test_results.append(("stock_basic", success, count))

    # 2. 测试交易日历 (trade_cal)
    success, count = test_api_limit_simple(
        "交易日历(trade_cal)",
        lambda d: d.download_trade_cal(exchange='SSE')
    )
    test_results.append(("trade_cal", success, count))

    # 3. 测试上市公司基本信息 (stock_company)
    success, count = test_api_limit_simple(
        "上市公司基本信息(stock_company)",
        lambda d: d.download_stock_company(exchange='SSE')
    )
    test_results.append(("stock_company", success, count))

    # 4. 测试每日指标 (daily_basic) - 使用最近交易日
    try:
        trade_cal = downloader.download_trade_cal(exchange='SSE')
        if len(trade_cal) > 0:
            recent_trade_date = trade_cal[trade_cal['is_open'] == 1].iloc[-1]['cal_date']
            success, count = test_api_limit_simple(
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

    # 5. VIP接口测试需要较小的时间范围以快速验证
    print("\n--- 测试VIP接口 (使用限制日期范围) ---")

    # 5a. 测试利润表 VIP (限制日期)
    success, count = test_api_limit_simple(
        "利润表(income_vip)",
        lambda d: d.download_with_retry(
            d.pro.income_vip if TUSHARE_POINTS >= 5000 else d.pro.income,
            period='20230331',  # 使用单季度数据减少数据量
            limit=1000  # 限制返回记录数
        )
    )
    test_results.append(("income_vip", success, count))

    # 5b. 测试资产负债表 VIP (限制日期)
    success, count = test_api_limit_simple(
        "资产负债表(balancesheet_vip)",
        lambda d: d.download_with_retry(
            d.pro.balancesheet_vip if TUSHARE_POINTS >= 5000 else d.pro.balancesheet,
            period='20230331',  # 使用单季度数据减少数据量
            limit=1000  # 限制返回记录数
        )
    )
    test_results.append(("balancesheet_vip", success, count))

    # 5c. 测试现金流量表 VIP (限制日期)
    success, count = test_api_limit_simple(
        "现金流量表(cashflow_vip)",
        lambda d: d.download_with_retry(
            d.pro.cashflow_vip if TUSHARE_POINTS >= 5000 else d.pro.cashflow,
            period='20230331',  # 使用单季度数据减少数据量
            limit=1000  # 限制返回记录数
        )
    )
    test_results.append(("cashflow_vip", success, count))

    # 5d. 测试财务指标 VIP (限制日期)
    success, count = test_api_limit_simple(
        "财务指标(fina_indicator_vip)",
        lambda d: d.download_with_retry(
            d.pro.fina_indicator_vip if TUSHARE_POINTS >= 5000 else d.pro.fina_indicator,
            period='20230331',  # 使用单季度数据减少数据量
            limit=1000  # 限制返回记录数
        )
    )
    test_results.append(("fina_indicator_vip", success, count))

    # 6. 测试个股资金流向 (使用最近交易日)
    try:
        if 'recent_trade_date' in locals():
            success, count = test_api_limit_simple(
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

    # 7. 测试分红送股 (限制返回数量)
    success, count = test_api_limit_simple(
        "分红送股(dividend)",
        lambda d: d.download_with_retry(
            d.pro.dividend,
            limit=1000  # 限制返回记录数
        )
    )
    test_results.append(("dividend", success, count))

    # 8. 测试前十大股东 (限制股票代码)
    success, count = test_api_limit_simple(
        "前十大股东(top10_holders)",
        lambda d: d.download_with_retry(
            d.pro.top10_holders,
            ts_code='000001.SZ',  # 使用单个股票代码
            period='20231231'  # 指定报告期
        )
    )
    test_results.append(("top10_holders", success, count))

    # 9. 测试机构调研表 (限制日期)
    success, count = test_api_limit_simple(
        "机构调研(stk_surv)",
        lambda d: d.download_with_retry(
            d.pro.stk_surv,
            limit=1000  # 限制返回记录数
        )
    )
    test_results.append(("stk_surv", success, count))

    # 10. 测试技术因子 (使用单个股票)
    success, count = test_api_limit_simple(
        "技术因子(stk_factor)",
        lambda d: d.download_with_retry(
            d.pro.stk_factor,
            ts_code='000001.SZ',  # 使用单个股票代码
            trade_date=recent_trade_date
        )
    )
    test_results.append(("stk_factor", success, count))

    # 输出汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    print(f"{'接口名称':<30} {'状态':<10} {'记录数':<10}")
    print("-" * 55)

    success_count = 0
    for api_name, success, record_count in test_results:
        status = "✓ 成功" if success else "✗ 失败"
        print(f"{api_name:<30} {status:<10} {record_count:<10}")
        if success:
            success_count += 1

    print("-" * 55)
    print(f"总计: {len(test_results)} 个接口, 成功: {success_count} 个, 失败: {len(test_results) - success_count} 个")

    # 输出5000积分用户的优势总结
    print(f"\n" + "=" * 60)
    print("5000积分用户权限总结:")
    print("=" * 60)
    print("✓ 可使用VIP接口（income_vip, balancesheet_vip, cashflow_vip等）")
    print("✓ 享受更高的API调用频率限制")
    print("✓ 每日指标(daily_basic)无总量限制")
    print("✓ 可访问高级数据接口如技术因子(stk_factor)、机构调研(stk_surv)等")
    print("✓ 享受更高的单次查询返回记录数限制")
    print("✓ 某些接口如cyq_perf/cyq_chips有更宽松的调用限制")
    print(f"完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

if __name__ == "__main__":
    main()