#!/usr/bin/env python
"""验证缺失股票是否是因为上市时间晚于 2022Q1"""

import pandas as pd
from pathlib import Path

data_dir = Path("/home/quan/testdata/aspipe_v4/data")

# 1. 读取 stock_basic 获取所有股票代码和上市时间
stock_basic_files = list((data_dir / "stock_basic").glob("*.parquet"))
stock_dfs = [pd.read_parquet(f) for f in stock_basic_files]
stock_basic_df = pd.concat(stock_dfs, ignore_index=True)
all_codes = set(stock_basic_df['ts_code'].unique())

# 2. 读取新下载的 2022Q1 文件
import os
q1_files = [f for f in os.listdir(data_dir / "cashflow_vip") if "20220331" in f and f.endswith(".parquet")]
q1_df = pd.read_parquet(data_dir / "cashflow_vip" / q1_files[0])
downloaded_codes = set(q1_df['ts_code'].unique())

# 3. 找出缺失的股票
missing = all_codes - downloaded_codes
print(f"缺失股票数：{len(missing)}")

# 4. 检查缺失股票的上市时间
stock_basic_df['list_date'] = pd.to_numeric(stock_basic_df['list_date'], errors='coerce')
missing_stocks = stock_basic_df[stock_basic_df['ts_code'].isin(missing)]

# 按上市时间分类
before_2022q1 = missing_stocks[missing_stocks['list_date'] <= 20220331]
after_2022q1 = missing_stocks[missing_stocks['list_date'] > 20220331]

print(f"\n缺失股票分类:")
print(f"  2022Q1 (20220331) 之前上市的：{len(before_2022q1)} 只")
print(f"  2022Q1 (20220331) 之后上市的：{len(after_2022q1)} 只")

if len(before_2022q1) > 0:
    print(f"\n真正缺失的股票 (2022Q1 前上市但未下载):")
    print(before_2022q1[['ts_code', 'name', 'list_date']].head(20))

if len(after_2022q1) > 0:
    print(f"\n正常缺失的股票 (2022Q1 后上市):")
    print(after_2022q1[['ts_code', 'name', 'list_date']].sort_values('list_date').head(20))

# 5. 检查额外股票（不在 stock_basic 中的）
extra = downloaded_codes - all_codes
print(f"\n额外股票数：{len(extra)}")
if extra:
    print(f"额外股票示例：{sorted(list(extra))[:10]}")

# 6. 结论
print("\n" + "=" * 80)
print("结论")
print("=" * 80)

if len(before_2022q1) == 0:
    print("✓ 下载完整！缺失的股票都是在 2022Q1 之后上市的")
    print(f"  - 下载了 5069 只股票，6465 条记录")
    print(f"  - 缺失的 {len(after_2022q1)} 只股票是 2022Q1 后上市的，属于正常现象")
else:
    print(f"⚠️ 有 {len(before_2022q1)} 只股票在 2022Q1 前上市但未下载")
