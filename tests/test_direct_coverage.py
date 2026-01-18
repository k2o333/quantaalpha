import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import tempfile
from pathlib import Path
import polars as pl

from app4.core.coverage_manager import CoverageManager
from app4.core.storage import StorageManager
from app4.core.config_loader import ConfigLoader


def test_direct_coverage_read():
    """直接测试CoverageManager的读取功能"""
    # Initialize components using real data directory
    config_loader = ConfigLoader(config_dir="app4/config")
    storage = StorageManager(storage_dir="../data")  # 使用实际数据目录
    coverage_manager = CoverageManager(storage, config_loader)

    # Mock downloader to provide trade calendar
    class MockDownloader:
        def get_trade_calendar(self, start, end):
            # Return 5 days of trading days (20240101 to 20240105)
            return [
                {'cal_date': '20240101', 'is_open': 1},
                {'cal_date': '20240102', 'is_open': 1},
                {'cal_date': '20240103', 'is_open': 1},
                {'cal_date': '20240104', 'is_open': 1},
                {'cal_date': '20240105', 'is_open': 1}
            ]

    coverage_manager.downloader = MockDownloader()

    print("Testing read_interface_data directly...")
    # 测试直接读取数据
    df = storage.read_interface_data(
        'daily',
        start_date='20240101',
        end_date='20240105',
        columns=['trade_date'],
        ts_code='000002.SZ'
    )
    print(f"Found {len(df)} records with ts_code=000002.SZ in 20240101-20240105")
    if not df.is_empty():
        print(f"Trade dates: {df['trade_date'].to_list()}")

    print("Testing get_missing_date_ranges...")
    # Test coverage detection with ts_code
    action, missing_ranges, message = coverage_manager.get_missing_date_ranges(
        "daily", "20240101", "20240105", ts_code="000002.SZ"
    )

    print(f"Action: {action}")
    print(f"Missing ranges: {missing_ranges}")
    print(f"Message: {message}")

    return action, missing_ranges, message


if __name__ == "__main__":
    test_direct_coverage_read()