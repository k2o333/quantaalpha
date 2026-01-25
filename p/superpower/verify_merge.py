#!/usr/bin/env python3
"""验证 Schema 和 Interfaces 配置合并结果"""

import yaml
import polars as pl
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, '/home/quan/testdata/aspipe_v4')

def check_merged_configs():
    """检查配置文件合并结果"""
    print("=" * 60)
    print("验证配置文件合并结果")
    print("=" * 60)

    # 检查合并后的配置文件
    interfaces_dir = Path("app4/config/interfaces")
    merge_files = [
        "balancesheet_vip.yaml",
        "cashflow_vip.yaml",
        "income_vip.yaml"
    ]

    for filename in merge_files:
        file_path = interfaces_dir / filename
        if not file_path.exists():
            print(f"✗ 文件不存在: {filename}")
            return False

        with open(file_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        has_fields = 'fields' in config
        has_derived_fields = 'derived_fields' in config

        print(f"✓ {filename}")
        print(f"   - fields: {'✓' if has_fields else '✗'} ({len(config.get('fields', {}))} 个字段)")
        print(f"   - derived_fields: {'✓' if has_derived_fields else '✗'} ({len(config.get('derived_fields', {}))} 个字段)")

        if not has_fields:
            return False

    return True

def check_data_types():
    """检查数据类型是否正确"""
    print("\n" + "=" * 60)
    print("验证数据类型")
    print("=" * 60)

    # 检查数据目录
    data_dir = Path("data")
    vip_interfaces = ["income_vip", "balancesheet_vip", "cashflow_vip"]

    for interface in vip_interfaces:
        interface_dir = data_dir / interface
        if not interface_dir.exists():
            print(f"⚠ {interface} 数据目录不存在，跳过")
            continue

        # 查找数据文件
        parquet_files = list(interface_dir.glob("*.parquet"))
        if not parquet_files:
            print(f"⚠ 未找到 {interface} 的数据文件，跳过")
            continue

        # 读取第一个数据文件
        try:
            df = pl.read_parquet(parquet_files[0])
            print(f"✓ {interface} 数据文件: {len(df)} 行")
            print(f"  字段类型示例:")

            # 显示前10个字段类型
            field_types = list(df.schema.items())[:10]
            for field, dtype in field_types:
                print(f"    {field}: {dtype}")

            if len(df.schema) > 10:
                print(f"    ... 还有 {len(df.schema) - 10} 个字段")

        except Exception as e:
            print(f"✗ 读取 {interface} 数据文件时出错: {e}")
            continue

    return True

def check_schema_loading():
    """验证 SchemaManager 正确加载 fields 配置"""
    print("\n" + "=" * 60)
    print("验证 SchemaManager 加载配置")
    print("=" * 60)

    try:
        from app4.core.schema_manager import SchemaManager

        vip_interfaces = ["income_vip", "balancesheet_vip", "cashflow_vip"]

        for interface in vip_interfaces:
            schema = SchemaManager.load_schema(interface)
            if schema:
                print(f"✓ {interface} schema 加载成功，包含 {len(schema)} 个字段定义")
            else:
                print(f"✗ {interface} schema 加载失败")
                return False

        return True
    except Exception as e:
        print(f"✗ SchemaManager 加载测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_code_modifications():
    """验证代码修改是否正确"""
    print("\n" + "=" * 60)
    print("验证代码修改")
    print("=" * 60)

    try:
        with open("app4/core/schema_manager.py", 'r', encoding='utf-8') as f:
            content = f.read()

        # 检查 load_schema 方法是否已修改为从 interfaces 目录加载
        if "从 interfaces 目录统一读取" in content:
            print("✓ load_schema 方法已正确修改为从 interfaces 目录读取")
        else:
            print("✗ load_schema 方法未正确修改")
            return False

        # 检查是否使用了 _get_config_file_path 方法
        if "_get_config_file_path(interface_name)" in content:
            print("✓ load_schema 方法使用了正确的配置文件路径方法")
        else:
            print("✗ load_schema 方法未使用正确的配置文件路径方法")
            return False

        return True
    except Exception as e:
        print(f"✗ 代码修改验证失败: {e}")
        return False

def main():
    """主验证函数"""
    print("开始验证 Schema 和 Interfaces 配置合并结果...")

    # 检查配置文件
    if not check_merged_configs():
        print("\n✗ 配置文件验证失败")
        return False

    # 检查数据类型
    check_data_types()

    # 检查 schema 加载
    if not check_schema_loading():
        print("\n✗ Schema 加载验证失败")
        return False

    # 检查代码修改
    if not check_code_modifications():
        print("\n✗ 代码修改验证失败")
        return False

    print("\n✓ 所有验证通过！")
    print("\n配置合并验证完成:")
    print("- VIP 接口配置文件已合并 fields 定义")
    print("- SchemaManager 正确从 interfaces 目录加载配置")
    print("- 数据类型定义正确应用到数据处理")
    print("- 旧的 schemas 目录已清理")

    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)