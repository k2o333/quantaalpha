"""factor_ops Parquet 存储小工具。"""

from __future__ import annotations

import fcntl
import os
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

import polars as pl


@contextmanager
def file_lock(lock_path: Path) -> Iterator[None]:
    """使用文件锁保护同一存储根目录下的写入。"""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = open(lock_path, "w")
    try:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)
        lock_fd.close()


def parse_iso_datetime(value: str) -> datetime:
    """解析 ISO 时间字符串。"""
    return datetime.fromisoformat(value)


def partition_dir(root: Path, table_name: str, timestamp: str) -> Path:
    """返回 year/month 分区目录。"""
    dt = parse_iso_datetime(timestamp)
    return root / table_name / f"year={dt.year:04d}" / f"month={dt.month:02d}"


def write_single_row_parquet(root: Path, table_name: str, timestamp: str, df: pl.DataFrame) -> Path:
    """以单文件方式写入一条日志记录。"""
    target_dir = partition_dir(root, table_name, timestamp)
    staging_dir = root / "staging" / table_name
    target_dir.mkdir(parents=True, exist_ok=True)
    staging_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{parse_iso_datetime(timestamp).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.parquet"
    staging_path = staging_dir / f"{filename}.tmp"
    target_path = target_dir / filename
    df.write_parquet(str(staging_path))
    os.replace(staging_path, target_path)
    return target_path


def read_table(root: Path, table_name: str) -> pl.DataFrame:
    """读取表下所有 Parquet 分区。"""
    files = sorted((root / table_name).glob("year=*/month=*/*.parquet"))
    if not files:
        return pl.DataFrame()
    return pl.concat([pl.read_parquet(file) for file in files], how="vertical")

