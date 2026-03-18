"""
数据适配器：准备 vnpy AlphaDataset 所需的输入数据
"""

import polars as pl
from pathlib import Path
from typing import Optional, Tuple
import hashlib


class DataAdapter:
    """
    将原始数据转换为 vnpy AlphaDataset 格式
    """

    # vnpy 必需的列
    REQUIRED_COLUMNS = ["datetime", "vt_symbol", "open", "high", "low", "close", "volume"]

    # 可选列
    OPTIONAL_COLUMNS = ["vwap", "amount", "turnover", "bid1", "ask1"]

    def __init__(self, data_dir: str = None):
        # 默认数据目录在 p/factormining/mvp/data
        if data_dir is None:
            # 获取项目根目录
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / "p" / "factormining" / "mvp" / "data"
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def load_from_csv(
        self,
        csv_path: str,
        date_col: str = "date",
        symbol_col: str = "symbol",
        **column_mapping
    ) -> pl.DataFrame:
        """
        从 CSV 加载数据并转换为 vnpy 格式

        Args:
            csv_path: CSV 文件路径
            date_col: 日期列名
            symbol_col: 股票代码列名
            column_mapping: 列名映射，如 {"open_price": "open"}
        """
        df = pl.read_csv(csv_path)

        # 重命名列
        rename_map = {date_col: "datetime", symbol_col: "vt_symbol"}
        rename_map.update(column_mapping)

        for old_name, new_name in rename_map.items():
            if old_name in df.columns:
                df = df.rename({old_name: new_name})

        # 转换日期格式
        if df["datetime"].dtype == pl.Utf8:
            df = df.with_columns(pl.col("datetime").str.to_datetime())

        # 转换 vt_symbol 格式
        df = df.with_columns(
            pl.col("vt_symbol").map_elements(
                self._format_vt_symbol,
                return_dtype=pl.Utf8
            )
        )

        return df

    def load_from_parquet(self, parquet_path: str) -> pl.DataFrame:
        """从 Parquet 加载数据"""
        return pl.read_parquet(parquet_path)

    def save_to_parquet(self, df: pl.DataFrame, filename: str) -> str:
        """保存为 Parquet 格式"""
        output_path = self.data_dir / filename
        df.write_parquet(output_path)
        return str(output_path)

    def validate(self, df: pl.DataFrame) -> Tuple[bool, list]:
        """
        验证数据格式

        Returns:
            (is_valid, missing_columns)
        """
        missing = [col for col in self.REQUIRED_COLUMNS if col not in df.columns]
        return len(missing) == 0, missing

    def create_sample_data(
        self,
        start_date: str = "2020-01-01",
        end_date: str = "2023-01-01",
        n_symbols: int = 10,
        output_file: str = "sample_data.parquet"
    ) -> str:
        """
        创建示例数据用于测试

        Returns:
            输出文件路径
        """
        import numpy as np
        from datetime import datetime, timedelta

        # 生成日期范围（跳过周末）
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        dates = []
        current = start
        while current <= end:
            # 跳过周末
            if current.weekday() < 5:
                dates.append(current)
            current += timedelta(days=1)

        # 生成股票代码
        symbols = [f"{i:06d}.SZSE" if i % 2 == 0 else f"{i:06d}.SSE"
                   for i in range(1, n_symbols + 1)]

        # 生成数据
        rows = []
        np.random.seed(42)

        for symbol in symbols:
            base_price = np.random.uniform(10, 100)
            for date in dates:
                # 随机游走生成价格
                change = np.random.normal(0, 0.02)
                close = base_price * (1 + change)
                open_price = close * (1 + np.random.normal(0, 0.005))
                high = max(open_price, close) * (1 + abs(np.random.normal(0, 0.01)))
                low = min(open_price, close) * (1 - abs(np.random.normal(0, 0.01)))
                volume = int(np.random.uniform(100000, 1000000))

                rows.append({
                    "datetime": date,
                    "vt_symbol": symbol,
                    "open": round(open_price, 2),
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "close": round(close, 2),
                    "volume": volume,
                })

                base_price = close

        df = pl.DataFrame(rows)
        df = df.sort(["datetime", "vt_symbol"])

        output_path = self.save_to_parquet(df, output_file)
        return output_path

    def _format_vt_symbol(self, symbol: str) -> str:
        """
        格式化 vt_symbol

        支持的输入格式：
        - 000001.SZ → 000001.SZSE
        - 000001 → 000001.SZSE (默认深交所)
        - 600000.SH → 600000.SSE
        """
        if symbol is None:
            return "000000.SZSE"

        symbol = str(symbol).strip()

        if "." in symbol:
            code, exchange = symbol.split(".", 1)
            exchange_map = {
                "SZ": "SZSE",
                "SH": "SSE",
                "BJ": "BSE",
            }
            return f"{code}.{exchange_map.get(exchange, exchange)}"
        else:
            # 根据代码规则判断交易所
            if symbol.startswith("6"):
                return f"{symbol}.SSE"
            else:
                return f"{symbol}.SZSE"

    def get_data_hash(self, df: pl.DataFrame) -> str:
        """计算数据哈希，用于缓存"""
        # 使用数据的形状和前几行计算哈希
        sample = df.head(100).to_numpy().tobytes()
        return hashlib.md5(sample).hexdigest()[:16]


if __name__ == "__main__":
    # 测试
    adapter = DataAdapter()

    # 创建示例数据
    print("创建示例数据...")
    data_path = adapter.create_sample_data(
        start_date="2022-01-01",
        end_date="2022-12-31",
        n_symbols=5,
        output_file="test_sample.parquet"
    )
    print(f"数据已保存到: {data_path}")

    # 加载并验证
    df = adapter.load_from_parquet(data_path)
    print(f"数据形状: {df.shape}")
    print(f"列: {df.columns}")

    is_valid, missing = adapter.validate(df)
    print(f"验证结果: {'通过' if is_valid else '失败'}")
    if missing:
        print(f"缺失列: {missing}")
