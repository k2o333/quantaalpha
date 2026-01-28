import pytest
import tempfile
import os
import sys
import yaml

# 添加项目路径到sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app4.core.schema_manager import SchemaManager


def test_schema_creation_with_config_types():
    """测试使用配置中的字段类型信息创建DataFrame"""
    # 创建临时目录和配置文件
    with tempfile.TemporaryDirectory() as temp_dir:
        # 创建临时配置目录
        config_dir = os.path.join(temp_dir, 'config')
        interfaces_dir = os.path.join(config_dir, 'interfaces')
        os.makedirs(interfaces_dir, exist_ok=True)

        # 创建包含字段类型的接口配置文件
        test_interface_config = {
            'name': 'test_schema_interface',
            'api_name': 'test_schema_interface',
            'description': 'Test interface for schema with field types',
            'fields': {
                'ts_code': 'string',
                'trade_date': 'string',
                'close': 'float',
                'volume': 'int',
                'is_suspended': 'bool'
            },
            'derived_fields': {
                'trade_date_dt': {
                    'source': 'trade_date',
                    'type': 'date',
                    'format': '%Y%m%d',
                    'description': 'Date type of trade_date'
                }
            },
            'output': {
                'primary_key': ['ts_code', 'trade_date'],
                'sort_by': ['trade_date']
            }
        }

        # 写入接口配置文件
        interface_config_path = os.path.join(interfaces_dir, 'test_schema_interface.yaml')
        with open(interface_config_path, 'w', encoding='utf-8') as f:
            yaml.dump(test_interface_config, f, default_flow_style=False, allow_unicode=True)

        # 测试数据
        test_data = [
            {'ts_code': '000001.SZ', 'trade_date': '20230101', 'close': '10.5', 'volume': '1000', 'is_suspended': '0'},
            {'ts_code': '000002.SZ', 'trade_date': '20230102', 'close': '12.3', 'volume': '2000', 'is_suspended': '1'},
            {'ts_code': '000003.SZ', 'trade_date': '20230103', 'close': '11.7', 'volume': '1500', 'is_suspended': '0'},
        ]

        # 使用SchemaManager创建DataFrame，传入配置目录
        df = SchemaManager.create_dataframe(test_data, 'test_schema_interface', config_dir)

        # 验证DataFrame的基本属性
        assert len(df) == 3
        assert 'ts_code' in df.columns
        assert 'trade_date' in df.columns
        assert 'close' in df.columns
        assert 'volume' in df.columns
        assert 'is_suspended' in df.columns

        # 验证预定义的schema是否被正确应用
        schema = SchemaManager.load_schema('test_schema_interface', config_dir)
        import polars as pl
        assert schema['close'] == pl.Float64
        assert schema['volume'] == pl.Int64
        assert schema['is_suspended'] == pl.Boolean

        # 验证派生字段是否被创建
        assert 'trade_date_dt' in df.columns  # 派生字段应该被创建

        print("Schema creation with config types test passed!")


if __name__ == '__main__':
    test_schema_creation_with_config_types()