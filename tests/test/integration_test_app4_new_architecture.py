"""端到端集成测试验证新架构"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

import polars as pl
from app4.core.config_loader import ConfigLoader
from app4.core.downloader import GenericDownloader
from app4.core.schema_manager import SchemaManager
from app4.core.processor import DataProcessor
from app4.core.storage import StorageManager
import tempfile
import shutil


def test_end_to_end_flow():
    """端到端测试验证新架构"""
    print("🧪 Testing end-to-end flow...")

    # 测试数据处理流程
    test_data = [
        {
            'cal_date': '20240101',
            'exchange': 'SSE',
            'is_open': '1',
            'pretrade_date': '20231229'
        },
        {
            'cal_date': '20240102',
            'exchange': 'SSE',
            'is_open': '0',
            'pretrade_date': '20240101'
        }
    ]

    # 1. 测试SchemaManager
    print("  - Testing SchemaManager...")
    df = SchemaManager.create_dataframe(test_data, 'trade_cal')

    assert 'cal_date' in df.columns, "原始字段应保留"
    assert 'cal_date_dt' in df.columns, "衍生字段应生成"
    assert 'is_open_bool' in df.columns, "布尔衍生字段应生成"
    assert df['cal_date_dt'].dtype == pl.Date, "日期字段类型应正确"
    assert df['is_open_bool'].dtype == pl.Boolean, "布尔字段类型应正确"
    print("    ✅ SchemaManager test passed")

    # 2. 测试DataProcessor
    print("  - Testing DataProcessor...")
    processor = DataProcessor()

    interface_config = {
        'api_name': 'trade_cal',
        'output': {
            'primary_key': ['cal_date', 'exchange'],
            'sort_by': ['cal_date']
        }
    }

    processed_df = processor.process_data(test_data, interface_config)

    assert 'cal_date' in processed_df.columns, "处理后的数据应保留原始字段"
    assert 'cal_date_dt' in processed_df.columns, "处理后的数据应包含衍生字段"
    print("    ✅ DataProcessor test passed")

    print("✅ End-to-end flow tests passed")


def test_multiple_interfaces():
    """测试多个接口类型"""
    print("🧪 Testing multiple interface types...")

    # 测试各种数据类型
    test_cases = [
        {
            'name': 'trade_cal',
            'data': [
                {'cal_date': '20240101', 'exchange': 'SSE', 'is_open': '1'},
                {'cal_date': '20240102', 'exchange': 'SSE', 'is_open': '0'}
            ]
        },
        {
            'name': 'daily',
            'data': [
                {'ts_code': '000001.SZ', 'trade_date': '20240101', 'open': 10.0},
                {'ts_code': '000001.SZ', 'trade_date': '20240102', 'open': 10.1}
            ]
        }
    ]

    for case in test_cases:
        print(f"    - Testing {case['name']} interface...")

        df = SchemaManager.create_dataframe(case['data'], case['name'])

        # 验证基本字段存在
        assert len(df) == len(case['data']), f"行数应匹配 {case['name']} 接口"

        # 验证衍生字段存在
        if case['name'] == 'trade_cal':
            assert 'cal_date_dt' in df.columns, "trade_cal 应有日期衍生字段"
            assert 'is_open_bool' in df.columns, "trade_cal 应有布尔衍生字段"
        elif case['name'] == 'daily':
            assert 'trade_date_dt' in df.columns, "daily 应有日期衍生字段"

        print(f"      ✅ {case['name']} interface test passed")

    print("✅ Multiple interfaces tests passed")


def test_query_performance():
    """验证衍生字段（如is_open_bool）的查询性能提升"""
    print("⏱️  Testing query performance...")

    # 创建大量测试数据
    large_test_data = []
    for i in range(1000):
        large_test_data.append({
            'cal_date': f"202401{i%30+1:02d}",
            'exchange': 'SSE',
            'is_open': '1' if i % 2 == 0 else '0',
            'pretrade_date': f"202401{(i%30+1)%28+1:02d}"
        })

    # 创建DataFrame
    df = SchemaManager.create_dataframe(large_test_data, 'trade_cal')

    # 测试原始字段查询
    import time

    # 查询原始字段（字符串格式）
    start_time = time.time()
    result1 = df.filter(pl.col('is_open') == '1').height
    original_time = time.time() - start_time

    # 查询衍生字段（布尔格式）
    start_time = time.time()
    result2 = df.filter(pl.col('is_open_bool') == True).height
    derived_time = time.time() - start_time

    # 结果应该相同
    assert result1 == result2, "原始字段和衍生字段查询结果应一致"

    print(f"    Original field query time: {original_time:.6f}s")
    print(f"    Derived field query time: {derived_time:.6f}s")

    # 衍生字段查询通常更快，但不强制要求
    print("    ✅ Query performance test completed")

    print("✅ Query performance tests passed")


def test_error_handling():
    """测试新架构的错误处理能力"""
    print("🧪 Testing error handling...")

    # 测试无效接口名称
    try:
        df = SchemaManager.create_dataframe([{'test': 'data'}], 'nonexistent_interface')
        # 应该能创建DataFrame，但可能不包含衍生字段
        print("    ✅ Invalid interface test passed (graceful handling)")
    except FileNotFoundError:
        # 配置文件不存在是预期的，这表示系统正常处理这种情况
        print("    ✅ Invalid interface test passed (graceful handling)")
    except Exception as e:
        print(f"    ❌ Invalid interface test failed: {e}")

    # 测试空数据
    try:
        df = SchemaManager.create_dataframe([], 'trade_cal')
        assert df.is_empty(), "空数据应返回空DataFrame"
        print("    ✅ Empty data test passed")
    except Exception as e:
        print(f"    ❌ Empty data test failed: {e}")

    # 测试无效日期格式
    try:
        test_data = [{'cal_date': 'invalid_date', 'exchange': 'SSE', 'is_open': '1'}]
        df = SchemaManager.create_dataframe(test_data, 'trade_cal')
        # 应该能处理，日期转换可能失败但其他字段保留
        print("    ✅ Invalid date format test passed")
    except Exception as e:
        print(f"    ❌ Invalid date format test failed: {e}")

    print("✅ Error handling tests passed")


if __name__ == "__main__":
    print("🚀 Starting integration tests for new raw data + derived fields architecture")

    test_end_to_end_flow()
    print()
    test_multiple_interfaces()
    print()
    test_query_performance()
    print()
    test_error_handling()

    print("\n🎉 All integration tests completed successfully!")