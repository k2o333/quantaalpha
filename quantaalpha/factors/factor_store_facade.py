"""
FactorStoreFacade - 统一因子存储入口

职责:
- 封装 ParquetFactorLibrary 的读写操作
- 提供稳定的业务 API
- 不做业务逻辑（如 check_redundancy、select_revalidation_candidates）

设计原则:
- append-only 事件模型，不修改老记录
- compact 只合并文件，不承担"修改老记录"语义
"""

from pathlib import Path
from typing import List

import pandas as pd

from quantaalpha.factors.parquet_library import ParquetFactorLibrary, REQUIRED_COLUMNS


class FactorStoreFacade:
    """统一因子存储入口，向业务层提供稳定 API"""

    def __init__(self, store_path: str | Path):
        """初始化 FactorStoreFacade

        Args:
            store_path: Parquet store 根目录的绝对或相对路径
        """
        self.store_path = Path(store_path)
        self._parquet = ParquetFactorLibrary(str(self.store_path))

    def write_factor(self, entry: dict) -> None:
        """写入单个因子到 delta 目录

        Args:
            entry: 因子 entry dict，包含 required schema 的所有字段
        """
        self._parquet.write_factor_delta(entry)

    def read_effective_factors(self) -> pd.DataFrame:
        """读取有效因子列表（compacted + delta，已去重）

        Returns:
            pandas DataFrame，包含所有有效因子记录
        """
        df = self._parquet.read_factor_library()
        if df is None or df.is_empty():
            return pd.DataFrame(columns=REQUIRED_COLUMNS)
        return df.to_pandas()

    def read_effective_factor_records(self) -> list[dict]:
        """读取有效因子记录列表

        Returns:
            list of dict，每个 dict 代表一条因子记录
        """
        return self.read_effective_factors().to_dict("records")

    def to_factor_zoo_frame(self) -> pd.DataFrame:
        """返回因子动物园视图（factor_name, factor_expression）

        Returns:
            pandas DataFrame，仅包含 factor_name 和 factor_expression 列
        """
        df = self.read_effective_factors()
        if "factor_name" not in df.columns or "factor_expression" not in df.columns:
            return pd.DataFrame(columns=["factor_name", "factor_expression"])
        return df[["factor_name", "factor_expression"]].copy()

    def delta_file_count(self) -> int:
        """返回 delta 目录中的 parquet 文件数量

        Returns:
            delta 目录中的 .parquet 文件数
        """
        delta_dir = self.store_path / "delta"
        if not delta_dir.exists():
            return 0
        return len(list(delta_dir.glob("*.parquet")))

    def compact(self) -> None:
        """执行 compact 操作，合并 delta 到 compacted"""
        before_count = self.delta_file_count()
        if before_count == 0:
            return
        self._parquet.compact()
