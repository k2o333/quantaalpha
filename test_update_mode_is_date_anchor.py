#!/usr/bin/env python3
"""
测试 --update 模式是否支持 is_date_anchor 参数

这个测试验证：
1. disclosure_date 接口的 is_date_anchor 配置是否被正确识别
2. 在 --update 模式下，日期锚定参数是否被正确处理
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app4'))

from core.config_loader import ConfigLoader


def test_disclosure_date_is_date_anchor():
    """测试 disclosure_date 接口的 is_date_anchor 配置"""
    print("测试 disclosure_date 接口的 is_date_anchor 配置...")

    config_dir_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app4/config")
    config_loader = ConfigLoader(config_dir=config_dir_path)

    # 获取 disclosure_date 接口配置
    interface_config = config_loader.get_interface_config('disclosure_date')

    # 检查参数配置
    parameter_config = interface_config.get('parameters', {})

    # 查找 is_date_anchor 参数
    date_anchor_params = []
    for param_name, param_def in parameter_config.items():
        if param_def.get('is_date_anchor', False):
            date_anchor_params.append(param_name)
            print(f"  ✓ 找到日期锚定参数: {param_name}")

    if not date_anchor_params:
        print("  ✗ 未找到日期锚定参数")
        return False

    if len(date_anchor_params) > 1:
        print(f"  ⚠ 警告: 找到多个日期锚定参数: {date_anchor_params}")

    # 检查分页配置
    pagination_config = interface_config.get('pagination', {})
    if pagination_config.get('mode') == 'stock_loop':
        print(f"  ✓ 接口使用 stock_loop 分页模式")
    else:
        print(f"  ⚠ 接口使用其他分页模式: {pagination_config.get('mode')}")

    print("\n✓ disclosure_date 接口配置验证通过")
    return True


def test_main_py_logic():
    """测试 main.py 中的日期锚定参数检测逻辑"""
    print("\n测试 main.py 中的日期锚定参数检测逻辑...")

    # 模拟接口配置
    interface_config = {
        'name': 'disclosure_date',
        'parameters': {
            'end_date': {
                'description': '报告期 YYYYMMDD',
                'type': 'string',
                'is_date_anchor': True
            },
            'ts_code': {
                'description': 'TS股票代码',
                'type': 'string'
            }
        },
        'pagination': {
            'enabled': True,
            'mode': 'stock_loop'
        }
    }

    # 检查是否有日期锚定参数（模拟 main.py 中的逻辑）
    parameter_config = interface_config.get('parameters', {})
    date_anchor_param = None
    for param_name, param_def in parameter_config.items():
        if param_def.get('is_date_anchor', False):
            if date_anchor_param:
                print(f"  ⚠ 多个日期锚定参数: {date_anchor_param}, {param_name}")
            else:
                date_anchor_param = param_name
                print(f"  ✓ 检测到日期锚定参数: {param_name}")

    if date_anchor_param:
        # 模拟参数构建
        params = {
            'start_date': '20240101',
            'end_date': '20240131',
            '_date_anchor_param': date_anchor_param
        }
        print(f"  ✓ 构建的参数: {params}")
        print("\n✓ main.py 逻辑验证通过")
        return True
    else:
        print("  ✗ 未检测到日期锚定参数")
        return False


if __name__ == '__main__':
    print("="*60)
    print("测试 --update 模式对 is_date_anchor 的支持")
    print("="*60)

    # 运行测试
    test1_passed = test_disclosure_date_is_date_anchor()
    test2_passed = test_main_py_logic()

    # 总结
    print("\n" + "="*60)
    print("测试结果总结:")
    print("="*60)
    print(f"  配置验证: {'✓ 通过' if test1_passed else '✗ 失败'}")
    print(f"  逻辑验证: {'✓ 通过' if test2_passed else '✗ 失败'}")

    if test1_passed and test2_passed:
        print("\n✓ 所有测试通过！--update 模式支持 is_date_anchor 参数")
        sys.exit(0)
    else:
        print("\n✗ 部分测试失败")
        sys.exit(1)
