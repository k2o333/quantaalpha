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


def test_data_cleaning_with_rules():
    """测试数据清理规则功能"""
    # 创建临时目录和配置文件
    with tempfile.TemporaryDirectory() as temp_dir:
        # 创建临时配置目录
        config_dir = os.path.join(temp_dir, 'config')
        interfaces_dir = os.path.join(config_dir, 'interfaces')
        os.makedirs(interfaces_dir, exist_ok=True)

        # 创建测试接口配置文件，包含清理规则
        test_interface_config = {
            'name': 'test_cleaning_interface',
            'api_name': 'test_cleaning_interface',
            'description': 'Test interface for cleaning rules',
            'cleaning_rules': {
                'replace_values': {
                    '': None,
                    'NULL': None,
                    'null': None,
                    'N/A': None,
                    'Unknown': 'UNKNOWN'
                },
                'numeric_fields': ['close', 'volume'],
                'date_fields': ['trade_date']
            },
            'output': {
                'primary_key': ['ts_code', 'trade_date'],
                'sort_by': ['trade_date']
            }
        }

        # 写入接口配置文件
        interface_config_path = os.path.join(interfaces_dir, 'test_cleaning_interface.yaml')
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
            },
            'storage': {
                'base_dir': '../data',
                'format': 'parquet',
            }
        }

        # 写入全局配置文件
        global_config_path = os.path.join(config_dir, 'settings.yaml')
        with open(global_config_path, 'w', encoding='utf-8') as f:
            yaml.dump(global_config, f, default_flow_style=False, allow_unicode=True)

        # 测试清理规则功能
        test_data = [
            {'ts_code': '000001.SZ', 'trade_date': '', 'close': '10.5', 'volume': '1000'},
            {'ts_code': '000002.SZ', 'trade_date': '20230101', 'close': 'NULL', 'volume': 'N/A'},
            {'ts_code': '000003.SZ', 'trade_date': '20230102', 'close': '12.3', 'volume': None},
            {'ts_code': '000004.SZ', 'trade_date': '20230103', 'close': '', 'volume': '2000'},
            {'ts_code': '000005.SZ', 'trade_date': 'N/A', 'close': '13.5', 'volume': '3000'},
        ]

        # 使用清理规则处理数据
        cleaned_data = SchemaManager._clean_data_with_rules(test_data, 'test_cleaning_interface', config_dir)

        # 验证清理结果
        assert cleaned_data[0]['trade_date'] is None  # 空字符串应该被替换为None
        assert cleaned_data[1]['close'] is None       # 'NULL' 应该被替换为None
        assert cleaned_data[1]['volume'] is None      # 'N/A' 应该被替换为None
        assert cleaned_data[3]['close'] is None       # 空字符串应该被替换为None
        assert cleaned_data[4]['trade_date'] is None  # 'N/A' 应该被替换为None

        print("Data cleaning with interface-specific rules test passed!")


if __name__ == '__main__':
    test_data_cleaning_with_rules()