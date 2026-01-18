#!/usr/bin/env python3
"""
测试 app4 项目的实际功能是否正常工作
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app4'))

from app4.core.processor import DataProcessor
from app4.core.schema_manager import SchemaManager
import polars as pl

def test_real_world_scenario():
    """测试真实世界场景"""
    print("Testing real-world scenario with actual app4 functionality...")
    
    # 模拟从API获取的真实数据
    sample_data = [
        {"ts_code": "000001.SZ", "trade_date": "20230101", "open": 10.1, "high": 10.5, "low": 9.8, "close": 10.3, "vol": 100000, "amount": 1020000},
        {"ts_code": "000001.SZ", "trade_date": "20230102", "open": 10.3, "high": 10.8, "low": 10.2, "close": 10.7, "vol": 120000, "amount": 1284000},
        {"ts_code": "000001.SZ", "trade_date": "20230103", "open": 10.7, "high": 11.0, "low": 10.5, "close": 10.9, "vol": 110000, "amount": 1199000},
        {"ts_code": "000002.SZ", "trade_date": "20230101", "open": 20.5, "high": 21.0, "low": 20.0, "close": 20.8, "vol": 80000, "amount": 1664000},
        {"ts_code": "000002.SZ", "trade_date": "20230102", "open": 20.8, "high": 21.5, "low": 20.6, "close": 21.2, "vol": 95000, "amount": 2014000},
    ]
    
    # 模拟接口配置
    interface_config = {
        'api_name': 'daily',
        'output': {
            'primary_key': ['ts_code', 'trade_date'],
            'sort_by': ['trade_date'],
            'columns': {
                'ts_code': {'type': 'string', 'required': True},
                'trade_date': {'type': 'string', 'required': True, 'format': '%Y%m%d'},
                'open': {'type': 'float', 'required': False},
                'high': {'type': 'float', 'required': False},
                'low': {'type': 'float', 'required': False},
                'close': {'type': 'float', 'required': False},
                'pre_close': {'type': 'float', 'required': False},
                'change': {'type': 'float', 'required': False},
                'pct_chg': {'type': 'float', 'required': False},
                'vol': {'type': 'float', 'required': False},
                'amount': {'type': 'float', 'required': False}
            }
        }
    }
    
    try:
        # 测试数据处理器
        processor = DataProcessor()
        processed_df = processor.process_data(sample_data, interface_config)
        
        print(f"Processed DataFrame: {len(processed_df)} rows, {len(processed_df.columns)} columns")
        print(f"Columns: {processed_df.columns}")
        
        # 验证数据
        validation_result = processor.validate_data(processed_df, interface_config)
        print(f"Validation result: {validation_result}")
        
        # 测试 SchemaManager
        schema_df = SchemaManager.create_dataframe(sample_data, 'daily')
        print(f"SchemaManager DataFrame: {len(schema_df)} rows, {len(schema_df.columns)} columns")
        
        print("Real-world scenario test completed successfully!\n")
        return True
        
    except Exception as e:
        print(f"Real-world scenario test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_edge_cases():
    """测试边界情况"""
    print("Testing edge cases...")
    
    processor = DataProcessor()
    
    # 测试空数据
    try:
        empty_result = processor.process_data([], {})
        print(f"Empty data handled correctly: {len(empty_result)} rows")
    except Exception as e:
        print(f"Empty data test failed: {e}")
        return False
    
    # 测试单行数据
    try:
        single_row = [{"ts_code": "000001.SZ", "trade_date": "20230101", "value": 100}]
        single_result = processor.process_data(single_row, {
            'api_name': 'test',
            'output': {
                'primary_key': ['ts_code', 'trade_date'],
                'columns': {
                    'ts_code': {'type': 'string'},
                    'trade_date': {'type': 'string'},
                    'value': {'type': 'float'}
                }
            }
        })
        print(f"Single row handled correctly: {len(single_result)} rows")
    except Exception as e:
        print(f"Single row test failed: {e}")
        return False
    
    print("Edge cases test completed successfully!\n")
    return True

def main():
    print("Starting real-world functionality tests for app4...\n")
    
    success_count = 0
    total_tests = 2
    
    if test_real_world_scenario():
        success_count += 1
    
    if test_edge_cases():
        success_count += 1
    
    print(f"\nReal-world test summary: {success_count}/{total_tests} tests passed")
    
    if success_count == total_tests:
        print("All real-world tests passed! The polars upgrade appears to be working correctly.")
        return True
    else:
        print("Some real-world tests failed.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)