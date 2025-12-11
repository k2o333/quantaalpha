#!/usr/bin/env python3
"""
cyq_chips接口10000+条数据下载验证脚本
"""
import sys
import os
import pandas as pd
import logging
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.tushare_api import TuShareDownloader

def test_cyq_chips_10k_plus():
    """
    测试cyq_chips接口下载10000+条数据
    """
    print("=" * 60)
    print("开始测试cyq_chips接口10000+条数据下载...")
    print("=" * 60)

    # 初始化下载器
    downloader = TuShareDownloader()
    print(f"用户积分: {downloader.current_points}")

    if downloader.current_points >= 5000:
        print("使用全市场股票循环下载cyq_chips数据...")
        all_data = []
        total_records = 0

        try:
            # 获取股票列表
            print("获取股票列表...")
            stock_df = downloader.download_stock_basic()
            if stock_df.empty:
                print("❌ 无法获取股票列表")
                return False

            print(f"获取到 {len(stock_df)} 只股票")

            # 循环下载每只股票的cyq_chips数据
            success_count = 0
            fail_count = 0

            test_date = '20231201'  # 测试日期
            print(f"开始循环下载每只股票的cyq_chips数据，目标日期: {test_date}")

            for i, stock in stock_df.iterrows():
                ts_code = stock['ts_code']

                try:
                    # 下载单只股票的数据
                    df = downloader.download_cyq_chips(ts_code=ts_code, trade_date=test_date)

                    if df is not None and not df.empty:
                        records_count = len(df)
                        all_data.append(df)
                        total_records += records_count
                        success_count += 1

                        if success_count % 100 == 0:  # 每100只股票输出一次进度
                            print(f"  已处理 {success_count} 只股票，当前总记录数: {total_records}")

                        if total_records >= 10000:
                            print(f"✅ 成功获取超过10000条数据！当前总数: {total_records}")
                            print(f"  从 {success_count} 只股票下载了数据")
                            break
                    else:
                        # 即使没有数据也继续（可能该股票当天无数据）
                        pass

                except Exception as e:
                    fail_count += 1
                    if fail_count % 100 == 0:  # 每失败100次输出一次
                        print(f"  下载错误 {fail_count} 次: {ts_code}, 错误: {e}")
                    continue

            print(f"\n循环下载完成: 成功 {success_count}, 失败 {fail_count}")
            print(f"最终记录数: {total_records}")

            if total_records >= 10000:
                print(f"✅ cyq_chips接口测试通过！获取了 {total_records} 条记录")
                return True
            else:
                print(f"❌ cyq_chips接口测试未通过！仅获取了 {total_records} 条记录")
                return False

        except Exception as e:
            print(f"❌ cyq_chips下载测试出错: {e}")
            return False
    else:
        print("❌ 积分不足5000，无法测试cyq_chips接口")
        return False

def main():
    """
    主测试函数
    """
    print("cyq_chips接口10000+条数据下载验证")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    success = test_cyq_chips_10k_plus()

    print("\n" + "=" * 60)
    if success:
        print("🎉 cyq_chips接口10000+条数据下载测试通过！")
    else:
        print("💥 cyq_chips接口10000+条数据下载测试未通过！")
    print("=" * 60)

    return success

if __name__ == "__main__":
    main()