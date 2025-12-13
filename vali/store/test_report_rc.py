#!/usr/bin/env python3
"""
Validation script to test the report_rc interface directly
"""
import sys
import os
import pandas as pd
sys.path.append('/home/quan/testdata/aspipe_v4/app')

# Import from the app directory
from tushare_api import TuShareDownloader
from config import TUSHARE_POINTS, TUSHARE_TOKEN

def test_report_rc_interface():
    """
    Test the report_rc interface with various parameters
    """
    print(f"Testing report_rc interface with current points: {TUSHARE_POINTS}")

    # Initialize the downloader
    downloader = TuShareDownloader()

    # Test with different parameter combinations

    print("\n1. Testing report_rc with report_date parameter (Tushare doc example)...")
    try:
        df1 = downloader.download_with_retry(
            downloader.pro.report_rc,
            report_date='20220429'  # From the documentation example
        )
        print(f"   Result: {len(df1) if hasattr(df1, '__len__') else 'unknown'} records")
        if not df1.empty:
            print("   Columns:", list(df1.columns))
            print("   Sample data:")
            print(df1.head())
    except Exception as e:
        print(f"   Error: {e}")

    print("\n2. Testing report_rc with period parameter...")
    try:
        df2 = downloader.download_with_retry(
            downloader.pro.report_rc,
            period='20231231'  # Using period instead
        )
        print(f"   Result: {len(df2) if hasattr(df2, '__len__') else 'unknown'} records")
        if not df2.empty:
            print("   Columns:", list(df2.columns))
            print("   Sample data:")
            print(df2.head())
    except Exception as e:
        print(f"   Error: {e}")

    print("\n3. Testing report_rc with ts_code parameter...")
    try:
        df3 = downloader.download_with_retry(
            downloader.pro.report_rc,
            ts_code='000001.SZ'  # Using a specific stock
        )
        print(f"   Result: {len(df3) if hasattr(df3, '__len__') else 'unknown'} records")
        if not df3.empty:
            print("   Columns:", list(df3.columns))
            print("   Sample data:")
            print(df3.head())
    except Exception as e:
        print(f"   Error: {e}")

    print("\n4. Testing report_rc with no parameters...")
    try:
        df4 = downloader.download_with_retry(
            downloader.pro.report_rc
        )
        print(f"   Result: {len(df4) if hasattr(df4, '__len__') else 'unknown'} records")
        if not df4.empty:
            print("   Columns:", list(df4.columns))
            print("   Sample data:")
            print(df4.head())
    except Exception as e:
        print(f"   Error: {e}")

    print("\n5. Testing report_rc with start_date and end_date...")
    try:
        df5 = downloader.download_with_retry(
            downloader.pro.report_rc,
            start_date='20230101',
            end_date='20231231'
        )
        print(f"   Result: {len(df5) if hasattr(df5, '__len__') else 'unknown'} records")
        if not df5.empty:
            print("   Columns:", list(df5.columns))
            print("   Sample data:")
            print(df5.head())
    except Exception as e:
        print(f"   Error: {e}")

def check_token_permissions():
    """
    Check the token permissions for report_rc access
    """
    print(f"\nToken information:")
    print(f"- Current points: {TUSHARE_POINTS}")
    print(f"- Token has 5000+ points: {TUSHARE_POINTS >= 5000}")
    print(f"- Token has 8000+ points: {TUSHARE_POINTS >= 8000}")
    print(f"- report_rc should work with 5000+ points for trial, 8000+ for full access")

    # Check if the interface is available based on points
    if TUSHARE_POINTS < 5000:
        print("- Current token does NOT have sufficient points for report_rc")
        return False
    else:
        print("- Current token has sufficient points for report_rc (trial access)")
        return True

def test_with_manual_call():
    """
    Test the report_rc interface directly using tushare without the wrapper
    """
    import tushare as ts

    print(f"\n6. Testing report_rc with direct tushare call...")

    try:
        pro = ts.pro_api(TUSHARE_TOKEN)

        # Try with report_date as per documentation
        print("   Trying with report_date='20220429'...")
        df = pro.report_rc(report_date='20220429')
        print(f"   Result: {len(df) if hasattr(df, '__len__') else 'unknown'} records")
        if not df.empty:
            print("   Columns:", list(df.columns))
            print("   Sample data:")
            print(df.head())
    except Exception as e:
        print(f"   Error with report_date: {e}")

    try:
        # Try with ts_code as per documentation
        print("   Trying with ts_code='' and report_date='20220429'...")
        df = pro.report_rc(ts_code='', report_date='20220429')
        print(f"   Result: {len(df) if hasattr(df, '__len__') else 'unknown'} records")
        if not df.empty:
            print("   Columns:", list(df.columns))
            print("   Sample data:")
            print(df.head())
    except Exception as e:
        print(f"   Error: {e}")

if __name__ == "__main__":
    print("Validating report_rc interface...")

    # Check permissions first
    has_permissions = check_token_permissions()

    if has_permissions:
        test_report_rc_interface()
        test_with_manual_call()
    else:
        print("Cannot test: insufficient token permissions for report_rc interface")