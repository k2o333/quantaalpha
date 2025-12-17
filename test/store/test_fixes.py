"""
测试修复后的功能
"""
import sys
import os
sys.path.insert(0, '/home/quan/testdata/aspipe_v4/app')

from tushare_api import TuShareDownloader
from date_range_downloader import DateRangeDownloader

def test_cyq_chips_fix():
    """测试cyq_chips接口修复"""
    print("测试cyq_chips接口修复...")
    try:
        downloader = TuShareDownloader()

        # 测试分页下载方法
        result = downloader.download_cyq_chips_paginated(trade_date='20231201', ts_code='000001.SZ')
        print(f"  单股cyq_chips下载结果: {len(result)} 条记录" if not result.empty else "  单股cyq_chips无数据")

        # 测试无ts_code时的全市场下载
        result_all = downloader.download_cyq_chips_paginated(trade_date='20231201')
        print(f"  全市场cyq_chips下载结果: {len(result_all)} 条记录" if not result_all.empty else "  全市场cyq_chips无数据")

        print("  ✓ cyq_chips接口修复测试完成")
    except Exception as e:
        print(f"  ✗ cyq_chips接口修复测试失败: {e}")

def test_financial_data_fix():
    """测试财务数据下载修复"""
    print("\n测试财务数据下载修复...")
    try:
        downloader = DateRangeDownloader('20231201', '20231201')

        # 测试下载方法
        result = downloader._download_financial_type_for_range('income')
        print(f"  财务数据下载结果: {result}" if result else "  财务数据无结果")

        print("  ✓ 财务数据下载修复测试完成")
    except Exception as e:
        print(f"  ✗ 财务数据下载修复测试失败: {e}")

def test_holder_data_fix():
    """测试股东数据下载修复"""
    print("\n测试股东数据下载修复...")
    try:
        downloader = DateRangeDownloader('20231201', '20231201')

        # 测试下载方法
        result = downloader._download_holder_type_for_range('top10_holders')
        print(f"  股东数据下载结果: {result}" if result else "  股东数据无结果")

        print("  ✓ 股东数据下载修复测试完成")
    except Exception as e:
        print(f"  ✗ 股东数据下载修复测试失败: {e}")

def test_event_data_fix():
    """测试事件数据下载修复"""
    print("\n测试事件数据下载修复...")
    try:
        downloader = DateRangeDownloader('20231201', '20231201')

        # 测试单个时间段下载方法
        result = downloader._download_event_data_single_period('forecast', '20231201', '20231231')
        print(f"  事件数据下载结果: {len(result)} 条记录" if not result.empty else "  事件数据无数据")

        print("  ✓ 事件数据下载修复测试完成")
    except Exception as e:
        print(f"  ✗ 事件数据下载修复测试失败: {e}")

if __name__ == "__main__":
    print("开始验证修复后的功能...")

    test_cyq_chips_fix()
    test_financial_data_fix()
    test_holder_data_fix()
    test_event_data_fix()

    print("\n所有修复验证完成！")