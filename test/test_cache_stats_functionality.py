#!/usr/bin/env python3
"""
Test script to verify the cache statistics functionality in GenericDownloader
"""
import os
import sys
from unittest.mock import Mock, patch
import tempfile
import shutil
from datetime import datetime

# Add the app4 module to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

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

    # Create a basic daily interface config for testing
    daily_content = """
name: daily
api_name: daily
description: "日线行情"

permissions:
  min_points: 0
  rate_limit: 120
  query_limit: 10000

pagination:
  enabled: true
  mode: "date_range"
  window_size_days: 365

parameters:
  ts_code:
    type: string
    required: false
    description: "证券代码"
  start_date:
    type: string
    required: false
    description: "开始日期"
  end_date:
    type: string
    required: false
    description: "结束日期"

output:
  primary_key: ["ts_code", "trade_date"]
  sort_by: ["trade_date"]
  columns:
    ts_code: {type: string, required: true}
    trade_date: {type: date, format: "%Y%m%d", required: true}
    open: {type: float, required: false}
    high: {type: float, required: false}
    low: {type: float, required: false}
    close: {type: float, required: false}
    pre_close: {type: float, required: false}
    change: {type: float, required: false}
    pct_chg: {type: float, required: false}
    vol: {type: float, required: false}
    amount: {type: float, required: false}
"""

    daily_path = os.path.join(interfaces_dir, 'daily.yaml')
    with open(daily_path, 'w', encoding='utf-8') as f:
        f.write(daily_content)

    return temp_dir


def test_cache_stats_functionality():
    """Test the cache statistics functionality"""
    print("Testing cache statistics functionality...")

    # Create test configuration
    config_dir = create_test_config()

    try:
        # Initialize config loader
        config_loader = ConfigLoader(config_dir)

        # Mock the storage manager since we don't need storage functionality for this test
        mock_storage_manager = Mock()

        # Initialize the downloader
        downloader = GenericDownloader(config_loader, storage_manager=mock_storage_manager)

        # Test 1: Initial state
        print("\n1. Initial cache stats:")
        initial_stats = downloader.get_cache_stats()
        print(f"   Stats: {initial_stats}")
        assert initial_stats['exact_match'] == 0
        assert initial_stats['superset_match'] == 0
        assert initial_stats['file_hit'] == 0
        assert initial_stats['miss'] == 0

        # Test 2: Initial hit rate
        print("\n2. Initial cache hit rate:")
        initial_hit_rate = downloader.get_cache_hit_rate()
        print(f"   Hit rate: {initial_hit_rate:.2f}%")
        assert initial_hit_rate == 0.0

        # Test 3: Simulate cache operations
        print("\n3. After simulating cache operations:")
        with downloader._cache_stats_lock:
            downloader._cache_stats['exact_match'] += 10
            downloader._cache_stats['superset_match'] += 5
            downloader._cache_stats['file_hit'] += 3
            downloader._cache_stats['miss'] += 2

        stats_after = downloader.get_cache_stats()
        print(f"   Stats: {stats_after}")
        assert stats_after['exact_match'] == 10
        assert stats_after['superset_match'] == 5
        assert stats_after['file_hit'] == 3
        assert stats_after['miss'] == 2

        hit_rate_after = downloader.get_cache_hit_rate()
        print(f"   Hit rate: {hit_rate_after:.2f}%")
        expected_hit_rate = (10 + 5 + 3) / (10 + 5 + 3 + 2) * 100
        assert hit_rate_after == expected_hit_rate

        # Test 4: Formatted display
        print("\n4. Formatted cache stats display:")
        formatted_stats = downloader.display_cache_stats(formatted=True)
        print(formatted_stats)
        assert "缓存统计信息" in formatted_stats
        assert "总访问次数: 20" in formatted_stats
        assert "缓存命中率: 90.00%" in formatted_stats
        assert "精确匹配命中: 10" in formatted_stats

        # Test 5: Simple display
        print("\n5. Simple cache stats display:")
        simple_stats = downloader.display_cache_stats(formatted=False)
        print(simple_stats)
        assert "Cache stats" in simple_stats
        assert "Hit Rate: 90.00%" in simple_stats
        assert "Exact: 10" in simple_stats

        # Test 6: Thread safety by simulating concurrent access
        print("\n6. Testing thread safety...")
        import threading
        import time

        def update_stats(thread_id):
            for i in range(5):
                with downloader._cache_stats_lock:
                    downloader._cache_stats['exact_match'] += 1
                    downloader._cache_stats['miss'] += 1
                time.sleep(0.001)  # Small delay to increase chance of race condition

        # Create multiple threads to update stats
        threads = []
        for i in range(3):
            t = threading.Thread(target=update_stats, args=(i,))
            threads.append(t)
            t.start()

        # Wait for all threads to complete
        for t in threads:
            t.join()

        # Check final counts (should be 15 more for each due to 3 threads * 5 updates each)
        final_stats = downloader.get_cache_stats()
        expected_exact = 10 + 15  # Original 10 + 3 threads * 5 updates
        expected_miss = 2 + 15    # Original 2 + 3 threads * 5 updates
        expected_superset = 5     # Unchanged
        expected_file = 3         # Unchanged

        print(f"   Final stats: {final_stats}")
        assert final_stats['exact_match'] == expected_exact
        assert final_stats['miss'] == expected_miss
        assert final_stats['superset_match'] == expected_superset
        assert final_stats['file_hit'] == expected_file

        print("\n✓ All cache statistics functionality tests passed!")
        return True

    finally:
        # Clean up temporary config directory
        shutil.rmtree(config_dir)


def test_edge_cases():
    """Test edge cases for cache statistics"""
    print("\n\nTesting edge cases...")

    config_dir = create_test_config()

    try:
        config_loader = ConfigLoader(config_dir)
        mock_storage_manager = Mock()
        downloader = GenericDownloader(config_loader, storage_manager=mock_storage_manager)

        # Edge case 1: All zeros
        print("1. Testing all zeros case:")
        zero_stats = downloader.display_cache_stats(formatted=True)
        assert "总访问次数: 0" in zero_stats
        assert "缓存命中率: 0.00%" in zero_stats
        assert "缓存未命中率: 0.00%" in zero_stats

        # Edge case 2: Only misses
        with downloader._cache_stats_lock:
            downloader._cache_stats['miss'] = 10
        miss_only_stats = downloader.display_cache_stats(formatted=True)
        assert "缓存命中率: 0.00%" in miss_only_stats
        assert "缓存未命中率: 100.00%" in miss_only_stats

        # Edge case 3: Only hits
        with downloader._cache_stats_lock:
            downloader._cache_stats['exact_match'] = 10
            downloader._cache_stats['miss'] = 0
        hit_only_stats = downloader.display_cache_stats(formatted=True)
        assert "缓存命中率: 100.00%" in hit_only_stats
        assert "缓存未命中率: 0.00%" in hit_only_stats

        print("   ✓ All edge cases passed!")
        return True

    finally:
        shutil.rmtree(config_dir)


def main():
    """Main function to run the tests"""
    print("Running cache statistics functionality tests...")

    success = True

    try:
        success &= test_cache_stats_functionality()
        success &= test_edge_cases()

        if success:
            print("\n🎉 All tests passed successfully!")
            return 0
        else:
            print("\n❌ Some tests failed!")
            return 1

    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())