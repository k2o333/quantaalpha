#!/usr/bin/env python3
"""
测试改进后的交易日历缓存功能
"""
import os
import sys
import logging
from datetime import datetime
import polars as pl

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config_loader import ConfigLoader
from core.downloader import GenericDownloader
from core.storage import StorageManager
from core.coverage_manager import CoverageManager

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_trade_calendar_caching():
    """测试交易日历缓存功能"""
    print("测试交易日历缓存功能...")
    
    # 创建存储目录和交易日历数据
    os.makedirs("./data/trade_cal", exist_ok=True)
    
    # 创建交易日历数据（2023年1月的交易日）
    trade_cal_data = [
        {
            "exchange": "SSE",
            "cal_date": f"202301{day:02d}",
            "is_open": 1 if day not in [1, 2, 7, 8, 14, 15, 21, 22, 28, 29] else 0  # 假设周末和部分日期不开市
        }
        for day in range(1, 32)  # 1月1-31日
    ]
    
    # 保存交易日历数据
    df_trade_cal = pl.DataFrame(trade_cal_data)
    df_trade_cal.write_parquet("./data/trade_cal/trade_cal_20230101_20230131_1234567890_mnop3456.parquet")
    
    print("交易日历数据已创建")
    
    # 初始化组件
    config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
    config_loader = ConfigLoader(config_dir=config_dir)
    storage_manager = StorageManager(storage_dir="./data")
    storage_manager.start_writer()
    
    # 创建下载器（带覆盖率管理器）
    downloader = GenericDownloader(config_loader, storage_manager)
    
    # 测试CoverageManager的交易日历获取功能
    print("\n测试CoverageManager的交易日历获取功能...")
    
    # 模拟调用交易日历获取方法
    calendar_params = {
        'start_date': '20230101',
        'end_date': '20230115',
        'exchange': 'SSE'
    }
    
    trade_calendar = downloader.coverage_manager._make_request_to_trade_cal(calendar_params)
    
    if trade_calendar:
        print(f"成功获取 {len(trade_calendar)} 条交易日历数据")
        print(f"日期范围: {trade_calendar[0]['cal_date']} 到 {trade_calendar[-1]['cal_date']}")
    else:
        print("未能获取交易日历数据")
    
    # 测试覆盖率检查功能
    print("\n测试日期范围覆盖率检查...")
    params = {
        'start_date': '20230103',
        'end_date': '20230106'
    }
    
    # 创建测试数据
    os.makedirs("./data/daily", exist_ok=True)
    daily_data = [
        {
            "ts_code": "000001.SZ",
            "trade_date": f"202301{day:02d}",
            "close": 10.0 + day * 0.1
        }
        for day in range(3, 7)  # 1月3-6日
    ]
    
    df_daily = pl.DataFrame(daily_data)
    df_daily.write_parquet("./data/daily/daily_20230103_20230106_1234567890_test1234.parquet")
    
    result = downloader.coverage_manager.should_skip('daily', params, strategy='date_range')
    print(f"日期范围 {params['start_date']}-{params['end_date']} 覆盖检测结果: {'跳过' if result else '下载'}")
    
    storage_manager.stop_writer()
    
    print("\n交易日历缓存功能测试完成")

def test_without_local_data():
    """测试没有本地数据时的行为"""
    print("\n测试没有本地交易日历数据时的行为...")
    
    # 确保交易日历目录为空
    trade_cal_dir = "./data/trade_cal"
    if os.path.exists(trade_cal_dir):
        import shutil
        shutil.rmtree(trade_cal_dir)
    os.makedirs(trade_cal_dir, exist_ok=True)
    
    # 初始化组件
    config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
    config_loader = ConfigLoader(config_dir=config_dir)
    storage_manager = StorageManager(storage_dir="./data")
    storage_manager.start_writer()
    
    # 创建下载器（带覆盖率管理器）
    downloader = GenericDownloader(config_loader, storage_manager)
    
    # 测试没有本地数据时的交易日历获取
    calendar_params = {
        'start_date': '20230201',
        'end_date': '20230215',
        'exchange': 'SSE'
    }
    
    print("尝试获取本地不存在的交易日历数据...")
    trade_calendar = downloader.coverage_manager._make_request_to_trade_cal(calendar_params)
    
    if trade_calendar is None:
        print("正确：没有本地数据且无法从API获取时返回None")
    else:
        print(f"获取到 {len(trade_calendar)} 条数据（可能来自API模拟）")
    
    storage_manager.stop_writer()
    
    print("无本地数据测试完成")

def main():
    """主测试函数"""
    print("="*60)
    print("交易日历缓存功能测试")
    print("="*60)
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    test_trade_calendar_caching()
    test_without_local_data()
    
    print(f"\n所有测试完成！当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if __name__ == "__main__":
    main()