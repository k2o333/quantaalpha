import pytest
import polars as pl
from app4.core.schema_manager import SchemaManager


def test_mixed_type_dataframe():
    """测试混合类型的数据处理，包括字符串和数值混合的场景"""
    # 创建包含混合类型的数据
    data = {
        'ts_code': ['000001.SZ', '000002.SZ', '000003.SZ'],
        'trade_date': ['20230101', '20230102', '20230103'],
        'close': ['10.5', '11.2', 12.8],  # 混合字符串和数值
        'volume': [1000000, '2000000', 1500000],  # 混合数值和字符串
        'name': ['平安银行', '万科A', '国农科技']
    }

    # 将字典转换为列表格式
    list_data = []
    for i in range(len(data['ts_code'])):
        row = {key: data[key][i] for key in data.keys()}
        list_data.append(row)

    # 创建SchemaManager实例
    schema_manager = SchemaManager()

    # 使用create_dataframe_safe方法处理混合类型数据
    df = schema_manager.create_dataframe_safe(list_data, 'daily')

    # 验证DataFrame结构
    assert df.shape[0] == 3
    assert 'ts_code' in df.columns
    assert 'trade_date' in df.columns
    assert 'close' in df.columns
    assert 'volume' in df.columns
    assert 'name' in df.columns

    # 验证数据类型转换
    # close列应该被转换为数值型
    close_series = df['close']
    assert close_series.dtype in [pl.Float32, pl.Float64]

    # volume列应该被转换为数值型
    volume_series = df['volume']
    assert volume_series.dtype in [pl.Int32, pl.Int64, pl.Float32, pl.Float64]

    # 验证数据值
    assert close_series[0] == 10.5
    assert close_series[1] == 11.2
    assert close_series[2] == 12.8

    assert volume_series[0] == 1000000
    assert volume_series[1] == 2000000
    assert volume_series[2] == 1500000

    print("test_mixed_type_dataframe passed!")


if __name__ == "__main__":
    test_mixed_type_dataframe()