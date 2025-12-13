#!/usr/bin/env python3
"""
快速接口验证脚本
验证所有接口都能正常返回数据，特别是之前有问题的接口
"""
import sys
import time
import pandas as pd
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, '/home/quan/testdata/aspipe_v4')

from app.tushare_api import TuShareDownloader

def test_interface(name, func, *args, **kwargs):
    """测试单个接口"""
    print(f"测试 {name}...")
    start_time = time.time()

    try:
        result = func(*args, **kwargs)
        elapsed = time.time() - start_time

        if result is not None and not result.empty:
            print(f"  ✓ {name}: {len(result)} 条记录, 耗时 {elapsed:.2f}秒")
            return True, len(result), elapsed
        else:
            print(f"  ✗ {name}: 无数据返回, 耗时 {elapsed:.2f}秒")
            return False, 0, elapsed
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"  ✗ {name}: 错误 - {e}, 耗时 {elapsed:.2f}秒")
        return False, 0, elapsed

def main():
    """主测试函数"""
    print("开始快速接口验证测试...")
    print("=" * 50)

    # 初始化下载器
    downloader = TuShareDownloader()

    # 获取基础数据用于测试
    print("获取基础股票列表...")
    stock_basic = downloader.basic_data.download_stock_basic()
    if stock_basic.empty:
        print("无法获取股票列表，测试终止")
        return

    test_stock = stock_basic.iloc[0]['ts_code'] if not stock_basic.empty else '000001.SZ'
    print(f"使用股票代码: {test_stock}")

    # 获取最近的交易日和日期范围
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    start_date_str = start_date.strftime('%Y%m%d')
    end_date_str = end_date.strftime('%Y%m%d')

    # 获取交易日历
    trade_cal = downloader.basic_data.download_trade_cal(start_date=start_date_str, end_date=end_date_str)
    trading_days = trade_cal[trade_cal['is_open'] == 1]['cal_date'].tolist() if not trade_cal.empty else []
    latest_trade_date = trading_days[-1] if trading_days else end_date_str

    print(f"最近交易日: {latest_trade_date}")

    # 测试结果统计
    results = []

    # 1. 基础数据接口
    print("\n--- 基础数据接口 ---")
    results.append(test_interface("股票基本信息", downloader.basic_data.download_stock_basic))
    results.append(test_interface("交易日历", downloader.basic_data.download_trade_cal, start_date=start_date_str, end_date=end_date_str))

    # 2. 日线数据接口
    print("\n--- 日线数据接口 ---")
    results.append(test_interface("日线数据", downloader.daily_data.download_daily_data, test_stock, start_date=start_date_str, end_date=end_date_str))

    # 3. 财务数据接口
    print("\n--- 财务数据接口 ---")
    # 获取最近的财报期
    current_year = datetime.now().year
    recent_periods = [f"{current_year}0930", f"{current_year}0630"]

    for period in recent_periods:
        success, count, elapsed = test_interface(f"利润表({period})", downloader.financial_data.download_income, period=period)
        results.append((success, count, elapsed))
        if success and count > 0:
            break  # 如果成功获取到数据就停止

    # 4. 资金流向接口
    print("\n--- 资金流向接口 ---")
    results.append(test_interface("资金流向", downloader.market_flow.download_moneyflow_range, start_date_str, end_date_str))

    # 5. 股东数据接口
    print("\n--- 股东数据接口 ---")
    results.append(test_interface("前十大股东", downloader.holders_data.download_top10_holders, test_stock))

    # 6. 技术因子接口
    print("\n--- 技术因子接口 ---")
    results.append(test_interface("技术因子", downloader.technical_factors.download_stk_factor, trade_date=latest_trade_date))

    # 7. 市场结构接口
    print("\n--- 市场结构接口 ---")
    results.append(test_interface("停复牌信息", downloader.market_structure.download_suspend_d_range, start_date_str, end_date_str))

    # 8. 研究数据接口
    print("\n--- 研究数据接口 ---")
    for period in recent_periods:
        success, count, elapsed = test_interface(f"研究报告({period})", downloader.research_data.download_report_rc, period=period)
        results.append((success, count, elapsed))
        if success and count > 0:
            break  # 如果成功获取到数据就停止

    # 输出测试总结
    print("\n" + "=" * 50)
    print("测试总结:")

    successful = sum(1 for success, _, _ in results if success)
    total = len(results)

    print(f"成功接口数: {successful}/{total}")

    if successful > 0:
        total_time = sum(elapsed for _, _, elapsed in results if elapsed is not None)
        avg_time = total_time / successful
        print(f"平均耗时: {avg_time:.2f}秒")

        # 显示哪些接口成功了
        print("\n成功接口列表:")
        interface_names = [
            "股票基本信息", "交易日历", "日线数据", "利润表",
            "资金流向", "前十大股东", "技术因子", "停复牌信息", "研究报告"
        ]
        for i, (success, count, elapsed) in enumerate(results):
            if i < len(interface_names):
                status = "✓" if success else "✗"
                print(f"  {status} {interface_names[i]}")
    else:
        print("所有接口测试失败，请检查配置和网络连接")

    print("\n快速接口验证测试完成!")

if __name__ == "__main__":
    main()