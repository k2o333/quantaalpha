#!/usr/bin/env python3
"""
添加指数数据到 Qlib 数据集
解决: ValueError: The benchmark ['SH000300'] does not exist

使用方法:
    cd /home/quan/testdata/aspipe_v4/third_party/scripts/dataconvert
    /root/miniforge3/envs/mining/bin/python add_index_to_qlib.py
"""

import os
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np

# ==================== 配置 ====================
QLIB_DATA_DIR = Path("/home/quan/testdata/aspipe_v4/third_party/data/qlib_data_csi300_bin")

# Tushare 配置
TUSHARE_TOKEN = os.environ.get('TUSHARE_TOKEN', '81df46dcdf60768a4bffc2242e46a47d388076f3de9d8b1e31ac568a35ec60ff')
PROXY_URL = os.environ.get('PROXY_URL', 'http://tushare.xyz')

# 指数代码列表 (沪深300 + 其他常用指数)
INDEX_CODES = [
    ('000300.SH', 'SH000300'),  # 沪深300
    # ('000016.SH', 'SH000016'),  # 上证50
    # ('000905.SH', 'SH000905'),  # 中证500
    # ('000001.SH', 'SH000001'),  # 上证指数
    # ('399001.SZ', 'SZ399001'),  # 深证成指
]

# 时间范围
START_DATE = "20160101"
END_DATE = "20251231"


def get_index_data_from_tushare(ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    从 Tushare 获取指数数据
    """
    try:
        import tushare as ts
        
        # 设置代理
        if PROXY_URL:
            os.environ['HTTP_PROXY'] = PROXY_URL
            os.environ['HTTPS_PROXY'] = PROXY_URL
        
        pro = ts.pro_api(TUSHARE_TOKEN)
        
        print(f"正在获取 {ts_code} 指数数据...")
        
        # 使用 index_daily 接口获取指数日线数据
        df = pro.index_daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
        
        if df is None or len(df) == 0:
            print(f"警告: 未获取到 {ts_code} 数据")
            return None
        
        print(f"获取到 {len(df)} 条记录")
        return df
        
    except Exception as e:
        print(f"错误: 获取 {ts_code} 数据失败: {e}")
        return None


def convert_to_qlib_bin(df: pd.DataFrame, qlib_code: str, output_dir: Path):
    """
    将 DataFrame 转换为 Qlib bin 格式
    
    Args:
        df: Tushare 返回的指数数据
        qlib_code: Qlib 格式的代码 (如 SH000300)
        output_dir: features 目录
    """
    # 按日期排序
    df = df.sort_values('trade_date')
    
    # 创建目录
    inst_dir = output_dir / qlib_code.lower()
    inst_dir.mkdir(parents=True, exist_ok=True)
    
    # 准备数据
    dates = pd.to_datetime(df['trade_date'], format='%Y%m%d')
    
    # 各字段数据
    data = {
        'open': df['open'].values.astype(np.float32),
        'close': df['close'].values.astype(np.float32),
        'high': df['high'].values.astype(np.float32),
        'low': df['low'].values.astype(np.float32),
        'volume': df['vol'].values.astype(np.float32),
    }
    
    # 计算收益率
    returns = np.zeros(len(df), dtype=np.float32)
    returns[1:] = (df['close'].values[1:] / df['close'].values[:-1] - 1).astype(np.float32)
    data['return'] = returns
    
    # 保存为 bin 格式
    for field, values in data.items():
        # 构造 Series
        series = pd.Series(values, index=dates)
        series.index.name = 'datetime'
        
        # 保存为 bin 文件 (使用 qlib 的格式)
        bin_path = inst_dir / f"{field}.day.bin"
        
        # Qlib bin 格式: 先写入日期数，然后写入数据
        with open(bin_path, 'wb') as f:
            # 写入数据点数量 (int32)
            f.write(np.int32(len(series)).tobytes())
            
            # 写入日期 (int64, Unix时间戳)
            timestamps = series.index.astype(np.int64) // 10**9  # 转换为秒级时间戳
            f.write(timestamps.values.astype(np.int64).tobytes())
            
            # 写入数据值 (float32)
            f.write(values.tobytes())
        
        print(f"  保存: {bin_path}")
    
    return qlib_code.lower(), dates.min(), dates.max()


def update_instruments_file(qlib_code: str, start_date: str, end_date: str):
    """
    更新 instruments 文件，添加指数代码
    """
    all_file = QLIB_DATA_DIR / "instruments" / "all.txt"
    
    # 检查是否已存在
    if all_file.exists():
        with open(all_file, 'r') as f:
            content = f.read()
        
        if qlib_code in content:
            print(f"  {qlib_code} 已在 instruments 中")
            return
    
    # 添加到文件末尾
    with open(all_file, 'a') as f:
        f.write(f"{qlib_code}\t{start_date}\t{end_date}\n")
    
    print(f"  已添加 {qlib_code} 到 instruments/all.txt")


def main():
    print("=" * 60)
    print("添加指数数据到 Qlib 数据集")
    print("=" * 60)
    print(f"QLIB_DATA_DIR: {QLIB_DATA_DIR}")
    print(f"时间范围: {START_DATE} ~ {END_DATE}")
    
    # 检查目录
    if not QLIB_DATA_DIR.exists():
        print(f"错误: Qlib 数据目录不存在: {QLIB_DATA_DIR}")
        sys.exit(1)
    
    features_dir = QLIB_DATA_DIR / "features"
    if not features_dir.exists():
        print(f"错误: features 目录不存在: {features_dir}")
        sys.exit(1)
    
    # 处理每个指数
    for ts_code, qlib_code in INDEX_CODES:
        print(f"\n处理: {ts_code} -> {qlib_code}")
        print("-" * 40)
        
        # 获取数据
        df = get_index_data_from_tushare(ts_code, START_DATE, END_DATE)
        
        if df is None or len(df) == 0:
            print(f"跳过 {ts_code}")
            continue
        
        # 转换并保存
        result = convert_to_qlib_bin(df, qlib_code, features_dir)
        
        if result:
            code, start_dt, end_dt = result
            # 更新 instruments 文件
            update_instruments_file(
                code.upper(),
                start_dt.strftime('%Y-%m-%d'),
                end_dt.strftime('%Y-%m-%d')
            )
        
        print(f"✓ {ts_code} 处理完成")
    
    print("\n" + "=" * 60)
    print("全部完成!")
    print("=" * 60)
    
    # 验证
    print("\n验证结果:")
    for _, qlib_code in INDEX_CODES:
        inst_dir = features_dir / qlib_code.lower()
        if inst_dir.exists():
            files = list(inst_dir.glob("*.bin"))
            print(f"  {qlib_code}: {len(files)} 个 bin 文件")
        else:
            print(f"  {qlib_code}: 未创建")


if __name__ == "__main__":
    main()
