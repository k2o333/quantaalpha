#!/usr/bin/env python3
"""
Debug test for the stock_basic saving issue
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
import logging

# Enable logging to see what's happening
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def debug_test():
    print("Debugging stock_basic save issue...")

    # Initialize components
    config_dir = os.path.join(os.path.dirname(__file__), "app4", "config")
    config_loader = ConfigLoader(config_dir=config_dir)

    processor = DataProcessor()
    storage_dir = "../data_test_debug"
    os.makedirs(storage_dir, exist_ok=True)

    storage_manager = StorageManager(
        processor=processor,
        config_loader=config_loader,
        storage_dir=storage_dir,
        format="parquet",
        batch_size=10000
    )

    # Start the storage writer threads
    storage_manager.start_writer()

    downloader = GenericDownloader(
        config_loader=config_loader,
        storage_manager=storage_manager,
        trade_calendar_cache=None,
        stock_list_cache=None
    )

    print(f"Downloader.storage_manager exists: {downloader.storage_manager is not None}")

    # Clear any cache to force API call
    downloader._memory_cache["stock_list"] = None

    print("Calling _get_stock_list() to trigger API fetch...")

    # This should trigger the API call and save
    stock_list = downloader._get_stock_list()

    print(f"Retrieved {len(stock_list) if stock_list else 0} stock records")

    # Wait for any async operations
    time.sleep(3)

    # Check if data was written to storage
    stock_basic_path = os.path.join(storage_dir, "stock_basic")
    if os.path.exists(stock_basic_path):
        files = os.listdir(stock_basic_path)
        print(f"Files in stock_basic directory: {files}")
        for f in files:
            file_path = os.path.join(stock_basic_path, f)
            size = os.path.getsize(file_path)
            print(f"  {f}: {size} bytes")
    else:
        print("stock_basic directory does not exist")

    # Also test a direct save to see if storage manager works
    print("\nTesting direct save to storage...")
    test_data = [{"ts_code": "000001.SZ", "symbol": "平安银行", "name": "PINGAN"}]
    try:
        downloader.storage_manager.save_data('stock_basic', test_data, async_write=False)
        print("Direct save attempted")

        # Wait and check again
        time.sleep(1)
        if os.path.exists(stock_basic_path):
            files = os.listdir(stock_basic_path)
            print(f"After direct save, files in stock_basic: {files}")
    except Exception as e:
        print(f"Direct save failed: {e}")

    # Stop storage writer threads
    storage_manager.stop_writer()

if __name__ == "__main__":
    debug_test()