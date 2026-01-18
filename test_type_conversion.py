#!/usr/bin/env python3
"""
测试类型转换行为 - 验证"接口给什么就保存什么"是否可行
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'app4'))

import polars as pl
from core.processor import DataProcessor
from core.schema_manager import SchemaManager

def test_current_behavior():
    """测试当前的行为"""
    print("=== 测试当前类型转换行为 ===")
    
    # 模拟API返回的原始数据（混合类型）
    mock_data = [
        {
            'ts_code': '000001.SZ',
            'trade_date': '20240101',  # 字符串格式的日期
            'open': '10.5',            # 字符串格式的数字
            'high': 11.0,              # 浮点数
            'low': 9.8,                # 浮点数
            'close': '10.2',           # 字符串格式的数字
            'vol': 1000000,            # 整数
            'amount': '15000000.0'     # 字符串格式的数字
        },
        {
            'ts_code': '000002.SZ',
            'trade_date': '20240101',
            'open': 8.5,
            'high': 9.0,
            'low': 8.3,
            'close': 8.8,
            'vol': 800000,
            'amount': 12000000.0
        }
    ]
    
    # daily接口配置
    interface_config = {
        'api_name': 'daily',
        'output': {
            'primary_key': ['ts_code', 'trade_date'],
            'sort_by': ['trade_date'],
            'columns': {
                'ts_code': {'type': 'string', 'required': True},
                'trade_date': {'type': 'date', 'format': '%Y%m%d', 'required': True},
                'open': {'type': 'float'},
                'high': {'type': 'float'},
                'low': {'type': 'float'},
                'close': {'type': 'float'},
                'vol': {'type': 'float'},
                'amount': {'type': 'float'}
            }
        }
    }
    
    processor = DataProcessor()
    
    print("\n原始数据:")
    for i, row in enumerate(mock_data):
        print(f"Row {i}: {row}")
        for key, value in row.items():
            print(f"  {key}: {value} (type: {type(value).__name__})")
    
    # 测试当前处理流程
    df = processor.process_data(mock_data, interface_config)
    
    print(f"\n处理后的数据形状: {df.shape}")
    print("\n处理后的Schema:")
    for col, dtype in df.schema.items():
        print(f"  {col}: {dtype}")
    
    print("\n处理后的数据:")
    print(df)
    
    return df

def test_no_type_conversion():
    """测试不进行类型转换的行为"""
    print("\n=== 测试不进行类型转换的行为 ===")
    
    # 同样的模拟数据
    mock_data = [
        {
            'ts_code': '000001.SZ',
            'trade_date': '20240101',
            'open': '10.5',
            'high': 11.0,
            'low': 9.8,
            'close': '10.2',
            'vol': 1000000,
            'amount': '15000000.0'
        }
    ]
    
    # 不使用SchemaManager，直接创建DataFrame
    df_raw = pl.DataFrame(mock_data)
    
    print("\n不转换时的Schema:")
    for col, dtype in df_raw.schema.items():
        print(f"  {col}: {dtype}")
    
    print("\n不转换时的数据:")
    print(df_raw)
    
    return df_raw

def test_schema_manager_behavior():
    """测试SchemaManager的行为"""
    print("\n=== 测试SchemaManager行为 ===")
    
    mock_data = [
        {
            'ts_code': '000001.SZ',
            'trade_date': '20240101',
            'open': '10.5',
            'high': 11.0,
            'low': 9.8,
            'close': '10.2',
            'vol': 1000000,
            'amount': '15000000.0'
        }
    ]
    
    # 1. 从YAML配置创建schema
    schema_from_yaml = SchemaManager._load_schema_from_config('daily')
    print(f"\n从YAML加载的Schema: {schema_from_yaml}")
    
    if schema_from_yaml:
        df_yaml = SchemaManager.create_dataframe(mock_data, 'daily')
        print("\n使用YAML Schema创建的DataFrame:")
        print("Schema:")
        for col, dtype in df_yaml.schema.items():
            print(f"  {col}: {dtype}")
        print("Data:")
        print(df_yaml)
    
    # 2. 从数据推断schema
    schema_inferred = SchemaManager._infer_schema_from_data(mock_data)
    print(f"\n从数据推断的Schema: {schema_inferred}")
    
    return schema_from_yaml, schema_inferred

def test_raw_api_data_parsing():
    """测试原始API数据解析（不经过任何类型转换）"""
    print("\n=== 测试原始API数据解析 ===")
    
    # 模拟真实的API响应（可能包含各种类型）
    api_response = [
        {
            'ts_code': '000001.SZ',           # 字符串
            'trade_date': 20240101,           # 整数格式的日期
            'open': '10.50',                  # 字符串
            'high': 11.0,                     # 浮点数
            'low': 9.8,                       # 浮点数
            'close': '10.20',                 # 字符串
            'pre_close': None,                # 空值
            'change': '',                     # 空字符串
            'pct_chg': '0.00',                # 字符串
            'vol': 1000000,                   # 整数
            'amount': '15000000.00'           # 字符串
        }
    ]
    
    # 直接创建DataFrame，不做任何类型转换
    df_raw = pl.DataFrame(api_response)
    
    print("原始API响应的Schema:")
    for col, dtype in df_raw.schema.items():
        print(f"  {col}: {dtype}")
    
    print("\n原始API响应的数据:")
    print(df_raw)
    
    return df_raw

if __name__ == "__main__":
    print("开始测试类型转换行为...")
    
    # 测试当前行为
    df_current = test_current_behavior()
    
    # 测试不转换的行为
    df_no_conversion = test_no_type_conversion()
    
    # 测试SchemaManager行为
    schema_yaml, schema_inferred = test_schema_manager_behavior()
    
    # 测试原始API数据解析
    df_raw = test_raw_api_data_parsing()
    
    print("\n=== 总结 ===")
    print("1. 当前YAML配置确实会强制进行类型转换")
    print("2. 类型转换逻辑在 processor.py 的 _apply_type_conversions 方法中")
    print("3. SchemaManager会根据YAML配置定义的schema创建DataFrame")
    print("4. 要实现'接口给什么就保存什么'，需要:")
    print("   - 移除processor.py中的类型转换逻辑")
    print("   - 或者修改YAML配置，将所有字段类型设为string")
    print("   - 或者添加开关控制是否进行类型转换")
