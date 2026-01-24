#!/usr/bin/env python3
"""
Test script to verify that the enhanced cache functions work correctly
"""

import pandas as pd
import os
from pathlib import Path

# Add the app directory to the path so we can import modules
import sys
sys.path.insert(0, str(Path(__file__).parent / 'app'))

from data_storage import (
    get_interface_cache_path,
    is_interface_data_cached,
    load_interface_cached_data,
    save_interface_data_to_cache,
    get_cached_or_download_data
)

def test_cache_functions():
    """Test the enhanced cache functions"""
    print("Testing enhanced cache functions...")

    # Create test data
    test_data = pd.DataFrame({
        'ts_code': ['000001.SZ', '000002.SZ', '000003.SZ'],
        'trade_date': ['20230101', '20230102', '20230103'],
        'close': [10.1, 10.2, 10.3]
    })

    print(f"Test data shape: {test_data.shape}")

    # Test get_interface_cache_path
    cache_path = get_interface_cache_path('daily', ts_code='000001.SZ', trade_date='20230101')
    print(f"Generated cache path: {cache_path}")

    # Test save_interface_data_to_cache
    success = save_interface_data_to_cache(test_data, 'daily', ts_code='000001.SZ', trade_date='20230101')
    print(f"Save successful: {success}")

    # Test is_interface_data_cached
    is_cached = is_interface_data_cached('daily', cache_ttl_hours=24, ts_code='000001.SZ', trade_date='20230101')
    print(f"Data is cached: {is_cached}")

    # Test load_interface_cached_data
    loaded_data = load_interface_cached_data('daily', ts_code='000001.SZ', trade_date='20230101')
    print(f"Loaded data shape: {loaded_data.shape if not loaded_data.empty else 'Empty'}")

    # Check if loaded data matches original
    if not loaded_data.empty:
        data_matches = loaded_data.equals(test_data)
        print(f"Data matches original: {data_matches}")

    # Test with different parameter combinations
    cache_path2 = get_interface_cache_path('daily_basic', trade_date='20230101')
    print(f"Generated cache path for daily_basic: {cache_path2}")

    cache_path3 = get_interface_cache_path('income', period='20230331')
    print(f"Generated cache path for income: {cache_path3}")

    # Test get_cached_or_download_data with a dummy download function
    def dummy_download_func(**kwargs):
        print(f"Executing dummy download with params: {kwargs}")
        dummy_data = pd.DataFrame({'dummy': [1, 2, 3]})
        return dummy_data

    # First call - should execute download function
    result1 = get_cached_or_download_data('test_interface', dummy_download_func, cache_ttl_hours=24, test_param='value1')
    print(f"First call result shape: {result1.shape}")

    # Second call - should use cache
    result2 = get_cached_or_download_data('test_interface', dummy_download_func, cache_ttl_hours=24, test_param='value1')
    print(f"Second call result shape: {result2.shape}")

    print("All cache function tests completed successfully!")

if __name__ == "__main__":
    test_cache_functions()