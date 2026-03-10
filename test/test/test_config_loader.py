import pytest
import tempfile
import os
from unittest.mock import patch
import sys
import yaml

# 添加项目路径到sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app4.core.config_loader import ConfigLoader
from app4.core.schema_manager import SchemaManager


def test_field_type_configuration():
    """测试字段类型配置和接口特定的清理规则"""
    # 创建临时目录和配置文件
    with tempfile.TemporaryDirectory() as temp_dir:
        # 创建临时配置目录
        config_dir = os.path.join(temp_dir, 'config')
        interfaces_dir = os.path.join(config_dir, 'interfaces')
        os.makedirs(interfaces_dir, exist_ok=True)

        # 创建测试接口配置文件，包含字段类型配置和清理规则
        test_interface_config = {
            'name': 'test_interface',
            'api_name': 'test_interface',
            'description': 'Test interface for field type configuration',
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
                },
                'is_suspended_bool': {
                    'source': 'is_suspended',
                    'type': 'boolean',
                    'description': 'Boolean type of is_suspended'
                }
            },
            'cleaning_rules': {
                'replace_values': {
                    '': None,
                    'NULL': None,
                    'null': None
                },
                'numeric_fields': ['close', 'volume'],
                'date_fields': ['trade_date']
            },
            'output': {
                'primary_key': ['ts_code', 'trade_date'],
                'sort_by': ['trade_date']
            },
            'pagination': {
                'enabled': True,
                'mode': 'date_range'
            },
            'permissions': {
                'min_points': 0,
                'rate_limit': 100,
                'query_limit': 5000
            }
        }

        # 写入接口配置文件
        interface_config_path = os.path.join(interfaces_dir, 'test_interface.yaml')
        with open(interface_config_path, 'w', encoding='utf-8') as f:
            yaml.dump(test_interface_config, f, default_flow_style=False, allow_unicode=True)

        # 创建全局配置
        global_config = {
            'app': {
                'name': 'aspipe_v4_test',
                'version': '4.0.0'
            },
            'tushare': {
                'token': 'test_token',
                'base_url': 'http://api.tushare.pro',
                'points_thresholds': {
                    'basic': 120,
                    'standard': 2000,
                    'advanced': 5000,
                    'professional': 8000
                }
            },
            'concurrency': {
                'max_workers': 4,
                'max_queue_size': 1000
            },
            'request': {
                'max_retries': 3,
                'retry_delay': 1.0,
                'timeout': 30
            },
            'cache': {
                'directory': 'cache',
                'ttl_hours': 24,
                'max_size_gb': 10
            },
            'storage': {
                'base_dir': '../data',
                'format': 'parquet',
                'batch_size': 10000
            },
            'logging': {
                'level': 'INFO',
                'file': 'log/app4.log',
                'max_size_mb': 100,
                'backup_count': 5
            }
        }

        # 写入全局配置文件
        global_config_path = os.path.join(config_dir, 'settings.yaml')
        with open(global_config_path, 'w', encoding='utf-8') as f:
            yaml.dump(global_config, f, default_flow_style=False, allow_unicode=True)

        # 测试配置加载器
        config_loader = ConfigLoader(config_dir)

        # 测试字段类型配置
        interface_config = config_loader.get_interface_config('test_interface')
        assert 'fields' in interface_config
        assert interface_config['fields']['ts_code'] == 'string'
        assert interface_config['fields']['close'] == 'float'
        assert interface_config['fields']['volume'] == 'int'
        assert interface_config['fields']['is_suspended'] == 'bool'

        # 测试派生字段配置
        assert 'derived_fields' in interface_config
        derived_fields = interface_config['derived_fields']
        assert 'trade_date_dt' in derived_fields
        assert 'is_suspended_bool' in derived_fields
        assert derived_fields['trade_date_dt']['type'] == 'date'
        assert derived_fields['is_suspended_bool']['type'] == 'boolean'

        # 测试清理规则配置
        assert 'cleaning_rules' in interface_config
        cleaning_rules = interface_config['cleaning_rules']
        assert 'replace_values' in cleaning_rules
        assert '' in cleaning_rules['replace_values']
        assert 'numeric_fields' in cleaning_rules
        assert 'date_fields' in cleaning_rules
        assert 'close' in cleaning_rules['numeric_fields']
        assert 'trade_date' in cleaning_rules['date_fields']

        # 测试SchemaManager是否能正确处理字段类型
        # 首先测试字段类型加载
        schema = SchemaManager.load_schema('test_interface', config_dir)
        assert schema is not None
        assert 'ts_code' in schema
        assert 'close' in schema
        assert 'volume' in schema
        assert 'is_suspended' in schema

        # 验证类型映射是否正确
        import polars as pl
        assert schema['ts_code'] == pl.String
        assert schema['close'] == pl.Float64
        assert schema['volume'] == pl.Int64
        assert schema['is_suspended'] == pl.Boolean

        # 验证派生字段配置
        derived_config = SchemaManager.load_derived_fields_config('test_interface', config_dir)
        assert derived_config is not None
        assert 'trade_date_dt' in derived_config
        assert 'is_suspended_bool' in derived_config
        assert derived_config['trade_date_dt']['type'] == 'date'
        assert derived_config['is_suspended_bool']['type'] == 'boolean'

        print("Field type configuration and interface-specific cleaning rules test passed!")


if __name__ == '__main__':
    test_field_type_configuration()