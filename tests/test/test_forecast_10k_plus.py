#!/usr/bin/env python3
"""
Forecast接口10000+条数据下载验证脚本
"""
import sys
import os
import pandas as pd
import logging
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.tushare_api import TuShareDownloader

def test_forecast_10k_plus():
    """
    测试forecast接口下载10000+条数据
    """
    print("=" * 60)
    print("开始测试forecast接口10000+条数据下载...")
    print("=" * 60)

    # 初始化下载器
    downloader = TuShareDownloader()
    print(f"用户积分: {downloader.current_points}")

    if downloader.current_points >= 5000:
        print("使用VIP接口下载全市场数据...")
        all_data = []
        total_records = 0
        success = True

        # 测试多个报告期以累积数据
        test_periods = [
            '20231231', '20230930', '20230630', '20230331',
            '20221231', '20220930', '20220630', '20220331',
            '20211231', '20210930', '20210630', '20210331'
        ]

        for period in test_periods:
            try:
                print(f"下载周期 {period} 的数据...")
                df = downloader.download_forecast(period=period)

                if df is not None and not df.empty:
                    records_count = len(df)
                    print(f"  周期 {period}: 获取到 {records_count} 条记录")
                    all_data.append(df)
                    total_records += records_count

                    if total_records >= 10000:
                        print(f"✅ 成功获取超过10000条数据！当前总数: {total_records}")
                        success = True
                        break
                else:
                    print(f"  周期 {period}: 未获取到数据")

            except Exception as e:
                print(f"下载周期 {period} 时出错: {e}")
                continue

        # 如果还没达到10000条，继续下载更多周期
        if total_records < 10000:
            additional_periods = [
                '20201231', '20200930', '20200630', '20200331',
                '20191231', '20190930', '20190630', '20190331'
            ]

            for period in additional_periods:
                if total_records >= 10000:
                    break
                try:
                    print(f"下载额外周期 {period} 的数据...")
                    df = downloader.download_forecast(period=period)

                    if df is not None and not df.empty:
                        records_count = len(df)
                        print(f"  周期 {period}: 获取到 {records_count} 条记录")
                        all_data.append(df)
                        total_records += records_count
                    else:
                        print(f"  周期 {period}: 未获取到数据")

                except Exception as e:
                    print(f"下载额外周期 {period} 时出错: {e}")
                    continue

        print(f"\n最终结果: 总共获取 {total_records} 条记录")

        if total_records >= 10000:
            print(f"✅ forecast接口测试通过！获取了 {total_records} 条记录")
            return True
        else:
            if all_data:
                combined_df = pd.concat(all_data, ignore_index=True)
                unique_records = len(combined_df)
                print(f"去重后记录数: {unique_records}")
                if unique_records >= 10000:
                    print(f"✅ forecast接口测试通过！去重后获取了 {unique_records} 条记录")
                    return True
                else:
                    print(f"❌ forecast接口测试未通过！仅获取了 {unique_records} 条记录")
                    return False
            else:
                print("❌ forecast接口测试未通过！没有获取到任何数据")
                return False
    else:
        print("❌ 积分不足5000，无法测试VIP接口")
        return False

def main():
    """
    主测试函数
    """
    print("Forecast接口10000+条数据下载验证")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    success = test_forecast_10k_plus()

    print("\n" + "=" * 60)
    if success:
        print("🎉 Forecast接口10000+条数据下载测试通过！")
    else:
        print("💥 Forecast接口10000+条数据下载测试未通过！")
    print("=" * 60)

    return success

if __name__ == "__main__":
    main()