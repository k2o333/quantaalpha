#!/usr/bin/env python3
"""
增强版接口下载速度测试脚本
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

def get_last_year_quarters():
    """获取最近4个季度"""
    current_year = datetime.now().year
    current_month = datetime.now().month
    quarters = []

    # 获取最近4个季度
    for i in range(4):
        if current_month <= 3:
            quarter = f"{current_year-1}1231"
        elif current_month <= 6:
            quarter = f"{current_year}0331"
        elif current_month <= 9:
            quarter = f"{current_year}0630"
        else:
            quarter = f"{current_year}0930"

        quarters.append(quarter)
        # 计算上一季度
        year, month = int(quarter[:4]), int(quarter[4:])
        if month == 331:
            prev_quarter = f"{year}1231"
        elif month == 630:
            prev_quarter = f"{year}0331"
        elif month == 930:
            prev_quarter = f"{year}0630"
        else:  # month == 1231
            prev_quarter = f"{year-1}0930"

        quarters = [prev_quarter] + quarters

    return quarters[:4]

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

        # 测试分红信息
        dividend = downloader.basic_data.download_dividend()
        print(f"  分红信息: {len(dividend)} 条记录")

        # 测试新股信息
        new_share_start, new_share_end = get_last_3_months()
        try:
            new_share = downloader.basic_data.download_new_share(start_date=new_share_start, end_date=new_share_end)
            print(f"  新股信息: {len(new_share)} 条记录")
        except:
            print("  新股信息: 无数据或权限不足")

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

        # 增加测试股票数量以获取更多数据
        test_stocks = stock_basic.head(10)['ts_code'].tolist()  # 测试前10只股票

        # 测试日线数据（最近3个月）
        start_date, end_date = get_last_3_months()
        total_records = 0

        for ts_code in test_stocks:
            try:
                daily_data = downloader.daily_data.download_daily_data(ts_code, start_date=start_date, end_date=end_date)
                total_records += len(daily_data)
                if total_records >= 20000:  # 如果已达到2万条数据，停止
                    break
            except Exception as e:
                print(f"    {ts_code} 日线数据下载失败: {e}")
                continue

        print(f"  日线数据: {total_records} 条记录 (测试{min(len(test_stocks), len([x for x in test_stocks if total_records < 20000]))}只股票)")

        # 测试每日指标数据（最近3个月）
        try:
            daily_basic = downloader.daily_data.download_daily_basic_range(start_date, end_date)
            print(f"  每日指标: {len(daily_basic)} 条记录")
            total_records += len(daily_basic)
        except Exception as e:
            print(f"  每日指标数据下载失败: {e}")

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
        periods = [f"{current_year}0930", f"{current_year}0630", f"{current_year}0331", f"{current_year-1}1231"]

        total_records = 0

        # 使用VIP接口获取全市场数据
        for period in periods:
            try:
                # 尝试使用VIP接口
                try:
                    income = downloader.financial_data.download_income(period=period)
                    total_records += len(income)
                    print(f"  利润表({period}): {len(income)} 条记录")
                except:
                    print(f"  利润表({period}): 下载失败")

                if total_records >= 20000:  # 如果已达到2万条数据，停止
                    break

            except Exception as e:
                print(f"    财报({period})数据下载失败: {e}")
                continue

        print(f"  财务数据总计: {total_records} 条记录")

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
        # 测试最近一个月的资金流向数据
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        start_date_str = start_date.strftime('%Y%m%d')
        end_date_str = end_date.strftime('%Y%m%d')

        moneyflow = downloader.market_flow.download_moneyflow_range(start_date_str, end_date_str)
        print(f"  资金流向: {len(moneyflow)} 条记录")

        # 尝试使用高级资金流向接口
        try:
            # 获取最近交易日
            trade_cal = downloader.basic_data.download_trade_cal(start_date=start_date_str, end_date=end_date_str)
            trading_days = trade_cal[trade_cal['is_open'] == 1]['cal_date'].tolist()
            if trading_days:
                latest_trade_date = trading_days[-1]

                # 测试多个资金流向接口
                try:
                    moneyflow_dc = downloader.market_flow.download_moneyflow_dc(trade_date=latest_trade_date)
                    print(f"  资金流向(东财): {len(moneyflow_dc)} 条记录")
                except:
                    print("  资金流向(东财): 无数据或权限不足")

                try:
                    moneyflow_ths = downloader.market_flow.download_moneyflow_ths(trade_date=latest_trade_date)
                    print(f"  资金流向(同花顺): {len(moneyflow_ths)} 条记录")
                except:
                    print("  资金流向(同花顺): 无数据或权限不足")

        except Exception as e:
            print(f"  高级资金流向接口测试失败: {e}")

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

        test_stocks = stock_basic.head(5)['ts_code'].tolist()  # 测试前5只股票

        total_records = 0
        for ts_code in test_stocks:
            try:
                # 测试前十大股东
                holders = downloader.holders_data.download_top10_holders(ts_code)
                total_records += len(holders)

                # 测试前十大流通股东 (需要5000积分)
                try:
                    float_holders = downloader.holders_data.download_top10_floatholders(ts_code)
                    total_records += len(float_holders)
                except:
                    pass  # 5000积分以下用户可能无法访问

            except Exception as e:
                print(f"    {ts_code} 股东数据下载失败: {e}")
                continue

        print(f"  股东数据: {total_records} 条记录 (测试{len(test_stocks)}只股票)")

        # 测试管理层薪酬 (如果积分足够)
        try:
            # 获取更多股票测试
            test_stocks2 = stock_basic.head(10)['ts_code'].tolist()
            all_rewards = []
            for ts_code in test_stocks2:
                try:
                    rewards = downloader.holders_data.download_stk_rewards(ts_code)
                    all_rewards.append(rewards)
                    total_records += len(rewards)
                    if total_records >= 20000:  # 如果已达到2万条数据，停止
                        break
                except:
                    continue

            print(f"  管理层薪酬数据: {sum(len(r) for r in all_rewards if r is not None and not r.empty)} 条记录")
        except Exception as e:
            print(f"  管理层薪酬接口测试失败: {e}")

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
        start_date = end_date - timedelta(days=30)  # 增加时间范围
        start_date_str = start_date.strftime('%Y%m%d')
        end_date_str = end_date.strftime('%Y%m%d')

        # 获取交易日历
        trade_cal = downloader.basic_data.download_trade_cal(start_date=start_date_str, end_date=end_date_str)
        trading_days = trade_cal[trade_cal['is_open'] == 1]['cal_date'].tolist()

        total_records = 0
        if trading_days:
            # 尝试获取多个交易日的技术因子数据
            for trade_date in trading_days[:5]:  # 取前5个交易日
                try:
                    stk_factor = downloader.technical_factors.download_stk_factor(trade_date=trade_date)
                    total_records += len(stk_factor)
                    if total_records >= 20000:  # 如果已达到2万条数据，停止
                        break
                except:
                    continue

        print(f"  技术因子: {total_records} 条记录")

        # 测试筹码分布数据
        try:
            if trading_days:
                for trade_date in trading_days[:3]:  # 取前3个交易日
                    try:
                        cyq_perf = downloader.technical_factors.download_cyq_perf(trade_date=trade_date)
                        total_records += len(cyq_perf)
                        if total_records >= 20000:  # 如果已达到2万条数据，停止
                            break
                    except:
                        continue
        except Exception as e:
            print(f"  筹码分布接口测试失败: {e}")

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
        # 测试最近一个月的停复牌信息
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)  # 增加时间范围
        start_date_str = start_date.strftime('%Y%m%d')
        end_date_str = end_date.strftime('%Y%m%d')

        suspend_data = downloader.market_structure.download_suspend_d_range(start_date_str, end_date_str)
        print(f"  停复牌信息: {len(suspend_data)} 条记录")

        # 测试大宗交易数据
        try:
            block_trade = downloader.market_structure.download_block_trade(start_date=start_date_str, end_date=end_date_str)
            print(f"  大宗交易: {len(block_trade)} 条记录")
        except Exception as e:
            print(f"  大宗交易接口测试失败: {e}")

        # 测试限售股解禁数据
        try:
            share_float = downloader.market_structure.download_share_float(start_date=start_date_str, end_date=end_date_str)
            print(f"  限售股解禁: {len(share_float)} 条记录")
        except Exception as e:
            print(f"  限售股解禁接口测试失败: {e}")

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
        periods = [f"{current_year}0930", f"{current_year}0630", f"{current_year}0331", f"{current_year-1}1231"]

        total_records = 0
        for period in periods:
            try:
                report_rc = downloader.research_data.download_report_rc(period=period)
                total_records += len(report_rc)
                if total_records >= 20000:  # 如果已达到2万条数据，停止
                    break
            except Exception as e:
                print(f"    研究数据({period})下载失败: {e}")
                continue

        print(f"  研究数据: {total_records} 条记录")

        # 测试机构调研数据
        try:
            for period in periods:
                try:
                    stk_surv = downloader.research_data.download_stk_surv(period=period)
                    total_records += len(stk_surv)
                    if total_records >= 20000:  # 如果已达到2万条数据，停止
                        break
                except:
                    continue
            print(f"  机构调研: {total_records - len(report_rc) if 'report_rc' in locals() else total_records} 条记录 (累计)")
        except Exception as e:
            print(f"  机构调研接口测试失败: {e}")

        elapsed = time.time() - start_time
        print(f"  研究数据接口测试完成，耗时: {elapsed:.2f}秒")
        return elapsed
    except Exception as e:
        print(f"  研究数据接口测试失败: {e}")
        return None

def main():
    """主测试函数"""
    print("开始增强版接口下载速度测试...")
    print("目标: 每个接口下载至少20,000条数据")
    print("=" * 60)

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
    print("=" * 60)
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

    print("\n增强版接口下载速度测试完成!")

if __name__ == "__main__":
    main()