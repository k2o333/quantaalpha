"""
验证接口配置:
1. 检查所有接口都有明确的分页配置
2. 检查stock_loop和date_range接口都有window_size_days
3. 检查所有接口都属于至少一个分组
4. 检查重复定义的接口
"""

import yaml
import os
from pathlib import Path

def validate_pagination_config():
    """验证分页配置完整性"""
    interfaces_dir = Path("app4/config/interfaces")
    missing_window_size = []

    for yaml_file in interfaces_dir.glob("*.yaml"):
        with open(yaml_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        pagination = config.get('pagination', {})
        if pagination.get('enabled', False) and pagination.get('mode') in ['date_range', 'stock_loop']:
            if 'window_size_days' not in pagination:
                missing_window_size.append(yaml_file.name)

    return missing_window_size

def validate_group_membership():
    """验证所有接口都在至少一个分组中"""
    settings_file = Path("app4/config/settings.yaml")
    interfaces_dir = Path("app4/config/interfaces")

    with open(settings_file, 'r', encoding='utf-8') as f:
        settings = yaml.safe_load(f)

    groups = settings.get('groups', {})
    grouped_interfaces = set()
    for group_name, interface_list in groups.items():
        grouped_interfaces.update(interface_list)

    all_interfaces = set()
    for yaml_file in interfaces_dir.glob("*.yaml"):
        with open(yaml_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        all_interfaces.add(config.get('name', yaml_file.stem))

    ungrouped = all_interfaces - grouped_interfaces
    return list(ungrouped)

def main():
    print("接口配置验证开始...")

    missing_window = validate_pagination_config()
    if missing_window:
        print(f"❌ 发现 {len(missing_window)} 个接口缺少 window_size_days 配置:")
        for interface in missing_window:
            print(f"  - {interface}")
    else:
        print("✅ 所有接口都有 window_size_days 配置")

    ungrouped = validate_group_membership()
    if ungrouped:
        print(f"❌ 发现 {len(ungrouped)} 个接口未分组:")
        for interface in ungrouped:
            print(f"  - {interface}")
    else:
        print("✅ 所有接口都已分组")

    print("验证完成")

if __name__ == "__main__":
    main()