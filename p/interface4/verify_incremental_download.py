#!/usr/bin/env python3

import os
import pandas as pd
from pathlib import Path

DATA_DIR = "/home/quan/testdata/aspipe_v4/data"

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
        
        for col in date_columns:
            try:
                df[col] = pd.to_datetime(df[col], errors='coerce')
                if df[col].notna().any():
                    date_range = (df[col].min(), df[col].max())
                    break
            except:
                continue
        
        if date_range is None:
            return None, None, len(df)
        
        return date_range[0], date_range[1], len(df)
    except Exception as e:
        print(f"Error reading {parquet_file}: {e}")
        return None, None, 0

def analyze_interface_incremental(interface_name):
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
    print("=" * 120)
    print("增量下载验证报告 - 验证第二次下载是否补充了第一次缺失的日期")
    print("=" * 120)
    print()
    print("测试配置:")
    print("  第一次下载范围: 2024-01-01 ~ 2024-06-30")
    print("  第二次下载范围: 2023-01-01 ~ 2024-12-31")
    print("  预期: 第二次下载应该补充 2023-01-01 ~ 2024-01-01 和 2024-06-30 ~ 2024-12-31 的数据")
    print()
    print("=" * 120)
    print()
    
    for interface in INTERFACES:
        print(f"接口: {interface}")
        print("-" * 120)
        
        results = analyze_interface_incremental(interface)
        
        if results is None:
            print("  状态: 下载失败（无数据目录）")
        elif not results:
            print("  状态: 下载失败（无parquet文件）")
        elif len(results) == 1:
            result = results[0]
            print(f"  状态: 只有1个parquet文件（无法验证增量下载）")
            print(f"  文件: {result['file']}")
            if result['min_date'] and result['max_date']:
                print(f"  日期范围: {result['min_date'].strftime('%Y-%m-%d')} ~ {result['max_date'].strftime('%Y-%m-%d')}")
                print(f"  记录数: {result['count']}")
        else:
            print(f"  状态: 有{len(results)}个parquet文件（可以验证增量下载）")
            print()
            
            for i, result in enumerate(results, 1):
                print(f"  文件 {i}: {result['file']}")
                if result['min_date'] and result['max_date']:
                    print(f"    日期范围: {result['min_date'].strftime('%Y-%m-%d')} ~ {result['max_date'].strftime('%Y-%m-%d')}")
                else:
                    print(f"    日期范围: 无法确定")
                print(f"    记录数: {result['count']}")
                print()
            
            if len(results) >= 2:
                overall_min = min(r['min_date'] for r in results if r['min_date'])
                overall_max = max(r['max_date'] for r in results if r['max_date'])
                total_count = sum(r['count'] for r in results)
                
                print(f"  综合日期范围: {overall_min.strftime('%Y-%m-%d')} ~ {overall_max.strftime('%Y-%m-%d')}")
                print(f"  总记录数: {total_count}")
                print()
                
                if overall_min and overall_max:
                    if overall_min <= pd.Timestamp('2024-01-01'):
                        print(f"  ✓ 第二次下载成功补充了 2023-01-01 ~ 2024-01-01 的数据")
                    else:
                        print(f"  ✗ 第二次下载未能补充 2023-01-01 ~ 2024-01-01 的数据")
                    
                    if overall_max >= pd.Timestamp('2024-06-30'):
                        print(f"  ✓ 第二次下载成功补充了 2024-06-30 ~ 2024-12-31 的数据")
                    else:
                        print(f"  ✗ 第二次下载未能补充 2024-06-30 ~ 2024-12-31 的数据")
        
        print()

if __name__ == "__main__":
    main()