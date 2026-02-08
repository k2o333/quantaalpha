#!/usr/bin/env python3
"""
简单测试：验证 disclosure_date.yaml 配置中的 is_date_anchor
"""

import yaml
import sys
import os


def test_disclosure_date_config():
    """直接读取并验证配置文件"""
    print("="*60)
    print("测试 disclosure_date 接口的 is_date_anchor 配置")
    print("="*60)

    config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               'app4/config/interfaces/disclosure_date.yaml')

    if not os.path.exists(config_file):
        print(f"✗ 配置文件不存在: {config_file}")
        return False

    # 读取配置文件
    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    print(f"\n接口名称: {config.get('name')}")
    print(f"API 名称: {config.get('api_name')}")
    print(f"描述: {config.get('description')}")

    # 检查参数配置
    parameters = config.get('parameters', {})
    print(f"\n参数配置:")

    date_anchor_params = []
    for param_name, param_def in parameters.items():
        is_anchor = param_def.get('is_date_anchor', False)
        print(f"  - {param_name}:")
        print(f"    类型: {param_def.get('type')}")
        print(f"    描述: {param_def.get('description')}")
        print(f"    is_date_anchor: {is_anchor}")

        if is_anchor:
            date_anchor_params.append(param_name)

    # 检查分页配置
    pagination = config.get('pagination', {})
    print(f"\n分页配置:")
    print(f"  - 启用: {pagination.get('enabled')}")
    print(f"  - 模式: {pagination.get('mode')}")
    print(f"  - 窗口大小: {pagination.get('window_size_days')} 天")

    # 验证结果
    print("\n" + "="*60)
    print("验证结果:")
    print("="*60)

    if date_anchor_params:
        print(f"✓ 找到日期锚定参数: {', '.join(date_anchor_params)}")
    else:
        print("✗ 未找到日期锚定参数")

    if pagination.get('mode') == 'stock_loop':
        print(f"✓ 接口使用 stock_loop 分页模式")
    else:
        print(f"⚠ 接口使用其他分页模式: {pagination.get('mode')}")

    if date_anchor_params and pagination.get('mode') == 'stock_loop':
        print("\n✓ 配置验证通过！is_date_anchor 参数已正确配置")
        return True
    else:
        print("\n⚠ 配置可能存在问题")
        return False


if __name__ == '__main__':
    success = test_disclosure_date_config()
    sys.exit(0 if success else 1)
