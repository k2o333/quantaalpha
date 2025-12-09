#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试两个接口按天下载数据的极限速率
"""

import sys
import time
import pandas as pd
from datetime import datetime, timedelta

import os
# 添加项目根目录到Python路径
sys.path.append('/home/quan/testdata/aspipe_v4')

# 切换到app目录以确保正确导入
current_dir = os.getcwd()
if current_dir.endswith('vali'):
    os.chdir('/home/quan/testdata/aspipe_v4/app')

from tushare_api import TuShareDownloader
from config import TUSHARE_POINTS

# 切换回原目录
os.chdir(current_dir)

def get_recent_trading_days(count=10):
    """
    获取最近的交易日列表
    """
    downloader = TuShareDownloader()
    try:
        # 获取最近30天的交易日历
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=30)).strftime('%Y%m%d')

        trade_cal = downloader.download_trade_cal(
            exchange='SSE',
            start_date=start_date,
            end_date=end_date
        )

        # 过滤出交易日并取最近的几个
        trading_days = trade_cal[trade_cal['is_open'] == 1]['cal_date'].tolist()
        trading_days.sort(reverse=True)  # 倒序排列，最新的在前面

        return trading_days[:count]
    except Exception as e:
        print(f"获取交易日历失败: {e}")
        # 返回默认的测试日期
        return ['20241206', '20241205', '20241204', '20241203', '20241202']

def test_daily_download_rate():
    """
    测试daily接口按天下载的速率
    """
    print("测试 daily 接口按天下载速率...")
    downloader = TuShareDownloader()

    # 获取最近的交易日
    trading_days = get_recent_trading_days(5)
    print(f"测试日期: {trading_days}")

    total_records = 0
    total_time = 0

    for i, trade_date in enumerate(trading_days):
        print(f"\n[{i+1}/{len(trading_days)}] 下载 {trade_date} 的数据...")

        try:
            start_time = time.time()
            # 下载指定日期的daily数据
            result = downloader.download_daily_data(
                ts_code=None,  # 下载所有股票
                start_date=trade_date,
                end_date=trade_date
            )
            end_time = time.time()

            download_time = end_time - start_time
            record_count = len(result)

            print(f"  - 记录数: {record_count}")
            print(f"  - 耗时: {download_time:.2f}秒")
            print(f"  - 平均速率: {record_count/download_time:.0f} records/秒" if download_time > 0 else "N/A")

            total_records += record_count
            total_time += download_time

        except Exception as e:
            print(f"  - 下载失败: {e}")
            continue

    if total_time > 0:
        avg_rate = total_records / total_time
        print(f"\ndaily接口总体性能:")
        print(f"  - 总记录数: {total_records}")
        print(f"  - 总耗时: {total_time:.2f}秒")
        print(f"  - 平均速率: {avg_rate:.0f} records/秒")

    return total_records, total_time

def test_daily_basic_download_rate():
    """
    测试daily_basic接口按天下载的速率
    """
    print("\n测试 daily_basic 接口按天下载速率...")
    downloader = TuShareDownloader()

    # 获取最近的交易日
    trading_days = get_recent_trading_days(5)
    print(f"测试日期: {trading_days}")

    total_records = 0
    total_time = 0

    for i, trade_date in enumerate(trading_days):
        print(f"\n[{i+1}/{len(trading_days)}] 下载 {trade_date} 的数据...")

        try:
            start_time = time.time()
            # 下载指定日期的daily_basic数据
            result = downloader.download_daily_basic(trade_date=trade_date)
            end_time = time.time()

            download_time = end_time - start_time
            record_count = len(result)

            print(f"  - 记录数: {record_count}")
            print(f"  - 耗时: {download_time:.2f}秒")
            print(f"  - 平均速率: {record_count/download_time:.0f} records/秒" if download_time > 0 else "N/A")

            total_records += record_count
            total_time += download_time

        except Exception as e:
            print(f"  - 下载失败: {e}")
            continue

    if total_time > 0:
        avg_rate = total_records / total_time
        print(f"\ndaily_basic接口总体性能:")
        print(f"  - 总记录数: {total_records}")
        print(f"  - 总耗时: {total_time:.2f}秒")
        print(f"  - 平均速率: {avg_rate:.0f} records/秒")

    return total_records, total_time

def main():
    """
    主函数
    """
    print("=" * 60)
    print("TuShare API 按天下载速率测试")
    print(f"Token积分: {TUSHARE_POINTS}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 测试daily接口
    daily_records, daily_time = test_daily_download_rate()

    # 测试daily_basic接口
    daily_basic_records, daily_basic_time = test_daily_basic_download_rate()

    # 输出最终结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    if daily_time > 0:
        print(f"daily接口:")
        print(f"  - 平均速率: {daily_records/daily_time:.0f} records/秒")
        print(f"  - 总记录数: {daily_records}")
        print(f"  - 总耗时: {daily_time:.2f}秒")

    if daily_basic_time > 0:
        print(f"daily_basic接口:")
        print(f"  - 平均速率: {daily_basic_records/daily_basic_time:.0f} records/秒")
        print(f"  - 总记录数: {daily_basic_records}")
        print(f"  - 总耗时: {daily_basic_time:.2f}秒")

    print("=" * 60)
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()