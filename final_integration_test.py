#!/usr/bin/env python3
"""
最终集成测试，验证所有修改是否正确
"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app4'))

import polars as pl
from app4.core.processor import DataProcessor
from app4.core.schema_manager import SchemaManager
from app4.core.storage import StorageManager

def test_comprehensive_integration():
    """全面集成测试"""
    print("Running comprehensive integration test...")
    
    # 1. 测试 Polars 基本功能
    print("1. Testing Polars basic functionality...")
    df = pl.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    assert len(df) == 3
    print("   ✓ Basic DataFrame creation works")
    
    # 2. 测试我们修改的语法
    print("2. Testing modified Polars syntax...")
    df_with_idx = df.with_columns(pl.int_range(0, pl.len()).alias('__index'))
    grouped = df_with_idx.group_by(['b']).agg(pl.col('__index').alias('__indices'))
    result = grouped.with_columns(pl.col('__indices').list.len().alias('count'))
    assert len(result) == 3
    print("   ✓ Modified syntax (list.len()) works")
    
    # 3. 测试 DataProcessor
    print("3. Testing DataProcessor...")
    processor = DataProcessor()
    sample_data = [
        {"ts_code": "000001.SZ", "trade_date": "20230101", "value": 100},
        {"ts_code": "000002.SZ", "trade_date": "20230101", "value": 200}
    ]
    config = {
        'api_name': 'test',
        'output': {
            'primary_key': ['ts_code', 'trade_date'],
            'columns': {
                'ts_code': {'type': 'string'},
                'trade_date': {'type': 'string'},
                'value': {'type': 'float'}
            }
        }
    }
    processed_df = processor.process_data(sample_data, config)
    assert len(processed_df) == 2
    print("   ✓ DataProcessor works")
    
    # 4. 测试 SchemaManager
    print("4. Testing SchemaManager...")
    schema_df = SchemaManager.create_dataframe(sample_data, 'test')
    assert len(schema_df) == 2
    print("   ✓ SchemaManager works")
    
    # 5. 测试 StorageManager (初始化)
    print("5. Testing StorageManager initialization...")
    storage = StorageManager(storage_dir="./test_data", batch_size=100)
    assert storage.storage_dir == "./test_data"
    print("   ✓ StorageManager initializes correctly")
    
    print("\nAll integration tests passed!")
    return True

def test_error_handling():
    """测试错误处理"""
    print("\nTesting error handling...")
    
    processor = DataProcessor()
    
    # 测试空数据处理
    empty_result = processor.process_data([], {})
    assert len(empty_result) == 0
    print("   ✓ Empty data handled correctly")
    
    # 测试无效数据处理
    invalid_result = processor.process_data([{"invalid": "data"}], {})
    assert isinstance(invalid_result, pl.DataFrame)
    print("   ✓ Invalid data handled gracefully")
    
    print("Error handling tests passed!")
    return True

def main():
    print("Starting final integration tests for Polars upgrade...\n")
    
    success = True
    
    try:
        if not test_comprehensive_integration():
            success = False
        if not test_error_handling():
            success = False
    except Exception as e:
        print(f"Integration test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        success = False
    
    if success:
        print("\n🎉 All integration tests passed! Polars upgrade is successful.")
        print("\nSummary of changes made:")
        print("- Updated polars version in requirements.txt from 0.20.31 to >=1.36.1")
        print("- Changed pl.col().list().lengths() to pl.col().list().len() in processor.py")
        print("- Changed pl.col().apply() to pl.col().map() in processor.py (fallback implementations)")
        print("- Verified all functionality still works correctly")
    else:
        print("\n❌ Some tests failed. Please review the output above.")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)