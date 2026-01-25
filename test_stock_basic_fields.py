#!/usr/bin/env python3
"""测试 stock_basic 接口返回的字段"""
import sys
import os
sys.path.insert(0, '/home/quan/testdata/aspipe_v4/app4')

from core.config_loader import ConfigLoader
from core.downloader import GenericDownloader
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def test_stock_basic_fields():
    """测试 stock_basic 接口返回的所有字段"""

    # 初始化配置加载器
    config_loader = ConfigLoader(config_dir='/home/quan/testdata/aspipe_v4/app4/config')

    # 初始化下载器
    downloader = GenericDownloader(
        config_loader=config_loader,
        storage_manager=None,
        force_download=True
    )

    # 获取 stock_basic 接口配置
    interface_config = config_loader.get_interface_config('stock_basic')

    print("=" * 80)
    print("stock_basic 接口配置:")
    print("=" * 80)
    print(f"API名称: {interface_config.get('api_name')}")
    print(f"描述: {interface_config.get('description')}")
    print(f"分页模式: {interface_config.get('pagination', {}).get('mode')}")
    print()

    # 下载 stock_basic 数据
    print("=" * 80)
    print("正在下载 stock_basic 数据...")
    print("=" * 80)

    params = {'list_status': 'L'}  # 只获取上市股票
    data = downloader.download('stock_basic', params)

    if not data:
        print("❌ 下载失败，没有返回数据")
        return

    print(f"✅ 成功下载 {len(data)} 条记录")
    print()

    # 分析返回的字段
    print("=" * 80)
    print("API 实际返回的字段:")
    print("=" * 80)

    if data:
        first_record = data[0]
        returned_fields = list(first_record.keys())

        print(f"总共返回 {len(returned_fields)} 个字段:")
        for i, field in enumerate(returned_fields, 1):
            value = first_record.get(field)
            value_str = str(value) if value is not None else "NULL"
            print(f"  {i:2d}. {field:20s} = {value_str}")

        print()

        # 与 TuShare 文档中的字段对比
        print("=" * 80)
        print("与 TuShare 文档对比:")
        print("=" * 80)

        # TuShare 文档中列出的所有字段
        documented_fields = [
            'ts_code', 'symbol', 'name', 'area', 'industry', 'fullname', 'enname',
            'cnspell', 'market', 'exchange', 'curr_type', 'list_status', 'list_date',
            'delist_date', 'is_hs', 'act_name', 'act_ent_type'
        ]

        print(f"文档中列出的字段数: {len(documented_fields)}")
        print(f"API实际返回的字段数: {len(returned_fields)}")
        print()

        # 检查哪些文档字段没有返回
        missing_fields = set(documented_fields) - set(returned_fields)
        if missing_fields:
            print(f"⚠️  文档中的字段但API未返回 ({len(missing_fields)}个):")
            for field in sorted(missing_fields):
                print(f"  - {field}")
        else:
            print("✅ 所有文档中的字段都已返回")

        print()

        # 检查是否有额外的字段
        extra_fields = set(returned_fields) - set(documented_fields)
        if extra_fields:
            print(f"ℹ️  API返回但文档未列出的字段 ({len(extra_fields)}个):")
            for field in sorted(extra_fields):
                print(f"  - {field}")
        else:
            print("✅ 没有额外的字段")

        print()

        # 检查派生字段
        derived_fields_config = interface_config.get('derived_fields', {})
        if derived_fields_config:
            print("=" * 80)
            print("派生字段配置:")
            print("=" * 80)
            for field_name, field_config in derived_fields_config.items():
                print(f"  - {field_name}: {field_config.get('description')}")
                print(f"    源字段: {field_config.get('source')}")
                print(f"    类型: {field_config.get('type')}")
            print()

            # 检查派生字段是否已添加
            derived_fields_present = [f for f in returned_fields if f in derived_fields_config]
            if derived_fields_present:
                print(f"✅ 派生字段已添加 ({len(derived_fields_present)}个):")
                for field in derived_fields_present:
                    print(f"  - {field}")
            else:
                print("⚠️  派生字段未添加（可能需要通过 DataProcessor 处理）")

        print()
        print("=" * 80)
        print("结论:")
        print("=" * 80)

        if missing_fields:
            print(f"❌ 当前配置没有让所有输出参数都返回")
            print(f"   缺少 {len(missing_fields)} 个字段: {', '.join(sorted(missing_fields))}")
        else:
            print(f"✅ 当前配置能够让所有输出参数都返回")
            print(f"   API 返回了所有 {len(returned_fields)} 个字段")

if __name__ == '__main__':
    test_stock_basic_fields()