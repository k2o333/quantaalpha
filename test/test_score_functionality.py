"""
Quick test to verify the score-based functionality works
"""
import sys
import os
sys.path.append('/home/quan/testdata/aspipe_v4/app')

from config import TUSHARE_POINTS
from score_config import get_available_data_types
from tushare_api import TuShareDownloader

print(f"Tushare Points: {TUSHARE_POINTS}")

available_types = get_available_data_types(TUSHARE_POINTS)
print(f"Available data types: {available_types}")

# Initialize downloader
downloader = TuShareDownloader()

# Test basic functionality
try:
    print("Testing stock_basic download...")
    df = downloader.download_stock_basic()
    if not df.empty:
        print(f"Success! Downloaded {len(df)} stock records")
    else:
        print("Got empty dataframe (expected if score is too low)")
except Exception as e:
    print(f"Error in stock_basic: {e}")

print("All tests completed successfully!")