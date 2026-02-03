#!/usr/bin/env python3
"""详细分析重复数据"""
import sys
import os

# 添加app4路径到系统路径
app4_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, app4_dir)

import polars as pl

file_path = '/home/quan/testdata/aspipe_v4/data/stock_hsgt/stock_hsgt_20260129_20260203_1770089172106_067e8500.parquet'

# 读取数据
df = pl.read_parquet(file_path)

print(f"总记录数: {len(df)}")

# 检查(ts_code, trade_date)组合重复
combo_df = df.group_by(['ts_code', 'trade_date']).agg(
    pl.len().alias('count'),
    pl.col('type').alias('types')
).filter(pl.col('count') > 1)

print(f"\n有 {len(combo_df)} 个(ts_code, trade_date)组合出现了多次")
print(f"\n这些组合的重复分布:")
print(combo_df.group_by('count').agg(pl.len().alias('combos')))

# 展示一些重复的例子
print(f"\n重复组合示例 (前20个):")
for i in range(min(20, len(combo_df))):
    row = combo_df.row(i, named=True)
    print(f"  {i+1}. ts_code={row['ts_code']}, trade_date={row['trade_date']}, 出现次数={row['count']}")

# 查看具体的重复记录
print(f"\n具体重复记录示例 (取前5个重复组合):")
for i in range(min(5, len(combo_df))):
    row = combo_df.row(i, named=True)
    ts_code = row['ts_code']
    trade_date = row['trade_date']

    print(f"\n组合 {i+1}: ts_code={ts_code}, trade_date={trade_date}")
    duplicate_records = df.filter(
        (pl.col('ts_code') == ts_code) &
        (pl.col('trade_date') == trade_date)
    )
    print(duplicate_records.select(['ts_code', 'trade_date', 'type', 'name', 'type_name']))

# 统计哪些type组合最常重复
print(f"\n按type组合统计重复:")
type_combo = df.group_by(['ts_code', 'trade_date']).agg(
    pl.col('type').alias('types')
).filter(pl.len().over(['ts_code', 'trade_date']) > 1)

# 统计每个type组合的出现次数
type_pairs = {}
for types_str in type_combo['types'].to_list():
    types = sorted(types_str)  # types是一个列表
    pair = tuple(types)
    type_pairs[pair] = type_pairs.get(pair, 0) + 1

print("\n重复的type组合统计:")
for pair, count in sorted(type_pairs.items(), key=lambda x: x[1], reverse=True):
    print(f"  {' + '.join(pair)}: {count}次")

# 检查是否所有重复都是type不同但其他字段相同
print(f"\n分析重复记录的模式:")
sample_combos = combo_df.head(3)
for i in range(len(sample_combos)):
    row = sample_combos.row(i, named=True)
    ts_code = row['ts_code']
    trade_date = row['trade_date']

    print(f"\n样本 {i+1}: ts_code={ts_code}, trade_date={trade_date}")
    records = df.filter(
        (pl.col('ts_code') == ts_code) &
        (pl.col('trade_date') == trade_date)
    )

    # 检查除了type之外，其他字段是否相同
    for j in range(len(records)):
        print(f"  记录{j+1}: type={records[j]['type']}, name={records[j]['name']}, type_name={records[j]['type_name']}")