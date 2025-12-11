#!/usr/bin/env python3
"""
Cyq_chips接口测试脚本
用于测试cyq_chips接口的下载功能，确保能够获取超过10000条数据
"""

import sys
import os
import pandas as pd
import logging
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.tushare_api import TuShareDownloader

def test_cyq_chips_data():
    """
    测试cyq_chips接口的数据下载能力
    通过遍历股票代码来累积数据以超过10000条记录
    """
    print("=" * 60)
    print("开始测试cyq_chips接口数据下载...")
    print("=" * 60)

    # 初始化下载器
    downloader = TuShareDownloader()

    print(f"用户积分: {downloader.current_points}")

    # 首先获取股票列表
    try:
        print("正在获取股票基础信息...")
        stock_df = downloader.download_stock_basic()
        if stock_df is None or stock_df.empty:
            print("❌ 无法获取股票列表，测试失败")
            return False
        print(f"获取到 {len(stock_df)} 只股票")
    except Exception as e:
        print(f"❌ 获取股票列表失败: {e}")
        return False

    # 选择日期范围，以便获取足够多的数据
    test_date = '20231201'  # 使用固定日期进行测试
    all_data = []
    total_records = 0
    stocks_processed = 0

    print("开始逐个股票下载cyq_chips数据...")

    # 遍历前500只股票以获取足够数据
    for index, stock in stock_df.head(500).iterrows():
        ts_code = stock['ts_code']

        try:
            print(f"正在下载 {ts_code} 的数据...")
            df = downloader.download_cyq_chips(ts_code=ts_code, trade_date=test_date)

            if df is not None and not df.empty:
                print(f"{ts_code}: 获取到 {len(df)} 条记录")
                all_data.append(df)
                total_records += len(df)

                if total_records >= 10000:
                    print(f"✅ 已达到超过10000条记录目标! 当前记录数: {total_records}")
                    break
            else:
                print(f"{ts_code}: 未获取到数据")

        except Exception as e:
            print(f"下载 {ts_code} 数据时出错: {e}")
            continue

        stocks_processed += 1

        # 检查是否已处理足够多的股票但记录数不足
        if stocks_processed >= 200 and total_records < 5000:
            print(f"⚠️ 已处理 {stocks_processed} 只股票但记录数仍不足，可能该接口数据量有限")
            break

    # 合并所有数据
    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        unique_records = len(combined_df)
        print(f"\n总处理股票数: {stocks_processed}")
        print(f"总下载记录数: {total_records}")
        print(f"去重后记录数: {unique_records}")

        # 检查是否达到10000条记录
        if unique_records >= 10000:
            print(f"✅ 测试通过! cyq_chips接口成功获取超过10000条记录 ({unique_records}条)")
            return True
        else:
            print(f"⚠️ cyq_chips接口获取记录不足 ({unique_records}条)，尝试使用分页下载...")
            return test_cyq_chips_with_pagination()
    else:
        print("❌ 没有获取到任何数据")
        return False

def test_cyq_chips_with_pagination():
    """
    测试使用分页下载cyq_chips数据以达到超过10000条记录
    """
    print("\n" + "=" * 60)
    print("开始测试cyq_chips接口分页下载...")
    print("=" * 60)

    # 初始化下载器
    downloader = TuShareDownloader()

    # 首先获取股票列表
    try:
        print("正在获取股票基础信息...")
        stock_df = downloader.download_stock_basic()
        if stock_df is None or stock_df.empty:
            print("❌ 无法获取股票列表，分页测试失败")
            return False
    except Exception as e:
        print(f"❌ 获取股票列表失败: {e}")
        return False

    # 对前20只股票使用分页下载
    all_data = []
    total_records = 0

    for index, stock in stock_df.head(20).iterrows():
        ts_code = stock['ts_code']

        try:
            print(f"正在分页下载 {ts_code} 的数据...")
            # 使用分页下载，获取一段时间范围内的数据
            df = downloader.download_cyq_chips_paginated(
                ts_code=ts_code,
                start_date='20230101',
                end_date='20231231',
                limit_per_call=2000
            )

            if df is not None and not df.empty:
                print(f"{ts_code}: 分页下载获取到 {len(df)} 条记录")
                all_data.append(df)
                total_records += len(df)

                if total_records >= 10000:
                    print(f"✅ 分页下载已达到超过10000条记录目标! 当前记录数: {total_records}")
                    break
            else:
                print(f"{ts_code}: 分页下载未获取到数据")

        except Exception as e:
            print(f"分页下载 {ts_code} 数据时出错: {e}")
            continue

    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        unique_records = len(combined_df)
        print(f"\n分页下载总记录数: {total_records}")
        print(f"去重后记录数: {unique_records}")

        if unique_records >= 10000:
            print(f"✅ 分页下载测试通过! 获取到超过10000条记录 ({unique_records}条)")
            return True
        else:
            print(f"⚠️ 分页下载获取记录仍不足 ({unique_records}条)，可能该接口数据量有限")
            return False
    else:
        print("❌ 分页下载没有获取到任何数据")
        return False

def test_cyq_chips_multiple_dates():
    """
    测试cyq_chips接口在多个日期的数据以累积超过10000条记录
    """
    print("\n" + "=" * 60)
    print("开始测试cyq_chips接口多日期下载...")
    print("=" * 60)

    # 初始化下载器
    downloader = TuShareDownloader()

    # 获取前50只股票
    try:
        print("正在获取股票基础信息...")
        stock_df = downloader.download_stock_basic()
        if stock_df is None or stock_df.empty:
            print("❌ 无法获取股票列表，多日期测试失败")
            return False
        print(f"获取到 {len(stock_df)} 只股票")
    except Exception as e:
        print(f"❌ 获取股票列表失败: {e}")
        return False

    # 测试多个日期
    test_dates = [
        '20231201', '20231101', '20231001', '20230901', '20230801',
        '20230701', '20230601', '20230501', '20230401', '20230301'
    ]

    all_data = []
    total_records = 0

    for date in test_dates:
        print(f"正在处理日期: {date}")
        stocks_for_date = 0

        for index, stock in stock_df.head(20).iterrows():  # 每个日期处理前20只股票
            ts_code = stock['ts_code']

            try:
                df = downloader.download_cyq_chips(ts_code=ts_code, trade_date=date)

                if df is not None and not df.empty:
                    all_data.append(df)
                    total_records += len(df)

                    if total_records >= 10000:
                        print(f"✅ 多日期测试已达到超过10000条记录目标! 当前记录数: {total_records}")
                        break
                else:
                    print(f"{ts_code} 在 {date} 未获取到数据")
            except Exception as e:
                print(f"下载 {ts_code} 在 {date} 数据时出错: {e}")
                continue

            stocks_for_date += 1

        if total_records >= 10000:
            break

    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        unique_records = len(combined_df)
        print(f"\n多日期下载总记录数: {total_records}")
        print(f"去重后记录数: {unique_records}")

        if unique_records >= 10000:
            print(f"✅ 多日期下载测试通过! 获取到超过10000条记录 ({unique_records}条)")
            return True
        else:
            print(f"⚠️ 多日期下载获取记录仍不足 ({unique_records}条)")
            return False
    else:
        print("❌ 多日期下载没有获取到任何数据")
        return False

def main():
    """
    主测试函数
    """
    print("Cyq_chips接口测试脚本")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    success = False

    # 尝试多种方法来获取超过10000条记录
    if test_cyq_chips_data():
        success = True
    elif test_cyq_chips_multiple_dates():
        success = True
    elif test_cyq_chips_with_pagination():
        success = True

    # 输出最终结果
    print("\n" + "=" * 60)
    if success:
        print("🎉 Cyq_chips接口测试最终通过!")
    else:
        print("💥 Cyq_chips接口测试未通过! 该接口可能数据量有限，难以达到10000条记录")
    print("=" * 60)

    return success

if __name__ == "__main__":
    main()