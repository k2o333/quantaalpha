import pytest
import polars as pl
from app4.core.schema_manager import SchemaManager


def test_field_name_based_numeric_detection():
    """测试基于字段名的数值字段识别功能"""
    # 创建包含金融数据字段名的数据，其中包含混合类型
    data = {
        'ts_code': ['000001.SZ', '000002.SZ', '000003.SZ'],
        'trade_date': ['20230101', '20230102', '20230103'],
        'close': ['10.5', '11.2', 12.8],  # 混合字符串和数值 - 字段名表明这是数值
        'volume': [1000000, '2000000', 1500000],  # 混合数值和字符串 - 字段名表明这是数值
        'pe': ['12.5', 13.2, '14.1'],  # 混合字符串和数值 - 字段名表明这是数值
        'name': ['平安银行', '万科A', '国农科技'],  # 非数值字段
        'is_hs': ['0', '1', '0']  # 非数值字段（即使内容可转换为数值）
    }

    # 将字典转换为列表格式
    list_data = []
    for i in range(len(data['ts_code'])):
        row = {key: data[key][i] for key in data.keys()}
        list_data.append(row)

    # 创建SchemaManager实例
    schema_manager = SchemaManager()

    # 使用create_dataframe_safe方法处理数据
    df = schema_manager.create_dataframe_safe(list_data, 'daily')

    # 验证DataFrame结构
    assert df.shape[0] == 3
    assert 'ts_code' in df.columns
    assert 'trade_date' in df.columns
    assert 'close' in df.columns
    assert 'volume' in df.columns
    assert 'pe' in df.columns
    assert 'name' in df.columns
    assert 'is_hs' in df.columns

    # 验证基于字段名的数值转换
    # close列应该被转换为数值型（因为字段名包含在预定义模式中）
    close_series = df['close']
    assert close_series.dtype in [pl.Float32, pl.Float64]

    # volume列应该被转换为数值型（因为字段名包含在预定义模式中）
    volume_series = df['volume']
    assert volume_series.dtype in [pl.Int32, pl.Int64, pl.Float32, pl.Float64]

    # pe列应该被转换为数值型（因为字段名包含在预定义模式中）
    pe_series = df['pe']
    assert pe_series.dtype in [pl.Float32, pl.Float64]

    # 验证数据值的正确性
    assert close_series[0] == 10.5
    assert close_series[1] == 11.2
    assert close_series[2] == 12.8

    assert volume_series[0] == 1000000
    assert volume_series[1] == 2000000
    assert volume_series[2] == 1500000

    assert pe_series[0] == 12.5
    assert pe_series[1] == 13.2
    assert pe_series[2] == 14.1

    # 非数值字段应保持为字符串
    name_series = df['name']
    assert name_series.dtype == pl.String

    is_hs_series = df['is_hs']
    assert is_hs_series.dtype == pl.String

    print("test_field_name_based_numeric_detection passed!")


if __name__ == "__main__":
    test_field_name_based_numeric_detection()