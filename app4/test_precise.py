#!/usr/bin/env python3
"""
精确验证日期范围覆盖率检测功能
"""
import os
import sys
import logging
from datetime import datetime
from typing import Dict, Any, List
import polars as pl

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config_loader import ConfigLoader
from core.storage import StorageManager
from core.coverage_manager import CoverageManager

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_precise_test_data():
    """创建精确的测试数据"""
    print("创建精确测试数据...")
    
    # 创建存储目录
    os.makedirs("./data/daily", exist_ok=True)
    os.makedirs("./data/trade_cal", exist_ok=True)
    
    # 创建daily接口的模拟数据（2023年1月1日到15日的交易日）
    daily_data = [
        {
            "ts_code": "000001.SZ",
            "trade_date": f"202301{day:02d}",
            "open": 10.0 + day * 0.1,
            "high": 10.5 + day * 0.1,
            "low": 9.8 + day * 0.1,
            "close": 10.2 + day * 0.1,
            "pre_close": 9.9 + day * 0.1,
            "change": 0.3,
            "pct_chg": 3.0,
            "vol": 100000 + day * 1000,
            "amount": 1000000 + day * 10000
        }
        for day in range(1, 16)  # 2023年1月1日到15日（假设都是交易日）
    ]
    
    # 保存daily数据
    df_daily = pl.DataFrame(daily_data)
    df_daily.write_parquet("./data/daily/daily_20230101_20230115_1234567890_abcd1234.parquet")
    
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
    
    print("精确测试数据创建完成")

def test_date_range_coverage_precise():
    """精确测试日期范围覆盖率检测"""
    print("\n" + "="*60)
    print("精确测试: 日期范围覆盖率检测")
    print("="*60)
    
    # 初始化组件
    config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
    config_loader = ConfigLoader(config_dir=config_dir)
    storage_manager = StorageManager(storage_dir="./data")
    storage_manager.start_writer()
    
    coverage_manager = CoverageManager(storage_manager, config_loader)
    
    # 测试已覆盖的日期范围（应该返回True，因为我们有1月1-15日的数据）
    print("\n测试1: 检测已覆盖的日期范围 (20230103-20230106)")
    params_covered = {
        'start_date': '20230103',
        'end_date': '20230106'
    }
    result_covered = coverage_manager.should_skip('daily', params_covered, strategy='date_range')
    print(f"结果: {'跳过（已覆盖）' if result_covered else '下载（未覆盖）'}")
    
    # 测试部分覆盖的日期范围（应该返回False，因为1月16-20日没有数据）
    print("\n测试2: 检测部分覆盖的日期范围 (20230103-20230120)")
    params_partial = {
        'start_date': '20230103',
        'end_date': '20230120'
    }
    result_partial = coverage_manager.should_skip('daily', params_partial, strategy='date_range')
    print(f"结果: {'跳过（已覆盖）' if result_partial else '下载（未覆盖）'}")
    
    # 测试未覆盖的日期范围（应该返回False）
    print("\n测试3: 检测未覆盖的日期范围 (20230201-20230210)")
    params_uncovered = {
        'start_date': '20230201',
        'end_date': '20230210'
    }
    result_uncovered = coverage_manager.should_skip('daily', params_uncovered, strategy='date_range')
    print(f"结果: {'跳过（已覆盖）' if result_uncovered else '下载（未覆盖）'}")
    
    # 测试完全覆盖的范围（1月1-15日）
    print("\n测试4: 检测完全覆盖的日期范围 (20230101-20230115)")
    params_full = {
        'start_date': '20230101',
        'end_date': '20230115'
    }
    result_full = coverage_manager.should_skip('daily', params_full, strategy='date_range')
    print(f"结果: {'跳过（已覆盖）' if result_full else '下载（未覆盖）'}")
    
    storage_manager.stop_writer()
    
    print(f"\n精确测试结果:")
    print(f"  已覆盖范围 (20230103-20230106): {'跳过' if result_covered else '下载'}")
    print(f"  部分覆盖范围 (20230103-20230120): {'跳过' if result_partial else '下载'}")
    print(f"  未覆盖范围 (20230201-20230210): {'跳过' if result_uncovered else '下载'}")
    print(f"  完全覆盖范围 (20230101-20230115): {'跳过' if result_full else '下载'}")
    
    # 验收标准：已覆盖和完全覆盖的范围应该被跳过，部分覆盖和未覆盖的范围不应该被跳过
    success = result_covered and not result_partial and not result_uncovered and result_full
    print(f"\n精确测试验收: {'通过' if success else '未通过'}")
    return success

def main():
    """主测试函数"""
    print("aspipe_v4 重复数据检测功能精确验证")
    print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 创建精确测试数据
    create_precise_test_data()
    
    # 运行精确测试
    success = test_date_range_coverage_precise()
    
    print(f"\n精确验证完成！当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)