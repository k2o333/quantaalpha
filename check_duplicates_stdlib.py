#!/usr/bin/env python3
"""检查parquet文件中的重复数据 - 使用标准库"""
import sys
import os
import json
import subprocess

# 使用parquet-tools或者通过app4来读取
file_path = '/home/quan/testdata/aspipe_v4/data/stock_hsgt/stock_hsgt_20260129_20260203_1770089172106_067e8500.parquet'

if not os.path.exists(file_path):
    print(f"文件不存在: {file_path}")
    sys.exit(1)

print(f"文件路径: {file_path}")
print(f"文件大小: {os.path.getsize(file_path)} bytes")

# 尝试使用parquet-tools
try:
    result = subprocess.run(['parquet-tools', 'show', file_path],
                          capture_output=True, text=True, timeout=10)
    if result.returncode == 0:
        print("\n文件内容 (使用parquet-tools):")
        print(result.stdout[:2000])  # 限制输出长度
    else:
        print("parquet-tools不可用")
except FileNotFoundError:
    print("parquet-tools未安装")
except Exception as e:
    print(f"使用parquet-tools出错: {e}")

# 尝试使用pandas
try:
    result = subprocess.run(['python3', '-c', '''
import sys
import pandas as pd
import pyarrow.parquet as pq

file_path = "/home/quan/testdata/aspipe_v4/data/stock_hsgt/stock_hsgt_20260129_20260203_1770089172106_067e8500.parquet"

# 读取数据
df = pd.read_parquet(file_path)

print(f"总记录数: {len(df)}")
print(f"列名: {df.columns.tolist()}")

# 检查重复
total_rows = len(df)
unique_rows = len(df.drop_duplicates())
duplicates_count = total_rows - unique_rows
print(f"完全重复的行数: {duplicates_count}")

# 检查关键字段重复
key_duplicates = total_rows - len(df.drop_duplicates(subset=["ts_code", "trade_date", "type"]))
print(f"关键字段(ts_code, trade_date, type)重复的行数: {key_duplicates}")

# 按type统计
print(f"\n按type分组统计:")
print(df.groupby("type").size())

# 数据预览
print(f"\n数据预览 (前15行):")
print(df.head(15))

# 检查(ts_code, trade_date)组合重复
combo = df.groupby(["ts_code", "trade_date"]).size()
multi_combo = combo[combo > 1]
if len(multi_combo) > 0:
    print(f"\n警告: {len(multi_combo)}个(ts_code, trade_date)组合重复:")
    print(multi_combo.head(10))
else:
    print(f"\n✓ 没有重复的(ts_code, trade_date)组合")

# 总结
print(f"\n总结:")
print(f"  总记录数: {total_rows}")
print(f"  完全重复: {duplicates_count}")
print(f"  关键字段重复: {key_duplicates}")
print(f"  组合重复: {len(multi_combo)}")

if duplicates_count == 0 and key_duplicates == 0 and len(multi_combo) == 0:
    print("\n✓ 数据无重复!")
else:
    print("\n✗ 发现重复数据!")
'''], capture_output=True, text=True, timeout=30)

    if result.returncode == 0:
        print("\n" + "="*60)
        print("重复数据检查结果:")
        print("="*60)
        print(result.stdout)
        if result.stderr:
            print("错误输出:", result.stderr)
    else:
        print(f"执行失败 (返回码: {result.returncode})")
        print("标准输出:", result.stdout)
        print("错误输出:", result.stderr)

except subprocess.TimeoutExpired:
    print("命令执行超时")
except Exception as e:
    print(f"执行出错: {e}")
