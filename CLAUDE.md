# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

aspipe_v4 is a comprehensive financial data pipeline system that downloads stock market data from TuShare API and stores it in Parquet format. The system is designed to work with different TuShare account tiers (积分/points) and automatically adapts its data access based on the user's account level.

## Architecture

### Core Components
1. **TuShare API Integration** (`app/tushare_api.py`): Handles API authentication, rate limiting, retry mechanisms, and token switching between primary/secondary tokens
2. **Score-Based Access Control** (`app/score_config.py`): Maps TuShare积分 to available data interfaces and API limits
3. **Modular Interface System** (`app/interfaces/`): Separate modules for different data categories (basic, daily, financial, market flow, etc.)
4. **Data Storage** (`app/data_storage.py`): Manages saving/loading data in Parquet format with caching support
5. **Error Handling** (`app/error_handler.py`): Centralized error handling with retry mechanisms and rate limit management

### Key Modules
- **Main Entry Point**: `app/main.py` - Unified entry point for all data downloads
- **Configuration**: `app/config.py` - Environment variable loading and API limit configuration
- **Interface Modules**: `app/interfaces/` - Modularized API interfaces for different data types
- **Utils**: `app/utils/` - Helper functions for date handling and other utilities

## Data Categories by Score Level

- **120+ points**: Basic info (new_share, trade_cal, namechange)
- **2000+ points**: Stock basics, daily data, financial statements, holders, events, and basic moneyflow
- **3000+ points**: ST stock lists and additional holder data
- **5000+ points**: Advanced data (cyq_chips, cyq_perf, stk_factor), advanced funds flow, and all financial VIP APIs
- **8000+ points**: Advanced research data

## Key Features

1. **Token Management**: Automatic token switching between primary and secondary tokens when rate limits are reached
2. **Rate Limiting**: Smart rate limiting with randomization to avoid API detection
3. **Retry Mechanisms**: Comprehensive retry logic with exponential backoff
4. **Pagination**: Automatic pagination for large datasets
5. **Data Validation**: Basic data validation and cleaning
6. **Caching**: Data caching with freshness checks
7. **Logging**: Comprehensive logging in Chinese with detailed progress tracking

## Development Commands

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables in .env file:
# tushare_token=your_token
# tushare_points=your_points
# tushare2_token=secondary_token (optional)
# tushare2_points=secondary_points (optional)
```

### Running the System
```bash
# Run from the project root (not app directory)
python app/main.py --start_date 20230101 --end_date 20231231

# Default start date is 20230101, end date is today
python app/main.py
```

### Development Tasks
```bash
# To run specific data type downloads, you can import and use the TuShareDownloader
# in custom scripts or interactive sessions

# For testing individual modules:
python app/interfaces/basic_data.py  # Example for testing individual modules
```

## File Structure
```
aspipe_v4/
├── app/                    # Main application code
│   ├── main.py            # Entry point for unified downloads
│   ├── config.py          # Configuration and token management
│   ├── score_config.py    # Score-based access control
│   ├── tushare_api.py     # Main API integration class
│   ├── data_storage.py    # Data storage and caching
│   ├── error_handler.py   # Error handling and retry logic
│   ├── interfaces/        # Modular interface classes
│   └── utils/             # Utility functions
├── data/                  # Output directory for downloaded data
├── log/                   # Log files
├── cache/                 # Temporary cache files
├── requirements.txt       # Dependencies
├── .env                   # Environment variables (not committed)
├── test/                  # 所有测试脚本都放在这里，别放在app/
└── p/                     # 所有生成的文档，除了 claude.md和readme.md 都放在这里
```

## Development Notes

- All logging is in Chinese for better readability
- The system uses pandas for data processing and pyarrow for Parquet storage
- Rate limiting includes randomization to avoid API detection
- Multiple token support allows for increased data access
- Error messages include specific handling for common TuShare API responses
- Data is automatically paginated for large result sets