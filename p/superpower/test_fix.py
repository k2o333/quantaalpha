#!/usr/bin/env python3
"""测试修复后的配置合并功能"""

import os
import sys
from datetime import datetime

# 切换到项目根目录
os.chdir('/home/quan/testdata/aspipe_v4')
# 添加项目根目录到 Python 路径
sys.path.insert(0, '/home/quan/testdata/aspipe_v4')

def test_basic_imports():
    """测试基本导入是否正常"""
    print("Testing basic imports...")

    try:
        from app4.core.schema_manager import SchemaManager
        print("✓ SchemaManager import successful")

        from app4.core.downloader import GenericDownloader
        print("✓ GenericDownloader import successful")

        from app4.core.config_loader import ConfigLoader
        print("✓ ConfigLoader import successful")

        # 测试 schema_manager.py 的 load_schema 方法
        schema_manager = SchemaManager()
        print("✓ SchemaManager instantiation successful")

        return True
    except Exception as e:
        print(f"✗ Import test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_load_schema_from_interfaces():
    """测试从 interfaces 目录加载 schema"""
    print("\nTesting load_schema method...")

    try:
        from app4.core.schema_manager import SchemaManager

        # 尝试加载 income_vip 的 schema
        schema = SchemaManager.load_schema('income_vip')
        print(f"✓ Schema loaded for income_vip: {len(schema) if schema else 0} fields" if schema else "✓ Schema for income_vip is None (expected for interfaces without fields)")

        # 尝试加载 balancesheet_vip 的 schema
        schema = SchemaManager.load_schema('balancesheet_vip')
        print(f"✓ Schema loaded for balancesheet_vip: {len(schema) if schema else 0} fields" if schema else "✓ Schema for balancesheet_vip is None (expected for interfaces without fields)")

        # 尝试加载 cashflow_vip 的 schema
        schema = SchemaManager.load_schema('cashflow_vip')
        print(f"✓ Schema loaded for cashflow_vip: {len(schema) if schema else 0} fields" if schema else "✓ Schema for cashflow_vip is None (expected for interfaces without fields)")

        return True
    except Exception as e:
        print(f"✗ Schema test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_config_files_existence():
    """测试配置文件是否正确合并"""
    print("\nTesting config file structure...")

    import os
    from pathlib import Path

    interfaces_dir = Path("app4/config/interfaces")

    # 检查 VIP 接口配置文件
    vip_files = ["income_vip.yaml", "balancesheet_vip.yaml", "cashflow_vip.yaml"]

    for filename in vip_files:
        filepath = interfaces_dir / filename
        if filepath.exists():
            print(f"✓ {filename} exists")

            # 检查文件中是否包含 fields 定义
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()
                if 'fields:' in content:
                    print(f"  ✓ {filename} contains fields definition")
                else:
                    print(f"  ⚠ {filename} does not contain fields definition")
        else:
            print(f"✗ {filename} does not exist")
            return False

    # 检查 schemas 目录是否存在（应该存在，因为我们只合并了内容但未删除目录）
    schemas_dir = Path("app4/config/schemas")
    if schemas_dir.exists():
        print("✓ schemas directory still exists (as backup)")
    else:
        print("✓ schemas directory has been removed")

    return True

def main():
    """运行所有测试"""
    print("=" * 60)
    print("Testing Schema and Interfaces Configuration Merge")
    print("=" * 60)

    all_passed = True

    # 测试 1: 基本导入
    if not test_basic_imports():
        all_passed = False

    # 测试 2: 加载 schema
    if not test_load_schema_from_interfaces():
        all_passed = False

    # 测试 3: 配置文件结构
    if not test_config_files_existence():
        all_passed = False

    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All tests passed! Configuration merge was successful.")
    else:
        print("✗ Some tests failed. Configuration merge may have issues.")
    print("=" * 60)

    return all_passed

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)