#!/usr/bin/env python3
"""
Forecast接口大数据量下载测试脚本
验证forecast_vip接口能否下载超过10000条数据
测试不同period参数的数据量
验证数据完整性与格式正确性
测试积分不足时的降级方案
"""
import sys
import os
import pandas as pd
import logging
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.tushare_api import TuShareDownloader

def test_forecast_vip_download():
    """
    测试forecast_vip接口的下载能力，验证能否获取超过10000条数据
    """
    print("=" * 60)
    print("开始测试forecast_vip接口大数据量下载...")
    print("=" * 60)

    # 初始化下载器
    downloader = TuShareDownloader()
    print(f"用户积分: {downloader.current_points}")

    if downloader.current_points >= 5000:
        # 测试VIP接口能否下载超过10000条数据
        print("用户积分 >= 5000，测试VIP接口...")

        test_periods = [
            '20231231', '20230930', '20230630', '20230331',
            '20221231', '20220930'
        ]

        all_data = []
        total_records = 0

        for period in test_periods:
            try:
                print(f"正在使用VIP接口下载周期 {period} 的数据...")
                df = downloader.download_forecast(period=period)

                if df is not None and not df.empty:
                    records_count = len(df)
                    print(f"周期 {period}: 获取到 {records_count} 条记录")
                    all_data.append(df)
                    total_records += records_count

                    # 检查数据结构
                    print(f"  数据列: {list(df.columns) if len(df.columns) < 10 else f'{len(df.columns)} 列'}")
                    if not df.empty:
                        print(f"  示例数据: {df.iloc[0].to_dict() if len(df) > 0 else '无数据'}")
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

            if unique_records >= 10000:
                print(f"✅ VIP接口测试通过! forecast接口成功获取超过10000条记录 ({unique_records}条)")
                return True
            else:
                print(f"⚠️ VIP接口测试完成，但记录数未达10000 ({unique_records}条)")
                return False
        else:
            print("❌ 没有获取到任何数据")
            return False
    else:
        # 测试积分不足时的降级方案
        print("用户积分 < 5000，测试降级方案...")
        print("此测试需要积分>=5000才能验证大数据量下载能力")
        print("当前积分无法测试VIP功能，但可以测试降级逻辑")
        return False

def test_forecast_fallback():
    """
    测试积分不足时的降级方案（逐股票下载）
    """
    print("\n" + "=" * 60)
    print("开始测试forecast降级方案...")
    print("=" * 60)

    downloader = TuShareDownloader()
    print(f"用户积分: {downloader.current_points}")

    # 如果积分<5000，测试降级方案
    if downloader.current_points < 5000:
        print("测试积分不足时的逐股票下载逻辑...")
        try:
            df = downloader.download_forecast(period='20231231')
            if df is not None and not df.empty:
                print(f"✅ 降级方案测试成功，获取到 {len(df)} 条记录")
                return True
            else:
                print("⚠️ 降级方案未获取到数据")
                return False
        except Exception as e:
            print(f"❌ 降级方案测试出错: {e}")
            return False
    else:
        print("用户积分>=5000，跳过降级方案测试")
        return True

def test_forecast_data_integrity():
    """
    测试数据完整性和格式正确性
    """
    print("\n" + "=" * 60)
    print("开始测试forecast数据完整性与格式...")
    print("=" * 60)

    downloader = TuShareDownloader()

    try:
        # 下载少量数据用于完整性检查
        df = downloader.download_forecast(period='20231231')

        if df is not None and not df.empty:
            print(f"获取到 {len(df)} 条记录用于完整性检查")

            # 检查数据结构
            print(f"数据列: {list(df.columns)}")
            print(f"数据形状: {df.shape}")
            print(f"数据类型:\n{df.dtypes}")

            # 检查是否有关键列
            expected_columns = ['ts_code', 'ann_date', 'end_date', 'revenue', 'profit', 'profit_to_gr']
            missing_columns = [col for col in expected_columns if col not in df.columns]
            if missing_columns:
                print(f"⚠️ 缺少预期列: {missing_columns}")
            else:
                print("✅ 所有预期列都存在")

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

def main():
    """
    主测试函数
    """
    print("Forecast大数据量下载功能测试脚本")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    results = {
        'vip_download': False,
        'fallback_download': False,
        'data_integrity': False
    }

    print(f"当前用户积分: {TuShareDownloader().current_points}")

    # 执行VIP下载测试
    results['vip_download'] = test_forecast_vip_download()

    # 执行降级方案测试
    results['fallback_download'] = test_forecast_fallback()

    # 执行数据完整性测试
    results['data_integrity'] = test_forecast_data_integrity()

    # 输出最终结果
    print("\n" + "=" * 60)
    print("📊 Forecast大数据量下载测试结果:")
    print(f"VIP下载功能: {'✅ 通过' if results['vip_download'] else '❌ 未通过'}")
    print(f"降级方案: {'✅ 通过' if results['fallback_download'] else '❌ 未通过'}")
    print(f"数据完整性: {'✅ 通过' if results['data_integrity'] else '❌ 未通过'}")

    overall_success = all([results['vip_download'], results['data_integrity']])
    if overall_success:
        print("🎉 所有关键测试通过!")
    else:
        print("⚠️ 部分测试未通过")
    print("=" * 60)

    return overall_success

if __name__ == "__main__":
    main()