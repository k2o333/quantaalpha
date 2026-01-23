"""
根据接口库存CSV更新接口配置
"""

import yaml
import csv
from pathlib import Path

def update_interface_config():
    """根据CSV更新接口配置"""
    # 读取接口库存CSV
    csv_path = Path("p/2026-1-20/interface_inventory.csv")
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        interfaces_data = list(reader)

    interfaces_dir = Path("app4/config/interfaces")

    # 更新每个接口的配置
    for interface_data in interfaces_data:
        yaml_file = interfaces_dir / interface_data['file_name']
        if not yaml_file.exists():
            print(f"⚠️  文件不存在: {yaml_file}")
            continue

        with open(yaml_file, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        # 更新分页配置
        pagination = config.get('pagination', {})
        if pagination.get('enabled', False) and pagination.get('mode') in ['date_range', 'stock_loop']:
            if interface_data['window_size_days'] != 'not configured':
                window_size = int(interface_data['window_size_days'])
                if pagination.get('window_size_days') != window_size:
                    pagination['window_size_days'] = window_size
                    print(f"Updated {interface_data['api_name']}: window_size_days = {window_size}")
                    config['pagination'] = pagination

        # 写回文件
        with open(yaml_file, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

def main():
    update_interface_config()
    print("接口配置更新完成")

if __name__ == "__main__":
    main()