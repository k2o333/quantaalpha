#!/usr/bin/env python3
"""
接口下载速度测试脚本
测试每个接口下载3个月的数据并验证下载速度
"""
import sys
import os
import time
import pandas as pd
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, '/home/quan/testdata/aspipe_v4')

from app.tushare_api import TuShareDownloader

def get_last_3_months():
    """获取最近3个月的日期范围"""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=90)
    return start_date.strftime('%Y%m%d'), end_date.strftime('%Y%m%d')

def test_basic_data(downloader):
    """测试基础数据接口"""
    print("测试基础数据接口...")
    start_time = time.time()

    try:
        # 测试股票基本信息
        stock_basic = downloader.basic_data.download_stock_basic()
        print(f"  股票基本信息: {len(stock_basic)} 条记录")

        # 测试交易日历（最近3个月）
        start_date, end_date = get_last_3_months()
        trade_cal = downloader.basic_data.download_trade_cal(start_date=start_date, end_date=end_date)
        print(f"  交易日历: {len(trade_cal)} 条记录")

        elapsed = time.time() - start_time
        print(f"  基础数据接口测试完成，耗时: {elapsed:.2f}秒")
        return elapsed
    except Exception as e:
        print(f"  基础数据接口测试失败: {e}")
        return None

def test_daily_data(downloader):
    """测试日线数据接口"""
    print("测试日线数据接口...")
    start_time = time.time()

    try:
        # 先获取一些股票代码用于测试
        stock_basic = downloader.basic_data.download_stock_basic()
        if stock_basic.empty:
            print("  无法获取股票列表")
            return None

        test_stocks = stock_basic.head(5)['ts_code'].tolist()  # 测试前5只股票

        # 测试日线数据（最近3个月）
        start_date, end_date = get_last_3_months()
        total_records = 0

        for ts_code in test_stocks:
            try:
                daily_data = downloader.daily_data.download_daily_data(ts_code, start_date=start_date, end_date=end_date)
                total_records += len(daily_data)
            except Exception as e:
                print(f"    {ts_code} 日线数据下载失败: {e}")
                continue

        print(f"  日线数据: {total_records} 条记录 (测试{len(test_stocks)}只股票)")

        elapsed = time.time() - start_time
        print(f"  日线数据接口测试完成，耗时: {elapsed:.2f}秒")
        return elapsed
    except Exception as e:
        print(f"  日线数据接口测试失败: {e}")
        return None

def test_financial_data(downloader):
    """测试财务数据接口"""
    print("测试财务数据接口...")
    start_time = time.time()

    try:
        # 获取最近的财报期
        current_year = datetime.now().year
        periods = [f"{current_year}1231", f"{current_year-1}1231", f"{current_year-2}1231"]

        total_records = 0
        for period in periods[:1]:  # 只测试最近一期
            try:
                income = downloader.financial_data.download_income(period=period)
                total_records += len(income)
            except Exception as e:
                print(f"    利润表数据下载失败: {e}")
                continue

        print(f"  财务数据: {total_records} 条记录")

        elapsed = time.time() - start_time
        print(f"  财务数据接口测试完成，耗时: {elapsed:.2f}秒")
        return elapsed
    except Exception as e:
        print(f"  财务数据接口测试失败: {e}")
        return None

def test_market_flow(downloader):
    """测试资金流向接口"""
    print("测试资金流向接口...")
    start_time = time.time()

    try:
        # 测试最近一周的资金流向数据
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        start_date_str = start_date.strftime('%Y%m%d')
        end_date_str = end_date.strftime('%Y%m%d')

        moneyflow = downloader.market_flow.download_moneyflow_range(start_date_str, end_date_str)
        print(f"  资金流向: {len(moneyflow)} 条记录")

        elapsed = time.time() - start_time
        print(f"  资金流向接口测试完成，耗时: {elapsed:.2f}秒")
        return elapsed
    except Exception as e:
        print(f"  资金流向接口测试失败: {e}")
        return None

def test_holders_data(downloader):
    """测试股东数据接口"""
    print("测试股东数据接口...")
    start_time = time.time()

    try:
        # 先获取一些股票代码用于测试
        stock_basic = downloader.basic_data.download_stock_basic()
        if stock_basic.empty:
            print("  无法获取股票列表")
            return None

        test_stocks = stock_basic.head(3)['ts_code'].tolist()  # 测试前3只股票

        total_records = 0
        for ts_code in test_stocks:
            try:
                holders = downloader.holders_data.download_top10_holders(ts_code)
                total_records += len(holders)
            except Exception as e:
                print(f"    {ts_code} 股东数据下载失败: {e}")
                continue

        print(f"  股东数据: {total_records} 条记录 (测试{len(test_stocks)}只股票)")

        elapsed = time.time() - start_time
        print(f"  股东数据接口测试完成，耗时: {elapsed:.2f}秒")
        return elapsed
    except Exception as e:
        print(f"  股东数据接口测试失败: {e}")
        return None

def test_technical_factors(downloader):
    """测试技术因子接口"""
    print("测试技术因子接口...")
    start_time = time.time()

    try:
        # 获取最近的交易日
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        start_date_str = start_date.strftime('%Y%m%d')
        end_date_str = end_date.strftime('%Y%m%d')

        # 获取交易日历
        trade_cal = downloader.basic_data.download_trade_cal(start_date=start_date_str, end_date=end_date_str)
        trading_days = trade_cal[trade_cal['is_open'] == 1]['cal_date'].tolist()

        if trading_days:
            latest_trade_date = trading_days[-1]
            stk_factor = downloader.technical_factors.download_stk_factor(trade_date=latest_trade_date)
            print(f"  技术因子: {len(stk_factor)} 条记录")
        else:
            print("  无法获取交易日")
            return None

        elapsed = time.time() - start_time
        print(f"  技术因子接口测试完成，耗时: {elapsed:.2f}秒")
        return elapsed
    except Exception as e:
        print(f"  技术因子接口测试失败: {e}")
        return None

def test_market_structure(downloader):
    """测试市场结构接口"""
    print("测试市场结构接口...")
    start_time = time.time()

    try:
        # 测试最近一周的停复牌信息
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)
        start_date_str = start_date.strftime('%Y%m%d')
        end_date_str = end_date.strftime('%Y%m%d')

        suspend_data = downloader.market_structure.download_suspend_d_range(start_date_str, end_date_str)
        print(f"  停复牌信息: {len(suspend_data)} 条记录")

        elapsed = time.time() - start_time
        print(f"  市场结构接口测试完成，耗时: {elapsed:.2f}秒")
        return elapsed
    except Exception as e:
        print(f"  市场结构接口测试失败: {e}")
        return None

def test_research_data(downloader):
    """测试研究数据接口"""
    print("测试研究数据接口...")
    start_time = time.time()

    try:
        # 获取最近的研究报告期
        current_year = datetime.now().year
        period = f"{current_year}1231"

        report_rc = downloader.research_data.download_report_rc(period=period)
        print(f"  研究数据: {len(report_rc)} 条记录")

        elapsed = time.time() - start_time
        print(f"  研究数据接口测试完成，耗时: {elapsed:.2f}秒")
        return elapsed
    except Exception as e:
        print(f"  研究数据接口测试失败: {e}")
        return None

def main():
    """主测试函数"""
    print("开始接口下载速度测试...")
    print("=" * 50)

    # 初始化下载器
    downloader = TuShareDownloader()

    # 存储各接口测试结果
    results = {}

    # 测试各个接口
    test_functions = [
        ("基础数据", test_basic_data),
        ("日线数据", test_daily_data),
        ("财务数据", test_financial_data),
        ("资金流向", test_market_flow),
        ("股东数据", test_holders_data),
        ("技术因子", test_technical_factors),
        ("市场结构", test_market_structure),
        ("研究数据", test_research_data)
    ]

    for interface_name, test_func in test_functions:
        try:
            elapsed_time = test_func(downloader)
            results[interface_name] = elapsed_time
            print()
        except Exception as e:
            print(f"{interface_name} 测试出错: {e}")
            results[interface_name] = None
            print()

    # 输出测试总结
    print("=" * 50)
    print("测试总结:")
    total_time = 0
    successful_tests = 0

    for interface_name, elapsed_time in results.items():
        if elapsed_time is not None:
            print(f"  {interface_name}: {elapsed_time:.2f}秒")
            total_time += elapsed_time
            successful_tests += 1
        else:
            print(f"  {interface_name}: 失败")

    print(f"\n成功测试接口数: {successful_tests}/{len(test_functions)}")
    print(f"总耗时: {total_time:.2f}秒")
    print(f"平均每个接口耗时: {total_time/successful_tests:.2f}秒" if successful_tests > 0 else "无成功测试")

    print("\n接口下载速度测试完成!")

if __name__ == "__main__":
    main()