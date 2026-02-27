#!/usr/bin/env python3
"""
Test with proper configuration to ensure correct storage directory is used
"""
import os
import sys
import tempfile
import shutil

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app4.core.config_loader import ConfigLoader
from app4.core.downloader import GenericDownloader
from app4.core.storage import StorageManager
from app4.core.processor import DataProcessor

def test_with_proper_config():
    print("Testing with proper configuration...")

    # Create a temporary clean storage location
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Using temporary directory: {temp_dir}")

        # Create a config with custom storage directory
        config_dir = os.path.join(os.path.dirname(__file__), "app4", "config")

        # Temporarily override storage directory in global config
        # We'll create a custom settings file or modify it temporarily

        import yaml

        # Read the original settings
        settings_path = os.path.join(config_dir, 'settings.yaml')
        with open(settings_path, 'r', encoding='utf-8') as f:
            original_config = yaml.safe_load(f)

        # Modify storage directory
        test_settings_path = os.path.join(temp_dir, 'temp_settings.yaml')
        modified_config = original_config.copy()
        if 'storage' not in modified_config:
            modified_config['storage'] = {}
        modified_config['storage']['base_dir'] = temp_dir

        # Write modified config
        with open(test_settings_path, 'w', encoding='utf-8') as f:
            yaml.dump(modified_config, f, default_flow_style=False, allow_unicode=True)

        # Use modified config loader
        config_loader = ConfigLoader(config_dir=config_dir)
        # Override the global config to use our test directory
        config_loader.global_config = modified_config

        processor = DataProcessor()
        storage_manager = StorageManager(
            processor=processor,
            config_loader=config_loader,
            storage_dir=temp_dir,
            format="parquet",
            batch_size=10000
        )

        # Initialize downloader - it will use the modified global config
        downloader = GenericDownloader(
            config_loader=config_loader,  # This now has the modified config
            storage_manager=storage_manager,
            trade_calendar_cache=None,
            stock_list_cache=None
        )

        # Start storage system
        storage_manager.start_writer()

        try:
            # Verify that the downloader's global config uses the temp dir
            storage_dir_from_downloader = downloader.global_config.get("storage", {}).get("base_dir", "../data")
            print(f"Downloader will look for data in: {storage_dir_from_downloader}")

            # Step 1: Test trade calendar API fetch and save
            print("\nStep 1: Testing trade calendar API fetch")

            # Use a date range that should return data (recent past)
            import datetime
            start_date = (datetime.datetime.now() - datetime.timedelta(days=10)).strftime("%Y%m%d")
            end_date = (datetime.datetime.now() - datetime.timedelta(days=5)).strftime("%Y%m%d")

            print(f"Fetching trade calendar: {start_date} to {end_date}")

            # This should trigger API call since no local data exists in temp dir
            trade_cal = downloader.get_trade_calendar(start_date, end_date)

            if trade_cal:
                print(f"✓ Retrieved {len(trade_cal)} trade calendar records")

                # Check if saved to storage
                trade_cal_dir = os.path.join(temp_dir, "trade_cal")
                if os.path.exists(trade_cal_dir) and os.listdir(trade_cal_dir):
                    files = os.listdir(trade_cal_dir)
                    print(f"✓ Trade calendar data saved: {len(files)} files")
                    for f in files:
                        file_path = os.path.join(trade_cal_dir, f)
                        size = os.path.getsize(file_path)
                        print(f"  - {f} ({size} bytes)")
                    trade_cal_saved = True
                else:
                    print("✗ Trade calendar data was not saved")
                    trade_cal_saved = False
            else:
                print("✗ Failed to retrieve trade calendar data")
                trade_cal_saved = False

            # Step 2: Test stock list API fetch and save
            print("\nStep 2: Testing stock list API fetch")

            # Clear the memory cache to force the sequence: memory -> data dir -> API
            with downloader._cache_lock:
                downloader._memory_cache["stock_list"] = None

            # Now fetch stock list - this should first try data dir (in temp dir, which is empty), then API
            stock_list = downloader._get_stock_list()

            if stock_list:
                print(f"✓ Retrieved {len(stock_list)} stock records")

                # Check if saved to storage
                stock_basic_dir = os.path.join(temp_dir, "stock_basic")
                if os.path.exists(stock_basic_dir) and os.listdir(stock_basic_dir):
                    files = os.listdir(stock_basic_dir)
                    print(f"✓ Stock basic data saved: {len(files)} files")
                    for f in files:
                        file_path = os.path.join(stock_basic_dir, f)
                        size = os.path.getsize(file_path)
                        print(f"  - {f} ({size} bytes)")
                    stock_basic_saved = True
                else:
                    print("✗ Stock basic data was not saved")
                    print(f"  stock_basic directory exists: {os.path.exists(stock_basic_dir)}")
                    print(f"  parent contents: {os.listdir(temp_dir)}")
                    stock_basic_saved = False
            else:
                print("✗ Failed to retrieve stock list data")
                stock_basic_saved = False

            # Results
            print(f"\nResults:")
            print(f"  Trade calendar save fix: {'✓ WORKING' if trade_cal_saved else '✗ NOT WORKING'}")
            print(f"  Stock basic save fix: {'✓ WORKING' if stock_basic_saved else '✗ NOT WORKING'}")

            overall_success = trade_cal_saved and stock_basic_saved
            print(f"  Overall: {'✓ ALL FIXES WORKING' if overall_success else '✗ SOME FIXES NOT WORKING'}")

            return overall_success

        except Exception as e:
            print(f"Error during test: {e}")
            import traceback
            traceback.print_exc()
            return False

        finally:
            storage_manager.stop_writer()

if __name__ == "__main__":
    success = test_with_proper_config()
    if success:
        print("\n🎉 All runtime data saving fixes are working correctly!")
    else:
        print("\n❌ Some fixes are not working as expected.")

    sys.exit(0 if success else 1)