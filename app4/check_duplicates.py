#!/usr/bin/env python3
"""检查parquet文件中的重复数据 - 使用app4的polars"""
import sys
import os

# 添加app4路径到系统路径
app4_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, app4_dir)

import polars as pl

file_path = '/home/quan/testdata/aspipe_v4/data/stock_hsgt/stock_hsgt_20260129_20260203_1770089172106_067e8500.parquet'

if not os.path.exists(file_path):
    print(f"文件不存在: {file_path}")
    sys.exit(1)

print(f"文件路径: {file_path}")
print(f"文件大小: {os.path.getsize(file_path)} bytes")

# 读取数据
df = pl.read_parquet(file_path)

print(f"\n总记录数: {len(df)}")
print(f"列名: {df.columns}")

# 检查重复
total_rows = len(df)
unique_rows = len(df.unique())
duplicates_count = total_rows - unique_rows
print(f"完全重复的行数: {duplicates_count}")

# 检查关键字段重复
key_duplicates = total_rows - len(df.unique(subset=['ts_code', 'trade_date', 'type']))
print(f"关键字段(ts_code, trade_date, type)重复的行数: {key_duplicates}")

# 按type统计
print(f"\n按type分组统计:")
type_stats = df.groupby('type').agg(pl.len().alias('count'))
print(type_stats)

# 数据预览
print(f"\n数据预览 (前15行):")
print(df.head(15))

# 检查(ts_code, trade_date)组合重复
combo_df = df.groupby(['ts_code', 'trade_date']).agg(pl.len().alias('count'))
multi_combo_df = combo_df.filter(pl.col('count') > 1)
if len(multi_combo_df) > 0:
    print(f"\n警告: {len(multi_combo_df)}个(ts_code, trade_date)组合重复:")
    print(multi_combo_df.head(10))
else:
    print(f"\n✓ 没有重复的(ts_code, trade_date)组合")

# 详细检查每个type的数据
print(f"\n各type的详细统计:")
for t in df['type'].unique().to_list():
    type_df = df.filter(pl.col('type') == t)
    print(f"\nType: {t}")
    print(f"  记录数: {len(type_df)}")
    if len(type_df) > 0:
        print(f"  日期范围: {type_df['trade_date'].min()} - {type_df['trade_date'].max()}")
        type_key_dup = len(type_df) - len(type_df.unique(subset=['ts_code', 'trade_date']))
        print(f"  该type内重复数: {type_key_dup}")

# 总结
print(f"\n总结:")
print(f"  总记录数: {total_rows}")
print(f"  完全重复: {duplicates_count}")
print(f"  关键字段重复: {key_duplicates}")
print(f"  组合重复: {len(multi_combo_df)}")

if duplicates_count == 0 and key_duplicates == 0 and len(multi_combo_df) == 0:
    print("\n✓ 数据无重复!")
else:
    print("\n✗ 发现重复数据!")