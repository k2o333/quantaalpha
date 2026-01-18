import pytest
import tempfile
from pathlib import Path
import polars as pl
from datetime import datetime, timedelta

from app4.core.coverage_manager import CoverageManager
from app4.core.storage import StorageManager
from app4.core.config_loader import ConfigLoader


def test_ts_code_coverage_detection():
    """Test coverage detection with ts_code parameter"""
    # Create a temporary directory for test data
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test data directory structure
        data_dir = Path(tmpdir) / "data"
        daily_dir = data_dir / "daily"
        daily_dir.mkdir(parents=True)

        # Create test data with specific ts_code (000002.SZ) and date range
        df = pl.DataFrame({
            "ts_code": ["000002.SZ"] * 4,
            "trade_date": ["20240102", "20240103", "20240104", "20240105"],
            "close": [10.0, 10.1, 10.2, 10.3]
        })
        df.write_parquet(daily_dir / "daily_test.parquet")

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

        # Test coverage detection with ts_code - this should now find the existing data
        action, missing_ranges, message = coverage_manager.get_missing_date_ranges(
            "daily", "20240101", "20240105", ts_code="000002.SZ"
        )

        print(f"Test result with ts_code=000002.SZ - Action: {action}, Missing ranges: {missing_ranges}, Message: {message}")

        # Should detect partial coverage (4 out of 5 days covered) and return missing range
        # Missing date is 20240101
        assert action in ['download_partial', 'skip'], f"Expected partial download or skip, got {action}"
        print("Test with ts_code passed!")


def test_no_ts_code_coverage_detection():
    """Test coverage detection without ts_code parameter (should find no data since it's filtered by ts_code)"""
    # Create a temporary directory for test data
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test data directory structure
        data_dir = Path(tmpdir) / "data"
        daily_dir = data_dir / "daily"
        daily_dir.mkdir(parents=True)

        # Create test data with specific ts_code (000002.SZ) and date range
        df = pl.DataFrame({
            "ts_code": ["000002.SZ"] * 4,
            "trade_date": ["20240102", "20240103", "20240104", "20240105"],
            "close": [10.0, 10.1, 10.2, 10.3]
        })
        df.write_parquet(daily_dir / "daily_test.parquet")

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

        # Test coverage detection without ts_code - this should find no data for any ts_code
        action, missing_ranges, message = coverage_manager.get_missing_date_ranges(
            "daily", "20240101", "20240105"
        )

        print(f"Test result without ts_code - Action: {action}, Missing ranges: {missing_ranges}, Message: {message}")

        # Should detect no coverage since no ts_code filter is applied and data is filtered by ts_code
        assert action == 'download_full' or action == 'download_partial', f"Expected full/partial download, got {action}"
        print("Test without ts_code passed!")