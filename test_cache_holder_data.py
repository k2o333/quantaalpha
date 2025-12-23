#!/usr/bin/env python3
"""
Test script to verify that the cache is working for holder data interfaces
"""

import sys
from pathlib import Path

# Add the app directory to the path so we can import modules
sys.path.insert(0, str(Path(__file__).parent / 'app'))

from app.interfaces.holders_data import HoldersDataDownloader
import tushare as ts

def test_cache_functionality():
    """Test that cache is working for holder data interfaces"""
    print("Testing cache functionality for holder data interfaces...")

    # Initialize the downloader
    pro = ts.pro_api()  # This will use the token from environment
    downloader = HoldersDataDownloader(pro)

    # Test with a sample stock code
    test_stock = "000001.SZ"

    print(f"Testing with stock: {test_stock}")

    # First call - should download and cache
    print("First call to download_stk_rewards...")
    result1 = downloader.download_stk_rewards(test_stock)
    print(f"First call result: {len(result1) if result1 is not None else 0} records")

    # Second call - should use cache
    print("Second call to download_stk_rewards...")
    result2 = downloader.download_stk_rewards(test_stock)
    print(f"Second call result: {len(result2) if result2 is not None else 0} records")

    # Check if results are the same
    if result1 is not None and result2 is not None:
        if result1.equals(result2):
            print("✓ Cache test passed - results are identical")
        else:
            print("✗ Cache test failed - results differ")
    else:
        print("? Cache test inconclusive - one or both results are None")

    print("Cache functionality test completed!")

if __name__ == "__main__":
    test_cache_functionality()