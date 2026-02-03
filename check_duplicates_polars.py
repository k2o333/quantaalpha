#!/usr/bin/env python3
"""检查parquet文件中的重复数据 - 使用polars"""
import sys
import os

# 添加app4路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app4'))

try:
    import polars as pl

    # 读取parquet文件
    file_path = '/home/quan/testdata/aspipe_v4/app4/data/stock_hsgt/stock_hsgt_20260129_20260203_1770089172106_067e8500.parquet'

    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        sys.exit(1)

    df = pl.read_parquet(file_path)

    print(f'总记录数: {len(df)}')
    print(f'列名: {df.columns}')
    print(f'\n数据类型:')
    print(df.schema)
    print(f'\n数据预览 (前10行):')
    print(df.head(10))

    # 检查完全重复的行
    total_rows = len(df)
    unique_rows = len(df.unique())
    duplicates_count = total_rows - unique_rows
    print(f'\n完全重复的行数: {duplicates_count}')

    # 检查关键字段(ts_code, trade_date, type)的重复
    key_duplicates_count = total_rows - len(df.unique(subset=['ts_code', 'trade_date', 'type']))
    print(f'关键字段(ts_code, trade_date, type)重复的行数: {key_duplicates_count}')

    # 如果有重复，显示重复的行
    if duplicates_count > 0:
        print(f'\n完全重复的行 (前20行):')
        print(df.filter(df.is_duplicated()).head(20))

    if key_duplicates_count > 0:
        print(f'\n关键字段重复的行 (前20行):')
        print(df.filter(pl.len().over(['ts_code', 'trade_date', 'type']) > 1).head(20))

    # 按type分组统计
    print(f'\n按type分组统计:')
    print(df.groupby('type').agg(pl.len().alias('count')))

    # 检查是否有相同的(ts_code, trade_date)组合但type不同
    combo_check = df.groupby(['ts_code', 'trade_date']).agg(pl.len().alias('count'))
    multi_type_combos = combo_check.filter(pl.col('count') > 1)
    if len(multi_type_combos) > 0:
        print(f'\n警告: 有 {len(multi_type_combos)} 个(ts_code, trade_date)组合出现了多次:')
        print(multi_type_combos.head(20))
    else:
        print(f'\n✓ 没有重复的(ts_code, trade_date)组合')

    # 详细检查每个type的数据
    print(f'\n各type的详细统计:')
    for t in df['type'].unique().to_list():
        type_df = df.filter(pl.col('type') == t)
        print(f"\nType: {t}")
        print(f"  记录数: {len(type_df)}")
        print(f"  日期范围: {type_df['trade_date'].min()} - {type_df['trade_date'].max()}")
        type_duplicates = len(type_df) - len(type_df.unique(subset=['ts_code', 'trade_date']))
        print(f"  重复数: {type_duplicates}")

    # 总结
    print(f'\n总结:')
    print(f'  - 总记录数: {total_rows}')
    print(f'  - 完全重复行数: {duplicates_count}')
    print(f'  - 关键字段重复行数: {key_duplicates_count}')
    print(f'  - (ts_code, trade_date)组合重复数: {len(multi_type_combos)}')

    if duplicates_count == 0 and key_duplicates_count == 0 and len(multi_type_combos) == 0:
        print(f'\n✓ 数据无重复!')
    else:
        print(f'\n✗ 发现重复数据!')

except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保已安装polars: pip install polars")
    sys.exit(1)
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)