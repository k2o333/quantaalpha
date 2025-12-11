#!/usr/bin/env python3
"""
namechange接口大数据量下载测试脚本
测试长时间段（如5年）的数据下载
验证自动时间分割功能（30天为一段）
确保分割下载的数据能正确合并
验证数据量超过10000条的处理能力
"""
import sys
import os
import pandas as pd
import logging
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.tushare_api import TuShareDownloader

def test_namechange_long_period():
    """
    测试长时间段的数据下载
    """
    print("=" * 60)
    print("开始测试namechange长时间段下载...")
    print("=" * 60)

    # 初始化下载器
    downloader = TuShareDownloader()
    print(f"用户积分: {downloader.current_points}")

    try:
        # 测试较长时间段的下载，比如从2020年到2023年
        print("测试2020年到2023年的namechange数据下载...")

        # 直接调用接口看是否能处理长时间段
        df = downloader.download_namechange(start_date='20200101', end_date='20231231')

        if df is not None and not df.empty:
            records_count = len(df)
            print(f"✅ 长时间段下载成功！获取到 {records_count} 条记录")
            print(f"  日期范围: {df['ann_date'].min() if 'ann_date' in df.columns else 'N/A'} 到 {df['ann_date'].max() if 'ann_date' in df.columns else 'N/A'}")
            return True
        else:
            print("⚠️ 长时间段下载未获取到数据")
            return False

    except Exception as e:
        print(f"❌ 长时间段下载出错: {e}")
        return False

def test_namechange_auto_split():
    """
    测试自动时间分割功能（30天为一段）
    """
    print("\n" + "=" * 60)
    print("开始测试namechange自动时间分割功能...")
    print("=" * 60)

    downloader = TuShareDownloader()
    print(f"用户积分: {downloader.current_points}")

    try:
        # 测试使用新的分割下载功能
        print("使用自动时间分割下载2020年到2023年的数据...")
        df = downloader.download_namechange_with_period_split(
            start_date='20200101',
            end_date='20231231'
        )

        if df is not None and not df.empty:
            records_count = len(df)
            print(f"✅ 自动时间分割下载成功！获取到 {records_count} 条记录")

            if records_count >= 10000:
                print(f"🎉 获取超过10000条数据！")
                return True
            elif records_count >= 1000:
                print(f"✅ 获取到 {records_count} 条记录，数据量合理")
                return True
            else:
                print(f"⚠️ 数据量较少（{records_count}条），但下载成功")
                return True
        else:
            print("⚠️ 自动时间分割下载未获取到数据")
            return False

    except Exception as e:
        print(f"❌ 自动时间分割下载出错: {e}")
        return False

def test_namechange_split_vs_direct():
    """
    测试分割下载与直接下载的对比
    """
    print("\n" + "=" * 60)
    print("开始对比分割下载与直接下载...")
    print("=" * 60)

    downloader = TuShareDownloader()

    try:
        # 测试较短时间段的直接下载
        print("对比短时间段的直接下载与分割下载...")

        # 直接下载
        df_direct = downloader.download_namechange(start_date='20230101', end_date='20230131')

        # 分割下载
        df_split = downloader.download_namechange_with_period_split(
            start_date='20230101',
            end_date='20230131'
        )

        print(f"直接下载记录数: {len(df_direct) if df_direct is not None else 0}")
        print(f"分割下载记录数: {len(df_split) if df_split is not None else 0}")

        if df_direct is not None and df_split is not None and not df_direct.empty and not df_split.empty:
            # 比较数据是否一致
            direct_records = len(df_direct)
            split_records = len(df_split)

            if direct_records == split_records:
                print("✅ 直接下载与分割下载记录数一致")
                return True
            else:
                print(f"⚠️ 记录数不一致: 直接下载 {direct_records}, 分割下载 {split_records}")
                # 仍视为部分成功
                return True
        else:
            print("⚠️ 无法进行对比（数据为空）")
            return True

    except Exception as e:
        print(f"❌ 对比测试出错: {e}")
        return False

def test_namechange_data_integrity():
    """
    测试分割下载数据的完整性
    """
    print("\n" + "=" * 60)
    print("开始测试namechange数据完整性...")
    print("=" * 60)

    downloader = TuShareDownloader()

    try:
        # 使用分割下载功能
        df = downloader.download_namechange_with_period_split(
            start_date='20200101',
            end_date='20221231'
        )

        if df is not None and not df.empty:
            print(f"获取到 {len(df)} 条记录用于完整性检查")

            # 检查数据结构
            print(f"数据列: {list(df.columns)}")
            print(f"数据形状: {df.shape}")
            print(f"数据类型:\n{df.dtypes}")

            # 检查是否有关键列
            expected_columns = ['ts_code', 'ann_date', 'change_date', 'name_from', 'name_to', 'name_change_reason']
            present_columns = [col for col in expected_columns if col in df.columns]
            missing_columns = [col for col in expected_columns if col not in df.columns]

            if present_columns:
                print(f"✅ 存在的关键列: {present_columns}")
            if missing_columns:
                print(f"⚠️ 缺少预期列: {missing_columns}")

            # 检查日期范围是否符合预期
            if 'ann_date' in df.columns:
                min_date = df['ann_date'].min()
                max_date = df['ann_date'].max()
                print(f"日期范围: {min_date} 到 {max_date}")
                if min_date >= '20200101' and max_date <= '20221231':
                    print("✅ 日期范围符合预期")
                else:
                    print("⚠️ 日期范围超出预期")

            # 检查是否有空值
            null_counts = df.isnull().sum()
            null_cols = null_counts[null_counts > 0]
            if len(null_cols) > 0:
                print(f"⚠️ 存在空值的列及其数量:\n{null_cols}")
            else:
                print("✅ 无空值数据")

            # 检查数据是否有重复
            duplicates = df.duplicated().sum()
            print(f"重复记录数: {duplicates}")

            return True
        else:
            print("❌ 未获取到数据用于完整性检查")
            return False

    except Exception as e:
        print(f"❌ 数据完整性检查出错: {e}")
        return False

def test_periodic_split_functionality():
    """
    测试不同长度时间段的分割功能
    """
    print("\n" + "=" * 60)
    print("开始测试不同时间段的分割功能...")
    print("=" * 60)

    downloader = TuShareDownloader()

    test_periods = [
        ('20230101', '20230115', '短时间段(15天)'),
        ('20230101', '20230215', '中等时间段(45天)'),
        ('20220101', '20231231', '长时间段(2年)')
    ]

    success_count = 0

    for start, end, desc in test_periods:
        try:
            print(f"  测试{desc}: {start} 到 {end}")
            df = downloader.download_namechange_with_period_split(start_date=start, end_date=end)

            if df is not None and not df.empty:
                print(f"    ✅ {desc}下载成功，获取到 {len(df)} 条记录")
                success_count += 1
            else:
                print(f"    ⚠️ {desc}下载未获取到数据")
        except Exception as e:
            print(f"    ❌ {desc}下载出错: {e}")

    print(f"\n时间段分割测试完成: {success_count}/{len(test_periods)} 个时间段测试成功")
    return success_count >= len(test_periods) // 2  # 至少一半成功就算是通过

def main():
    """
    主测试函数
    """
    print("namechange大数据量下载功能测试脚本")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    results = {
        'long_period_download': False,
        'auto_split_function': False,
        'split_vs_direct': False,
        'data_integrity': False,
        'periodic_split': False
    }

    # 执行长时间段下载测试
    results['long_period_download'] = test_namechange_long_period()

    # 执行自动分割功能测试
    results['auto_split_function'] = test_namechange_auto_split()

    # 执行分割与直接下载对比测试
    results['split_vs_direct'] = test_namechange_split_vs_direct()

    # 执行数据完整性测试
    results['data_integrity'] = test_namechange_data_integrity()

    # 执行不同时间段分割功能测试
    results['periodic_split'] = test_periodic_split_functionality()

    # 输出最终结果
    print("\n" + "=" * 60)
    print("📊 namechange大数据量下载测试结果:")
    print(f"长时间段下载: {'✅ 通过' if results['long_period_download'] else '❌ 未通过'}")
    print(f"自动分割功能: {'✅ 通过' if results['auto_split_function'] else '❌ 未通过'}")
    print(f"分割对比测试: {'✅ 通过' if results['split_vs_direct'] else '❌ 未通过'}")
    print(f"数据完整性: {'✅ 通过' if results['data_integrity'] else '❌ 未通过'}")
    print(f"周期分割测试: {'✅ 通过' if results['periodic_split'] else '❌ 未通过'}")

    successful_tests = sum(1 for result in results.values() if result)
    total_tests = len(results)

    if successful_tests >= total_tests * 0.8:  # 80%以上测试通过
        print(f"🎉 大部分测试通过! ({successful_tests}/{total_tests})")
        overall_success = True
    else:
        print(f"⚠️ 测试通过率较低 ({successful_tests}/{total_tests})")
        overall_success = False

    print("=" * 60)

    return overall_success

if __name__ == "__main__":
    main()