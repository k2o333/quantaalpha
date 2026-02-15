#!/usr/bin/env python3

import os
import pandas as pd
from pathlib import Path

DATA_DIR = "/home/quan/testdata/aspipe_v4/data"
OUTPUT_DIR = "/home/quan/testdata/aspipe_v4/p/interface4/output"

INTERFACES = [
    "cyq_chips",
    "moneyflow_dc",
    "stk_factor_pro",
    "income_vip",
    "balancesheet_vip",
    "cashflow_vip",
    "fina_indicator_vip",
    "fina_audit",
    "fina_mainbz_vip",
    "forecast_vip",
    "top10_floatholders",
    "disclosure_date",
    "top10_holders",
    "dividend",
    "pledge_stat",
    "stk_rewards",
    "pledge_detail"
]

def get_date_columns(df):
    date_columns = []
    for col in df.columns:
        if 'date' in col.lower() or 'time' in col.lower():
            date_columns.append(col)
    return date_columns

def get_date_range_from_parquet(parquet_file):
    try:
        df = pd.read_parquet(parquet_file)
        if df.empty:
            return None, None, 0
        
        date_columns = get_date_columns(df)
        date_range = None
        date_col = None
        
        for col in date_columns:
            try:
                df[col] = pd.to_datetime(df[col], errors='coerce')
                if df[col].notna().any():
                    date_range = (df[col].min(), df[col].max())
                    date_col = col
                    break
            except:
                continue
        
        if date_range is None:
            return None, None, len(df)
        
        return date_range[0], date_range[1], len(df)
    except Exception as e:
        print(f"Error reading {parquet_file}: {e}")
        return None, None, 0

def analyze_interface(interface_name):
    interface_dir = os.path.join(DATA_DIR, interface_name)
    
    if not os.path.exists(interface_dir):
        return None
    
    parquet_files = list(Path(interface_dir).glob("*.parquet"))
    
    if not parquet_files:
        return None
    
    results = []
    for parquet_file in sorted(parquet_files):
        min_date, max_date, count = get_date_range_from_parquet(parquet_file)
        results.append({
            'file': parquet_file.name,
            'min_date': min_date,
            'max_date': max_date,
            'count': count
        })
    
    return results

def main():
    print("=" * 100)
    print("Parquet文件日期范围分析报告")
    print("=" * 100)
    print()
    
    for interface in INTERFACES:
        print(f"接口: {interface}")
        print("-" * 100)
        
        results = analyze_interface(interface)
        
        if results is None:
            print("  状态: 下载失败（无数据目录）")
        elif not results:
            print("  状态: 下载失败（无parquet文件）")
        else:
            print(f"  状态: 下载成功")
            print(f"  Parquet文件数量: {len(results)}")
            print()
            
            for i, result in enumerate(results, 1):
                print(f"  文件 {i}: {result['file']}")
                if result['min_date'] and result['max_date']:
                    print(f"    日期范围: {result['min_date'].strftime('%Y-%m-%d')} ~ {result['max_date'].strftime('%Y-%m-%d')}")
                else:
                    print(f"    日期范围: 无法确定")
                print(f"    记录数: {result['count']}")
                print()
        
        print()

if __name__ == "__main__":
    main()