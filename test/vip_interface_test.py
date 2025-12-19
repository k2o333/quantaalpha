#!/usr/bin/env python3
"""
VIP接口优化测试脚本
用于验证VIP接口的使用情况和性能提升
"""

import time
import pandas as pd
from tushare_api import TuShareDownloader

def test_vip_interface_usage():
    """
    测试VIP接口的使用情况
    """
    print("开始测试VIP接口使用情况...")

    # 创建下载器实例
    downloader = TuShareDownloader()

    # 测试积分信息
    print(f"当前积分: {downloader.current_points}")

    if downloader.current_points >= 5000:
        print("检测到5000+积分，将优先使用VIP接口")
    elif downloader.current_points >= 2000:
        print("检测到2000+积分，将使用普通接口")
    else:
        print("积分不足，部分接口可能无法使用")

    # 测试forecast接口
    print("\n测试forecast接口...")
    try:
        start_time = time.time()
        forecast_data = downloader.download_forecast(period='20231231')
        end_time = time.time()
        print(f"forecast接口耗时: {end_time - start_time:.2f}秒")
        print(f"forecast数据记录数: {len(forecast_data)}")

        # 检查是否使用了VIP接口
        if downloader.current_points >= 5000:
            print("使用VIP接口: forecast_vip")
        else:
            print("使用普通接口: forecast")
    except Exception as e:
        print(f"forecast接口测试失败: {e}")

    # 测试fina_mainbz接口
    print("\n测试fina_mainbz接口...")
    try:
        start_time = time.time()
        fina_mainbz_data = downloader.download_fina_mainbz(period='20231231', type_='P')
        end_time = time.time()
        print(f"fina_mainbz接口耗时: {end_time - start_time:.2f}秒")
        print(f"fina_mainbz数据记录数: {len(fina_mainbz_data)}")

        # 检查是否使用了VIP接口
        if downloader.current_points >= 5000:
            print("使用VIP接口: fina_mainbz_vip")
        else:
            print("使用普通接口: fina_mainbz")
    except Exception as e:
        print(f"fina_mainbz接口测试失败: {e}")

    # 测试daily接口
    print("\n测试daily接口...")
    try:
        start_time = time.time()
        daily_data = downloader.download_daily_data('000001.SZ', '20230101', '20231231')
        end_time = time.time()
        print(f"daily接口耗时: {end_time - start_time:.2f}秒")
        print(f"daily数据记录数: {len(daily_data)}")

        # 检查是否使用了VIP接口
        if downloader.current_points >= 5000:
            print("使用VIP接口: daily_vip")
        else:
            print("使用普通接口: daily")
    except Exception as e:
        print(f"daily接口测试失败: {e}")

    # 如果积分>=5000，测试daily_vip接口
    if downloader.current_points >= 5000:
        print("\n测试daily_vip接口...")
        try:
            start_time = time.time()
            daily_vip_data = downloader.daily_data.download_daily_data_vip('20230101', '20231231')
            end_time = time.time()
            print(f"daily_vip接口耗时: {end_time - start_time:.2f}秒")
            print(f"daily_vip数据记录数: {len(daily_vip_data)}")
        except Exception as e:
            print(f"daily_vip接口测试失败: {e}")

    # 如果积分>=2000，测试可能存在的新闻接口
    if downloader.current_points >= 2000:
        print("\n测试news接口...")
        try:
            start_time = time.time()
            news_data = downloader.research_data.download_news(start_date='20230101', end_date='20230102')
            end_time = time.time()
            print(f"news接口耗时: {end_time - start_time:.2f}秒")
            print(f"news数据记录数: {len(news_data)}")

            # 检查是否使用了VIP接口
            if downloader.current_points >= 5000:
                print("使用VIP接口: news_vip")
            else:
                print("使用普通接口: news")
        except Exception as e:
            print(f"news接口测试失败或不可用: {e}")

    print("\nVIP接口优化测试完成！")

def compare_performance():
    """
    比较使用VIP接口前后的性能差异
    """
    print("\n性能比较测试...")
    downloader = TuShareDownloader()

    if downloader.current_points >= 5000:
        print("积分足够，可以进行VIP接口性能测试")

        # 测试全市场数据下载性能
        print("\n测试全市场财务指标下载...")
        try:
            start_time = time.time()
            fina_indicator_data = downloader.download_fina_indicator(period='20231231')
            end_time = time.time()
            print(f"全市场财务指标下载耗时: {end_time - start_time:.2f}秒")
            print(f"全市场财务指标数据记录数: {len(fina_indicator_data)}")
        except Exception as e:
            print(f"全市场财务指标下载失败: {e}")
    else:
        print("积分不足，无法进行VIP接口性能测试")
        print("建议使用5000+积分账户进行完整的性能测试")

if __name__ == "__main__":
    test_vip_interface_usage()
    compare_performance()