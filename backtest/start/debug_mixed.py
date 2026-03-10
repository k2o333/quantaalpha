#!/usr/bin/env python3
"""Polars+Pandas混用版Debug脚本 - 记录每次计算结果"""
import sys
sys.path.insert(0, '/home/quan/testdata/aspipe_v4/third_party/vnpy')

import glob
from datetime import datetime
from pathlib import Path
import polars as pl
import pandas as pd
import numpy as np
from tqdm import tqdm


def load_data(data_path: str, start_date: str, end_date: str) -> pl.DataFrame:
    print(f"加载数据从 {start_date} 到 {end_date}...")
    start_dt = datetime.strptime(start_date, "%Y%m%d").date()
    end_dt = datetime.strptime(end_date, "%Y%m%d").date()
    files = glob.glob(f"{data_path}/*.parquet")
    selected_files = []
    for f in files:
        basename = Path(f).stem
        parts = basename.split("_")
        if len(parts) >= 4:
            try:
                file_date = datetime.strptime(parts[3], "%Y%m%d").date()
                if start_dt <= file_date <= end_dt:
                    selected_files.append(f)
            except:
                continue
    print(f"找到 {len(selected_files)} 个数据文件")
    dfs = []
    for f in tqdm(selected_files, desc="读取文件"):
        try:
            df = pl.read_parquet(f)
            cols = ["ts_code", "trade_date", "open", "close", "vol", "trade_date_dt"]
            available_cols = [c for c in cols if c in df.columns]
            dfs.append(df.select(available_cols))
        except:
            pass
    if dfs:
        combined = pl.concat(dfs)
        combined = combined.unique(subset=["ts_code", "trade_date"])
        return combined
    return pl.DataFrame()


def calculate_alpha101_factor_debug(df: pl.DataFrame, debug_dir: str):
    """计算Alpha101因子 (Polars+Pandas混用版) - 带Debug"""
    print("\n=== Polars+Pandas混用版计算过程 ===")
    
    # Step 1: 截面排名
    print("Step 1: 计算截面排名...")
    df = df.with_columns([
        pl.col("open").rank().over("trade_date_dt").alias("open_rank"),
        pl.col("vol").rank().over("trade_date_dt").alias("vol_rank"),
    ])
    
    # 保存Step 1结果
    df.write_csv(f"{debug_dir}/step1_cs_rank.csv")
    print(f"  保存Step 1结果: {debug_dir}/step1_cs_rank.csv")
    
    # 显示部分数据
    sample = df.filter(pl.col("ts_code") == "000001.SZ").sort("trade_date_dt")
    print(f"  示例股票(000001.SZ)的排名:")
    print(sample[["trade_date_dt", "open", "vol", "open_rank", "vol_rank"]].head(10).to_pandas())
    
    # Step 2: 滚动相关系数 (使用Pandas)
    print("\nStep 2: 计算滚动相关系数 (Pandas)...")
    
    def calc_rolling_corr(group_df):
        pdf = group_df.to_pandas()
        pdf = pdf.sort_values("trade_date_dt")
        pdf["alpha3"] = pdf["open_rank"].rolling(window=10).corr(pdf["vol_rank"]) * -1
        return pl.from_pandas(pdf)
    
    result = df.group_by("ts_code", maintain_order=True).map_groups(calc_rolling_corr)
    
    # 保存Step 2结果
    result.write_csv(f"{debug_dir}/step2_rolling_corr.csv")
    print(f"  保存Step 2结果: {debug_dir}/step2_rolling_corr.csv")
    
    # 显示部分数据
    sample = result.filter(pl.col("ts_code") == "000001.SZ").sort("trade_date_dt")
    print(f"  示例股票(000001.SZ)的alpha3:")
    print(sample[["trade_date_dt", "open_rank", "vol_rank", "alpha3"]].head(15).to_pandas())
    
    # 统计alpha3分布
    print(f"\n  Alpha3统计:")
    print(f"    非NaN数量: {result['alpha3'].is_not_nan().sum()}")
    print(f"    NaN数量: {result['alpha3'].is_nan().sum()}")
    print(f"    最小值: {result['alpha3'].min()}")
    print(f"    最大值: {result['alpha3'].max()}")
    print(f"    均值: {result['alpha3'].mean()}")
    
    return result


def main():
    DATA_PATH = "/home/quan/testdata/aspipe_v4/data/stk_factor_pro"
    # 只回测一个月
    START_DATE = "20240101"
    END_DATE = "20240131"
    DEBUG_DIR = "/home/quan/testdata/aspipe_v4/debug_mixed"
    
    import os
    os.makedirs(DEBUG_DIR, exist_ok=True)
    
    df = load_data(DATA_PATH, START_DATE, END_DATE)
    if df.is_empty():
        print("没有加载到数据!")
        return
    
    print(f"\n数据加载完成，共 {len(df)} 条记录")
    print(f"股票数量: {df['ts_code'].n_unique()}")
    print(f"日期范围: {df['trade_date_dt'].min()} 到 {df['trade_date_dt'].max()}")
    
    # 计算因子
    result = calculate_alpha101_factor_debug(df, DEBUG_DIR)
    
    # 保存最终结果
    result.write_csv(f"{DEBUG_DIR}/final_result.csv")
    print(f"\n最终结果已保存到: {DEBUG_DIR}/final_result.csv")


if __name__ == "__main__":
    main()
