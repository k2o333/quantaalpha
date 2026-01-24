"""
Test script for aspipe_v4 system
"""
import sys
import os
import logging

# Add the app directory to the Python path to import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'app'))

from config import TUSHARE_TOKEN
from tushare_api import TuShareDownloader

logger = logging.getLogger(__name__)

def test_basic_functionality():
    """
    Test basic functionality without downloading all data
    """
    logger.info("🚀 Testing basic functionality...")
    
    # Test token
    logger.info(f"🔑 Token loaded: {'Yes' if TUSHARE_TOKEN else 'No'}")
    
    # Test API connection
    try:
        downloader = TuShareDownloader()
        logger.info("✅ TuShare API connection successful")
        
        # Test a quick API call to verify connection
        # We'll only fetch a minimal amount of data for testing
        test_data = downloader.download_with_retry(
            downloader.pro.stock_basic,
            exchange='',
            list_status='L',
            limit=5,  # Just get 5 records for testing
            fields='ts_code,symbol,name'
        )
        logger.info(f"✅ Test API call successful: got {len(test_data)} records")
        logger.info(f"📊 Sample data: {test_data[['ts_code', 'name']].head().values.tolist()}")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        raise
    
    logger.info("✅ All basic functionality tests passed!")

if __name__ == "__main__":
    test_basic_functionality()