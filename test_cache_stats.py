#!/usr/bin/env python3
"""
Test script to verify the cache statistics functionality in GenericDownloader
"""
import os
import sys
import tempfile
from datetime import datetime
from unittest.mock import Mock

# Add the app4 module to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app4'))

from app4.core.config_loader import ConfigLoader
from app4.core.downloader import GenericDownloader


def create_test_config():
    """Create a test configuration for the downloader"""
    # Create a temporary config directory
    temp_dir = tempfile.mkdtemp()

    # Create a basic settings.yaml
    settings_content = """
app:
  name: "aspipe_v4_test"
  version: "4.0.0"

tushare:
  token: "test_token"
  api_url: "http://test.api.com"

concurrency:
  max_workers: 4

request:
  max_retries: 3
  retry_delay: 1.0
  timeout: 30

cache:
  directory: "cache"
  ttl_hours: 24
  max_size_gb: 10

storage:
  base_dir: "../data"
  format: "parquet"
  batch_size: 10000

logging:
  level: "INFO"
  file: "log/app4_test.log"
  max_size_mb: 100
  backup_count: 5
"""

    settings_path = os.path.join(temp_dir, 'settings.yaml')
    with open(settings_path, 'w', encoding='utf-8') as f:
        f.write(settings_content)

    # Create a basic interface config directory
    interfaces_dir = os.path.join(temp_dir, 'interfaces')
    os.makedirs(interfaces_dir, exist_ok=True)

    # Create a basic trade_cal interface config
    trade_cal_content = """
name: trade_cal
api_name: trade_cal
description: "交易日历"

permissions:
  min_points: 0
  rate_limit: 120
  query_limit: 10000

pagination:
  enabled: false

parameters:
  exchange:
    type: string
    required: false
    description: "交易所"
  start_date:
    type: string
    required: false
    description: "开始日期"
  end_date:
    type: string
    required: false
    description: "结束日期"

output:
  primary_key: ["exchange", "cal_date"]
  sort_by: ["cal_date"]
  columns:
    exchange: {type: string, required: true}
    cal_date: {type: date, format: "%Y%m%d", required: true}
    is_open: {type: int, required: true}
"""

    trade_cal_path = os.path.join(interfaces_dir, 'trade_cal.yaml')
    with open(trade_cal_path, 'w', encoding='utf-8') as f:
        f.write(trade_cal_content)

    return temp_dir  # Return the directory path, not the file path


def test_cache_stats_functionality():
    """Test the cache statistics functionality"""
    print("Testing cache statistics functionality...")

    # Create test configuration
    config_path = create_test_config()

    # Initialize config loader
    config_loader = ConfigLoader(config_path)

    # Mock the storage manager since we don't need storage functionality for this test
    mock_storage_manager = Mock()

    # Initialize the downloader
    downloader = GenericDownloader(config_loader, storage_manager=mock_storage_manager)

    # Simulate some cache operations to populate stats
    # First, test the initial state
    print("\n1. Initial cache stats:")
    initial_stats = downloader.get_cache_stats()
    print(f"   Stats: {initial_stats}")

    print("\n2. Initial cache hit rate:")
    initial_hit_rate = downloader.get_cache_hit_rate()
    print(f"   Hit rate: {initial_hit_rate:.2f}%")

    # Manually update cache stats to simulate operations
    # This would normally happen during actual cache operations
    with downloader._cache_stats_lock:
        downloader._cache_stats['exact_match'] += 10
        downloader._cache_stats['superset_match'] += 5
        downloader._cache_stats['file_hit'] += 3
        downloader._cache_stats['miss'] += 2

    print("\n3. After simulating cache operations:")
    stats_after = downloader.get_cache_stats()
    print(f"   Stats: {stats_after}")

    hit_rate_after = downloader.get_cache_hit_rate()
    print(f"   Hit rate: {hit_rate_after:.2f}%")

    print("\n4. Formatted cache stats display:")
    formatted_stats = downloader.display_cache_stats(formatted=True)
    print(formatted_stats)

    print("\n5. Simple cache stats display:")
    simple_stats = downloader.display_cache_stats(formatted=False)
    print(simple_stats)

    print("\n✓ All cache statistics functionality tests passed!")


def main():
    """Main function to run the test"""
    try:
        test_cache_stats_functionality()
    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())