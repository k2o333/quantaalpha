#!/usr/bin/env python3
"""
重复数据检测功能验收测试脚本
根据验收文档进行功能验证
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

def create_mock_data():
    """创建模拟数据用于测试"""
    print("创建模拟数据...")
    
    # 创建存储目录
    os.makedirs("./data/daily", exist_ok=True)
    os.makedirs("./data/income_vip", exist_ok=True)
    
    # 创建daily接口的模拟数据
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
        for day in range(1, 16)  # 2023年1月1日到15日
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
    
    print("模拟数据创建完成")

def test_date_range_coverage():
    """测试日期范围覆盖率检测"""
    print("\n" + "="*60)
    print("验收测试1: 日期范围覆盖率检测")
    print("="*60)
    
    # 初始化组件
    config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
    config_loader = ConfigLoader(config_dir=config_dir)
    storage_manager = StorageManager(storage_dir="./data")
    storage_manager.start_writer()
    
    coverage_manager = CoverageManager(storage_manager, config_loader)
    
    # 测试已覆盖的日期范围（应该返回True）
    print("\n测试1.1: 检测已覆盖的日期范围 (20230101-20230115)")
    params_covered = {
        'start_date': '20230101',
        'end_date': '20230115'
    }
    result_covered = coverage_manager.should_skip('daily', params_covered, strategy='date_range')
    print(f"结果: {'跳过（已覆盖）' if result_covered else '下载（未覆盖）'}")
    
    # 测试部分覆盖的日期范围（应该返回False）
    print("\n测试1.2: 检测部分覆盖的日期范围 (20230101-20230120)")
    params_partial = {
        'start_date': '20230101',
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
    
    print(f"\n日期范围覆盖率检测验收: {'通过' if not result_covered and not result_uncovered else '未通过'}")
    return not result_uncovered  # 验收标准：未覆盖的范围不应被跳过

def test_period_coverage():
    """测试报告期存在性检测"""
    print("\n" + "="*60)
    print("验收测试2: 报告期存在性检测")
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
    
    storage_manager.stop_writer()
    
    print(f"\n报告期存在性检测验收: {'通过' if result_existing and not result_non_existing else '未通过'}")
    return result_existing and not result_non_existing

def test_stock_coverage():
    """测试股票存在性检测"""
    print("\n" + "="*60)
    print("验收测试3: 股票存在性检测")
    print("="*60)
    
    # 创建股票数据
    os.makedirs("./data/stk_rewards", exist_ok=True)
    
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
    
    # 初始化组件
    config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
    config_loader = ConfigLoader(config_dir=config_dir)
    storage_manager = StorageManager(storage_dir="./data")
    storage_manager.start_writer()
    
    coverage_manager = CoverageManager(storage_manager, config_loader)
    
    # 测试已存在的股票（应该返回True）
    print("\n测试3.1: 检测已存在的股票 (000001.SZ)")
    params_existing = {
        'ts_code': '000001.SZ'
    }
    result_existing = coverage_manager.should_skip('stk_rewards', params_existing, strategy='stock')
    print(f"结果: {'跳过（已存在）' if result_existing else '下载（不存在）'}")
    
    # 测试不存在的股票（应该返回False）
    print("\n测试3.2: 检测不存在的股票 (000002.SZ)")
    params_non_existing = {
        'ts_code': '000002.SZ'
    }
    result_non_existing = coverage_manager.should_skip('stk_rewards', params_non_existing, strategy='stock')
    print(f"结果: {'跳过（已存在）' if result_non_existing else '下载（不存在）'}")
    
    storage_manager.stop_writer()
    
    print(f"\n股票存在性检测验收: {'通过' if result_existing and not result_non_existing else '未通过'}")
    return result_existing and not result_non_existing

def test_performance():
    """测试性能"""
    print("\n" + "="*60)
    print("验收测试4: 性能测试")
    print("="*60)
    
    # 初始化组件
    config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
    config_loader = ConfigLoader(config_dir=config_dir)
    storage_manager = StorageManager(storage_dir="./data")
    storage_manager.start_writer()
    
    coverage_manager = CoverageManager(storage_manager, config_loader)
    
    # 多次测试以评估性能
    print("\n测试多次覆盖率检查的性能...")
    start_time = time.time()
    
    for i in range(100):
        params = {
            'start_date': '20230101',
            'end_date': '20230115'
        }
        coverage_manager.should_skip('daily', params, strategy='date_range')
    
    end_time = time.time()
    elapsed = end_time - start_time
    
    print(f"100次日期范围覆盖率检查耗时: {elapsed:.3f}秒")
    print(f"平均每次检查耗时: {elapsed/100*1000:.2f}毫秒")
    
    storage_manager.stop_writer()
    
    # 性能验收：平均每次检查应在50毫秒以内
    performance_ok = (elapsed/100*1000) < 50
    print(f"\n性能测试验收: {'通过' if performance_ok else '未通过'} (阈值: 50ms/次)")
    
    return performance_ok

def test_robustness():
    """测试鲁棒性"""
    print("\n" + "="*60)
    print("验收测试5: 鲁棒性测试")
    print("="*60)
    
    # 初始化组件
    config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
    config_loader = ConfigLoader(config_dir=config_dir)
    storage_manager = StorageManager(storage_dir="./data")
    storage_manager.start_writer()
    
    coverage_manager = CoverageManager(storage_manager, config_loader)
    
    # 测试不存在的接口
    print("\n测试5.1: 检测不存在的接口")
    try:
        result = coverage_manager.should_skip('nonexistent_interface', {'start_date': '20230101', 'end_date': '20230131'}, strategy='date_range')
        print(f"结果: {'跳过' if result else '下载'} (无异常)")
        robust1 = True
    except Exception as e:
        print(f"异常: {e}")
        robust1 = False
    
    # 测试错误的参数
    print("\n测试5.2: 检测错误的参数")
    try:
        result = coverage_manager.should_skip('daily', {}, strategy='date_range')
        print(f"结果: {'跳过' if result else '下载'} (无异常)")
        robust2 = True
    except Exception as e:
        print(f"异常: {e}")
        robust2 = False
    
    storage_manager.stop_writer()
    
    robust_ok = robust1 and robust2
    print(f"\n鲁棒性测试验收: {'通过' if robust_ok else '未通过'}")
    
    return robust_ok

def main():
    """主测试函数"""
    print("aspipe_v4 重复数据检测功能验收测试")
    print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 创建模拟数据
    create_mock_data()
    
    # 运行各项测试
    test_results = []
    
    test_results.append(("日期范围覆盖率检测", test_date_range_coverage()))
    test_results.append(("报告期存在性检测", test_period_coverage()))
    test_results.append(("股票存在性检测", test_stock_coverage()))
    test_results.append(("性能测试", test_performance()))
    test_results.append(("鲁棒性测试", test_robustness()))
    
    # 输出总结
    print("\n" + "="*60)
    print("验收测试总结")
    print("="*60)
    
    all_passed = True
    for test_name, result in test_results:
        status = "通过" if result else "未通过"
        print(f"{test_name}: {status}")
        if not result:
            all_passed = False
    
    print(f"\n总体验收结果: {'全部通过' if all_passed else '部分未通过'}")
    
    print(f"\n所有测试完成！当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)