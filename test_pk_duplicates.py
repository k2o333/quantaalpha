#!/usr/bin/env python3
"""
测试脚本：检查接口下载的数据根据主键分组后是否存在重复，
以及重复的记录是否每个字段都相同。
"""

import subprocess
import sys
import polars as pl
import glob
import os
from collections import defaultdict

# 添加项目路径
sys.path.insert(0, '/home/quan/testdata/aspipe_v4')

from app4.core.config_loader import ConfigLoader


def download_data(interface_name: str, ts_code: str = "000002.SZ"):
    """下载指定接口的数据"""
    print(f"\n{'='*60}")
    print(f"正在下载接口: {interface_name}, 股票: {ts_code}")
    print(f"{'='*60}")

    cmd = [
        "python", "app4/main.py",
        "--interface", interface_name,
        "--ts_code", ts_code
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, cwd="/home/quan/testdata/aspipe_v4")

    # 检查是否有错误
    if result.returncode != 0:
        print(f"下载失败: {result.stderr}")
        return None

    print(f"下载完成")
    return True


def find_latest_parquet(interface_name: str) -> str:
    """找到最新的 parquet 文件"""
    data_dir = f"/home/quan/testdata/aspipe_v4/data/{interface_name}"
    if not os.path.exists(data_dir):
        return None

    parquet_files = glob.glob(f"{data_dir}/*.parquet")
    if not parquet_files:
        return None

    # 按修改时间排序，取最新的
    latest_file = max(parquet_files, key=os.path.getmtime)
    return latest_file


def analyze_duplicates(interface_name: str):
    """分析数据中的重复情况"""
    print(f"\n{'='*60}")
    print(f"分析接口: {interface_name}")
    print(f"{'='*60}")

    # 加载接口配置
    config_loader = ConfigLoader("/home/quan/testdata/aspipe_v4/app4/config")
    interface_config = config_loader.get_interface_config(interface_name)

    primary_keys = interface_config.get('output', {}).get('primary_key', [])
    print(f"主键字段: {primary_keys}")

    # 找到并读取 parquet 文件
    parquet_file = find_latest_parquet(interface_name)
    if not parquet_file:
        print(f"错误: 找不到 {interface_name} 的数据文件")
        return

    print(f"数据文件: {parquet_file}")

    # 读取数据
    df = pl.read_parquet(parquet_file)
    print(f"总记录数: {len(df)}")
    print(f"数据字段: {df.columns}")

    # 检查主键字段是否都存在
    missing_keys = [k for k in primary_keys if k not in df.columns]
    if missing_keys:
        print(f"错误: 主键字段不存在于数据中: {missing_keys}")
        return

    # 根据主键分组，检查重复
    pk_groups = defaultdict(list)

    for row in df.to_dicts():
        pk_values = tuple(row.get(k) for k in primary_keys)
        pk_groups[pk_values].append(row)

    # 统计重复情况
    total_groups = len(pk_groups)
    duplicate_groups = 0
    full_duplicate_groups = 0
    partial_duplicate_groups = 0

    print(f"\n{'='*60}")
    print("重复分析结果")
    print(f"{'='*60}")

    for pk, records in pk_groups.items():
        if len(records) > 1:
            duplicate_groups += 1
            print(f"\n主键 {pk} 有 {len(records)} 条记录:")

            # 检查所有字段是否都相同
            all_fields_same = True
            field_differences = []

            # 获取所有字段（排除内部字段）
            all_fields = [f for f in df.columns if not f.startswith('_')]

            for field in all_fields:
                values = [r.get(field) for r in records]
                # 检查该字段的所有值是否相同
                if len(set(str(v) for v in values)) > 1:
                    all_fields_same = False
                    field_differences.append({
                        'field': field,
                        'values': values
                    })

            if all_fields_same:
                full_duplicate_groups += 1
                print(f"  -> 完全重复: 所有字段值都相同")
            else:
                partial_duplicate_groups += 1
                print(f"  -> 部分重复: 以下字段值不同:")
                for diff in field_differences[:5]:  # 只显示前5个不同字段
                    print(f"     - {diff['field']}: {diff['values']}")
                if len(field_differences) > 5:
                    print(f"     ... 还有 {len(field_differences) - 5} 个字段不同")

    print(f"\n{'='*60}")
    print("统计摘要")
    print(f"{'='*60}")
    print(f"总记录数: {len(df)}")
    print(f"主键分组数: {total_groups}")
    print(f"重复主键组数: {duplicate_groups}")
    print(f"  - 完全重复组数: {full_duplicate_groups}")
    print(f"  - 部分重复组数: {partial_duplicate_groups}")

    if duplicate_groups > 0:
        print(f"\n警告: 发现 {duplicate_groups} 个主键重复组！")
        if partial_duplicate_groups > 0:
            print(f"其中 {partial_duplicate_groups} 组是部分重复（字段值不同）")
        if full_duplicate_groups > 0:
            print(f"其中 {full_duplicate_groups} 组是完全重复（所有字段相同）")
    else:
        print(f"\n通过: 没有发现主键重复")

    return {
        'total_records': len(df),
        'total_groups': total_groups,
        'duplicate_groups': duplicate_groups,
        'full_duplicates': full_duplicate_groups,
        'partial_duplicates': partial_duplicate_groups
    }


def main():
    interfaces = ['top10_holders', 'top10_floatholders']
    ts_code = "000002.SZ"

    results = {}

    for interface in interfaces:
        # 下载数据
        success = download_data(interface, ts_code)
        if success:
            # 分析重复
            result = analyze_duplicates(interface)
            results[interface] = result
        else:
            print(f"跳过 {interface} 的分析（下载失败）")

    # 最终汇总
    print(f"\n{'='*60}")
    print("最终汇总")
    print(f"{'='*60}")

    for interface, result in results.items():
        if result:
            print(f"\n{interface}:")
            print(f"  总记录: {result['total_records']}")
            print(f"  重复组: {result['duplicate_groups']}")
            print(f"    - 完全重复: {result['full_duplicates']}")
            print(f"    - 部分重复: {result['partial_duplicates']}")


if __name__ == "__main__":
    main()
