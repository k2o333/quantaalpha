#!/usr/bin/env python3
"""
使用 Polars 懒加载将 parquet 数据转换为 QuantaAlpha 所需的格式
内存限制: 20GB

输出:
1. daily_pv.h5 - 用于因子挖掘 (6个字段: $open, $close, $high, $low, $volume, $return)
2. qlib_data/ - Qlib 格式目录结构

使用方法:
    cd /home/quan/testdata/aspipe_v4/third_party/scripts/dataconvert
    /root/miniforge3/envs/mining/bin/python convert_to_qlib_polars.py
"""

import os
import sys
import gc
import psutil
from pathlib import Path
from glob import glob
from datetime import datetime

import polars as pl
import pandas as pd
import numpy as np

# ==================== 配置 ====================
PARQUET_DATA_DIR = Path("/home/quan/testdata/aspipe_v4/data/stk_factor_pro")
OUTPUT_DIR = Path("/home/quan/testdata/aspipe_v4/third_party/data")
QLIB_DATA_DIR = OUTPUT_DIR / "qlib_data"

# 内存限制 (20GB)
MEMORY_LIMIT_GB = 20
MEMORY_LIMIT_BYTES = MEMORY_LIMIT_GB * 1024 * 1024 * 1024

# 批处理配置 - 减少批次大小
BATCH_SIZE = 100  # 每批处理的文件数
MAX_STOCKS = 100  # 最大股票数量

# 确保输出目录存在
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
QLIB_DATA_DIR.mkdir(parents=True, exist_ok=True)


def check_memory():
    """检查当前内存使用"""
    process = psutil.Process()
    mem_info = process.memory_info()
    mem_gb = mem_info.rss / (1024 * 1024 * 1024)
    return mem_gb


def log_memory(label=""):
    """记录内存使用情况"""
    mem_gb = check_memory()
    print(f"[内存] {label}: {mem_gb:.2f} GB")
    return mem_gb


def read_parquet_files_pandas(files_batch):
    """
    使用 pandas 读取一批 parquet 文件 (更稳定)
    
    Args:
        files_batch: parquet 文件路径列表
    
    Returns:
        pandas DataFrame
    """
    if not files_batch:
        return None
    
    dfs = []
    for f in files_batch:
        try:
            df = pd.read_parquet(f)
            dfs.append(df)
        except Exception as e:
            print(f"  跳过文件 {f}: {e}")
    
    if not dfs:
        return None
    
    # 合并
    combined_pd = pd.concat(dfs, ignore_index=True)
    return combined_pd


def process_data():
    """
    分批处理所有 parquet 文件
    """
    print("=" * 60)
    print("使用 Polars 转换数据")
    print("=" * 60)
    
    log_memory("初始")
    
    # 获取所有 parquet 文件
    parquet_files = sorted(glob(str(PARQUET_DATA_DIR / "*.parquet")))
    print(f"\n找到 {len(parquet_files)} 个 parquet 文件")
    
    if not parquet_files:
        print("错误: 未找到 parquet 文件!")
        sys.exit(1)
    
    # 分批处理
    all_results = []
    total_files = len(parquet_files)
    
    for batch_start in range(0, total_files, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total_files)
        batch_files = parquet_files[batch_start:batch_end]
        
        print(f"\n处理批次 {batch_start//BATCH_SIZE + 1}: 文件 {batch_start} - {batch_end}")
        log_memory(f"批次开始前")
        
        # 使用 pandas 读取 (更稳定)
        df_batch_pd = read_parquet_files_pandas(batch_files)
        if df_batch_pd is None:
            continue
        
        # 使用 pandas 进行列选择和转换
        df_selected_pd = pd.DataFrame()
        df_selected_pd['instrument'] = df_batch_pd['ts_code']
        df_selected_pd['datetime'] = pd.to_datetime(df_batch_pd['trade_date'], format='%Y%m%d')
        df_selected_pd['$open'] = df_batch_pd.get('open_qfq', df_batch_pd.get('open'))
        df_selected_pd['$close'] = df_batch_pd.get('close_qfq', df_batch_pd.get('close'))
        df_selected_pd['$high'] = df_batch_pd.get('high_qfq', df_batch_pd.get('high'))
        df_selected_pd['$low'] = df_batch_pd.get('low_qfq', df_batch_pd.get('low'))
        df_selected_pd['$volume'] = df_batch_pd.get('vol', df_batch_pd.get('volume', 0))
        
        # 过滤无效数据
        df_filtered_pd = df_selected_pd.dropna(subset=['$open', '$close', '$high', '$low'])
        
        # 转换为 polars
        df_filtered = pl.from_pandas(df_filtered_pd)
        
        if len(df_filtered) > 0:
            all_results.append(df_filtered)
            print(f"  本批次数据: {len(df_filtered)} 行")
        
        # 删除临时变量释放内存
        del df_batch_pd, df_selected_pd, df_filtered_pd, df_filtered
        gc.collect()
        
        log_memory(f"批次结束后")
        
        # 检查内存使用
        if check_memory() > MEMORY_LIMIT_GB * 0.7:
            print(f"警告: 内存使用超过 {MEMORY_LIMIT_GB * 0.7:.1f}GB，触发垃圾回收")
            gc.collect()
            log_memory("垃圾回收后")
    
    # 合并所有结果
    print("\n合并所有批次...")
    if not all_results:
        print("错误: 没有成功读取任何数据")
        sys.exit(1)
    
    # 使用 polars 合并
    df_combined = pl.concat(all_results, how="vertical_relaxed")
    print(f"合并完成: {len(df_combined)} 行")
    log_memory("合并后")
    
    return df_combined


def calculate_returns(df):
    """
    计算收益率
    """
    print("\n计算收益率...")
    
    # 按股票分组计算收益率
    df_with_return = df.with_columns(
        pl.col("$close").pct_change().over("instrument").fill_null(0).alias("$return")
    )
    
    # 按日期和股票排序
    df_sorted = df_with_return.sort(["datetime", "instrument"])
    
    print(f"计算完成: {len(df_sorted)} 行")
    return df_sorted


def limit_stocks_and_convert(df, max_stocks=MAX_STOCKS):
    """
    限制股票数量并转换为 pandas
    """
    print(f"\n限制股票数量为 {max_stocks}...")
    
    # 获取唯一的股票代码
    unique_instruments = df.select("instrument").unique().to_series().to_list()
    print(f"原始股票数: {len(unique_instruments)}")
    
    if len(unique_instruments) > max_stocks:
        selected = unique_instruments[:max_stocks]
        df = df.filter(pl.col("instrument").is_in(selected))
        print(f"限制后股票数: {max_stocks}")
    
    # 转换为 pandas
    print("转换为 pandas DataFrame...")
    df_pandas = df.to_pandas()
    
    # 设置 MultiIndex
    df_pandas = df_pandas.set_index(["datetime", "instrument"]).sort_index()
    
    # 检查数据时间范围
    date_range = df_pandas.index.get_level_values(0)
    days = (date_range.max() - date_range.min()).days
    print(f"数据时间跨度: {days} 天")
    print(f"股票数: {df_pandas.index.get_level_values(1).nunique()}")
    
    log_memory("转换后")
    
    return df_pandas


def save_h5_files(df):
    """保存 HDF5 文件"""
    print("\n保存 HDF5 文件...")
    
    # 保存完整数据
    h5_path = OUTPUT_DIR / "daily_pv.h5"
    df.to_hdf(h5_path, key='data', mode='w')
    print(f"✓ daily_pv.h5: {h5_path} ({df.shape})")
    
    # 创建 debug 版本 (20 只股票)
    debug_instruments = df.index.get_level_values(1).unique()[:20]
    df_debug = df[df.index.get_level_values(1).isin(debug_instruments)]
    debug_path = OUTPUT_DIR / "daily_pv_debug.h5"
    df_debug.to_hdf(debug_path, key='data', mode='w')
    print(f"✓ daily_pv_debug.h5: {debug_path} ({df_debug.shape})")
    
    return h5_path, debug_path


def create_qlib_structure(df):
    """创建 Qlib 目录结构"""
    print("\n创建 Qlib 目录结构...")
    
    # 创建目录
    (QLIB_DATA_DIR / "calendars").mkdir(parents=True, exist_ok=True)
    (QLIB_DATA_DIR / "instruments").mkdir(parents=True, exist_ok=True)
    (QLIB_DATA_DIR / "features").mkdir(parents=True, exist_ok=True)
    
    df_reset = df.reset_index()
    
    # 1. 交易日历
    trading_days = sorted(df_reset['datetime'].dt.strftime('%Y-%m-%d').unique())
    with open(QLIB_DATA_DIR / "calendars" / "day.txt", 'w') as f:
        f.write('\n'.join(trading_days) + '\n')
    print(f"✓ 交易日历: {len(trading_days)} 天")
    
    # 2. 股票列表
    instruments = sorted(df_reset['instrument'].unique())
    start_date = df_reset['datetime'].min().strftime('%Y-%m-%d')
    end_date = df_reset['datetime'].max().strftime('%Y-%m-%d')
    
    with open(QLIB_DATA_DIR / "instruments" / "all.txt", 'w') as f:
        for inst in instruments:
            f.write(f"{inst}\t{start_date}\t{end_date}\n")
    print(f"✓ 股票列表: {len(instruments)} 只")
    
    # 3. 特征数据
    print("保存特征数据...")
    for inst in instruments:
        inst_data = df_reset[df_reset['instrument'] == inst].copy()
        inst_data = inst_data.sort_values('datetime')
        
        inst_dir = QLIB_DATA_DIR / "features" / inst.replace('.', '_')
        inst_dir.mkdir(parents=True, exist_ok=True)
        inst_data.to_csv(inst_dir / "data.csv", index=False)
    
    print(f"✓ 特征数据已保存")
    return QLIB_DATA_DIR


def update_env_file():
    """更新 .env 文件"""
    env_path = Path("/home/quan/testdata/aspipe_v4/third_party/quantaalpha/.env")
    
    if not env_path.exists():
        print(f"\n警告: 未找到 .env 文件")
        return
    
    print("\n更新 .env 文件...")
    
    with open(env_path, 'r') as f:
        content = f.read()
    
    # 更新路径
    content = content.replace(
        'QLIB_DATA_DIR=/home/quan/testdata/aspipe_v4/data',
        f'QLIB_DATA_DIR={QLIB_DATA_DIR}'
    )
    content = content.replace(
        'QLIB_PROVIDER_URI=/home/quan/testdata/aspipe_v4/data',
        f'QLIB_PROVIDER_URI={QLIB_DATA_DIR}'
    )
    
    with open(env_path, 'w') as f:
        f.write(content)
    
    print("✓ .env 文件已更新")


def main():
    print("=" * 60)
    print("QuantaAlpha 数据转换 (Polars 版)")
    print(f"内存限制: {MEMORY_LIMIT_GB} GB")
    print("=" * 60)
    
    # 1. 处理数据
    df = process_data()
    
    # 2. 计算收益率
    df_with_return = calculate_returns(df)
    
    # 3. 限制股票数量并转换为 pandas
    df_pandas = limit_stocks_and_convert(df_with_return)
    
    # 4. 保存 HDF5
    save_h5_files(df_pandas)
    
    # 5. 创建 Qlib 结构
    create_qlib_structure(df_pandas)
    
    # 6. 更新配置
    update_env_file()
    
    log_memory("最终")
    
    print("\n" + "=" * 60)
    print("转换完成!")
    print("=" * 60)
    print(f"\n输出文件:")
    print(f"  HDF5 数据: {OUTPUT_DIR}")
    print(f"  Qlib 数据: {QLIB_DATA_DIR}")


if __name__ == "__main__":
    main()
