#!/usr/bin/env python3
"""合并 schemas 和 interfaces 配置文件

将 app4/config/schemas/ 中的 fields 定义合并到 app4/config/interfaces/ 对应文件中
"""

import yaml
import os
import shutil
from pathlib import Path
from datetime import datetime

def backup_directories():
    """备份现有配置目录"""
    base_dir = Path("app4/config")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # 备份 schemas 目录
    if (base_dir / "schemas").exists():
        backup_schemas = base_dir / f"schemas.backup_{timestamp}"
        shutil.copytree(base_dir / "schemas", backup_schemas)
        print(f"✓ schemas 目录已备份到: {backup_schemas}")

    # 备份 interfaces 目录
    if (base_dir / "interfaces").exists():
        backup_interfaces = base_dir / f"interfaces.backup_{timestamp}"
        shutil.copytree(base_dir / "interfaces", backup_interfaces)
        print(f"✓ interfaces 目录已备份到: {backup_interfaces}")

    return timestamp

def merge_single_file(schema_file: Path, interface_file: Path):
    """合并单个配置文件"""
    print(f"\n处理文件: {schema_file.name}")

    if not schema_file.exists():
        print(f"  ✗ schemas 文件不存在: {schema_file}")
        return False

    if not interface_file.exists():
        print(f"  ✗ interfaces 文件不存在: {interface_file}")
        return False

    # 读取两个文件
    with open(schema_file, 'r', encoding='utf-8') as f:
        schema_config = yaml.safe_load(f)

    with open(interface_file, 'r', encoding='utf-8') as f:
        interface_config = yaml.safe_load(f)

    # 检查是否有 fields 定义
    if 'fields' not in schema_config:
        print(f"  ✗ schemas 文件中没有 fields 定义")
        return False

    # 检查 interfaces 文件是否已有 fields 定义
    if 'fields' in interface_config:
        print(f"  ⚠ interfaces 文件中已存在 fields 定义，将被覆盖")

    # 合并：将 fields 添加到 interface_config
    interface_config['fields'] = schema_config['fields']
    print(f"  ✓ 已合并 {len(schema_config['fields'])} 个字段定义")

    # 备份原 interfaces 文件
    backup_file = interface_file.with_suffix('.yaml.backup')
    if backup_file.exists():
        # 如果备份已存在，删除旧的
        backup_file.unlink()
    shutil.copy2(interface_file, backup_file)
    print(f"  ✓ 原文件已备份到: {backup_file.name}")

    # 写入合并后的文件
    with open(interface_file, 'w', encoding='utf-8') as f:
        yaml.dump(interface_config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)

    print(f"  ✓ 合并完成")
    return True

def merge_configs():
    """执行合并操作"""
    print("=" * 60)
    print("Schema 和 Interfaces 配置合并工具")
    print("=" * 60)

    # 获取项目根目录
    project_root = Path(__file__).parent.parent.parent
    os.chdir(project_root)

    print(f"\n工作目录: {os.getcwd()}")

    # 检查目录是否存在
    interfaces_dir = Path("app4/config/interfaces")
    schemas_dir = Path("app4/config/schemas")

    if not interfaces_dir.exists():
        print(f"✗ 错误: interfaces 目录不存在: {interfaces_dir}")
        return False

    if not schemas_dir.exists():
        print(f"✗ 错误: schemas 目录不存在: {schemas_dir}")
        return False

    # 备份配置
    print("\n步骤 1: 备份现有配置...")
    timestamp = backup_directories()

    # 需要合并的文件列表
    merge_files = [
        "balancesheet_vip.yaml",
        "cashflow_vip.yaml",
        "income_vip.yaml"
    ]

    print(f"\n步骤 2: 合并配置文件...")
    success_count = 0

    for filename in merge_files:
        schema_file = schemas_dir / filename
        interface_file = interfaces_dir / filename

        if merge_single_file(schema_file, interface_file):
            success_count += 1

    print("\n" + "=" * 60)
    print(f"合并完成: {success_count}/{len(merge_files)} 个文件成功")
    print("=" * 60)

    # 显示后续步骤
    print("\n后续步骤:")
    print("1. 检查合并后的配置文件:")
    for filename in merge_files:
        print(f"   - app4/config/interfaces/{filename}")
    print("\n2. 修改 app4/core/schema_manager.py 的 load_schema() 方法")
    print("\n3. 运行测试验证:")
    print("   cd app4")
    print("   python main.py --interface income_vip --start_date 20240101 --end_date 20240131")
    print("\n4. 测试通过后，删除 schemas 目录:")
    print("   rm -rf app4/config/schemas")

    return success_count == len(merge_files)

def verify_merge():
    """验证合并结果"""
    print("\n验证合并结果...")

    interfaces_dir = Path("app4/config/interfaces")
    merge_files = [
        "balancesheet_vip.yaml",
        "cashflow_vip.yaml",
        "income_vip.yaml"
    ]

    all_valid = True
    for filename in merge_files:
        file_path = interfaces_dir / filename
        with open(file_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        has_fields = 'fields' in config
        has_derived_fields = 'derived_fields' in config

        status = "✓" if has_fields else "✗"
        print(f"  {status} {filename}")
        print(f"     fields: {'是' if has_fields else '否'} ({len(config.get('fields', {}))} 个字段)")
        print(f"     derived_fields: {'是' if has_derived_fields else '否'} ({len(config.get('derived_fields', {}))} 个字段)")

        if not has_fields:
            all_valid = False

    return all_valid

if __name__ == "__main__":
    import sys

    # 执行合并
    if merge_configs():
        # 验证结果
        if verify_merge():
            print("\n✓ 所有验证通过！")
            sys.exit(0)
        else:
            print("\n✗ 验证失败，请检查配置文件")
            sys.exit(1)
    else:
        print("\n✗ 合并失败")
        sys.exit(1)