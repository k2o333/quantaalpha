#!/usr/bin/env python3
"""
测试配置迁移修复：验证migrate_legacy_config函数是否正确保留mode字段
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app4'))

from app4.core.config_loader import ConfigLoader
from app4.core.pagination import migrate_legacy_config, create_context_with_legacy_support, PaginationContext

def test_config_migration():
    """测试migrate_legacy_config函数是否保留mode字段"""
    print("=== 测试配置迁移函数 ===")

    # 模拟cyq_perf的旧版配置
    interface_config = {
        'name': 'cyq_perf',
        'api_name': 'cyq_perf',
        'description': '每日筹码及胜率',
        'pagination': {
            'enabled': True,
            'mode': 'reverse_date_range',
            'window_size_days': 1,
            'empty_threshold_days': 90
        },
        'parameters': {
            'trade_date': {
                'description': '交易日期 YYYYMMDD',
                'required': False,
                'type': 'string',
                'is_date_anchor': True
            },
            'ts_code': {
                'description': '股票代码',
                'required': False,
                'type': 'string'
            }
        }
    }

    print("原始配置:")
    original_pagination = interface_config['pagination']
    print(f"  mode: {original_pagination.get('mode')}")
    print(f"  window_size_days: {original_pagination.get('window_size_days')}")

    # 执行配置迁移
    migrated_config = migrate_legacy_config(interface_config)

    print(f"\n迁移后的配置:")
    print(f"  mode: {migrated_config.get('mode')}")
    print(f"  time_range: {migrated_config.get('time_range', {})}")

    # 检查是否保留了mode字段
    mode_preserved = migrated_config.get('mode') == 'reverse_date_range'
    print(f"\nmode字段是否保留: {'✓ 是' if mode_preserved else '✗ 否'}")

    return mode_preserved

def test_context_creation():
    """测试create_context_with_legacy_support是否正确处理配置"""
    print("\n=== 测试上下文创建 ===")

    interface_config = {
        'name': 'cyq_perf',
        'api_name': 'cyq_perf',
        'pagination': {
            'enabled': True,
            'mode': 'reverse_date_range',
            'window_size_days': 1,
            'empty_threshold_days': 90
        },
        'parameters': {
            'trade_date': {
                'description': '交易日期 YYYYMMDD',
                'required': False,
                'type': 'string',
                'is_date_anchor': True
            }
        }
    }

    print("创建分页上下文...")
    try:
        context = create_context_with_legacy_support(interface_config)
        pagination_config = context.pagination_config

        print(f"上下文中的分页配置:")
        print(f"  mode: {pagination_config.get('mode')}")
        print(f"  time_range: {pagination_config.get('time_range', {})}")

        mode_in_context = pagination_config.get('mode') == 'reverse_date_range'
        print(f"上下文中的mode字段是否保留: {'✓ 是' if mode_in_context else '✗ 否'}")

        return mode_in_context
    except Exception as e:
        print(f"创建上下文时出错: {e}")
        return False

def test_compose_method():
    """测试PaginationComposer.compose方法是否能正确识别reverse_date_range模式"""
    print("\n=== 测试PaginationComposer.compose方法 ===")

    from app4.core.pagination import PaginationComposer

    interface_config = {
        'name': 'cyq_perf',
        'api_name': 'cyq_perf',
        'pagination': {
            'enabled': True,
            'mode': 'reverse_date_range',
            'window_size_days': 1,
            'empty_threshold_days': 90
        },
        'parameters': {
            'trade_date': {
                'description': '交易日期 YYYYMMDD',
                'required': False,
                'type': 'string',
                'is_date_anchor': True
            }
        }
    }

    context = PaginationContext(
        interface_config=interface_config,
        user_provided_dates=True
    )

    composer = PaginationComposer(context)

    # 检查配置
    pagination_mode = composer.config.get("mode", "")
    is_date_anchor = composer._is_date_anchor_interface()

    print(f"PaginationComposer配置检查:")
    print(f"  mode: {pagination_mode}")
    print(f"  is_date_anchor_interface: {is_date_anchor}")

    # 测试compose方法
    base_params = {'start_date': '20260205', 'end_date': '20260210'}
    result = list(composer.compose(base_params))

    print(f"  compose结果数量: {len(result)}")
    if result:
        print(f"  前2个结果: {result[:2]}")

    # 验证是否正确处理了日期锚定范围
    correct_handling = (pagination_mode == 'reverse_date_range' and
                       is_date_anchor and
                       all('trade_date' in p for p in result))

    print(f"是否正确处理(模式识别+参数转换): {'✓ 是' if correct_handling else '✗ 否'}")

    return correct_handling

if __name__ == "__main__":
    print("测试配置迁移修复...")

    migration_ok = test_config_migration()
    context_ok = test_context_creation()
    compose_ok = test_compose_method()

    print(f"\n=== 总结 ===")
    print(f"配置迁移: {'✓' if migration_ok else '✗'}")
    print(f"上下文创建: {'✓' if context_ok else '✗'}")
    print(f"Compose方法: {'✓' if compose_ok else '✗'}")

    if migration_ok and context_ok and compose_ok:
        print(f"\n✓ 所有测试通过！配置迁移问题已修复。")
        print(f"  - migrate_legacy_config函数正确保留了mode字段")
        print(f"  - create_context_with_legacy_support函数正常工作")
        print(f"  - PaginationComposer.compose方法能正确识别reverse_date_range模式")
    else:
        print(f"\n✗ 部分测试失败！")
        sys.exit(1)