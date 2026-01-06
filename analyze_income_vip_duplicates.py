#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
分析income_vip数据中的重复记录
"""
import pandas as pd

def analyze_duplicates():
    # 读取数据文件
    file_path = '/home/quan/testdata/aspipe_v4/data/income_vip/income_vip_nodate_1767667102177_2e4d3330.parquet'
    df = pd.read_parquet(file_path)
    
    print("=" * 60)
    print("income_vip数据重复分析报告")
    print("=" * 60)
    print(f'数据总行数: {len(df)}')
    print(f'数据列数: {len(df.columns)}')
    print(f'唯一ts_code数量: {df["ts_code"].nunique()}')
    
    # 检查完全重复的行
    duplicated_rows = df.duplicated()
    print(f'完全重复行数量: {duplicated_rows.sum()}')
    
    # 检查基于ts_code的重复
    ts_code_duplicates = df.duplicated(subset=['ts_code'])
    print(f'基于ts_code的重复数量: {ts_code_duplicates.sum()}')
    
    # 分析重复的ts_code
    duplicate_ts_codes = df[df.duplicated(subset=['ts_code'], keep=False)]['ts_code'].unique()
    print(f'重复ts_code数量: {len(duplicate_ts_codes)}')
    
    print("\n重复ts_code的详细情况:")
    print("-" * 40)
    
    total_duplicate_records = 0
    for ts_code in duplicate_ts_codes:
        dup_records = df[df['ts_code'] == ts_code]
        total_duplicate_records += len(dup_records)
        print(f'\n{ts_code}: {len(dup_records)}条记录')
        for idx, row in dup_records.iterrows():
            print(f'  - 公告日期: {row["ann_date"]}, 报告期: {row["end_date"]}, 基本每股收益: {row["basic_eps"]}')
    
    print(f'\n总计重复记录数: {total_duplicate_records}')
    print(f'实际唯一股票数量: {df["ts_code"].nunique()}')
    print(f'数据中包含的市场: {df["ts_code"].str.split(".").str[1].unique()}')
    
    # 统计各市场的股票数量
    market_counts = df['ts_code'].str.split('.').str[1].value_counts()
    print(f'\n各市场股票数量分布:')
    for market, count in market_counts.items():
        print(f'  {market}: {count}只')

if __name__ == "__main__":
    analyze_duplicates()