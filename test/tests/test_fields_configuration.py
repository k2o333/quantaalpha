#!/usr/bin/env python3
"""测试 fields 参数配置功能"""
import sys
import os
sys.path.insert(0, '/home/quan/testdata/aspipe_v4')

from app4.core.config_loader import ConfigLoader
from app4.core.downloader import GenericDownloader
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

def test_fields_configuration():
    """测试 fields 参数配置功能"""
    print("=" * 80)
    print("开始测试 fields 参数配置功能...")
    print("=" * 80)

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

    print("stock_basic 接口配置中的 fields 设置:")
    fields_config = interface_config.get('fields', [])
    print(f"配置的额外字段: {fields_config}")
    print()

    # 下载 stock_basic 数据
    print("正在下载 stock_basic 数据...")
    params = {'list_status': 'L'}  # 只获取上市股票
    data = downloader.download('stock_basic', params)

    if not data:
        print("❌ 下载失败，没有返回数据")
        return

    print(f"✅ 成功下载 {len(data)} 条记录")
    print()

    # 分析返回的字段
    if data:
        first_record = data[0]
        returned_fields = list(first_record.keys())

        print(f"API 实际返回 {len(returned_fields)} 个字段:")
        for i, field in enumerate(returned_fields, 1):
            value = first_record.get(field)
            value_str = str(value) if value is not None else "NULL"
            print(f"  {i:2d}. {field:20s} = {value_str}")

        print()

        # 检查是否包含了配置中指定的字段
        missing_config_fields = [f for f in fields_config if f not in returned_fields]
        if missing_config_fields:
            print(f"❌ 配置中指定的字段但API未返回 ({len(missing_config_fields)}个):")
            for field in missing_config_fields:
                print(f"  - {field}")
        else:
            print(f"✅ 配置中指定的 {len(fields_config)} 个字段都已返回")

        print()

        # 显示所有返回的字段
        print("所有返回的字段:")
        for field in returned_fields:
            if field in fields_config:
                print(f"  [配置] {field}")
            else:
                print(f"  [默认] {field}")

if __name__ == '__main__':
    test_fields_configuration()