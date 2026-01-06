#!/usr/bin/env python3
"""
重复数据检测功能测试脚本
用于验证CoverageManager是否按预期工作
"""
import os
import sys
import logging
from datetime import datetime
from typing import Dict, Any, List

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config_loader import ConfigLoader
from core.downloader import GenericDownloader
from core.storage import StorageManager
from core.coverage_manager import CoverageManager

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_coverage_manager():
    """测试CoverageManager功能"""
    print("="*50)
    print("开始测试CoverageManager功能")
    print("="*50)
    
    # 初始化组件
    config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
    config_loader = ConfigLoader(config_dir=config_dir)
    storage_manager = StorageManager(storage_dir="./data")
    
    # 启动存储管理器
    storage_manager.start_writer()
    
    # 创建CoverageManager
    coverage_manager = CoverageManager(storage_manager, config_loader)
    
    # 测试1: 日期范围覆盖率检测（应该返回False，因为没有数据）
    print("\n测试1: 日期范围覆盖率检测")
    params1 = {
        'start_date': '20230101',
        'end_date': '20230131'
    }
    result1 = coverage_manager.should_skip('daily', params1, strategy='date_range')
    print(f"日期范围 {params1['start_date']}-{params1['end_date']} 覆盖检测结果: {result1}")
    
    # 测试2: 报告期存在性检测（应该返回False，因为没有数据）
    print("\n测试2: 报告期存在性检测")
    params2 = {
        'period': '20230331'
    }
    result2 = coverage_manager.should_skip('income_vip', params2, strategy='period')
    print(f"报告期 {params2['period']} 存在检测结果: {result2}")
    
    # 测试3: 股票存在性检测（应该返回False，因为没有数据）
    print("\n测试3: 股票存在性检测")
    params3 = {
        'ts_code': '000001.SZ'
    }
    result3 = coverage_manager.should_skip('daily', params3, strategy='stock')
    print(f"股票 {params3['ts_code']} 存在检测结果: {result3}")
    
    # 测试4: 自动策略检测
    print("\n测试4: 自动策略检测")
    result4 = coverage_manager.should_skip('daily', params1, strategy='auto')
    print(f"接口 daily 自动策略检测结果: {result4}")
    
    result5 = coverage_manager.should_skip('income_vip', params2, strategy='auto')
    print(f"接口 income_vip 自动策略检测结果: {result5}")
    
    result6 = coverage_manager.should_skip('stk_rewards', params3, strategy='auto')
    print(f"接口 stk_rewards 自动策略检测结果: {result6}")
    
    # 停止存储管理器
    storage_manager.stop_writer()
    
    print("\n" + "="*50)
    print("CoverageManager功能测试完成")
    print("="*50)

def test_downloader_with_coverage():
    """测试下载器与覆盖率管理器集成"""
    print("\n" + "="*50)
    print("开始测试下载器与覆盖率管理器集成")
    print("="*50)
    
    # 初始化组件
    config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
    config_loader = ConfigLoader(config_dir=config_dir)
    storage_manager = StorageManager(storage_dir="./data")
    
    # 启动存储管理器
    storage_manager.start_writer()
    
    # 创建下载器（带覆盖率管理器）
    downloader = GenericDownloader(config_loader, storage_manager)
    
    # 测试覆盖率检查方法
    print("\n测试下载器中的覆盖率检查方法")
    
    # 测试日期范围
    params1 = {
        'start_date': '20230101',
        'end_date': '20230131'
    }
    if downloader.coverage_manager:
        result1 = downloader.coverage_manager.should_skip('daily', params1, strategy='date_range')
        print(f"下载器中日期范围检测结果: {result1}")
        
        result2 = downloader.coverage_manager.should_skip('income_vip', {'period': '20230331'}, strategy='period')
        print(f"下载器中报告期检测结果: {result2}")
        
        result3 = downloader.coverage_manager.should_skip('daily', {'ts_code': '000001.SZ'}, strategy='stock')
        print(f"下载器中股票检测结果: {result3}")
    else:
        print("下载器中未找到覆盖率管理器")
    
    # 停止存储管理器
    storage_manager.stop_writer()
    
    print("\n" + "="*50)
    print("下载器与覆盖率管理器集成测试完成")
    print("="*50)

def test_config_loading():
    """测试配置加载功能"""
    print("\n" + "="*50)
    print("开始测试配置加载功能")
    print("="*50)
    
    config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
    config_loader = ConfigLoader(config_dir=config_dir)
    
    # 测试daily接口配置
    daily_config = config_loader.get_interface_config('daily')
    duplicate_detection = daily_config.get('duplicate_detection', {})
    print(f"daily接口重复检测配置: {duplicate_detection}")
    
    # 测试income_vip接口配置
    income_vip_config = config_loader.get_interface_config('income_vip')
    duplicate_detection2 = income_vip_config.get('duplicate_detection', {})
    print(f"income_vip接口重复检测配置: {duplicate_detection2}")
    
    print("\n" + "="*50)
    print("配置加载功能测试完成")
    print("="*50)

if __name__ == "__main__":
    print("aspipe_v4 重复数据检测功能测试")
    print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 运行测试
    test_config_loading()
    test_coverage_manager()
    test_downloader_with_coverage()
    
    print(f"\n所有测试完成！当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")