#!/usr/bin/env python3
"""
将 parquet 数据转换为 Qlib 格式，仅包含 CSI 300 成分股
用于因子挖掘和回测

训练集: 2016-2020
验证集: 2021
测试集: 2022-01-01 ~ 2025-12-26

使用方法:
    cd /home/quan/testdata/aspipe_v4/third_party/scripts/dataconvert
    /root/miniforge3/envs/mining/bin/python convert_csi300_to_qlib.py
"""

import os
import sys
import gc
import psutil
from pathlib import Path
from glob import glob
from datetime import datetime
from typing import List, Set, Optional

import polars as pl
import pandas as pd
import numpy as np
import qlib
from qlib.data import D

# ==================== 配置 ====================
PARQUET_DATA_DIR = Path("/home/quan/testdata/aspipe_v4/data/stk_factor_pro")
OUTPUT_DIR = Path("/home/quan/testdata/aspipe_v4/third_party/data")
QLIB_DATA_DIR = OUTPUT_DIR / "qlib_data_csi300"

# 时间范围配置
TRAIN_START = "2016-01-01"
TRAIN_END = "2020-12-31"
VALID_START = "2021-01-01"
VALID_END = "2021-12-31"
TEST_START = "2022-01-01"
TEST_END = "2025-12-26"

# 内存限制 (20GB)
MEMORY_LIMIT_GB = 20

# 批处理配置
BATCH_SIZE = 50  # 每批处理的文件数

# 确保输出目录存在
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
QLIB_DATA_DIR.mkdir(parents=True, exist_ok=True)


def log_memory(label=""):
    """记录内存使用情况"""
    process = psutil.Process()
    mem_gb = process.memory_info().rss / (1024 * 1024 * 1024)
    print(f"[内存] {label}: {mem_gb:.2f} GB")
    return mem_gb


def get_csi300_stocks() -> Set[str]:
    """
    获取 CSI 300 成分股列表
    返回格式: {'000001.SZ', '000002.SZ', ...}
    """
    print("获取 CSI 300 成分股列表...")
    
    # 初始化qlib以获取csi300列表
    existing_qlib = "/home/quan/testdata/aspipe_v4/third_party/data/qlib_data"
    qlib.init(provider_uri=existing_qlib)
    
    instruments = D.instruments(market='csi300')
    csi300_list = D.list_instruments(instruments=instruments, as_list=True)
    
    # 转换为 ts_code 格式 (SZ000001 -> 000001.SZ)
    csi300_stocks = set()
    for code in csi300_list:
        if code.startswith('SZ'):
            csi300_stocks.add(code[2:] + '.SZ')
        elif code.startswith('SH'):
            csi300_stocks.add(code[2:] + '.SH')
        elif code.startswith('BJ'):
            csi300_stocks.add(code[2:] + '.BJ')
    
    print(f"CSI 300 成分股数量: {len(csi300_stocks)}")
    return csi300_stocks


def get_target_dates() -> Set[str]:
    """
    获取目标日期集合 (训练集+验证集+测试集)
    返回格式: {'20160104', '20160105', ...}
    """
    # 生成交易日历
    from pandas.tseries.offsets import BDay
    
    dates = set()
    
    # 训练集 2016-2020
    train_dates = pd.date_range(TRAIN_START, TRAIN_END, freq='B')
    dates.update(train_dates.strftime('%Y%m%d').tolist())
    
    # 验证集 2021
    valid_dates = pd.date_range(VALID_START, VALID_END, freq='B')
    dates.update(valid_dates.strftime('%Y%m%d').tolist())
    
    # 测试集 2022-2025
    test_dates = pd.date_range(TEST_START, TEST_END, freq='B')
    dates.update(test_dates.strftime('%Y%m%d').tolist())
    
    print(f"目标交易日数量: {len(dates)} (从 {min(dates)} 到 {max(dates)})")
    return dates


def process_data(csi300_stocks: Set[str], target_dates: Set[str]):
    """
    分批处理 parquet 文件，仅保留 CSI 300 股票和目标日期
    """
    print("=" * 60)
    print("开始处理 parquet 数据")
    print("=" * 60)
    
    log_memory("初始")
    
    # 获取所有 parquet 文件
    parquet_files = sorted(glob(str(PARQUET_DATA_DIR / "*.parquet")))
    print(f"\n找到 {len(parquet_files)} 个 parquet 文件")
    
    if not parquet_files:
        print("错误: 未找到 parquet 文件!")
        sys.exit(1)
    
    # 筛选目标日期范围内的文件
    target_files = []
    for f in parquet_files:
        basename = os.path.basename(f)
        # 文件名格式: stk_factor_pro_YYYYMMDD_YYYYMMDD_xxx.parquet
        parts = basename.split('_')
        if len(parts) >= 4:
            date_str = parts[3]
            if date_str in target_dates:
                target_files.append(f)
    
    print(f"目标日期范围内的文件数: {len(target_files)}")
    
    # 分批处理
    all_results = []
    total_files = len(target_files)
    
    for batch_start in range(0, total_files, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total_files)
        batch_files = target_files[batch_start:batch_end]
        
        print(f"\n处理批次 {batch_start//BATCH_SIZE + 1}: 文件 {batch_start} - {batch_end}")
        log_memory(f"批次开始前")
        
        # 读取批次文件
        dfs = []
        for f in batch_files:
            try:
                df = pd.read_parquet(f)
                # 只保留 CSI 300 股票
                df = df[df['ts_code'].isin(csi300_stocks)]
                if len(df) > 0:
                    dfs.append(df)
            except Exception as e:
                print(f"  跳过文件 {f}: {e}")
        
        if not dfs:
            continue
        
        # 合并批次数据
        batch_df = pd.concat(dfs, ignore_index=True)
        
        # 选择需要的列
        df_selected = pd.DataFrame()
        df_selected['instrument'] = batch_df['ts_code']
        df_selected['datetime'] = pd.to_datetime(batch_df['trade_date'], format='%Y%m%d')
        df_selected['$open'] = batch_df.get('open_qfq', batch_df.get('open'))
        df_selected['$close'] = batch_df.get('close_qfq', batch_df.get('close'))
        df_selected['$high'] = batch_df.get('high_qfq', batch_df.get('high'))
        df_selected['$low'] = batch_df.get('low_qfq', batch_df.get('low'))
        df_selected['$volume'] = batch_df.get('vol', batch_df.get('volume', 0))
        
        # 过滤无效数据
        df_filtered = df_selected.dropna(subset=['$open', '$close', '$high', '$low'])
        
        if len(df_filtered) > 0:
            # 转换为 polars
            df_pl = pl.from_pandas(df_filtered)
            all_results.append(df_pl)
            print(f"  本批次数据: {len(df_filtered)} 行")
        
        # 删除临时变量释放内存
        del dfs, batch_df, df_selected, df_filtered
        gc.collect()
        
        log_memory(f"批次结束后")
    
    # 合并所有结果
    print("\n合并所有批次...")
    if not all_results:
        print("错误: 没有成功读取任何数据")
        sys.exit(1)
    
    df_combined = pl.concat(all_results, how="vertical_relaxed")
    print(f"合并完成: {len(df_combined)} 行")
    log_memory("合并后")
    
    return df_combined


def calculate_returns(df: pl.DataFrame) -> pl.DataFrame:
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


def convert_to_pandas(df: pl.DataFrame) -> pd.DataFrame:
    """
    转换为 pandas DataFrame 并设置 MultiIndex
    """
    print("\n转换为 pandas DataFrame...")
    
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


def save_h5_files(df: pd.DataFrame):
    """保存 HDF5 文件"""
    print("\n保存 HDF5 文件...")
    
    # 保存完整数据
    h5_path = OUTPUT_DIR / "daily_pv_csi300.h5"
    df.to_hdf(h5_path, key='data', mode='w')
    print(f"✓ daily_pv_csi300.h5: {h5_path} ({df.shape})")
    
    # 创建 debug 版本 (20 只股票)
    debug_instruments = df.index.get_level_values(1).unique()[:20]
    df_debug = df[df.index.get_level_values(1).isin(debug_instruments)]
    debug_path = OUTPUT_DIR / "daily_pv_csi300_debug.h5"
    df_debug.to_hdf(debug_path, key='data', mode='w')
    print(f"✓ daily_pv_csi300_debug.h5: {debug_path} ({df_debug.shape})")
    
    return h5_path, debug_path


def create_qlib_structure(df: pd.DataFrame):
    """创建 Qlib 目录结构"""
    print("\n创建 Qlib 目录结构...")
    
    # 清理旧数据
    import shutil
    if QLIB_DATA_DIR.exists():
        shutil.rmtree(QLIB_DATA_DIR)
    
    # 创建目录
    (QLIB_DATA_DIR / "calendars").mkdir(parents=True, exist_ok=True)
    (QLIB_DATA_DIR / "instruments").mkdir(parents=True, exist_ok=True)
    (QLIB_DATA_DIR / "features").mkdir(parents=True, exist_ok=True)
    
    df_reset = df.reset_index()
    
    # 1. 交易日历
    trading_days = sorted(df_reset['datetime'].dt.strftime('%Y-%m-%d').unique())
    with open(QLIB_DATA_DIR / "calendars" / "day.txt", 'w') as f:
        f.write('\n'.join(trading_days) + '\n')
    print(f"✓ 交易日历: {len(trading_days)} 天 ({trading_days[0]} ~ {trading_days[-1]})")
    
    # 2. 股票列表
    instruments = sorted(df_reset['instrument'].unique())
    start_date = df_reset['datetime'].min().strftime('%Y-%m-%d')
    end_date = df_reset['datetime'].max().strftime('%Y-%m-%d')
    
    with open(QLIB_DATA_DIR / "instruments" / "all.txt", 'w') as f:
        for inst in instruments:
            f.write(f"{inst}\t{start_date}\t{end_date}\n")
    print(f"✓ 股票列表: {len(instruments)} 只")
    
    # 3. 特征数据 (按股票分目录存储)
    print("保存特征数据...")
    for i, inst in enumerate(instruments):
        inst_data = df_reset[df_reset['instrument'] == inst].copy()
        inst_data = inst_data.sort_values('datetime')
        
        # 转换 instrument 格式 (000001.SZ -> SZ000001)
        if '.' in inst:
            code, market = inst.split('.')
            inst_name = market + code
        else:
            inst_name = inst
        
        inst_dir = QLIB_DATA_DIR / "features" / inst_name
        inst_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存为pickle格式 (qlib标准格式)
        for col in ['$open', '$close', '$high', '$low', '$volume', '$return']:
            if col in inst_data.columns:
                series = inst_data.set_index('datetime')[col]
                series.to_pickle(inst_dir / f"{col}.pkl")
        
        if (i + 1) % 50 == 0:
            print(f"  已处理 {i + 1}/{len(instruments)} 只股票")
    
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
    
    # 更新路径为新的CSI 300数据目录
    old_path = '/home/quan/testdata/aspipe_v4/third_party/data/qlib_data'
    new_path = str(QLIB_DATA_DIR)
    
    content = content.replace(f'QLIB_DATA_DIR={old_path}', f'QLIB_DATA_DIR={new_path}')
    content = content.replace(f'QLIB_PROVIDER_URI={old_path}', f'QLIB_PROVIDER_URI={new_path}')
    
    with open(env_path, 'w') as f:
        f.write(content)
    
    print(f"✓ .env 文件已更新")
    print(f"  QLIB_DATA_DIR={new_path}")
    print(f"  QLIB_PROVIDER_URI={new_path}")


def print_summary(df: pd.DataFrame):
    """打印数据摘要"""
    print("\n" + "=" * 60)
    print("数据摘要")
    print("=" * 60)
    
    df_reset = df.reset_index()
    
    # 按数据集划分统计
    train_mask = (df_reset['datetime'] >= TRAIN_START) & (df_reset['datetime'] <= TRAIN_END)
    valid_mask = (df_reset['datetime'] >= VALID_START) & (df_reset['datetime'] <= VALID_END)
    test_mask = (df_reset['datetime'] >= TEST_START) & (df_reset['datetime'] <= TEST_END)
    
    print(f"\n训练集 (2016-2020):")
    print(f"  日期数: {df_reset[train_mask]['datetime'].nunique()}")
    print(f"  股票数: {df_reset[train_mask]['instrument'].nunique()}")
    print(f"  总记录: {train_mask.sum()}")
    
    print(f"\n验证集 (2021):")
    print(f"  日期数: {df_reset[valid_mask]['datetime'].nunique()}")
    print(f"  股票数: {df_reset[valid_mask]['instrument'].nunique()}")
    print(f"  总记录: {valid_mask.sum()}")
    
    print(f"\n测试集 (2022-2025):")
    print(f"  日期数: {df_reset[test_mask]['datetime'].nunique()}")
    print(f"  股票数: {df_reset[test_mask]['instrument'].nunique()}")
    print(f"  总记录: {test_mask.sum()}")
    
    print(f"\n总计:")
    print(f"  日期数: {df_reset['datetime'].nunique()}")
    print(f"  股票数: {df_reset['instrument'].nunique()}")
    print(f"  总记录: {len(df_reset)}")


def main():
    print("=" * 60)
    print("CSI 300 数据转换工具")
    print("=" * 60)
    print(f"\n训练集: {TRAIN_START} ~ {TRAIN_END}")
    print(f"验证集: {VALID_START} ~ {VALID_END}")
    print(f"测试集: {TEST_START} ~ {TEST_END}")
    
    # 1. 获取 CSI 300 成分股
    csi300_stocks = get_csi300_stocks()
    
    # 2. 获取目标日期
    target_dates = get_target_dates()
    
    # 3. 处理数据
    df = process_data(csi300_stocks, target_dates)
    
    # 4. 计算收益率
    df_with_return = calculate_returns(df)
    
    # 5. 转换为 pandas
    df_pandas = convert_to_pandas(df_with_return)
    
    # 6. 保存 HDF5
    save_h5_files(df_pandas)
    
    # 7. 创建 Qlib 结构
    create_qlib_structure(df_pandas)
    
    # 8. 更新配置
    update_env_file()
    
    # 9. 打印摘要
    print_summary(df_pandas)
    
    log_memory("最终")
    
    print("\n" + "=" * 60)
    print("转换完成!")
    print("=" * 60)
    print(f"\n输出文件:")
    print(f"  HDF5 数据: {OUTPUT_DIR}/daily_pv_csi300.h5")
    print(f"  Qlib 数据: {QLIB_DATA_DIR}")


if __name__ == "__main__":
    main()
