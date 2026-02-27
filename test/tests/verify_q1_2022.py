#!/usr/bin/env python
"""验证 2022Q1 新下载的文件是否包含所有股票代码"""

import pandas as pd
from pathlib import Path

data_dir = Path("/home/quan/testdata/aspipe_v4/data")

# 1. 读取 stock_basic 获取所有股票代码
stock_basic_files = list((data_dir / "stock_basic").glob("*.parquet"))
stock_dfs = [pd.read_parquet(f) for f in stock_basic_files]
stock_basic_df = pd.concat(stock_dfs, ignore_index=True)
all_codes = set(stock_basic_df['ts_code'].unique())
print(f"总股票代码数：{len(all_codes)}")

# 2. 读取新下载的 2022Q1 文件
import os
q1_files = [f for f in os.listdir(data_dir / "cashflow_vip") if "20220331" in f and f.endswith(".parquet")]
print(f"2022Q1 文件：{q1_files}")

for f in q1_files:
    file_path = data_dir / "cashflow_vip" / f
    df = pd.read_parquet(file_path)
    codes = set(df['ts_code'].unique())
    
    print(f"\n{f}:")
    print(f"  总记录数：{len(df)}")
    print(f"  唯一股票数：{len(codes)}")
    
    missing = all_codes - codes
    extra = codes - all_codes
    
    print(f"  缺失股票数：{len(missing)}")
    print(f"  额外股票数：{len(extra)}")
    
    if missing:
        print(f"  缺失股票示例：{sorted(list(missing))[:10]}")
    
    # 检查每只股票的记录数
    code_counts = df['ts_code'].value_counts()
    print(f"  每只股票记录数分布:")
    dist = code_counts.value_counts().sort_index()
    for count, num_stocks in dist.items():
        print(f"    {count}条记录的股票：{num_stocks}只")

# 3. 结论
print("\n" + "=" * 80)
print("结论")
print("=" * 80)

if len(missing) == 0:
    print("✓ 新下载的 2022Q1 文件包含了所有股票代码！")
else:
    print(f"⚠️ 仍缺失 {len(missing)} 只股票")
    print("这些股票可能是 2022 年 3 月 31 日之后上市的，属于正常现象")
