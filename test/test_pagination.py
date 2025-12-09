#!/usr/bin/env python
"""
Test TuShare API pagination mechanism
"""
import sys
import os

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from tushare_api import TuShareDownloader
import pandas as pd


def test_namechange_pagination():
    """
    Test namechange API with pagination parameters
    """
    downloader = TuShareDownloader()
    
    print("Testing namechange API pagination...")
    
    # First, try original call to confirm 10000 limit
    print("\n1. Original call without pagination:")
    try:
        original_result = downloader.download_namechange()
        print(f"   Records returned: {len(original_result)}")
    except Exception as e:
        print(f"   Error in original call: {e}")
        original_result = pd.DataFrame()
    
    # Now test with pagination parameters
    print("\n2. Testing with pagination parameters:")
    
    all_data = []
    offset = 0
    limit = 5000  # Use a smaller limit to test pagination
    
    while True:
        print(f"   Fetching batch with offset={offset}, limit={limit}")
        try:
            # Direct call to TuShare API with pagination parameters
            batch = downloader.pro.namechange(limit=limit, offset=offset)
            batch_size = len(batch)
            print(f"   Got {batch_size} records in this batch")
            
            if batch_size == 0:
                print("   No more data to fetch")
                break
                
            all_data.append(batch)
            offset += limit
            
            # To avoid infinite loops, set a reasonable upper limit
            if offset > 50000:  # Stop after trying to fetch 50k records
                print("   Reached maximum fetch limit")
                break
                
        except Exception as e:
            print(f"   Error in paginated call: {e}")
            break
    
    if all_data:
        total_data = pd.concat(all_data, ignore_index=True)
        print(f"\n3. Total records with pagination: {len(total_data)}")
        
        # Compare with original result
        if len(original_result) == 10000 and len(total_data) > 10000:
            print("   SUCCESS: Pagination allowed fetching more than 10000 records!")
        elif len(total_data) == len(original_result):
            print("   SAME: Pagination returned same amount as original call (no more data available)")
        else:
            print(f"   DIFFERENT: Pagination returned {len(total_data)} vs original {len(original_result)}")
        
        return total_data
    else:
        print("   No data retrieved through pagination")
        return pd.DataFrame()


def test_other_paginated_apis():
    """
    Test other APIs for pagination support
    """
    downloader = TuShareDownloader()
    
    print("\nTesting other APIs for pagination support...")
    
    # Test stock_basic (might have many records)
    print("\nTesting stock_basic API:")
    try:
        # Try with pagination parameters
        result = downloader.pro.stock_basic(limit=1000, offset=0)
        print(f"   stock_basic with pagination: {len(result)} records")
    except Exception as e:
        print(f"   stock_basic pagination failed: {e}")
    
    # Test dividend (might have many records)
    print("\nTesting dividend API:")
    try:
        result = downloader.pro.dividend(limit=1000, offset=0)
        print(f"   dividend with pagination: {len(result)} records")
    except Exception as e:
        print(f"   dividend pagination failed: {e}")


if __name__ == "__main__":
    print("TuShare API Pagination Test")
    print("="*50)
    
    # Test namechange pagination
    result = test_namechange_pagination()
    
    # Test other APIs
    test_other_paginated_apis()
    
    print("\nPagination test completed.")