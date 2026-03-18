# test_schema_loading.py
import os
from app4.core.schema_manager import SchemaManager

def test_load_schema_method():
    """测试SchemaManager.load_schema方法"""
    # 测试加载balancesheet_vip schema
    loaded_schema = SchemaManager.load_schema('balancesheet_vip')
    assert loaded_schema is not None
    assert 'ts_code' in loaded_schema
    assert loaded_schema['ts_code'] == 'string'
    assert 'total_assets' in loaded_schema
    assert loaded_schema['total_assets'] == 'Float64'

    # 测试加载income_vip schema
    loaded_schema = SchemaManager.load_schema('income_vip')
    assert loaded_schema is not None
    assert 'revenue' in loaded_schema
    assert loaded_schema['revenue'] == 'Float64'

    # 测试加载cashflow_vip schema
    loaded_schema = SchemaManager.load_schema('cashflow_vip')
    assert loaded_schema is not None
    assert 'net_profit' in loaded_schema
    assert loaded_schema['net_profit'] == 'Float64'

    # 测试不存在的接口，应该返回None
    loaded_schema = SchemaManager.load_schema('nonexistent_interface')
    assert loaded_schema is None