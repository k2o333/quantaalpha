#!/usr/bin/env python3
"""检查parquet文件中的重复数据 - 使用pyarrow"""
import sys
import os

try:
    import pyarrow.parquet as pq

    # 读取parquet文件
    file_path = '/home/quan/testdata/aspipe_v4/app4/data/stock_hsgt/stock_hsgt_20260129_20260203_1770089172106_067e8500.parquet'

    if not os.path.exists(file_path):
        print(f"文件不存在: {file_path}")
        sys.exit(1)

    # 读取parquet文件
    table = pq.read_table(file_path)
    print(f'总记录数: {len(table)}')
    print(f'列名: {table.column_names}')

    # 转换为字典列表便于处理
    records = []
    for i in range(len(table)):
        record = {}
        for col in table.column_names:
            record[col] = table.column(col)[i].as_py()
        records.append(record)

    print(f'\n数据预览 (前10行):')
    for i, record in enumerate(records[:10]):
        print(f"  {i+1}: {record}")

    # 检查完全重复的行
    record_tuples = [tuple(sorted(record.items())) for record in records]
    unique_records = set(record_tuples)
    duplicates_count = len(records) - len(unique_records)
    print(f'\n完全重复的行数: {duplicates_count}')

    # 检查关键字段(ts_code, trade_date, type)的重复
    key_tuples = [(r.get('ts_code'), r.get('trade_date'), r.get('type')) for r in records]
    unique_keys = set(key_tuples)
    key_duplicates_count = len(records) - len(unique_keys)
    print(f'关键字段(ts_code, trade_date, type)重复的行数: {key_duplicates_count}')

    # 按type分组统计
    type_counts = {}
    for record in records:
        t = record.get('type', 'unknown')
        type_counts[t] = type_counts.get(t, 0) + 1

    print(f'\n按type分组统计:')
    for t, count in sorted(type_counts.items()):
        print(f"  {t}: {count}")

    # 检查是否有相同的(ts_code, trade_date)组合
    combo_dict = {}
    for record in records:
        key = (record.get('ts_code'), record.get('trade_date'))
        if key not in combo_dict:
            combo_dict[key] = []
        combo_dict[key].append(record.get('type'))

    multi_type_combos = {k: v for k, v in combo_dict.items() if len(v) > 1}
    if len(multi_type_combos) > 0:
        print(f'\n警告: 有 {len(multi_type_combos)} 个(ts_code, trade_date)组合出现了多次:')
        for i, (key, types) in enumerate(list(multi_type_combos.items())[:20]):
            print(f"  {i+1}. ts_code={key[0]}, trade_date={key[1]}, types={types}")
    else:
        print(f'\n✓ 没有重复的(ts_code, trade_date)组合')

    # 详细检查每个type的数据
    print(f'\n各type的详细统计:')
    type_records = {}
    for record in records:
        t = record.get('type')
        if t not in type_records:
            type_records[t] = []
        type_records[t].append(record)

    for t, type_data in sorted(type_records.items()):
        dates = [r.get('trade_date') for r in type_data]
        date_set = set(dates)
        ts_codes = [r.get('ts_code') for r in type_data]

        print(f"\nType: {t}")
        print(f"  记录数: {len(type_data)}")

        # 检查该type内是否有重复
        type_keys = [(r.get('ts_code'), r.get('trade_date')) for r in type_data]
        type_unique_keys = set(type_keys)
        type_duplicates = len(type_data) - len(type_unique_keys)
        print(f"  重复数: {type_duplicates}")

        if dates:
            print(f"  日期范围: {min(dates)} - {max(dates)}")
            print(f"  唯一日期数: {len(date_set)}")

    # 如果有重复，显示重复的行
    if duplicates_count > 0:
        print(f'\n完全重复的行 (前10个):')
        seen = set()
        for i, record in enumerate(records):
            record_tuple = tuple(sorted(record.items()))
            if record_tuple in seen:
                print(f"  重复行 {i+1}: {record}")
                if len([x for x in records[:i+1] if tuple(sorted(x.items())) == record_tuple]) > 10:
                    break
            seen.add(record_tuple)

    if key_duplicates_count > 0:
        print(f'\n关键字段重复的行 (前10个):')
        key_seen = {}
        for i, record in enumerate(records):
            key = (record.get('ts_code'), record.get('trade_date'), record.get('type'))
            if key in key_seen:
                print(f"  重复行 {i+1}: {record}")
                if sum(1 for r in records[:i+1] if (r.get('ts_code'), r.get('trade_date'), r.get('type')) == key) > 10:
                    break
            key_seen[key] = True

    # 总结
    print(f'\n总结:')
    print(f'  - 总记录数: {len(records)}')
    print(f'  - 完全重复行数: {duplicates_count}')
    print(f'  - 关键字段重复行数: {key_duplicates_count}')
    print(f'  - (ts_code, trade_date)组合重复数: {len(multi_type_combos)}')

    if duplicates_count == 0 and key_duplicates_count == 0 and len(multi_type_combos) == 0:
        print(f'\n✓ 数据无重复!')
    else:
        print(f'\n✗ 发现重复数据!')

except ImportError as e:
    print(f"导入错误: {e}")
    print("请确保已安装pyarrow: pip install pyarrow")
    sys.exit(1)
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)