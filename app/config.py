"""
Configuration management for aspipe_v4 with automatic fallback support
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv('/home/quan/testdata/aspipe_v4/.env')

# TuShare configuration - Primary token
TUSHARE_TOKEN = os.getenv('tushare_token')
TUSHARE2_TOKEN = os.getenv('tushare2_token')

if not TUSHARE_TOKEN:
    if TUSHARE2_TOKEN:
        # Fallback to second token if primary is not available
        TUSHARE_TOKEN = TUSHARE2_TOKEN
        TUSHARE_POINTS = int(os.getenv('tushare2_points', '2000'))
        PROXY_URL = os.getenv('PROXY_URL2', '')
        print("Using secondary token as primary")
    else:
        raise ValueError("No TUSHARE_TOKEN found in environment variables")
else:
    # Use primary token configuration
    TUSHARE_POINTS = int(os.getenv('tushare_points', '120'))  # Default to 120 if not specified
    PROXY_URL = os.getenv('PROXY_URL')

# Store both tokens for availability check
PRIMARY_TOKEN = os.getenv('tushare_token')
SECONDARY_TOKEN = os.getenv('tushare2_token')

# API limits configuration
API_LIMITS = {
    'daily': {'calls_per_minute': 500},  # Adjust based on your token's permissions
    'stock_basic': {'calls_per_minute': 200},
    'daily_basic': {'calls_per_minute': 500},
    # Add other API limits as needed
}

# Data directory configuration
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

# Default parameters
DEFAULT_START_DATE = '20100101'
DEFAULT_END_DATE = '20231231'
STOCK_LIMIT = 50  # Limit for first phase