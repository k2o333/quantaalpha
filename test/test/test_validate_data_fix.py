"""
测试 validate_data 方法的返回值
确保修复 KeyError: 'valid' bug
"""

import polars as pl
import sys
import os

# Add app4 to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app4'))

from core.processor import DataProcessor


def test_validate_data_contains_valid_field():
    """测试 validate_data 返回值包含 'valid' 字段"""
    processor = DataProcessor()
    
    # 基本接口配置
    interface_config = {
        'output': {
            'primary_key': ['ts_code', 'trade_date'],
            'columns': {}
        }
    }
    
    # 创建测试数据
    df = pl.DataFrame({
        'ts_code': ['000001.SZ', '000002.SZ'],
        'trade_date': ['20230101', '20230102'],
        'close': [10.5, 11.2]
    })

    # 调用 validate_data
    result = processor.validate_data(df, interface_config)

    # 验证返回值包含 'valid' 字段
    assert 'valid' in result, "validate_data 返回值必须包含 'valid' 字段"
    assert isinstance(result['valid'], bool), "'valid' 字段必须是布尔值"
    print("✅ test_validate_data_contains_valid_field: 通过")

def test_validate_data_valid_true_for_good_data():
    """测试对于好的数据，valid 应该为 True"""
    processor = DataProcessor()
    
    interface_config = {
        'output': {
            'primary_key': ['ts_code', 'trade_date'],
            'columns': {}
        }
    }
    
    # 创建干净的测试数据
    df = pl.DataFrame({
        'ts_code': ['000001.SZ', '000002.SZ'],
        'trade_date': ['20230101', '20230102'],
        'close': [10.5, 11.2]
    })

    result = processor.validate_data(df, interface_config)

    assert result['valid'] is True, "干净的数据应该通过验证"
    assert result['total_records'] == 2
    assert len(result['missing_required_fields']) == 0
    assert len(result['type_mismatches']) == 0
    print("✅ test_validate_data_valid_true_for_good_data: 通过")

def test_validate_data_backward_compatibility():
    """测试向后兼容性 - 其他字段应该仍然存在"""
    processor = DataProcessor()
    
    interface_config = {
        'output': {
            'primary_key': ['ts_code', 'trade_date'],
            'columns': {}
        }
    }
    
    df = pl.DataFrame({
        'ts_code': ['000001.SZ'],
        'trade_date': ['20230101'],
        'close': [10.5]
    })

    result = processor.validate_data(df, interface_config)

    # 验证所有期望的字段都存在
    expected_fields = [
        'total_records', 'total_columns', 'missing_required_fields',
        'type_mismatches', 'duplicate_records', 'total', 'unique',
        'duplicates', 'duplicate_rate', 'valid'
    ]
    
    for field in expected_fields:
        assert field in result, f"返回值必须包含字段: {field}"
    print("✅ test_validate_data_backward_compatibility: 通过")


if __name__ == '__main__':
    print("开始运行 validate_data 修复验证测试...")
    
    try:
        test_validate_data_contains_valid_field()
        test_validate_data_valid_true_for_good_data()
        test_validate_data_backward_compatibility()
        
        print("\n🎉 所有测试通过！validate_data 修复验证成功。")
        
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)