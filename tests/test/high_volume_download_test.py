#!/usr/bin/env python3
"""
改进版接口下载速度测试脚本 - 高数据量版
测试每个接口下载大量数据并验证下载速度
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

def get_recent_quarters(n=4):
    """获取最近n个季度"""
    current_year = datetime.now().year
    current_month = datetime.now().month
    quarters = []

    # 确定当前季度
    if current_month <= 3:
        current_q = f"{current_year}0331"
        year = current_year
    elif current_month <= 6:
        current_q = f"{current_year}0630"
        year = current_year
    elif current_month <= 9:
        current_q = f"{current_year}0930"
        year = current_year
    else:
        current_q = f"{current_year}1231"
        year = current_year

    # 添加当前季度和之前季度
    quarters.append(current_q)

    for i in range(1, n):
        if "0331" in quarters[-1]:
            prev_year = int(quarters[-1][:4]) - 1
            prev_q = f"{prev_year}1231"
        elif "0630" in quarters[-1]:
            prev_q = quarters[-1][:4] + "0331"
        elif "0930" in quarters[-1]:
            prev_q = quarters[-1][:4] + "0630"
        else:  # 1231
            prev_q = quarters[-1][:4] + "0930"
        quarters.append(prev_q)

    return quarters

def test_financial_data_large(downloader):
    """测试财务数据接口 - 重点获取大量数据"""
    print("测试财务数据接口（大容量版）...")
    start_time = time.time()

    try:
        # 获取最近的季度数据
        periods = get_recent_quarters(8)  # 获取更多季度的数据
        total_records = 0

        for period in periods:
            try:
                # 优先使用VIP接口获取全市场数据
                print(f"    尝试下载 {period} 季度利润表...")
                try:
                    income = downloader.financial_data.download_income(period=period)
                    if income is not None and not income.empty:
                        count = len(income)
                        total_records += count
                        print(f"      利润表({period}): {count} 条记录")
                        if total_records >= 20000:  # 如果已达到2万条数据，停止
                            print(f"      已达到20,000条记录目标，停止下载")
                            break
                    else:
                        print(f"      利润表({period}): 无数据")
                except Exception as e:
                    print(f"      利润表({period})下载失败: {e}")

                # 如果还没达到目标，继续尝试资产负债表
                if total_records < 20000:
                    print(f"    尝试下载 {period} 季度资产负债表...")
                    try:
                        balancesheet = downloader.financial_data.download_balancesheet(period=period)
                        if balancesheet is not None and not balancesheet.empty:
                            count = len(balancesheet)
                            total_records += count
                            print(f"      资产负债表({period}): {count} 条记录")
                            if total_records >= 20000:
                                print(f"      已达到20,000条记录目标，停止下载")
                                break
                        else:
                            print(f"      资产负债表({period}): 无数据")
                    except Exception as e:
                        print(f"      资产负债表({period})下载失败: {e}")

                # 如果还没达到目标，继续尝试现金流量表
                if total_records < 20000:
                    print(f"    尝试下载 {period} 季度现金流量表...")
                    try:
                        cashflow = downloader.financial_data.download_cashflow(period=period)
                        if cashflow is not None and not cashflow.empty:
                            count = len(cashflow)
                            total_records += count
                            print(f"      现金流量表({period}): {count} 条记录")
                            if total_records >= 20000:
                                print(f"      已达到20,000条记录目标，停止下载")
                                break
                        else:
                            print(f"      现金流量表({period}): 无数据")
                    except Exception as e:
                        print(f"      现金流量表({period})下载失败: {e}")

            except Exception as e:
                print(f"    财报({period})数据处理失败: {e}")
                continue

        print(f"  财务数据总计: {total_records} 条记录")

        elapsed = time.time() - start_time
        print(f"  财务数据接口测试完成，耗时: {elapsed:.2f}秒")
        return elapsed
    except Exception as e:
        print(f"  财务数据接口测试失败: {e}")
        return None

def test_technical_factors_large(downloader):
    """测试技术因子接口 - 重点获取大量数据"""
    print("测试技术因子接口（大容量版）...")
    start_time = time.time()

    try:
        # 获取最近的交易日
        end_date = datetime.now()
        start_date = end_date - timedelta(days=180)  # 增加到6个月
        start_date_str = start_date.strftime('%Y%m%d')
        end_date_str = end_date.strftime('%Y%m%d')

        # 获取交易日历
        trade_cal = downloader.basic_data.download_trade_cal(start_date=start_date_str, end_date=end_date_str)
        trading_days = trade_cal[trade_cal['is_open'] == 1]['cal_date'].tolist()

        total_records = 0
        print(f"  找到 {len(trading_days)} 个交易日")

        if trading_days:
            # 尝试获取更多交易日的技术因子数据
            for i, trade_date in enumerate(trading_days):
                try:
                    print(f"    下载 {trade_date} 的技术因子...")
                    stk_factor = downloader.technical_factors.download_stk_factor(trade_date=trade_date)
                    if stk_factor is not None and not stk_factor.empty:
                        count = len(stk_factor)
                        total_records += count
                        print(f"      技术因子({trade_date}): {count} 条记录")
                        if total_records >= 20000:  # 如果已达到2万条数据，停止
                            print(f"      已达到20,000条记录目标，停止下载")
                            break
                    else:
                        print(f"      技术因子({trade_date}): 无数据")
                except Exception as e:
                    print(f"      技术因子({trade_date})下载失败: {e}")
                    continue

                # 每下载10天暂停一下，防止触发频率限制
                if (i + 1) % 10 == 0:
                    print(f"      已下载{i+1}个交易日，暂停一下...")
                    time.sleep(1)

        print(f"  技术因子总计: {total_records} 条记录")

        # 如果还没达到目标，下载筹码分布数据
        if total_records < 20000 and trading_days:
            print(f"  继续下载筹码分布数据以增加记录数...")
            for i, trade_date in enumerate(trading_days[:10]):  # 只下载前10个交易日的筹码分布
                try:
                    print(f"    下载 {trade_date} 的筹码分布...")
                    cyq_perf = downloader.technical_factors.download_cyq_perf(trade_date=trade_date)
                    if cyq_perf is not None and not cyq_perf.empty:
                        count = len(cyq_perf)
                        total_records += count
                        print(f"      筹码分布({trade_date}): {count} 条记录")
                        if total_records >= 20000:
                            print(f"      已达到20,000条记录目标，停止下载")
                            break
                except Exception as e:
                    print(f"      筹码分布({trade_date})下载失败: {e}")
                    continue

        print(f"  技术因子（含筹码分布）总计: {total_records} 条记录")

        elapsed = time.time() - start_time
        print(f"  技术因子接口测试完成，耗时: {elapsed:.2f}秒")
        return elapsed
    except Exception as e:
        print(f"  技术因子接口测试失败: {e}")
        return None

def test_daily_data_large(downloader):
    """测试日线数据接口 - 重点获取大量数据"""
    print("测试日线数据接口（大容量版）...")
    start_time = time.time()

    try:
        # 先获取一些股票代码用于测试
        stock_basic = downloader.basic_data.download_stock_basic()
        if stock_basic.empty:
            print("  无法获取股票列表")
            return None

        # 扩大测试股票数量和时间范围以获取更多数据
        test_stocks = stock_basic.head(50)['ts_code'].tolist()  # 测试前50只股票
        print(f"  准备测试 {len(test_stocks)} 只股票的日线数据")

        # 扩大时间范围到最近6个月
        start_date, end_date = get_last_3_months()
        # 扩大到6个月
        end_date = datetime.now()
        start_date = end_date - timedelta(days=180)
        start_date_str = start_date.strftime('%Y%m%d')
        end_date_str = end_date.strftime('%Y%m%d')

        total_records = 0

        for i, ts_code in enumerate(test_stocks):
            try:
                daily_data = downloader.daily_data.download_daily_data(ts_code, start_date=start_date_str, end_date=end_date_str)
                if daily_data is not None and not daily_data.empty:
                    count = len(daily_data)
                    total_records += count
                    if i % 10 == 0:  # 每10只股票报告一次进度
                        print(f"    {ts_code}: {count} 条记录 (累计: {total_records})")
                    if total_records >= 20000:  # 如果已达到2万条数据，停止
                        print(f"      已达到20,000条记录目标，停止下载")
                        break
                else:
                    print(f"    {ts_code}: 无数据")
            except Exception as e:
                print(f"    {ts_code} 日线数据下载失败: {e}")
                continue

            # 每下载10只股票暂停一下，防止触发频率限制
            if (i + 1) % 10 == 0:
                print(f"      已下载{i+1}只股票，暂停一下...")
                time.sleep(1)

        print(f"  日线数据总计: {total_records} 条记录")

        # 测试每日指标数据（最近3个月）
        try:
            print(f"  尝试下载每日指标数据...")
            daily_basic = downloader.daily_data.download_daily_basic_range(start_date_str, end_date_str)
            if daily_basic is not None and not daily_basic.empty:
                basic_count = len(daily_basic)
                print(f"  每日指标: {basic_count} 条记录")
                total_records += basic_count
            else:
                print(f"  每日指标: 无数据")
        except Exception as e:
            print(f"  每日指标数据下载失败: {e}")

        print(f"  日线数据（含每日指标）总计: {total_records} 条记录")

        elapsed = time.time() - start_time
        print(f"  日线数据接口测试完成，耗时: {elapsed:.2f}秒")
        return elapsed
    except Exception as e:
        print(f"  日线数据接口测试失败: {e}")
        return None

def test_market_flow_large(downloader):
    """测试资金流向接口 - 重点获取大量数据"""
    print("测试资金流向接口（大容量版）...")
    start_time = time.time()

    try:
        # 测试最近3个月的资金流向数据
        end_date = datetime.now()
        start_date = end_date - timedelta(days=90)
        start_date_str = start_date.strftime('%Y%m%d')
        end_date_str = end_date.strftime('%Y%m%d')

        print(f"  下载 {start_date_str} 到 {end_date_str} 的资金流向数据...")
        moneyflow = downloader.market_flow.download_moneyflow_range(start_date_str, end_date_str)
        total_records = len(moneyflow) if moneyflow is not None and not moneyflow.empty else 0
        print(f"  资金流向: {total_records} 条记录")

        # 尝试使用高级资金流向接口
        try:
            # 获取最近交易日
            trade_cal = downloader.basic_data.download_trade_cal(start_date=start_date_str, end_date=end_date_str)
            trading_days = trade_cal[trade_cal['is_open'] == 1]['cal_date'].tolist()
            if trading_days and total_records < 20000:
                print(f"  继续下载高级资金流向数据...")
                # 使用最近的几个交易日
                recent_days = trading_days[-5:] if len(trading_days) >= 5 else trading_days  # 最近5个交易日

                for trade_date in recent_days:
                    try:
                        # 东财资金流向
                        moneyflow_dc = downloader.market_flow.download_moneyflow_dc(trade_date=trade_date)
                        if moneyflow_dc is not None and not moneyflow_dc.empty:
                            count = len(moneyflow_dc)
                            total_records += count
                            print(f"    资金流向(东财 {trade_date}): {count} 条记录")
                            if total_records >= 20000:
                                break
                    except Exception as e:
                        print(f"    资金流向(东财 {trade_date})下载失败: {e}")
                        continue

                    try:
                        # 同花顺资金流向
                        moneyflow_ths = downloader.market_flow.download_moneyflow_ths(trade_date=trade_date)
                        if moneyflow_ths is not None and not moneyflow_ths.empty:
                            count = len(moneyflow_ths)
                            total_records += count
                            print(f"    资金流向(同花顺 {trade_date}): {count} 条记录")
                            if total_records >= 20000:
                                break
                    except Exception as e:
                        print(f"    资金流向(同花顺 {trade_date})下载失败: {e}")
                        continue

                    if total_records >= 20000:
                        break

        except Exception as e:
            print(f"  高级资金流向接口测试失败: {e}")

        print(f"  资金流向总计: {total_records} 条记录")

        elapsed = time.time() - start_time
        print(f"  资金流向接口测试完成，耗时: {elapsed:.2f}秒")
        return elapsed
    except Exception as e:
        print(f"  资金流向接口测试失败: {e}")
        return None

def main():
    """主测试函数 - 只测试能获取大量数据的接口"""
    print("开始大容量接口下载速度测试...")
    print("目标: 每个接口下载至少20,000条数据")
    print("=" * 70)

    # 初始化下载器
    downloader = TuShareDownloader()

    # 存储各接口测试结果
    results = {}

    # 只测试能获取大量数据的关键接口
    test_functions = [
        ("日线数据", test_daily_data_large),
        ("财务数据", test_financial_data_large),
        ("技术因子", test_technical_factors_large),
        ("资金流向", test_market_flow_large),
    ]

    for interface_name, test_func in test_functions:
        try:
            print(f"\n开始测试: {interface_name}")
            elapsed_time = test_func(downloader)
            results[interface_name] = elapsed_time
            print("-" * 50)
        except Exception as e:
            print(f"{interface_name} 测试出错: {e}")
            results[interface_name] = None
            print("-" * 50)

    # 输出测试总结
    print("=" * 70)
    print("大容量测试总结:")
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

    print("\n大容量接口下载速度测试完成!")

if __name__ == "__main__":
    main()