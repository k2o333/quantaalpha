#!/usr/bin/env python3
"""检查parquet文件中的重复数据"""
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import pandas as pd
    import pyarrow.parquet as pq

    # 读取parquet文件
    file_path = '/home/quan/testdata/aspipe_v4/app4/data/stock_hsgt/stock_hsgt_20260129_20260203_1770089172106_067e8500.parquet'

    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        sys.exit(1)

    df = pd.read_parquet(file_path)

    print(f'总记录数: {len(df)}')
    print(f'列名: {df.columns.tolist()}')
    print(f'\n数据类型:')
    print(df.dtypes)
    print(f'\n数据预览 (前10行):')
    print(df.head(10))

    # 检查完全重复的行
    duplicates = df.duplicated()
    print(f'\n完全重复的行数: {duplicates.sum()}')

    # 检查关键字段(ts_code, trade_date, type)的重复
    key_duplicates = df.duplicated(subset=['ts_code', 'trade_date', 'type'])
    print(f'关键字段(ts_code, trade_date, type)重复的行数: {key_duplicates.sum()}')

    # 如果有重复，显示重复的行
    if duplicates.sum() > 0:
        print(f'\n完全重复的行 (前20行):')
        print(df[duplicates].head(20))

    if key_duplicates.sum() > 0:
        print(f'\n关键字段重复的行 (前20行):')
        print(df[key_duplicates].head(20))

    # 按type分组统计
    print(f'\n按type分组统计:')
    print(df.groupby('type').size())

    # 检查是否有相同的(ts_code, trade_date)组合但type不同
    combo_check = df.groupby(['ts_code', 'trade_date']).size()
    multi_type_combos = combo_check[combo_check > 1]
    if len(multi_type_combos) > 0:
        print(f'\n警告: 有 {len(multi_type_combos)} 个(ts_code, trade_date)组合出现了多次:')
        print(multi_type_combos.head(20))
    else:
        print(f'\n✓ 没有重复的(ts_code, trade_date)组合')

    # 总结
    print(f'\n总结:')
    print(f'  - 总记录数: {len(df)}')
    print(f'  - 完全重复行数: {duplicates.sum()}')
    print(f'  - 关键字段重复行数: {key_duplicates.sum()}')
    print(f'  - (ts_code, trade_date)组合重复数: {len(multi_type_combos)}')

    if duplicates.sum() == 0 and key_duplicates.sum() == 0 and len(multi_type_combos) == 0:
        print(f'\n✓ 数据无重复!')
    else:
        print(f'\n✗ 发现重复数据!')

except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保已安装pandas和pyarrow: pip install pandas pyarrow")
    sys.exit(1)
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)