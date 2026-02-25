#!/usr/bin/env python3
"""
Test the specific scenario mentioned in the original issue:
A download requiring trade calendar data outside the local range,
which triggers API fetch that should also be saved.
"""
import os
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app4.core.config_loader import ConfigLoader
from app4.core.downloader import GenericDownloader
from app4.core.storage import StorageManager
from app4.core.processor import DataProcessor
import shutil

def test_runtime_scenario():
    print("Testing the specific runtime scenario from the issue...")

    # Setup
    config_dir = os.path.join(os.path.dirname(__file__), "app4", "config")
    config_loader = ConfigLoader(config_dir=config_dir)

    processor = DataProcessor()
    # Use a clean test directory
    storage_dir = "../data_runtime_test"
    if os.path.exists(storage_dir):
        shutil.rmtree(storage_dir)
    os.makedirs(storage_dir, exist_ok=True)

    storage_manager = StorageManager(
        processor=processor,
        config_loader=config_loader,
        storage_dir=storage_dir,
        format="parquet",
        batch_size=10000
    )

    downloader = GenericDownloader(
        config_loader=config_loader,
        storage_manager=storage_manager,
        trade_calendar_cache=None,  # No preloaded cache
        stock_list_cache=None
    )

    # Start storage writer
    storage_manager.start_writer()

    try:
        # Test 1: Check the get_trade_calendar path when no local data exists for the date range
        print("\nTest 1: Forcing API fetch for trade calendar outside local range")

        # Use a future date range that shouldn't exist locally
        import datetime
        future_start = (datetime.datetime.now() + datetime.timedelta(days=365)).strftime("%Y%m%d")  # Next year
        future_end = (datetime.datetime.now() + datetime.timedelta(days=370)).strftime("%Y%m%d")

        print(f"Fetching trade calendar for future range: {future_start} to {future_end}")

        # This should trigger an API call since this future date range likely doesn't exist locally
        trade_calendar = downloader.get_trade_calendar(future_start, future_end)

        print(f"Retrieved {len(trade_calendar) if trade_calendar else 0} trade calendar records")

        # Wait for async operations
        time.sleep(2)

        # Check if data was saved
        trade_cal_dir = os.path.join(storage_dir, "trade_cal")
        if os.path.exists(trade_cal_dir) and os.listdir(trade_cal_dir):
            files = os.listdir(trade_cal_dir)
            print(f"✓ Trade calendar was saved: {len(files)} files found")
            for f in files:
                print(f"  - {f}")
        else:
            print("✗ No trade calendar files found in storage")

        print("\nTest 2: Testing stock_list API fetch by clearing all caches")
        # Clear internal caches to force API fetch
        downloader._memory_cache["stock_list"] = None

        # Simulate a scenario where local stock_basic data doesn't exist
        stock_basic_dir = os.path.join(storage_dir, "stock_basic")
        if os.path.exists(stock_basic_dir):
            import shutil
            shutil.rmtree(stock_basic_dir)

        # Now fetch should trigger API call since no local data exists in the test directory
        stock_list = downloader._get_stock_list()

        print(f"Retrieved {len(stock_list) if stock_list else 0} stock records from API")

        # Wait for operations to complete
        time.sleep(2)

        # Check if data was saved
        if os.path.exists(stock_basic_dir) and os.listdir(stock_basic_dir):
            files = os.listdir(stock_basic_dir)
            print(f"✓ Stock basic was saved: {len(files)} files found")
            for f in files:
                file_path = os.path.join(stock_basic_dir, f)
                size = os.path.getsize(file_path)
                print(f"  - {f} ({size} bytes)")
        else:
            print("✗ No stock_basic files found in storage")
            print(f"  stock_basic dir exists: {os.path.exists(stock_basic_dir)}")
            print(f"  Contents: {os.listdir(os.path.dirname(stock_basic_dir)) if os.path.exists(os.path.dirname(stock_basic_dir)) else 'N/A'}")

        print("\nTest completed.")

    finally:
        storage_manager.stop_writer()
        # Clean up test directory
        if os.path.exists(storage_dir):
            shutil.rmtree(storage_dir)

if __name__ == "__main__":
    test_runtime_scenario()