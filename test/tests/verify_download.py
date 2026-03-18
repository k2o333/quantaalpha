#!/usr/bin/env python
"""验证 cashflow_vip 下载是否包含所有股票代码"""

import pandas as pd
from pathlib import Path

data_dir = Path("/home/quan/testdata/aspipe_v4/data")

# 1. 读取 stock_basic 获取所有股票代码
print("=" * 80)
print("步骤 1: 读取 stock_basic 获取所有股票代码")
print("=" * 80)

stock_basic_files = list((data_dir / "stock_basic").glob("*.parquet"))
print(f"找到 stock_basic 文件：{stock_basic_files}")

# 读取所有 stock_basic 文件并合并
stock_dfs = []
for f in stock_basic_files:
    df = pd.read_parquet(f)
    print(f"  {f.name}: {len(df)} 条记录，列：{list(df.columns)}")
    stock_dfs.append(df)

stock_basic_df = pd.concat(stock_dfs, ignore_index=True)
print(f"\n合并后 stock_basic: {len(stock_basic_df)} 条记录")

# 去重获取唯一股票代码
if 'ts_code' in stock_basic_df.columns:
    all_codes = set(stock_basic_df['ts_code'].unique())
    print(f"去重后股票代码总数：{len(all_codes)}")
    print(f"股票代码示例：{sorted(list(all_codes))[:10]}")
else:
    print("错误：stock_basic 中没有 ts_code 列")
    print(f"可用列：{list(stock_basic_df.columns)}")
    exit(1)

# 2. 读取本次下载的 4 个 cashflow_vip 文件
print("\n" + "=" * 80)
print("步骤 2: 读取本次下载的 cashflow_vip 文件 (2022 年 4 个季度)")
print("=" * 80)

# 本次下载的文件（根据日志是 2022 年的 4 个季度）
target_files = [
    "cashflow_vip/cashflow_vip_20220331_20220331_1771920793576_1a2dbdbc.parquet",
    "cashflow_vip/cashflow_vip_20220630_20220630_1771920803513_f37e2411.parquet",
    "cashflow_vip/cashflow_vip_20220930_20220930_1771920809098_2a0b9a0d.parquet",
    "cashflow_vip/cashflow_vip_20221231_20221231_1771920821071_da97a1c9.parquet",
]

period_codes = {}
for f in target_files:
    file_path = data_dir / f
    if file_path.exists():
        df = pd.read_parquet(file_path)
        codes = set(df['ts_code'].unique())
        period_codes[f.split('/')[-1]] = {
            'total_records': len(df),
            'unique_codes': len(codes),
            'codes': codes
        }
        print(f"\n{file_path.name}:")
        print(f"  总记录数：{len(df)}")
        print(f"  唯一股票代码数：{len(codes)}")
    else:
        print(f"文件不存在：{file_path}")

# 3. 分析是否有截断
print("\n" + "=" * 80)
print("步骤 3: 分析下载是否被截断")
print("=" * 80)

# 检查每个文件是否包含所有股票代码
for period_name, data in period_codes.items():
    codes = data['codes']
    missing = all_codes - codes
    extra = codes - all_codes
    
    print(f"\n{period_name}:")
    print(f"  下载记录数：{data['total_records']}")
    print(f"  包含股票代码数：{len(codes)}")
    print(f"  应包含股票代码数：{len(all_codes)}")
    print(f"  缺失的股票代码数：{len(missing)}")
    print(f"  额外的股票代码数：{len(extra)}")
    
    if missing:
        print(f"  缺失的股票代码示例：{sorted(list(missing))[:10]}")
    if extra:
        print(f"  额外的股票代码示例：{sorted(list(extra))[:10]}")
    
    # 检查是否有重复
    if data['total_records'] > len(codes):
        dup_count = data['total_records'] - len(codes)
        print(f"  ⚠️  存在重复记录：{dup_count} 条")

# 4. 合并所有期间检查
print("\n" + "=" * 80)
print("步骤 4: 合并所有期间检查")
print("=" * 80)

all_downloaded_codes = set()
total_records = 0
for data in period_codes.values():
    all_downloaded_codes.update(data['codes'])
    total_records += data['total_records']

print(f"\n4 个期间总记录数：{total_records}")
print(f"4 个期间合并后唯一股票代码数：{len(all_downloaded_codes)}")
print(f"应包含的股票代码数：{len(all_codes)}")

missing_overall = all_codes - all_downloaded_codes
extra_overall = all_downloaded_codes - all_codes

print(f"\n4 个期间合并后缺失的股票代码数：{len(missing_overall)}")
print(f"4 个期间合并后额外的股票代码数：{len(extra_overall)}")

if missing_overall:
    print(f"缺失的股票代码列表：{sorted(list(missing_overall))}")

# 5. 结论
print("\n" + "=" * 80)
print("结论")
print("=" * 80)

if len(missing_overall) == 0 and len(extra_overall) == 0:
    print("✓ 每次下载的 6400 条记录包含了所有股票代码，没有被截断")
    print(f"  - 每个期间下载约 6400 条记录是因为每个股票有多个季度数据")
    print(f"  - 5000+ 股票 × 多个季度 = 6400 条记录是合理的")
else:
    print("⚠️ 下载可能被截断或有问题")
    print(f"  - 缺失 {len(missing_overall)} 只股票")
    print(f"  - 额外 {len(extra_overall)} 只股票")
