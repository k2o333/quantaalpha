#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app4'))

from core.config_loader import ConfigLoader
from core.downloader import GenericDownloader
from core.storage import StorageManager

# Initialize config
config_dir_path = os.path.join(os.path.dirname(__file__), "app4/config")
config_loader = ConfigLoader(config_dir=config_dir_path)

# Initialize storage
storage_manager = StorageManager(
    storage_dir=config_loader.global_config.get('storage', {}).get('base_dir', '../data'),
    format=config_loader.global_config.get('storage', {}).get('format', 'parquet'),
    batch_size=config_loader.global_config.get('storage', {}).get('batch_size', 10000)
)

# Initialize downloader
downloader = GenericDownloader(config_loader, storage_manager)

# Test the function
print("Testing _get_trade_calendar_from_data_dir...")
print(f"Storage dir: {downloader.global_config.get('storage', {}).get('base_dir', '../data')}")

result = downloader._get_trade_calendar_from_data_dir('19900101', '20260119')
print(f"Result: {result}")
if result:
    print(f"Number of records: {len(result)}")
    print(f"Date range: {result[0]['cal_date']} - {result[-1]['cal_date']}")
    print(f"First few records: {result[:3]}")
else:
    print("Returned None or empty")

# Try with the exact range
dir_path = os.path.join(downloader.global_config.get('storage', {}).get('base_dir', '../data'), 'trade_cal')
print(f"\nChecking directory: {dir_path}")
print(f"Directory exists: {os.path.exists(dir_path)}")
if os.path.exists(dir_path):
    files = os.listdir(dir_path)
    print(f"Files: {files}")
    parquet_files = [f for f in files if f.endswith('.parquet')]
    print(f"Parquet files: {parquet_files}")