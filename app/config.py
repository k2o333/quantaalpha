"""
Configuration management for aspipe_v4
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv('/home/quan/testdata/aspipe_v4/.env')

# TuShare configuration
TUSHARE_TOKEN = os.getenv('tushare_token')
if not TUSHARE_TOKEN:
    raise ValueError("TUSHARE_TOKEN not found in environment variables")

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