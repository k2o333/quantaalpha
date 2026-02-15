#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试接口是否可以通过只传递股票代码参数来一次性返回历史所有该股票记录
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app4'))

from app4.core.config_loader import ConfigLoader
from app4.core.downloader import GenericDownloader


def test_interface_with_stock_code_only(interface_name: str, ts_code: str = "000001.SZ"):
    """
    测试接口是否可以通过只传递股票代码参数来一次性返回历史所有该股票记录
    
    Args:
        interface_name: 接口名称
        ts_code: 股票代码，默认为平安银行
    """
    print(f"\n{'='*60}")
    print(f"Testing interface: {interface_name}")
    print(f"Stock code: {ts_code}")
    
    try:
        # 初始化配置加载器
        config_loader = ConfigLoader("./app4/config")
        
        # 获取接口配置
        interface_config = config_loader.get_interface_config(interface_name)
        print(f"Interface config loaded successfully")
        
        # 初始化下载器（不使用存储管理器，避免读取股票列表）
        downloader = GenericDownloader(config_loader, storage_manager=None)
        
        # 只传递股票代码参数
        params = {
            'ts_code': ts_code
        }
        
        print(f"Making request with params: {params}")
        
        # 发起请求
        result = downloader.download(interface_name, params)
        
        if result is not None:
            print(f"✓ Request successful")
            print(f"  Records returned: {len(result)}")
            
            if result:
                print(f"  Sample record keys: {list(result[0].keys())}")
                
                # 检查是否包含预期的日期字段
                date_field_mapping = {
                    'disclosure_date': 'end_date',
                    'top10_holders': 'end_date',  # period is the query param, but end_date is in data
                    'dividend': 'ann_date',
                    'pledge_stat': 'end_date',
                    'stk_rewards': 'end_date'
                }
                
                expected_date_field = date_field_mapping.get(interface_name)
                if expected_date_field and expected_date_field in result[0]:
                    print(f"  Date field '{expected_date_field}' present: {result[0][expected_date_field]}")
                    
                    # 检查是否有历史数据（最早的日期）
                    if len(result) > 1:
                        dates = [record.get(expected_date_field) for record in result if record.get(expected_date_field)]
                        if dates:
                            earliest_date = min(dates)
                            latest_date = max(dates)
                            print(f"  Date range: {earliest_date} to {latest_date}")
                
                # 检查是否包含股票代码
                if 'ts_code' in result[0]:
                    print(f"  Stock code field present: {result[0]['ts_code']}")
        else:
            print(f"✗ Request failed - returned None")
            
    except Exception as e:
        print(f"✗ Error occurred: {str(e)}")
        import traceback
        traceback.print_exc()


def main():
    """主函数 - 测试所有指定的接口"""
    print("Testing interfaces with stock code only parameter")
    print("This script tests if the following interfaces can return all historical records for a stock with only the stock code parameter:")
    print("- disclosure_date")
    print("- top10_holders") 
    print("- dividend")
    print("- pledge_stat")
    print("- stk_rewards")
    
    # 测试的接口列表
    interfaces_to_test = [
        'disclosure_date',
        'top10_holders',
        'dividend', 
        'pledge_stat',
        'stk_rewards'
    ]
    
    # 使用一个示例股票代码进行测试
    sample_stock_code = "000001.SZ"  # 平安银行
    
    for interface in interfaces_to_test:
        test_interface_with_stock_code_only(interface, sample_stock_code)


if __name__ == "__main__":
    main()