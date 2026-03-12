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

import pandas as pd
import numpy as np
import qlib
from qlib.config import C
from qlib.data.storage.file_storage import FileFeatureStorage

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


def load_trading_calendar() -> pd.DatetimeIndex:
    """加载 Qlib 日历，作为所有特征写入的唯一日期基准。"""
    calendar_path = QLIB_DATA_DIR / "calendars" / "day.txt"
    if not calendar_path.exists():
        raise FileNotFoundError(f"日历文件不存在: {calendar_path}")

    calendar = pd.read_csv(calendar_path, header=None, names=["date"])
    calendar["date"] = pd.to_datetime(calendar["date"])
    return pd.DatetimeIndex(calendar["date"])


def align_series_to_calendar(values: np.ndarray, dates: pd.Series, calendar: pd.DatetimeIndex) -> tuple[int, np.ndarray]:
    """
    将字段值对齐到 Qlib 交易日历，并返回 Qlib 所需的 start_index 和连续值数组。
    """
    series = pd.Series(values.astype(np.float32), index=pd.DatetimeIndex(dates)).sort_index()
    if series.empty:
        raise ValueError("指数数据为空，无法写入 Qlib bin")

    missing_dates = series.index.difference(calendar)
    if not missing_dates.empty:
        missing_sample = ", ".join(d.strftime("%Y-%m-%d") for d in missing_dates[:5])
        raise ValueError(f"指数数据存在不在 Qlib 日历中的日期: {missing_sample}")

    start_date = series.index.min()
    end_date = series.index.max()
    start_index = int(calendar.get_loc(start_date))
    end_index = int(calendar.get_loc(end_date))

    aligned_index = calendar[start_index : end_index + 1]
    aligned = series.reindex(aligned_index)
    return start_index, aligned.to_numpy(dtype=np.float32)


def write_qlib_feature_bin(bin_path: Path, start_index: int, values: np.ndarray) -> None:
    """按 Qlib FileFeatureStorage 兼容格式写入单个字段。"""
    payload = np.hstack([np.array([start_index], dtype=np.float32), values.astype(np.float32)]).astype("<f4")
    with open(bin_path, "wb") as fp:
        payload.tofile(fp)


def ensure_qlib_initialized() -> None:
    """为 FileFeatureStorage 验证准备最小 Qlib 运行环境。"""
    current_uri = getattr(C, "provider_uri", None)
    if isinstance(current_uri, dict):
        current_day_uri = current_uri.get("day") or current_uri.get("__DEFAULT_FREQ")
    else:
        current_day_uri = current_uri

    target_day_uri = str(QLIB_DATA_DIR)
    if not hasattr(C, "mount_path") or str(current_day_uri) != target_day_uri:
        qlib.init(provider_uri={"day": str(QLIB_DATA_DIR)}, expression_cache=None, dataset_cache=None)


def validate_feature_bin(qlib_code: str, field: str, start_index: int, expected_values: np.ndarray) -> None:
    """用 Qlib 自己的读取逻辑做 round-trip 校验。"""
    ensure_qlib_initialized()
    storage = FileFeatureStorage(
        instrument=qlib_code.lower(),
        field=field,
        freq="day",
        provider_uri={"day": str(QLIB_DATA_DIR)},
    )

    if storage.start_index != start_index:
        raise ValueError(
            f"{qlib_code} {field} start_index 校验失败: expected={start_index}, actual={storage.start_index}"
        )

    actual = storage[start_index : start_index + len(expected_values)].to_numpy(dtype=np.float32)
    if len(actual) != len(expected_values):
        raise ValueError(
            f"{qlib_code} {field} 长度校验失败: expected={len(expected_values)}, actual={len(actual)}"
        )

    if not np.allclose(actual, expected_values, equal_nan=True):
        raise ValueError(f"{qlib_code} {field} round-trip 校验失败")


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
    calendar = load_trading_calendar()

    in_calendar = dates.isin(calendar)
    if not in_calendar.all():
        dropped_dates = dates[~in_calendar]
        dropped_sample = ", ".join(d.strftime("%Y-%m-%d") for d in dropped_dates[:5])
        print(
            f"警告: {qlib_code} 有 {len(dropped_dates)} 个交易日不在目标 Qlib 日历中，将按目标日历裁剪: {dropped_sample}"
        )
        df = df.loc[in_calendar].copy()
        dates = dates[in_calendar]

    if df.empty:
        raise ValueError(f"{qlib_code} 经过目标日历裁剪后无可用数据")
    
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
        bin_path = inst_dir / f"{field}.day.bin"
        start_index, aligned_values = align_series_to_calendar(values, dates, calendar)
        write_qlib_feature_bin(bin_path, start_index, aligned_values)
        validate_feature_bin(qlib_code, field, start_index, aligned_values)
        print(f"  保存: {bin_path} (start_index={start_index}, len={len(aligned_values)})")

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
