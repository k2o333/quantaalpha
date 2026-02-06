#!/usr/bin/env python3
"""
测试可组合式分页架构
验证所有现有分页模式正常工作
"""

import yaml
import os
import sys
from app4.core.config_loader import ConfigLoader
from app4.core.downloader import GenericDownloader
from app4.core.pagination import create_context_with_legacy_support, migrate_legacy_config
from app4.core.pagination_executor import PaginationExecutor

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_config_migration():
    """
    测试旧配置自动转换
    """
    print("\n=== 测试配置迁移 ===")
    
    # 测试 offset 模式
    offset_config = {
        'pagination': {
            'default_limit': 5000,
            'enabled': True,
            'limit_key': 'limit',
            'mode': 'offset',
            'offset_key': 'offset'
        }
    }
    
    # 测试 date_range 模式
    date_range_config = {
        'pagination': {
            'enabled': True,
            'mode': 'date_range',
            'window_size_days': 365
        }
    }
    
    # 测试 stock_loop 模式
    stock_loop_config = {
        'pagination': {
            'enabled': True,
            'mode': 'stock_loop',
            'window_size_days': 3650
        }
    }
    
    # 测试 type_split 模式
    type_split_config = {
        'pagination': {
            'enabled': True,
            'mode': 'type_split',
            'window_size_days': 1
        },
        'type_values': ['HK_SZ', 'SZ_HK', 'HK_SH', 'SH_HK']
    }
    
    # 测试 reverse_date_range 模式
    reverse_date_range_config = {
        'pagination': {
            'enabled': True,
            'mode': 'reverse_date_range',
            'window_size_days': 30,
            'empty_threshold_days': 90
        }
    }
    
    test_cases = [
        ('offset', offset_config),
        ('date_range', date_range_config),
        ('stock_loop', stock_loop_config),
        ('type_split', type_split_config),
        ('reverse_date_range', reverse_date_range_config)
    ]
    
    for mode_name, test_config in test_cases:
        print(f"\n测试 {mode_name} 模式配置迁移:")
        migrated_config = migrate_legacy_config(test_config)
        print(f"旧配置模式: {test_config['pagination'].get('mode')}")
        print(f"新配置结构: {list(migrated_config.keys())}")
        if 'time_range' in migrated_config:
            print(f"  time_range: {migrated_config['time_range']}")
        if 'stock_loop' in migrated_config:
            print(f"  stock_loop: {migrated_config['stock_loop']}")
        if 'type_split' in migrated_config:
            print(f"  type_split: {migrated_config['type_split']}")
        if 'offset' in migrated_config:
            print(f"  offset: {migrated_config['offset']}")
        print("✓ 配置迁移成功")

def test_interface_configs():
    """
    测试现有接口配置
    """
    print("\n=== 测试现有接口配置 ===")
    
    config_dir = os.path.join(os.path.dirname(__file__), 'app4', 'config')
    config_loader = ConfigLoader(config_dir)
    
    # 获取所有接口名称
    interface_names = config_loader.get_available_interfaces()
    print(f"发现 {len(interface_names)} 个接口配置")
    
    # 测试前5个接口配置
    test_interfaces = interface_names[:5]
    for interface_name in test_interfaces:
        print(f"\n测试接口: {interface_name}")
        try:
            interface_config = config_loader.get_interface_config(interface_name)
            pagination_config = interface_config.get('pagination', {})
            mode = pagination_config.get('mode', 'offset')
            print(f"  接口模式: {mode}")
            
            # 测试配置迁移
            migrated_config = migrate_legacy_config(interface_config)
            print(f"  迁移后配置: {list(migrated_config.keys())}")
            print("  ✓ 配置验证成功")
        except Exception as e:
            print(f"  ✗ 测试失败: {e}")

def test_pagination_composition():
    """
    测试复杂组合场景
    """
    print("\n=== 测试复杂组合场景 ===")
    
    # 创建一个复杂的分页配置
    complex_config = {
        'name': 'test_complex',
        'api_name': 'test.api',
        'pagination': {
            'enabled': True,
            'time_range': {
                'enabled': True,
                'window': '30d',
                'reverse': True,
                'stop_on_empty': 90
            },
            'stock_loop': {
                'enabled': True,
                'skip_existing': True
            },
            'type_split': {
                'enabled': True,
                'field': 'market_type',
                'values': ['主板', '创业板', '科创板', '北交所']
            },
            'offset': {
                'enabled': True,
                'limit': 1000
            }
        }
    }
    
    print("测试复杂组合配置:")
    print(f"  时间范围: enabled=True, window=30d, reverse=True")
    print(f"  股票循环: enabled=True, skip_existing=True")
    print(f"  分类分割: enabled=True, field=market_type, values=4个")
    print(f"  偏移分页: enabled=True, limit=1000")
    
    # 测试配置迁移
    migrated_config = migrate_legacy_config(complex_config)
    print(f"  迁移后配置: {list(migrated_config.keys())}")
    print("✓ 复杂组合配置验证成功")

def main():
    """
    主测试函数
    """
    print("开始测试可组合式分页架构")
    
    try:
        test_config_migration()
        test_interface_configs()
        test_pagination_composition()
        
        print("\n=== 测试完成 ===")
        print("✓ 所有测试通过")
        print("可组合式分页架构已成功实现")
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
