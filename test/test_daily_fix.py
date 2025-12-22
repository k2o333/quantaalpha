#!/usr/bin/env python3
"""
Test script to verify the daily download fix
"""
import sys
import os
import pandas as pd

# Add the app directory to the path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from tushare_api import TuShareDownloader
from download_strategies import DailyDataStrategy


def test_daily_data_range_method():
    """Test the new download_daily_data_range method directly"""
    print("Testing download_daily_data_range method...")
    
    try:
        downloader = TuShareDownloader()
        # Test with a date range that should have data
        result = downloader.download_daily_data_range(start_date='20250930', end_date='20250930')
        print(f"Successfully called download_daily_data_range, got {len(result)} records")
        return True
    except Exception as e:
        print(f"Error in download_daily_data_range: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_daily_strategy():
    """Test the DailyDataStrategy with 'daily' interface"""
    print("\nTesting DailyDataStrategy for 'daily' interface...")
    
    try:
        strategy = DailyDataStrategy(interface_name='daily')
        # Test with parameters that would normally cause the error
        result = strategy.download(start_date='20250930', end_date='20250930')
        print(f"Successfully executed DailyDataStrategy for 'daily', got {len(result)} records")
        return True
    except Exception as e:
        print(f"Error in DailyDataStrategy: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("Testing the daily download fix...")
    
    test1_passed = test_daily_data_range_method()
    test2_passed = test_daily_strategy()
    
    print(f"\nTest Results:")
    print(f"download_daily_data_range: {'PASSED' if test1_passed else 'FAILED'}")
    print(f"DailyDataStrategy: {'PASSED' if test2_passed else 'FAILED'}")
    
    if test1_passed and test2_passed:
        print("\nAll tests passed! The fix should work correctly.")
        return 0
    else:
        print("\nSome tests failed. The fix may need more work.")
        return 1


if __name__ == "__main__":
    sys.exit(main())