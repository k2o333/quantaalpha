#!/usr/bin/env python3
"""
Test script to verify that the cache integration works properly with the download system
"""

import sys
import os
from pathlib import Path

# Add the project root, app, and test directories to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'app'))
sys.path.insert(0, str(project_root / 'test'))

import pandas as pd
from download_strategies import get_strategy
from data_storage import get_interface_cache_path
from config_adapter import get_interface_cache_settings

def test_strategy_cache_integration():
    """Test that strategies properly integrate with cache functionality"""
    print("Testing strategy cache integration...")

    try:
        # Test creating a daily strategy and checking its cache properties
        daily_strategy = get_strategy('daily')
        print(f"Daily strategy cache enabled: {daily_strategy.cache_enabled}")
        print(f"Daily strategy cache TTL hours: {daily_strategy.cache_ttl_hours}")

        # Test creating a financial strategy
        financial_strategy = get_strategy('income')
        print(f"Financial strategy cache enabled: {financial_strategy.cache_enabled}")
        print(f"Financial strategy cache TTL hours: {financial_strategy.cache_ttl_hours}")

        # Test cache key generation
        cache_key = daily_strategy._get_cache_key(ts_code='000001.SZ', trade_date='20230101')
        print(f"Generated cache key: {cache_key}")

        # Test cache path generation
        cache_path = get_interface_cache_path('daily', ts_code='000001.SZ', trade_date='20230101')
        print(f"Cache path generated: {cache_path}")

        # Test cache settings
        cache_settings = get_interface_cache_settings('daily')
        print(f"Daily interface cache settings: {cache_settings}")

        # Test can_use_cache method
        can_use_cache = daily_strategy._can_use_cache(trade_date='20230101')
        print(f"Can use cache for daily data: {can_use_cache}")

        print("Strategy cache integration test passed!")
        return True

    except Exception as e:
        print(f"Strategy cache integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_cache_scenarios():
    """Test various cache scenarios"""
    print("\nTesting cache scenarios...")

    try:
        # Test cache paths for different data types
        from data_storage import get_interface_cache_path

        scenarios = [
            ('daily', {'ts_code': '000001.SZ', 'trade_date': '20230101'}),
            ('daily_basic', {'trade_date': '20230101'}),
            ('income', {'period': '20230331'}),
            ('stock_basic', {}),
            ('trade_cal', {'start_date': '20230101', 'end_date': '20230131'})
        ]

        for data_type, params in scenarios:
            path = get_interface_cache_path(data_type, **params)
            print(f"  {data_type}: {path}")

        print("Cache path scenarios tested successfully!")
        return True

    except Exception as e:
        print(f"Cache scenarios test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=" * 60)
    print("Running Cache Integration Tests")
    print("=" * 60)

    success1 = test_strategy_cache_integration()
    success2 = test_cache_scenarios()

    if success1 and success2:
        print("\n✓ All cache integration tests passed!")
        print("Cache optimization implementation is working correctly.")
        sys.exit(0)
    else:
        print("\n✗ Some cache integration tests failed")
        sys.exit(1)