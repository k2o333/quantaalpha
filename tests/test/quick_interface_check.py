#!/usr/bin/env python3
"""
简化版接口下载速度监控脚本
可用于定期检查各接口的响应速度
"""
import sys
import time
import pandas as pd
from datetime import datetime, timedelta

# 添加项目路径
sys.path.insert(0, '/home/quan/testdata/aspipe_v4')

from app.tushare_api import TuShareDownloader

def quick_interface_test():
    """快速测试各接口的基本功能和响应速度"""
    print("开始快速接口测试...")
    print("-" * 40)

    # 初始化下载器
    downloader = TuShareDownloader()

    results = []

    # 1. 基础数据接口测试
    start_time = time.time()
    try:
        stock_count = len(downloader.basic_data.download_stock_basic())
        elapsed = time.time() - start_time
        results.append(("基础数据", stock_count, f"{elapsed:.2f}秒", "成功"))
        print(f"基础数据接口: {stock_count}条记录, 耗时{elapsed:.2f}秒")
    except Exception as e:
        elapsed = time.time() - start_time
        results.append(("基础数据", 0, f"{elapsed:.2f}秒", f"失败: {str(e)}"))
        print(f"基础数据接口测试失败: {e}")

    # 2. 日线数据接口测试 (测试1只股票)
    start_time = time.time()
    try:
        # 获取一只股票代码
        stock_basic = downloader.basic_data.download_stock_basic()
        if not stock_basic.empty:
            ts_code = stock_basic.iloc[0]['ts_code']
            start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')
            end_date = datetime.now().strftime('%Y%m%d')
            daily_data = downloader.daily_data.download_daily_data(ts_code, start_date=start_date, end_date=end_date)
            record_count = len(daily_data)
            elapsed = time.time() - start_time
            results.append(("日线数据", record_count, f"{elapsed:.2f}秒", "成功"))
            print(f"日线数据接口: {record_count}条记录, 耗时{elapsed:.2f}秒")
        else:
            results.append(("日线数据", 0, "0.00秒", "失败: 无法获取股票代码"))
            print("日线数据接口测试失败: 无法获取股票代码")
    except Exception as e:
        elapsed = time.time() - start_time
        results.append(("日线数据", 0, f"{elapsed:.2f}秒", f"失败: {str(e)}"))
        print(f"日线数据接口测试失败: {e}")

    # 3. 资金流向接口测试
    start_time = time.time()
    try:
        start_date = (datetime.now() - timedelta(days=7)).strftime('%Y%m%d')
        end_date = datetime.now().strftime('%Y%m%d')
        moneyflow_data = downloader.market_flow.download_moneyflow_range(start_date, end_date)
        record_count = len(moneyflow_data)
        elapsed = time.time() - start_time
        results.append(("资金流向", record_count, f"{elapsed:.2f}秒", "成功"))
        print(f"资金流向接口: {record_count}条记录, 耗时{elapsed:.2f}秒")
    except Exception as e:
        elapsed = time.time() - start_time
        results.append(("资金流向", 0, f"{elapsed:.2f}秒", f"失败: {str(e)}"))
        print(f"资金流向接口测试失败: {e}")

    # 输出汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总:")
    print("=" * 60)
    print(f"{'接口名称':<12} {'数据量':<10} {'耗时':<10} {'状态'}")
    print("-" * 60)

    total_time = 0
    success_count = 0

    for name, count, elapsed, status in results:
        print(f"{name:<12} {count:<10} {elapsed:<10} {status}")
        if "成功" in status:
            # 提取耗时数字
            elapsed_time = float(elapsed.replace("秒", ""))
            total_time += elapsed_time
            success_count += 1

    print("-" * 60)
    print(f"成功接口数: {success_count}/{len(results)}")
    print(f"总耗时: {total_time:.2f}秒")
    if success_count > 0:
        print(f"平均耗时: {total_time/success_count:.2f}秒")

    return results

if __name__ == "__main__":
    quick_interface_test()