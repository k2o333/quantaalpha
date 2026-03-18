# test_schema_manager.py
import pytest
import polars as pl
from app4.core.schema_manager import SchemaManager

def test_create_dataframe_with_mixed_types():
    """测试混合类型数据的DataFrame创建，前100行是整数，第101行是小数"""
    data = []
    # 前100行是整数
    for i in range(100):
        data.append({'ts_code': '000002.SZ', 'value': 100})
    # 第101行是小数，模拟balancesheet_vip问题
    data.append({'ts_code': '000002.SZ', 'value': 1.2488e7})

    # 旧版本会失败，新版本应该成功
    df = SchemaManager.create_dataframe(data, 'balancesheet_vip')
    assert df.height == len(data)
    assert df.schema['value'] in [pl.Float64, pl.Float32]  # 应该是浮点类型