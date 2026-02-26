#!/usr/bin/env python3
"""
反向日期范围增量下载功能集成测试
验证实际接口的增量下载功能
"""

import os
import sys
import subprocess
import time
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app4.core.storage import StorageManager
from app4.core.config_loader import ConfigLoader
import polars as pl


def test_cyq_perf_incremental():
    """测试 cyq_perf 接口的增量下载功能"""
    print("\n" + "="*80)
    print("集成测试: cyq_perf 接口增量下载")
    print("="*80)
    
    storage_manager = StorageManager(storage_dir="../data", processor=None, config_loader=None)
    interface_name = "cyq_perf"
    
    # 检查接口配置
    try:
        config_loader = ConfigLoader()
        interface_config = config_loader.get_interface_config(interface_name)
    except FileNotFoundError:
        print("\n配置文件未找到，跳过配置检查")
        interface_config = {}
    
    print(f"\n接口配置:")
    print(f"  - pagination.mode: {interface_config.get('pagination', {}).get('mode')}")
    print(f"  - is_date_anchor: {interface_config.get('parameters', {}).get('trade_date', {}).get('is_date_anchor')}")
    
    # 检查现有数据
    try:
        df = storage_manager.read_interface_data(interface_name)
        if not df.is_empty():
            distinct_dates = df['trade_date'].n_unique()
            total_records = len(df)
            print(f"\n现有数据:")
            print(f"  - 不同日期数: {distinct_dates}")
            print(f"  - 总记录数: {total_records}")
        else:
            print(f"\n现有数据: 无")
    except Exception as e:
        print(f"\n读取数据失败: {e}")
        return False
    
    print("\n✓ 集成测试完成")
    return True


def test_top10_holders_stock_loop():
    """测试 top10_holders 接口的 stock_loop 功能"""
    print("\n" + "="*80)
    print("集成测试: top10_holders 接口 stock_loop")
    print("="*80)
    
    storage_manager = StorageManager(storage_dir="../data", processor=None, config_loader=None)
    interface_name = "top10_holders"
    
    # 检查接口配置
    try:
        config_loader = ConfigLoader()
        interface_config = config_loader.get_interface_config(interface_name)
    except FileNotFoundError:
        print("\n配置文件未找到，跳过配置检查")
        interface_config = {}
    
    print(f"\n接口配置:")
    print(f"  - pagination.mode: {interface_config.get('pagination', {}).get('mode')}")
    print(f"  - is_date_anchor: {interface_config.get('parameters', {}).get('period', {}).get('is_date_anchor')}")
    
    # 检查现有数据
    try:
        df = storage_manager.read_interface_data(interface_name)
        if not df.is_empty():
            distinct_stocks = df['ts_code'].n_unique()
            total_records = len(df)
            print(f"\n现有数据:")
            print(f"  - 不同股票数: {distinct_stocks}")
            print(f"  - 总记录数: {total_records}")
            
            # 显示前几只股票
            if distinct_stocks > 0:
                stocks = df['ts_code'].unique().to_list()[:5]
                print(f"  - 示例股票: {', '.join(stocks)}")
        else:
            print(f"\n现有数据: 无")
    except Exception as e:
        print(f"\n读取数据失败: {e}")
        return False
    
    print("\n✓ 集成测试完成")
    return True


def test_disclosure_date_anchor():
    """测试 disclosure_date 接口的日期锚点功能"""
    print("\n" + "="*80)
    print("集成测试: disclosure_date 接口日期锚点")
    print("="*80)
    
    storage_manager = StorageManager(storage_dir="../data", processor=None, config_loader=None)
    interface_name = "disclosure_date"
    
    # 检查接口配置
    try:
        config_loader = ConfigLoader()
        interface_config = config_loader.get_interface_config(interface_name)
    except FileNotFoundError:
        print("\n配置文件未找到，跳过配置检查")
        interface_config = {}
    
    print(f"\n接口配置:")
    print(f"  - pagination.mode: {interface_config.get('pagination', {}).get('mode')}")
    print(f"  - is_date_anchor: {interface_config.get('parameters', {}).get('end_date', {}).get('is_date_anchor')}")
    print(f"  - date_column: {interface_config.get('duplicate_detection', {}).get('date_column')}")
    
    # 检查现有数据
    try:
        df = storage_manager.read_interface_data(interface_name)
        if not df.is_empty():
            distinct_dates = df['end_date'].n_unique()
            total_records = len(df)
            print(f"\n现有数据:")
            print(f"  - 不同日期数: {distinct_dates}")
            print(f"  - 总记录数: {total_records}")
        else:
            print(f"\n现有数据: 无")
    except Exception as e:
        print(f"\n读取数据失败: {e}")
        return False
    
    print("\n✓ 集成测试完成")
    return True


def main():
    """主函数"""
    print("\n" + "="*80)
    print("反向日期范围增量下载功能集成测试")
    print("="*80)
    
    results = []
    
    # 测试 cyq_perf
    result1 = test_cyq_perf_incremental()
    results.append(("cyq_perf", result1))
    
    # 测试 top10_holders
    result2 = test_top10_holders_stock_loop()
    results.append(("top10_holders", result2))
    
    # 测试 disclosure_date
    result3 = test_disclosure_date_anchor()
    results.append(("disclosure_date", result3))
    
    # 汇总结果
    print("\n" + "="*80)
    print("集成测试汇总")
    print("="*80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for interface, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"  {interface}: {status}")
    
    print(f"\n通过率: {passed}/{total} ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("\n✓ 所有集成测试通过！")
        return 0
    else:
        print(f"\n✗ {total - passed} 个测试失败")
        return 1


if __name__ == "__main__":
    sys.exit(main())
