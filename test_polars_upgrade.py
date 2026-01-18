#!/usr/bin/env python3
"""
测试脚本，用于验证 polars 升级后的功能
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app4'))

import polars as pl
from app4.core.processor import DataProcessor
from app4.core.schema_manager import SchemaManager

def test_basic_polars_functionality():
    """测试基本的 polars 功能"""
    print("Testing basic Polars functionality...")
    
    # 测试 DataFrame 创建
    data = [
        {"ts_code": "000001.SZ", "trade_date": "20230101", "open": 10.0, "close": 10.5},
        {"ts_code": "000001.SZ", "trade_date": "20230102", "open": 10.5, "close": 11.0},
        {"ts_code": "000002.SZ", "trade_date": "20230101", "open": 20.0, "close": 20.5}
    ]
    
    df = pl.DataFrame(data)
    print(f"Created DataFrame with {len(df)} rows and {len(df.columns)} columns")
    
    # 测试 lengths -> len 变更
    df_with_index = df.with_columns(pl.int_range(0, pl.len()).alias('__index'))
    grouped = df_with_index.group_by(['ts_code']).agg(pl.col('__index').alias('index_list'))
    print(f"Grouped data: {len(grouped)} groups")

    # 测试 map 替代 apply
    try:
        # 正确的 Polars 语法用于列表操作
        # 测试 list 操作
        df_with_lists = grouped.with_columns(pl.col('index_list').list.len().alias('list_len'))
        print(f"List length result: {df_with_lists}")
    except Exception as e:
        print(f"List operation failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("Basic Polars functionality test completed.\n")

def test_data_processor():
    """测试 DataProcessor 功能"""
    print("Testing DataProcessor functionality...")
    
    processor = DataProcessor()
    
    # 测试数据
    test_data = [
        {"ts_code": "000001.SZ", "trade_date": "20230101", "open": 10.0, "close": 10.5},
        {"ts_code": "000001.SZ", "trade_date": "20230102", "open": 10.5, "close": 11.0},
        {"ts_code": "000001.SZ", "trade_date": "20230102", "open": 10.6, "close": 11.1},  # 重复日期
        {"ts_code": "000002.SZ", "trade_date": "20230101", "open": 20.0, "close": 20.5}
    ]
    
    # 模拟接口配置
    interface_config = {
        'api_name': 'test_api',
        'output': {
            'primary_key': ['ts_code', 'trade_date'],
            'columns': {
                'ts_code': {'type': 'string'},
                'trade_date': {'type': 'string'},
                'open': {'type': 'float'},
                'close': {'type': 'float'}
            }
        }
    }
    
    try:
        result_df = processor.process_data(test_data, interface_config)
        print(f"Processed {len(result_df)} records")
        
        # 验证数据
        validation_result = processor.validate_data(result_df, interface_config)
        print(f"Validation result: {validation_result}")
        
        print("DataProcessor test completed successfully.\n")
    except Exception as e:
        print(f"DataProcessor test failed: {e}")
        import traceback
        traceback.print_exc()

def test_schema_manager():
    """测试 SchemaManager 功能"""
    print("Testing SchemaManager functionality...")
    
    # 测试数据
    test_data = [
        {"ts_code": "000001.SZ", "trade_date": "20230101", "open": 10.0, "close": 10.5},
        {"ts_code": "000002.SZ", "trade_date": "20230102", "open": 11.0, "close": 11.5}
    ]
    
    try:
        df = SchemaManager.create_dataframe(test_data, 'test_api')
        print(f"Created DataFrame via SchemaManager: {len(df)} rows, columns: {df.columns}")
        print("SchemaManager test completed successfully.\n")
    except Exception as e:
        print(f"SchemaManager test failed: {e}")
        import traceback
        traceback.print_exc()

def main():
    print("Starting Polars upgrade verification tests...\n")
    
    test_basic_polars_functionality()
    test_data_processor()
    test_schema_manager()
    
    print("All tests completed!")

if __name__ == "__main__":
    main()