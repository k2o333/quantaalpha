import pytest
import tempfile
from pathlib import Path
import polars as pl
from datetime import datetime, timedelta

from app4.core.coverage_manager import CoverageManager
from app4.core.storage import StorageManager
from app4.core.config_loader import ConfigLoader


def test_get_missing_date_ranges():
    """Test calculating missing date ranges for download"""
    # Create a temporary directory for test data
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test data directory structure
        data_dir = Path(tmpdir) / "data"
        daily_dir = data_dir / "daily"
        daily_dir.mkdir(parents=True)

        # Create test data with partial date range (20240101-0103, missing 0104-0105)
        df = pl.DataFrame({
            "ts_code": ["000001.SZ"] * 3,
            "trade_date": ["20240101", "20240102", "20240103"],
            "close": [10.0, 10.1, 10.2]
        })
        df.write_parquet(daily_dir / "daily_000001.SZ_test.parquet")

        # Initialize components
        config_loader = ConfigLoader(config_dir="app4/config")
        storage = StorageManager(storage_dir=str(data_dir))
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

        # Test incremental coverage detection
        action, missing_ranges, message = coverage_manager.get_missing_date_ranges(
            "daily", "20240101", "20240105", ts_code="000001.SZ"
        )

        # Should detect partial coverage and return missing ranges
        assert action == 'download_partial'
        assert len(missing_ranges) == 1
        assert missing_ranges[0] == ('20240104', '20240105')
        print(f"Test result: {action}, {missing_ranges}, {message}")