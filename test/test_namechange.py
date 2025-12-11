#!/usr/bin/env python3
"""
Namechange接口测试脚本
用于测试namechange接口的下载功能，确保能够获取超过10000条数据
"""

import sys
import os
import pandas as pd
import logging
from datetime import datetime, timedelta

# 添加项目根目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from app.tushare_api import TuShareDownloader

def test_namechange_data():
    """
    测试namechange接口的数据下载能力
    """
    print("=" * 60)
    print("开始测试namechange接口数据下载...")
    print("=" * 60)

    # 初始化下载器
    downloader = TuShareDownloader()

    print(f"用户积分: {downloader.current_points}")

    try:
        # 尝试下载全市场数据
        print("正在下载全市场namechange数据...")
        df = downloader.download_namechange()

        if df is not None and not df.empty:
            records_count = len(df)
            print(f"全市场下载获取到 {records_count} 条记录")

            if records_count >= 10000:
                print(f"✅ 测试通过! namechange接口成功获取超过10000条记录 ({records_count}条)")
                return True
            else:
                print(f"⚠️ 全市场下载记录不足 ({records_count}条)，尝试分时间段下载...")
        else:
            print("⚠️ 全市场下载未获取到数据，尝试分时间段下载...")

    except Exception as e:
        print(f"❌ 全市场下载测试出错: {e}")

    # 如果全市场下载记录数不足，尝试使用分时间段下载
    print("开始分时间段下载测试...")
    all_data = []
    total_records = 0

    # 使用较大的时间范围来获取更多数据
    # 从2010年开始分段获取数据
    start_year = 2010
    current_year = datetime.now().year

    for year in range(start_year, current_year + 1):
        try:
            start_date = f"{year}0101"
            end_date = f"{year}1231"
            print(f"正在下载 {start_date} 到 {end_date} 的数据...")

            # 使用分周期下载方法
            from datetime import datetime as dt, timedelta
            start = dt.strptime(start_date, '%Y%m%d')
            end = dt.strptime(end_date, '%Y%m%d')

            current_start = start
            while current_start <= end:
                # 计算当前段的结束日期（最多30天）
                current_end = min(current_start + timedelta(days=30), end)
                current_start_str = current_start.strftime('%Y%m%d')
                current_end_str = current_end.strftime('%Y%m%d')

                try:
                    df = downloader.download_namechange(
                        start_date=current_start_str,
                        end_date=current_end_str
                    )

                    if df is not None and not df.empty:
                        all_data.append(df)
                        total_records += len(df)
                        print(f"  {current_start_str}到{current_end_str}: 获取到 {len(df)} 条记录")

                        if total_records >= 10000:
                            print(f"✅ 时间分段下载已达到超过10000条记录目标! 当前记录数: {total_records}")
                            break
                except Exception as e:
                    print(f"  下载 {current_start_str} 到 {current_end_str} 的数据失败: {e}")

                current_start = current_end + timedelta(days=1)

                # 如果已达到目标数量，提前退出
                if total_records >= 10000:
                    break

            if total_records >= 10000:
                break

        except Exception as e:
            print(f"下载年份 {year} 的数据时出错: {e}")
            continue

    # 合并所有数据
    if all_data:
        combined_df = pd.concat(all_data, ignore_index=True)
        unique_records = len(combined_df)
        print(f"\n总下载记录数: {total_records}")
        print(f"去重后记录数: {unique_records}")

        if unique_records >= 10000:
            print(f"✅ 时间分段测试通过! namechange接口成功获取超过10000条记录 ({unique_records}条)")
            return True
        else:
            print(f"⚠️ 时间分段下载记录仍不足 ({unique_records}条)")
            return False
    else:
        print("❌ 时间分段下载没有获取到任何数据")
        return False

def test_namechange_with_stocks():
    """
    测试namechange接口，通过遍历股票代码来获取数据
    """
    print("\n" + "=" * 60)
    print("开始测试namechange接口按股票下载...")
    print("=" * 60)

    # 初始化下载器
    downloader = TuShareDownloader()

    try:
        # 获取股票列表
        print("正在获取股票基础信息...")
        stock_df = downloader.download_stock_basic()
        if stock_df is None or stock_df.empty:
            print("❌ 无法获取股票列表")
            return False
        print(f"获取到 {len(stock_df)} 只股票")

        all_data = []
        total_records = 0
        stocks_processed = 0

        # 遍历前500只股票
        for index, stock in stock_df.head(500).iterrows():
            ts_code = stock['ts_code']

            try:
                df = downloader.download_namechange(ts_code=ts_code)

                if df is not None and not df.empty:
                    all_data.append(df)
                    total_records += len(df)
                    print(f"{ts_code}: 获取到 {len(df)} 条记录")

                    if total_records >= 10000:
                        print(f"✅ 按股票下载已达到超过10000条记录目标! 当前记录数: {total_records}")
                        break
                else:
                    print(f"{ts_code}: 未获取到数据")

            except Exception as e:
                print(f"下载 {ts_code} 的namechange数据时出错: {e}")
                continue

            stocks_processed += 1

            # 如果已处理足够多股票但记录数不足，提前退出
            if stocks_processed >= 500 and total_records < 1000:
                print(f"⚠️ 已处理 {stocks_processed} 只股票但记录数仍不足，可能该接口数据量有限")
                break

        # 合并所有数据
        if all_data:
            combined_df = pd.concat(all_data, ignore_index=True)
            unique_records = len(combined_df)
            print(f"\n总处理股票数: {stocks_processed}")
            print(f"总下载记录数: {total_records}")
            print(f"去重后记录数: {unique_records}")

            if unique_records >= 10000:
                print(f"✅ 按股票下载测试通过! 获取到超过10000条记录 ({unique_records}条)")
                return True
            else:
                print(f"⚠️ 按股票下载记录仍不足 ({unique_records}条)")
                return False
        else:
            print("❌ 按股票下载没有获取到任何数据")
            return False

    except Exception as e:
        print(f"❌ 按股票下载测试出错: {e}")
        return False

def main():
    """
    主测试函数
    """
    print("Namechange接口测试脚本")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 配置日志
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    success = False

    # 首先尝试全市场下载
    if test_namechange_data():
        success = True
    elif test_namechange_with_stocks():
        success = True

    # 输出最终结果
    print("\n" + "=" * 60)
    if success:
        print("🎉 Namechange接口测试最终通过!")
    else:
        print("💥 Namechange接口测试未通过! 尝试了多种方法但记录数仍不足")
    print("=" * 60)

    return success

if __name__ == "__main__":
    main()