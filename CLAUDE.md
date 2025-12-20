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
6. **Download Scheduling** (`app/download_scheduler.py`): Complete download scheduler implementing producer-consumer pattern with task prioritization
7. **Parallel Downloader** (`app/parallel_downloader.py`): Parallel download framework supporting multiple concurrent interfaces with resource management
8. **Global Rate Limiter** (`app/global_rate_limiter.py`): Token bucket algorithm implementation for API call rate limiting
9. **Task Queue Manager** (`app/task_queue_manager.py`): Task queue management with priority and status tracking
10. **Storage Worker** (`app/storage_worker.py`): Consumer logic for data storage with thread-safe writes and error handling
11. **Strategy Factory** (`app/strategy_factory.py`): Strategy creation and management with caching mechanism
12. **Download Strategies** (`app/download_strategies.py`): Strategy pattern implementation for different data download approaches
13. **Config Adapter** (`app/config_adapter.py`): Adapter pattern for unified access to old and new configuration formats
14. **Enhanced Config** (`app/enhanced_download_config.py`): Advanced configuration options with priorities, retry settings, and API parameters
15. **Parameter Adapters** (`app/parameter_adapters.py`): Interface for adapting API parameters across different data interfaces

### Key Modules
- **Main Entry Point**: `app/main.py` - Unified entry point for all data downloads
- **Enhanced Main Downloader**: `app/enhanced_main_downloader.py` - Production-ready enhanced downloader with strategy pattern
- **Score-Based Downloader**: `app/score_based_downloader.py` - Download management based on user积分 levels
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
8. **Parallel Processing**: Production-ready parallel download capabilities with task scheduling
9. **Strategy Pattern**: Flexible download strategies for different data types
10. **Task Prioritization**: Priority-based task scheduling with queue management
11. **Configuration Management**: Advanced configuration with backward compatibility
12. **Producer-Consumer Pattern**: Efficient data pipeline with separate download and storage workers

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

# For enhanced download using production ready features
python app/enhanced_main_downloader.py --start_date 20230101 --end_date 20231231
```

### Development Tasks
```bash
# To run specific data type downloads, you can import and use the TuShareDownloader
# in custom scripts or interactive sessions

# For testing individual modules:
python app/interfaces/basic_data.py  # Example for testing individual modules
python app/test_enhanced_features.py  # Test the enhanced features
```

## File Structure
```
aspipe_v4/
├── app/                    # Main application code
│   ├── main.py            # Entry point for unified downloads
│   ├── enhanced_main_downloader.py  # Production-ready enhanced downloader with strategy pattern
│   ├── score_based_downloader.py  # Download management based on user积分 levels
│   ├── config.py          # Configuration and token management
│   ├── score_config.py    # Score-based access control
│   ├── tushare_api.py     # Main API integration class
│   ├── date_range_downloader.py  # Date range download implementations
│   ├── download_config.py  # Download configuration
│   ├── enhanced_download_config.py  # Enhanced download configuration with advanced options
│   ├── data_storage.py    # Data storage and caching
│   ├── download_scheduler.py  # Producer-consumer download scheduler
│   ├── parallel_downloader.py # Parallel download framework
│   ├── storage_worker.py  # Data storage consumer logic
│   ├── task_queue_manager.py # Task queue management with priorities
│   ├── download_strategies.py # Strategy pattern for different download approaches
│   ├── global_rate_limiter.py  # Global rate limiting with token bucket
│   ├── strategy_factory.py    # Strategy factory for management
│   ├── parameter_adapters.py  # API parameter adaptation
│   ├── config_adapter.py  # Interface configuration adapter
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
- New architecture uses producer-consumer pattern for efficient data pipeline
- Strategy pattern enables flexible handling of different data types
- Task queue management with priorities optimizes resource usage