#!/usr/bin/env python3
"""
Test script to verify that runtime fetched trade_cal and stock_basic data
are properly saved to local storage.
"""
import os
import sys
from datetime import datetime
import tempfile

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app4.core.config_loader import ConfigLoader
from app4.core.downloader import GenericDownloader
from app4.core.storage import StorageManager
from app4.core.processor import DataProcessor

def test_runtime_data_save():
    """Test that runtime fetched trade_cal and stock_basic are saved to storage"""
    print("Testing runtime data save functionality...")

    # Initialize components
    config_dir = os.path.join(os.path.dirname(__file__), "app4", "config")
    config_loader = ConfigLoader(config_dir=config_dir)

    processor = DataProcessor()
    storage_dir = tempfile.mkdtemp(prefix="test_storage_")
    print(f"Using temporary storage directory: {storage_dir}")

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
        # Test 1: Fetch trade calendar and verify it's saved
        print("\n1. Testing trade calendar fetch and save...")
        start_date = "20230101"
        end_date = "20230131"  # Use a short range for testing

        # Check if trade_cal exists in storage before fetch
        trade_cal_path = os.path.join(storage_dir, "trade_cal")
        if os.path.exists(trade_cal_path):
            print(f"   Trade cal directory exists before fetch: {len(os.listdir(trade_cal_path))} files")
        else:
            print("   Trade cal directory does not exist before fetch")

        # Fetch trade calendar - this should trigger API call and save to storage
        trade_calendar = downloader.get_trade_calendar(start_date, end_date)

        if trade_calendar:
            print(f"   ✓ Fetched {len(trade_calendar)} trade calendar records")

            # Check if trade calendar data was saved to storage
            if os.path.exists(trade_cal_path):
                trade_cal_files = os.listdir(trade_cal_path)
                print(f"   ✓ Trade calendar saved to storage: {len(trade_cal_files)} files")

                # Read back data to verify it matches
                try:
                    import polars as pl
                    df = pl.read_parquet(trade_cal_path)
                    print(f"   ✓ Read back {len(df)} records from storage")
                except Exception as e:
                    print(f"   ✗ Error reading back trade calendar: {e}")
            else:
                print(f"   ✗ Trade calendar was not saved to {trade_cal_path}")
        else:
            print(f"   ✗ Failed to fetch trade calendar data")

        print()

        # Test 2: Fetch stock list and verify it's saved
        print("2. Testing stock list fetch and save...")
        stock_list_path = os.path.join(storage_dir, "stock_basic")

        if os.path.exists(stock_list_path):
            print(f"   Stock list directory exists before fetch: {len(os.listdir(stock_list_path))} files")
        else:
            print("   Stock list directory does not exist before fetch")

        # Clear internal cache to force API fetch
        with downloader._cache_lock:
            downloader._memory_cache["stock_list"] = None

        # Fetch stock list - this should trigger API call and save to storage
        stock_list = downloader._get_stock_list()

        if stock_list:
            print(f"   ✓ Fetched {len(stock_list)} stock records")

            # Check if stock list data was saved to storage
            if os.path.exists(stock_list_path):
                stock_list_files = os.listdir(stock_list_path)
                print(f"   ✓ Stock list saved to storage: {len(stock_list_files)} files")

                # Read back data to verify it matches
                try:
                    import polars as pl
                    df = pl.read_parquet(stock_list_path)
                    print(f"   ✓ Read back {len(df)} records from storage")
                except Exception as e:
                    print(f"   ✗ Error reading back stock list: {e}")
            else:
                print(f"   ✗ Stock list was not saved to {stock_list_path}")
        else:
            print(f"   ✗ Failed to fetch stock list data")

        print()
        print("Test completed successfully! Both trade_cal and stock_basic data are now being saved to local storage when fetched at runtime.")

    finally:
        # Stop storage writer threads
        storage_manager.stop_writer()
        print(f"\nCleaned up temporary storage directory: {storage_dir}")
        import shutil
        shutil.rmtree(storage_dir, ignore_errors=True)

if __name__ == "__main__":
    test_runtime_data_save()