#!/usr/bin/env python
"""
Test TuShare API pagination mechanism for multiple APIs
"""
import sys
import os

# Add the app directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), 'app'))

from tushare_api import TuShareDownloader
import pandas as pd


def test_api_with_pagination(api_name, api_func, params=None, limit=5000):
    """
    Generic function to test pagination for any API
    """
    if params is None:
        params = {}
    
    downloader = TuShareDownloader()
    print(f"\nTesting {api_name} API with pagination...")
    
    # First, try original call without pagination (if applicable)
    print(f"1. Original call without pagination:")
    try:
        if api_name == 'stock_basic':
            original_result = downloader.download_stock_basic()
        elif api_name == 'dividend':
            # Use specific parameters for dividend to avoid error
            original_result = downloader.download_dividend(ts_code='000001.SZ')
        elif api_name == 'namechange':
            original_result = downloader.download_namechange()
        else:
            # For other APIs, try to call with minimal parameters
            original_result = api_func(**params)
        
        print(f"   Records returned: {len(original_result)}")
    except Exception as e:
        print(f"   Error in original call: {e}")
        original_result = pd.DataFrame()
    
    # Test with pagination parameters
    print(f"2. Testing with pagination parameters:")
    
    all_data = []
    offset = 0
    total_attempts = 0  # To prevent infinite loops
    
    while total_attempts < 10:  # Limit to 10 attempts to prevent infinite loops
        print(f"   Fetching batch with offset={offset}, limit={limit}")
        try:
            # Copy the original parameters and add pagination
            batch_params = params.copy()
            batch_params.update({'limit': limit, 'offset': offset})
            
            batch = api_func(**batch_params)
            batch_size = len(batch)
            print(f"   Got {batch_size} records in this batch")
            
            if batch_size == 0:
                print("   No more data to fetch")
                break
                
            all_data.append(batch)
            offset += limit
            total_attempts += 1
            
        except Exception as e:
            print(f"   Error in paginated call: {e}")
            break
    
    if all_data:
        total_data = pd.concat(all_data, ignore_index=True)
        print(f"3. Total records with pagination: {len(total_data)}")
        
        # Compare with original result if both succeeded
        if len(original_result) > 0:
            if len(total_data) > len(original_result):
                print(f"   SUCCESS: Pagination allowed fetching more than original call!")
            elif len(total_data) == len(original_result):
                print(f"   SAME: Pagination returned same amount as original call")
            else:
                print(f"   LESS: Pagination returned fewer records than original call")
        
        return total_data
    else:
        print(f"   No data retrieved through pagination")
        return pd.DataFrame()


def comprehensive_pagination_test():
    """
    Test pagination for multiple APIs
    """
    downloader = TuShareDownloader()
    
    print("\n" + "="*60)
    print("COMPREHENSIVE PAGINATION TEST")
    print("="*60)
    
    # Test different APIs for pagination support
    tests = [
        {
            'name': 'namechange',
            'func': downloader.pro.namechange,
            'params': {},
            'description': 'Stock name change history'
        },
        {
            'name': 'stock_basic',
            'func': downloader.pro.stock_basic,
            'params': {'list_status': 'L'},  # Only listed stocks
            'description': 'Basic stock information'
        },
        {
            'name': 'dividend',
            'func': downloader.pro.dividend,
            'params': {'ts_code': '000001.SZ'},  # Specific stock to avoid error
            'description': 'Dividend information for 000001.SZ'
        },
        {
            'name': 'fina_indicator',
            'func': downloader.pro.fina_indicator,
            'params': {'period': '20231231'},  # Specific period
            'description': 'Financial indicators for 2023Q4'
        },
        {
            'name': 'balancesheet',
            'func': downloader.pro.balancesheet,
            'params': {'period': '20231231'},  # Specific period
            'description': 'Balance sheet for 2023Q4'
        },
        {
            'name': 'income',
            'func': downloader.pro.income,
            'params': {'period': '20231231'},  # Specific period
            'description': 'Income statement for 2023Q4'
        },
        {
            'name': 'cashflow',
            'func': downloader.pro.cashflow,
            'params': {'period': '20231231'},  # Specific period
            'description': 'Cash flow statement for 2023Q4'
        }
    ]
    
    results = {}
    for test in tests:
        print(f"\n{'-'*50}")
        print(f"Testing {test['name']}: {test['description']}")
        print('-'*50)
        
        result = test_api_with_pagination(
            test['name'],
            test['func'],
            test['params']
        )
        results[test['name']] = result
    
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY OF PAGINATION TESTS")
    print("="*60)
    
    for name, data in results.items():
        original_count = 0
        # Get original count for comparison where possible
        try:
            if name == 'namechange':
                original_result = downloader.download_namechange()
                original_count = len(original_result)
            elif name == 'stock_basic':
                original_result = downloader.download_stock_basic()
                original_count = len(original_result)
        except:
            pass
            
        print(f"{name:15}: {len(data):6d} records with pagination")
        if original_count > 0 and len(data) > original_count:
            print(f"{'':17} -> {len(data) - original_count:6d} more records than original call")
    
    return results


if __name__ == "__main__":
    results = comprehensive_pagination_test()
    print(f"\nAll pagination tests completed.")