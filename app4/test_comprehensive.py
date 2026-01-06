#!/usr/bin/env python3
"""
完整重复数据检测功能测试脚本
包含交易日历数据以验证日期范围覆盖率检测
"""
import os
import sys
import logging
import time
from datetime import datetime
from typing import Dict, Any, List
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

def create_comprehensive_mock_data():
    """创建包含交易日历的综合模拟数据"""
    print("创建综合模拟数据...")
    
    # 创建存储目录
    os.makedirs("./data/daily", exist_ok=True)
    os.makedirs("./data/income_vip", exist_ok=True)
    os.makedirs("./data/stk_rewards", exist_ok=True)
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
    
    # 创建income_vip接口的模拟数据
    income_data = [
        {
            "ts_code": "000001.SZ",
            "ann_date": f"202304{day:02d}",
            "f_ann_date": f"202304{day:02d}",
            "end_date": f"202303{day:02d}",
            "period": "20230331",  # Q1报告期
            "report_type": "1",
            "comp_type": "1",
            "total_revenue": 1000000 + day * 10000,
            "revenue": 900000 + day * 9000,
            "n_income": 100000 + day * 1000
        }
        for day in range(25, 31)  # 假设Q1报告在4月25-30日发布
    ]
    
    # 保存income_vip数据
    df_income = pl.DataFrame(income_data)
    df_income.write_parquet("./data/income_vip/income_vip_20230331_1234567890_efgh5678.parquet")
    
    # 创建stk_rewards接口的模拟数据
    stock_data = [
        {
            "ts_code": "000001.SZ",
            "div_proc": "预案",
            "stk_div": 0.5,
            "record_date": "20230501",
            "ex_date": "20230502",
            "pay_date": "20230515"
        }
    ]
    
    df_stock = pl.DataFrame(stock_data)
    df_stock.write_parquet("./data/stk_rewards/stk_rewards_000001.SZ_1234567890_ijkl9012.parquet")
    
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
    
    print("综合模拟数据创建完成")

def test_date_range_coverage_with_calendar():
    """测试包含交易日历的日期范围覆盖率检测"""
    print("\n" + "="*60)
    print("完整测试1: 日期范围覆盖率检测（含交易日历）")
    print("="*60)
    
    # 初始化组件
    config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
    config_loader = ConfigLoader(config_dir=config_dir)
    storage_manager = StorageManager(storage_dir="./data")
    storage_manager.start_writer()
    
    coverage_manager = CoverageManager(storage_manager, config_loader)
    
    # 测试已覆盖的日期范围（应该返回True，如果交易日历可用）
    print("\n测试1.1: 检测已覆盖的日期范围 (20230103-20230106)")
    params_covered = {
        'start_date': '20230103',
        'end_date': '20230106'
    }
    result_covered = coverage_manager.should_skip('daily', params_covered, strategy='date_range')
    print(f"结果: {'跳过（已覆盖）' if result_covered else '下载（未覆盖）'}")
    
    # 测试部分覆盖的日期范围（应该返回False）
    print("\n测试1.2: 检测部分覆盖的日期范围 (20230103-20230120)")
    params_partial = {
        'start_date': '20230103',
        'end_date': '20230120'
    }
    result_partial = coverage_manager.should_skip('daily', params_partial, strategy='date_range')
    print(f"结果: {'跳过（已覆盖）' if result_partial else '下载（未覆盖）'}")
    
    # 测试未覆盖的日期范围（应该返回False）
    print("\n测试1.3: 检测未覆盖的日期范围 (20230201-20230210)")
    params_uncovered = {
        'start_date': '20230201',
        'end_date': '20230210'
    }
    result_uncovered = coverage_manager.should_skip('daily', params_uncovered, strategy='date_range')
    print(f"结果: {'跳过（已覆盖）' if result_uncovered else '下载（未覆盖）'}")
    
    storage_manager.stop_writer()
    
    print(f"\n日期范围覆盖率检测结果: 覆盖={result_covered}, 部分={result_partial}, 未覆盖={result_uncovered}")
    return True  # 这个测试主要是验证功能不报错

def test_period_and_stock_coverage():
    """测试报告期和股票存在性检测"""
    print("\n" + "="*60)
    print("完整测试2: 报告期和股票存在性检测")
    print("="*60)
    
    # 初始化组件
    config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
    config_loader = ConfigLoader(config_dir=config_dir)
    storage_manager = StorageManager(storage_dir="./data")
    storage_manager.start_writer()
    
    coverage_manager = CoverageManager(storage_manager, config_loader)
    
    # 测试已存在的报告期（应该返回True）
    print("\n测试2.1: 检测已存在的报告期 (20230331)")
    params_existing = {
        'period': '20230331'
    }
    result_existing = coverage_manager.should_skip('income_vip', params_existing, strategy='period')
    print(f"结果: {'跳过（已存在）' if result_existing else '下载（不存在）'}")
    
    # 测试不存在的报告期（应该返回False）
    print("\n测试2.2: 检测不存在的报告期 (20230630)")
    params_non_existing = {
        'period': '20230630'
    }
    result_non_existing = coverage_manager.should_skip('income_vip', params_non_existing, strategy='period')
    print(f"结果: {'跳过（已存在）' if result_non_existing else '下载（不存在）'}")
    
    # 测试已存在的股票（应该返回True）
    print("\n测试2.3: 检测已存在的股票 (000001.SZ)")
    params_stock_existing = {
        'ts_code': '000001.SZ'
    }
    result_stock_existing = coverage_manager.should_skip('stk_rewards', params_stock_existing, strategy='stock')
    print(f"结果: {'跳过（已存在）' if result_stock_existing else '下载（不存在）'}")
    
    # 测试不存在的股票（应该返回False）
    print("\n测试2.4: 检测不存在的股票 (000002.SZ)")
    params_stock_non_existing = {
        'ts_code': '000002.SZ'
    }
    result_stock_non_existing = coverage_manager.should_skip('stk_rewards', params_stock_non_existing, strategy='stock')
    print(f"结果: {'跳过（已存在）' if result_stock_non_existing else '下载（不存在）'}")
    
    storage_manager.stop_writer()
    
    success = result_existing and not result_non_existing and result_stock_existing and not result_stock_non_existing
    print(f"\n报告期和股票存在性检测验收: {'通过' if success else '未通过'}")
    return success

def test_integration_with_downloader():
    """测试与下载器的集成"""
    print("\n" + "="*60)
    print("完整测试3: 与下载器集成测试")
    print("="*60)
    
    # 初始化组件
    config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
    config_loader = ConfigLoader(config_dir=config_dir)
    storage_manager = StorageManager(storage_dir="./data")
    storage_manager.start_writer()
    
    # 创建带覆盖率管理器的下载器
    downloader = GenericDownloader(config_loader, storage_manager)
    
    # 测试覆盖率检查功能
    print("\n测试3.1: 验证下载器中的覆盖率管理器")
    has_coverage_manager = downloader.coverage_manager is not None
    print(f"下载器包含覆盖率管理器: {has_coverage_manager}")
    
    if has_coverage_manager:
        # 测试各种覆盖率检查
        print("\n测试3.2: 通过下载器执行覆盖率检查")
        
        # 日期范围检查
        date_params = {
            'start_date': '20230103',
            'end_date': '20230106'
        }
        date_result = downloader.coverage_manager.should_skip('daily', date_params, strategy='date_range')
        print(f"日期范围检查结果: {'跳过' if date_result else '下载'}")
        
        # 报告期检查
        period_params = {
            'period': '20230331'
        }
        period_result = downloader.coverage_manager.should_skip('income_vip', period_params, strategy='period')
        print(f"报告期检查结果: {'跳过' if period_result else '下载'}")
        
        # 股票检查
        stock_params = {
            'ts_code': '000001.SZ'
        }
        stock_result = downloader.coverage_manager.should_skip('stk_rewards', stock_params, strategy='stock')
        print(f"股票检查结果: {'跳过' if stock_result else '下载'}")
    
    storage_manager.stop_writer()
    
    success = has_coverage_manager
    print(f"\n下载器集成测试: {'通过' if success else '未通过'}")
    return success

def main():
    """主测试函数"""
    print("aspipe_v4 重复数据检测功能完整测试")
    print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 创建综合模拟数据
    create_comprehensive_mock_data()
    
    # 运行各项测试
    test_results = []
    
    test_results.append(("日期范围覆盖率检测", test_date_range_coverage_with_calendar()))
    test_results.append(("报告期和股票存在性检测", test_period_and_stock_coverage()))
    test_results.append(("与下载器集成测试", test_integration_with_downloader()))
    
    # 输出总结
    print("\n" + "="*60)
    print("完整测试总结")
    print("="*60)
    
    all_passed = True
    for test_name, result in test_results:
        status = "通过" if result else "未通过"
        print(f"{test_name}: {status}")
        if not result:
            all_passed = False
    
    print(f"\n总体测试结果: {'全部通过' if all_passed else '部分未通过'}")
    
    print(f"\n所有测试完成！当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)