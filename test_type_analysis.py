#!/usr/bin/env python3
"""
类型处理问题分析脚本
用于分析和验证app4系统中的类型处理流程
"""

import polars as pl
import json
from typing import Dict, Any, List
import os
import sys
import yaml

# 添加app4到路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app4'))

from core.schema_manager import SchemaManager
from core.processor import DataProcessor

def analyze_type_conversion_flow():
    """分析类型转换的完整流程"""
    print("=" * 80)
    print("app4系统类型处理流程分析")
    print("=" * 80)
    
    # 1. 模拟API返回的原始数据
    print("\n1. 模拟API返回的原始数据:")
    print("-" * 40)
    
    # 模拟trade_cal接口返回的数据
    raw_trade_cal_data = [
        {
            "cal_date": "20240101",
            "exchange": "SSE",
            "is_open": "0",  # 注意：这是字符串类型的0
            "pretrade_date": "20231229"
        },
        {
            "cal_date": "20240102",
            "exchange": "SSE",
            "is_open": "1",  # 注意：这是字符串类型的1
            "pretrade_date": "20240101"
        }
    ]
    
    print("原始数据类型:")
    for record in raw_trade_cal_data:
        for key, value in record.items():
            print(f"  {key}: {repr(value)} ({type(value).__name__})")
        print()
    
    # 2. 分析SchemaManager的处理
    print("\n2. SchemaManager.create_dataframe处理:")
    print("-" * 40)
    
    # 从配置加载schema
    schema = SchemaManager._load_schema_from_config('trade_cal')
    print("从YAML配置加载的schema:")
    if schema:
        for col, dtype in schema.items():
            print(f"  {col}: {dtype}")
    else:
        print("  未找到schema配置")
    
    # 创建DataFrame
    df = SchemaManager.create_dataframe(raw_trade_cal_data, 'trade_cal')
    print(f"\nSchemaManager创建的DataFrame schema:")
    print(df.schema)
    print(f"DataFrame内容:")
    print(df)
    
    # 3. 分析DataProcessor的类型转换
    print("\n3. DataProcessor._apply_type_conversions处理:")
    print("-" * 40)
    
    # 加载接口配置
    config_path = os.path.join(os.path.dirname(__file__), 'app4', 'config', 'interfaces', 'trade_cal.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        interface_config = yaml.safe_load(f)
    
    print("接口配置中的类型定义:")
    columns_config = interface_config.get('output', {}).get('columns', {})
    for col, config in columns_config.items():
        print(f"  {col}: {config}")
    
    # 应用类型转换
    processor = DataProcessor()
    df_converted = processor._apply_type_conversions(df, interface_config)
    
    print(f"\n类型转换后的DataFrame schema:")
    print(df_converted.schema)
    print(f"DataFrame内容:")
    print(df_converted)
    
    # 4. 分析存储时的类型
    print("\n4. 存储时的类型处理:")
    print("-" * 40)
    
    # 存储到Parquet
    import tempfile
    
    with tempfile.TemporaryDirectory() as temp_dir:
        test_file = os.path.join(temp_dir, 'test_trade_cal.parquet')
        df_converted.write_parquet(test_file)
        
        # 读取回来验证
        df_read = pl.read_parquet(test_file)
        print(f"从Parquet读取的DataFrame schema:")
        print(df_read.schema)
        print(f"读取的DataFrame内容:")
        print(df_read)
    
    # 5. 问题总结
    print("\n5. 问题总结:")
    print("-" * 40)
    print("发现的问题:")
    print("1. YAML配置中is_open定义为string类型，但API返回的是字符串'0'/'1'")
    print("2. SchemaManager根据YAML配置强制将is_open设为Utf8类型")
    print("3. DataProcessor没有对is_open进行特殊处理")
    print("4. 最终存储的is_open是字符串'0'/'1'，而不是整数0/1")
    
    print("\n建议的解决方案:")
    print("1. 修改YAML配置中的类型定义")
    print("2. 在DataProcessor中添加特殊类型转换逻辑")
    print("3. 实现'接口给什么就保存什么'的原则")
    print("4. 减少强制类型转换，保持原始数据类型")

def test_different_data_types():
    """测试不同数据类型的处理"""
    print("\n" + "=" * 80)
    print("不同数据类型处理测试")
    print("=" * 80)
    
    # 模拟不同接口的数据
    test_cases = [
        {
            "name": "daily接口",
            "interface": "daily",
            "data": [
                {
                    "ts_code": "000001.SZ",
                    "trade_date": "20240101",
                    "open": "10.50",  # 字符串形式的浮点数
                    "high": "11.00",
                    "low": "10.20",
                    "close": "10.80",
                    "vol": "1000000",  # 字符串形式的整数
                    "amount": "10800000.00"
                }
            ]
        },
        {
            "name": "stock_basic接口", 
            "interface": "stock_basic",
            "data": [
                {
                    "ts_code": "000001.SZ",
                    "symbol": "000001",
                    "name": "平安银行",
                    "area": "深圳",
                    "industry": "银行",
                    "list_date": "19910403",  # 字符串形式的日期
                    "market": "主板"
                }
            ]
        }
    ]
    
    for test_case in test_cases:
        print(f"\n测试 {test_case['name']}:")
        print("-" * 40)
        
        print("原始数据类型:")
        for record in test_case['data']:
            for key, value in record.items():
                print(f"  {key}: {repr(value)} ({type(value).__name__})")
        
        # SchemaManager处理
        df = SchemaManager.create_dataframe(test_case['data'], test_case['interface'])
        print(f"\nSchemaManager处理后:")
        print(df.schema)
        print(df)
        
        # DataProcessor处理
        config_path = os.path.join(os.path.dirname(__file__), 'app4', 'config', 'interfaces', f"{test_case['interface']}.yaml")
        with open(config_path, 'r', encoding='utf-8') as f:
            interface_config = yaml.safe_load(f)
        
        processor = DataProcessor()
        df_processed = processor.process_data(test_case['data'], interface_config)
        print(f"\nDataProcessor处理后:")
        print(df_processed.schema)
        print(df_processed)

if __name__ == "__main__":
    analyze_type_conversion_flow()
    test_different_data_types()
    
    print("\n" + "=" * 80)
    print("分析完成")
    print("=" * 80)
