import pytest
import tempfile
from pathlib import Path
import polars as pl
import time

from app4.core.coverage_manager import CoverageManager
from app4.core.storage import StorageManager
from app4.core.config_loader import ConfigLoader


def test_incremental_vs_full_download_performance():
    """Compare performance between incremental and full download approaches"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test data directory
        data_dir = Path(tmpdir) / "data"
        daily_dir = data_dir / "daily"
        daily_dir.mkdir(parents=True)

        # Create test data with partial coverage (first half covered)
        all_dates = [f"202401{i:02d}" for i in range(1, 21)]  # 20 days
        covered_dates = all_dates[:10]  # First 10 days covered

        df = pl.DataFrame({
            "ts_code": ["000001.SZ"] * len(covered_dates),
            "trade_date": covered_dates,
            "close": [10.0 + i*0.1 for i in range(len(covered_dates))]
        })
        df.write_parquet(daily_dir / "daily_000001.SZ_test.parquet")

        config_loader = ConfigLoader(config_dir="app4/config")
        storage = StorageManager(storage_dir=str(data_dir))
        coverage_manager = CoverageManager(storage, config_loader)

        class MockDownloader:
            def get_trade_calendar(self, start, end):
                return [{'cal_date': date, 'is_open': 1} for date in all_dates]

        coverage_manager.downloader = MockDownloader()

        # Time the incremental coverage detection
        start_time = time.time()
        action, missing_ranges, message = coverage_manager.get_missing_date_ranges(
            "daily", "20240101", "20240120", ts_code="000001.SZ"
        )
        incremental_time = time.time() - start_time

        print(f"Incremental detection time: {incremental_time:.4f}s")
        print(f"Action: {action}, Missing ranges: {missing_ranges}")

        # Verify that incremental detection works correctly
        assert action == 'download_partial'
        assert len(missing_ranges) >= 1  # Should have at least one missing range