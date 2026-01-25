#!/usr/bin/env python3
"""验证合并后数据类型正确性"""

import polars as pl
import os
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, '/home/quan/testdata/aspipe_v4')

def check_data_types():
    """检查数据类型是否正确"""
    print("验证数据类型正确性...")

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
            print(f"  字段类型:")

            for field, dtype in df.schema.items():
                print(f"    {field}: {dtype}")

                # 检查常见的字段类型是否正确
                if 'date' in field.lower() or 'dt' in field.lower():
                    # 日期相关字段应该是 Date 或 String 类型
                    if dtype not in [pl.Date, pl.String, pl.Datetime]:
                        print(f"      ⚠ {field} 应该是日期类型，但实际为 {dtype}")
                    else:
                        print(f"      ✓ {field} 日期类型正确: {dtype}")
                elif 'amount' in field.lower() or 'value' in field.lower() or 'revenue' in field.lower() or 'income' in field.lower():
                    # 金额相关字段应该是数值类型
                    if dtype not in [pl.Float32, pl.Float64, pl.Int32, pl.Int64]:
                        print(f"      ⚠ {field} 应该是数值类型，但实际为 {dtype}")
                    else:
                        print(f"      ✓ {field} 数值类型正确: {dtype}")
                elif 'type' in field.lower() or 'status' in field.lower():
                    # 类型相关字段通常是 String 或 Int
                    if dtype not in [pl.String, pl.Int32, pl.Int64]:
                        print(f"      ⚠ {field} 应该是字符串或整数类型，但实际为 {dtype}")
                    else:
                        print(f"      ✓ {field} 类型正确: {dtype}")

            # 验证特定字段是否存在
            if interface == "income_vip":
                required_fields = ["ts_code", "ann_date", "f_ann_date", "end_date", "report_type", "comp_type", "total_revenue"]
                for field in required_fields:
                    if field in df.columns:
                        print(f"      ✓ {interface} 包含必需字段: {field}")
                    else:
                        print(f"      ⚠ {interface} 缺少必需字段: {field}")
            elif interface == "balancesheet_vip":
                required_fields = ["ts_code", "ann_date", "end_date", "report_type", "comp_type"]
                for field in required_fields:
                    if field in df.columns:
                        print(f"      ✓ {interface} 包含必需字段: {field}")
                    else:
                        print(f"      ⚠ {interface} 缺少必需字段: {field}")
            elif interface == "cashflow_vip":
                required_fields = ["ts_code", "ann_date", "end_date", "report_type", "comp_type"]
                for field in required_fields:
                    if field in df.columns:
                        print(f"      ✓ {interface} 包含必需字段: {field}")
                    else:
                        print(f"      ⚠ {interface} 缺少必需字段: {field}")

        except Exception as e:
            print(f"✗ 读取 {interface} 数据文件时出错: {e}")
            continue

    print("\n数据类型验证完成！")

def check_schema_loading():
    """检查 schema 是否正确加载"""
    print("\n检查 schema 加载...")

    from app4.core.schema_manager import SchemaManager

    # 检查 VIP 接口的 schema 加载
    vip_interfaces = ["income_vip", "balancesheet_vip", "cashflow_vip"]

    for interface in vip_interfaces:
        schema = SchemaManager.load_schema(interface)
        if schema:
            print(f"✓ {interface} schema 加载成功，包含 {len(schema)} 个字段定义")

            # 检查一些常见类型定义
            for field, field_type in schema.items():
                if 'date' in field.lower():
                    if field_type in ['date', 'datetime', 'string']:
                        print(f"  ✓ {field} 类型定义正确: {field_type}")
                    else:
                        print(f"  ⚠ {field} 类型定义可能不正确: {field_type}")
                elif 'amount' in field.lower() or 'revenue' in field.lower():
                    if field_type in ['Float64', 'Float32', 'Int64', 'Int32']:
                        print(f"  ✓ {field} 数值类型定义正确: {field_type}")
                    else:
                        print(f"  ⚠ {field} 数值类型定义可能不正确: {field_type}")
        else:
            print(f"⚠ {interface} 未找到 schema 定义")

    print("Schema 加载检查完成！")

def main():
    """主函数"""
    print("=" * 60)
    print("验证数据类型正确性")
    print("=" * 60)

    # 检查数据类型
    check_data_types()

    # 检查 schema 加载
    check_schema_loading()

    print("\n" + "=" * 60)
    print("数据类型验证完成！")
    print("=" * 60)

if __name__ == "__main__":
    main()