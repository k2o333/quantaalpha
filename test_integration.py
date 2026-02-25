#!/usr/bin/env python3
"""
Integration test to verify the fixes work in a real scenario
"""
import os
import sys
import time
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app4.core.config_loader import ConfigLoader
from app4.core.downloader import GenericDownloader
from app4.core.storage import StorageManager
from app4.core.processor import DataProcessor

def test_integration():
    print("Running integration test for trade_cal/stock_basic save fixes...")

    # Initialize components
    config_dir = os.path.join(os.path.dirname(__file__), "app4", "config")
    config_loader = ConfigLoader(config_dir=config_dir)

    processor = DataProcessor()
    # Use a test directory to avoid interfering with real data
    storage_dir = "../data_test"
    if not os.path.exists(storage_dir):
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
        trade_calendar_cache=None,
        stock_list_cache=None
    )

    # Start the storage writer threads
    storage_manager.start_writer()

    try:
        print(f"Storage directory: {storage_dir}")

        # Count files before
        trade_cal_dir = os.path.join(storage_dir, "trade_cal")
        stock_basic_dir = os.path.join(storage_dir, "stock_basic")

        trade_cal_before = len(os.listdir(trade_cal_dir)) if os.path.exists(trade_cal_dir) else 0
        stock_basic_before = len(os.listdir(stock_basic_dir)) if os.path.exists(stock_basic_dir) else 0

        print(f"Files before test - trade_cal: {trade_cal_before}, stock_basic: {stock_basic_before}")

        # Test trade calendar fetch (which should save to storage)
        print("\nTesting trade calendar fetch...")
        start_date = datetime.now().strftime("%Y%m%d")  # Use today's date for testing
        end_date = start_date

        # Get trade calendar which should trigger API call and save
        trade_cal = downloader.get_trade_calendar(start_date, end_date)
        print(f"Retrieved trade calendar: {len(trade_cal) if trade_cal else 0} records")

        # Wait a moment for async operations to complete
        time.sleep(2)

        # Count files after trade_cal
        trade_cal_after = len(os.listdir(trade_cal_dir)) if os.path.exists(trade_cal_dir) else 0
        print(f"After trade_cal - trade_cal files: {trade_cal_after}")

        # Test stock list fetch (which should save to storage)
        print("\nTesting stock list fetch...")

        # Clear the cache to force a fresh API fetch
        downloader._memory_cache["stock_list"] = None

        stock_list = downloader._get_stock_list()
        print(f"Retrieved stock list: {len(stock_list) if stock_list else 0} records")

        # Wait a moment for async operations to complete
        time.sleep(3)

        # Count files after stock_basic
        stock_basic_after = len(os.listdir(stock_basic_dir)) if os.path.exists(stock_basic_dir) else 0
        print(f"After stock_list - stock_basic files: {stock_basic_after}")

        # Verify results
        trade_cal_saved = trade_cal_after > trade_cal_before
        stock_basic_saved = stock_basic_after > stock_basic_before

        print(f"\nResults:")
        print(f"  Trade calendar saved: {'✓' if trade_cal_saved else '✗'}")
        print(f"  Stock basic saved: {'✓' if stock_basic_saved else '✗'}")

        if trade_cal_saved and stock_basic_saved:
            print("\n🎉 All fixes are working correctly!")
            return True
        else:
            print("\n❌ Some fixes are not working as expected.")
            return False

    finally:
        # Stop storage writer threads
        storage_manager.stop_writer()

        # Clean up by removing test files (keep real files)
        import glob
        for pattern in [f"{trade_cal_dir}/*_test_*.parquet", f"{stock_basic_dir}/*_test_*.parquet"]:
            for file in glob.glob(pattern):
                try:
                    os.remove(file)
                    print(f"Removed test file: {file}")
                except:
                    pass

if __name__ == "__main__":
    success = test_integration()
    sys.exit(0 if success else 1)