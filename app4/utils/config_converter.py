"""配置转换工具 - 将旧格式YAML配置转换为新格式（原始数据+衍生字段）"""

import os
import yaml
from typing import Dict, Any


def migrate_yaml_config(config_path: str) -> Dict[str, Any]:
    """迁移YAML配置到新格式"""
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # 1. 保留基本配置
    basic_keys = ['name', 'api_name', 'description', 'enabled', 'permissions', 'request', 'parameters', 'pagination', 'duplicate_detection']
    new_config = {k: v for k, v in config.items() if k in basic_keys or k not in ['output']}

    # 2. 提取output配置（移除columns，保留primary_key和sort_by）
    if 'output' in config:
        output_config = config['output']
        new_config['output'] = {
            'primary_key': output_config.get('primary_key', []),
            'sort_by': output_config.get('sort_by', [])
        }

    # 3. 根据接口类型生成derived_fields
    interface_name = config.get('name', 'unknown')
    derived_fields = generate_derived_fields(interface_name, config.get('output', {}))
    if derived_fields:
        new_config['derived_fields'] = derived_fields

    return new_config


def generate_derived_fields(interface_name: str, old_output: Dict) -> Dict:
    """根据接口类型生成转化字段配置"""
    derived_fields = {}

    # 从旧的columns配置中提取日期字段信息
    old_columns = old_output.get('columns', {})

    # 日期字段转化 - 检查旧columns配置中定义的日期字段
    for field_name, field_config in old_columns.items():
        if field_config.get('type') == 'date':
            date_format = field_config.get('format', '%Y%m%d')
            derived_fields[f"{field_name}_dt"] = {
                'source': field_name,
                'type': 'date',
                'format': date_format,
                'description': f"日期类型的{field_name}"
            }

    # 特殊字段转化 - 为特定接口添加布尔类型字段
    if interface_name == 'trade_cal':
        if 'is_open' in old_columns:
            derived_fields['is_open_bool'] = {
                'source': 'is_open',
                'type': 'boolean',
                'description': '布尔类型的is_open，Polars查询性能最优'
            }

    return derived_fields


def convert_single_file(config_path: str, backup: bool = True):
    """转换单个配置文件"""
    if backup:
        # 创建备份
        backup_path = config_path + ".backup"
        with open(config_path, 'r', encoding='utf-8') as src:
            with open(backup_path, 'w', encoding='utf-8') as dst:
                dst.write(src.read())

    # 读取并转换配置
    new_config = migrate_yaml_config(config_path)

    # 写入新格式
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(new_config, f, default_flow_style=False, allow_unicode=True, indent=2)

    print(f"✅ 已转换配置文件: {config_path}")


def convert_all_configs(configs_dir: str = "app4/config/interfaces"):
    """批量转换所有配置文件"""
    import glob

    # 获取所有yaml配置文件（排除backup目录）
    yaml_files = glob.glob(os.path.join(configs_dir, "*.yaml"))
    yaml_files = [f for f in yaml_files if "backup" not in f]

    print(f"开始转换 {len(yaml_files)} 个配置文件...")

    for config_path in yaml_files:
        try:
            convert_single_file(config_path, backup=True)
        except Exception as e:
            print(f"❌ 转换失败 {config_path}: {str(e)}")
            continue

    print(f"✅ 完成转换 {len(yaml_files)} 个配置文件")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python config_converter.py <config_file>          # 转换单个文件")
        print("  python config_converter.py --migrate-all          # 转换所有配置文件")
        sys.exit(1)

    if sys.argv[1] == "--migrate-all":
        convert_all_configs()
    else:
        config_file = sys.argv[1]
        if os.path.exists(config_file):
            convert_single_file(config_file)
        else:
            print(f"配置文件不存在: {config_file}")