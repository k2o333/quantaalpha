#!/usr/bin/env python3
"""
namechange接口10000+条数据下载验证脚本
"""
import sys
import os
import pandas as pd
import logging
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.tushare_api import TuShareDownloader

def test_namechange_10k_plus():
    """
    测试namechange接口下载10000+条数据
    """
    print("=" * 60)
    print("开始测试namechange接口10000+条数据下载...")
    print("=" * 60)

    # 初始化下载器
    downloader = TuShareDownloader()
    print(f"用户积分: {downloader.current_points}")

    try:
        print("使用自动时间分割功能下载多年数据...")

        # 使用较长的时间范围以获取更多数据
        df = downloader.download_namechange_with_period_split(
            start_date='20180101',
            end_date='20231231'
        )

        if df is not None and not df.empty:
            records_count = len(df)
            print(f"✅ namechange接口下载完成！获取了 {records_count} 条记录")

            if records_count >= 10000:
                print(f"🎉 成功获取超过10000条数据！总数: {records_count}")
                return True
            else:
                print(f"❌ 未达到10000条数据目标，仅获取了 {records_count} 条")
                return False
        else:
            print("❌ namechange接口未获取到任何数据")
            return False

    except Exception as e:
        print(f"❌ namechange下载测试出错: {e}")
        return False

def main():
    """
    主测试函数
    """
    print("namechange接口10000+条数据下载验证")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    success = test_namechange_10k_plus()

    print("\n" + "=" * 60)
    if success:
        print("🎉 namechange接口10000+条数据下载测试通过！")
    else:
        print("💥 namechange接口10000+条数据下载测试未通过！")
    print("=" * 60)

    return success

if __name__ == "__main__":
    main()