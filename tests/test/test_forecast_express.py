#!/usr/bin/env python3
"""
测试forecast和express接口能否下载到数据
"""

import sys
import os
import logging
import pandas as pd

# 添加项目路径
sys.path.insert(0, '/home/quan/testdata/aspipe_v4/app')

from tushare_api import TuShareDownloader

def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def get_top_stocks(downloader, count=10):
    """获取市值前10的股票代码"""
    try:
        # 获取股票基本信息
        stock_df = downloader.download_stock_basic()
        if stock_df.empty:
            print("无法获取股票列表")
            return []

        # 简单选择前10只股票作为测试样本
        top_stocks = stock_df.head(count)['ts_code'].tolist()
        print(f"选择的测试股票: {top_stocks}")
        return top_stocks
    except Exception as e:
        print(f"获取股票列表失败: {e}")
        return []

def test_forecast_interface(downloader, stocks, periods):
    """测试forecast接口"""
    print("\n=== 测试forecast接口 ===")

    for period in periods:
        print(f"\n测试期间: {period}")
        total_records = 0

        # 方法1: 使用VIP接口获取整个期间的数据
        try:
            print("尝试使用forecast_vip接口获取整个期间数据...")
            df = downloader.download_forecast_safe(period=period)
            if df is not None and not df.empty:
                print(f"  forecast_vip({period}) 成功获取 {len(df)} 条记录")
                total_records += len(df)
            else:
                print(f"  forecast_vip({period}) 无数据")
        except Exception as e:
            print(f"  forecast_vip({period}) 失败: {e}")

        # 方法2: 逐个股票测试
        if total_records == 0:
            print("逐个股票测试forecast接口...")
            for stock in stocks:
                try:
                    df = downloader.pro.forecast(ts_code=stock, period=period)
                    if df is not None and not df.empty:
                        print(f"  forecast({stock}, {period}) 获取 {len(df)} 条记录")
                        total_records += len(df)
                        # 只测试前几个股票，避免过多请求
                        if len(df) > 0:
                            break
                except Exception as e:
                    print(f"  forecast({stock}, {period}) 失败: {e}")

        if total_records == 0:
            print(f"  期间 {period} 无数据")

def test_express_interface(downloader, stocks, periods):
    """测试express接口"""
    print("\n=== 测试express接口 ===")

    for period in periods:
        print(f"\n测试期间: {period}")
        total_records = 0

        # 方法1: 使用VIP接口获取整个期间的数据
        try:
            print("尝试使用express_vip接口获取整个期间数据...")
            df = downloader.download_express_safe(period=period)
            if df is not None and not df.empty:
                print(f"  express_vip({period}) 成功获取 {len(df)} 条记录")
                total_records += len(df)
            else:
                print(f"  express_vip({period}) 无数据")
        except Exception as e:
            print(f"  express_vip({period}) 失败: {e}")

        # 方法2: 逐个股票测试
        if total_records == 0:
            print("逐个股票测试express接口...")
            for stock in stocks:
                try:
                    df = downloader.pro.express(ts_code=stock, period=period)
                    if df is not None and not df.empty:
                        print(f"  express({stock}, {period}) 获取 {len(df)} 条记录")
                        total_records += len(df)
                        # 只测试前几个股票，避免过多请求
                        if len(df) > 0:
                            break
                except Exception as e:
                    print(f"  express({stock}, {period}) 失败: {e}")

        if total_records == 0:
            print(f"  期间 {period} 无数据")

def test_ann_date_approach(downloader):
    """测试使用公告日期的方式"""
    print("\n=== 测试公告日期方式 ===")

    # 测试几个典型的公告日期
    ann_dates = ['20231231', '20230930', '20230630', '20230331']

    for ann_date in ann_dates:
        try:
            print(f"测试forecast接口公告日期 {ann_date}...")
            df = downloader.pro.forecast(ann_date=ann_date)
            if df is not None and not df.empty:
                print(f"  forecast(ann_date={ann_date}) 获取 {len(df)} 条记录")
                # 显示前几条记录的信息
                print(f"  样本数据: {df[['ts_code', 'ann_date', 'end_date']].head(3).to_dict('records')}")
            else:
                print(f"  forecast(ann_date={ann_date}) 无数据")
        except Exception as e:
            print(f"  forecast(ann_date={ann_date}) 失败: {e}")

def main():
    """主测试函数"""
    setup_logging()

    print("开始测试forecast和express接口...")

    # 创建下载器实例
    downloader = TuShareDownloader()

    # 获取测试股票
    stocks = get_top_stocks(downloader, 10)
    if not stocks:
        print("无法获取测试股票，退出")
        return 1

    # 定义测试期间（过去几年的年报期间）
    test_periods = ['20231231', '20221231', '20211231', '20201231']

    # 测试forecast接口
    test_forecast_interface(downloader, stocks, test_periods)

    # 测试express接口
    test_express_interface(downloader, stocks, test_periods)

    # 测试公告日期方式
    test_ann_date_approach(downloader)

    print("\n测试完成")
    return 0

if __name__ == "__main__":
    sys.exit(main())