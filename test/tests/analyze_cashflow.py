#!/usr/bin/env python
"""详细分析 cashflow_vip 下载情况"""

import pandas as pd
from pathlib import Path

data_dir = Path("/home/quan/testdata/aspipe_v4/data")

print("=" * 80)
print("cashflow_vip 下载分析")
print("=" * 80)

# 1. 读取 stock_basic 获取所有股票代码
stock_basic_files = list((data_dir / "stock_basic").glob("*.parquet"))
stock_dfs = [pd.read_parquet(f) for f in stock_basic_files]
stock_basic_df = pd.concat(stock_dfs, ignore_index=True)
all_codes = set(stock_basic_df['ts_code'].unique())
print(f"\n总股票代码数：{len(all_codes)}")

# 2. 读取本次下载的 4 个文件
target_files = [
    "cashflow_vip/cashflow_vip_20220331_20220331_1771920793576_1a2dbdbc.parquet",
    "cashflow_vip/cashflow_vip_20220630_20220630_1771920803513_f37e2411.parquet",
    "cashflow_vip/cashflow_vip_20220930_20220930_1771920809098_2a0b9a0d.parquet",
    "cashflow_vip/cashflow_vip_20221231_20221231_1771920821071_da97a1c9.parquet",
]

print("\n" + "=" * 80)
print("详细分析每个文件")
print("=" * 80)

for f in target_files:
    file_path = data_dir / f
    if file_path.exists():
        df = pd.read_parquet(file_path)
        codes = df['ts_code']
        code_counts = codes.value_counts()
        
        print(f"\n{file_path.name}:")
        print(f"  总记录数：{len(df)}")
        print(f"  唯一股票数：{len(code_counts)}")
        
        # 统计每只股票的记录数分布
        print(f"  每只股票记录数分布:")
        dist = code_counts.value_counts().sort_index()
        for count, num_stocks in dist.items():
            print(f"    {count}条记录的股票：{num_stocks}只")
        
        # 检查是否有股票超过 1 条记录
        multi_record_stocks = code_counts[code_counts > 1]
        if len(multi_record_stocks) > 0:
            print(f"  ⚠️  有 {len(multi_record_stocks)} 只股票有多条记录")
            print(f"     最多的股票：{multi_record_stocks.head(3).to_dict()}")

# 3. 分析缺失的股票
print("\n" + "=" * 80)
print("缺失股票分析")
print("=" * 80)

all_downloaded_codes = set()
for f in target_files:
    file_path = data_dir / f
    if file_path.exists():
        df = pd.read_parquet(file_path)
        all_downloaded_codes.update(df['ts_code'].unique())

missing = all_codes - all_downloaded_codes
print(f"\n缺失股票数：{len(missing)}")

# 检查缺失股票的上市时间
stock_basic_df['list_date'] = pd.to_numeric(stock_basic_df['list_date'], errors='coerce')
missing_stocks = stock_basic_df[stock_basic_df['ts_code'].isin(missing)]

if len(missing_stocks) > 0:
    print(f"\n缺失股票的上市时间分布:")
    print(missing_stocks['list_date'].describe())
    
    # 按上市时间排序
    print(f"\n缺失股票 (按上市时间排序):")
    print(missing_stocks[['ts_code', 'name', 'list_date']].sort_values('list_date').head(20))

# 4. 结论
print("\n" + "=" * 80)
print("结论")
print("=" * 80)

# 检查 6400 是否是上限
for f in target_files:
    file_path = data_dir / f
    if file_path.exists():
        df = pd.read_parquet(file_path)
        if len(df) == 6400:
            print(f"\n{file_path.name}:")
            print(f"  记录数={len(df)}，达到 6400 上限")
            unique_codes = len(df['ts_code'].unique())
            print(f"  但唯一股票数只有 {unique_codes}，说明有重复记录")
            print(f"  平均每只股票记录数：{len(df)/unique_codes:.2f}")

print("\n" + "=" * 80)
print("最终判断:")
print("=" * 80)
print("6400 是 API 返回的记录数上限，不是股票数量上限")
print("每个期间应该下载约 5000+ 只股票，但由于:")
print("1. 部分股票有多条记录 (同一季度多次公告)")
print("2. API 限制每次最多返回 6400 条记录")
print("3. 导致部分股票的数据被截断")
print("\n解决方案：需要实现 offset 分页或 limit 参数控制")
