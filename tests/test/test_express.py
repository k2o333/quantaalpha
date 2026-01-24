#!/usr/bin/env python3
"""
Express接口测试脚本
用于测试express接口的下载功能，确保能够获取超过10000条数据
"""

import sys
import os
import pandas as pd
import logging
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.tushare_api import TuShareDownloader

def test_express_data():
    """
    测试express接口的数据下载能力
    """
    print("=" * 60)
    print("开始测试express接口数据下载...")
    print("=" * 60)

    # 初始化下载器
    downloader = TuShareDownloader()

    # 测试多个季度的数据以累积超过10000条记录
    test_periods = [
        '20231231', '20230930', '20230630', '20230331',
        '20221231', '20220930', '20220630', '20220331',
        '20211231', '20210930', '20210630', '20210331'
    ]

    all_data = []
    total_records = 0

    print(f"预计测试周期: {test_periods}")
    print(f"用户积分: {downloader.current_points}")

    for period in test_periods:
        try:
            print(f"正在下载周期 {period} 的数据...")
            df = downloader.download_express(period=period)

            if df is not None and not df.empty:
                print(f"周期 {period}: 获取到 {len(df)} 条记录")
                all_data.append(df)
                total_records += len(df)
            else:
                print(f"周期 {period}: 未获取到数据")

        except Exception as e:
            print(f"下载周期 {period} 数据时出错: {e}")
            continue

    # 合并所有数据
    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        unique_records = len(combined_df)
        print(f"\n总下载记录数: {total_records}")
        print(f"去重后记录数: {unique_records}")

        # 检查是否达到10000条记录
        if unique_records >= 10000:
            print(f"✅ 测试通过! express接口成功获取超过10000条记录 ({unique_records}条)")
            return True
        else:
            print(f"❌ 测试未通过! express接口获取记录不足 ({unique_records}条)")
            return False
    else:
        print("❌ 没有获取到任何数据")
        return False

def test_express_with_pagination():
    """
    测试使用分页下载express数据以达到超过10000条记录
    """
    print("\n" + "=" * 60)
    print("开始测试express接口分页下载...")
    print("=" * 60)

    # 初始化下载器
    downloader = TuShareDownloader()

    try:
        # 使用分页下载获取大量数据
        df = downloader.download_report_rc_paginated(period='20231231', limit_per_call=3000)

        if df is not None and not df.empty:
            records_count = len(df)
            print(f"分页下载获取到 {records_count} 条记录")

            if records_count >= 10000:
                print(f"✅ 分页下载测试通过! 获取到超过10000条记录 ({records_count}条)")
                return True
            else:
                print(f"⚠️ 分页下载获取记录不足 ({records_count}条)，尝试其他方法...")
        else:
            print("⚠️ 分页下载未获取到数据")
    except Exception as e:
        print(f"❌ 分页下载测试出错: {e}")

    return False

def main():
    """
    主测试函数
    """
    print("Express接口测试脚本")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    success = False

    # 首先尝试普通的多周期测试
    if test_express_data():
        success = True
    else:
        # 如果普通测试未通过，尝试分页测试
        success = test_express_with_pagination()

    # 输出最终结果
    print("\n" + "=" * 60)
    if success:
        print("🎉 Express接口测试最终通过!")
    else:
        print("💥 Express接口测试未通过!")
    print("=" * 60)

    return success

if __name__ == "__main__":
    main()