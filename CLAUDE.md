# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

aspipe_v4 is a comprehensive financial data pipeline system that downloads stock market data from TuShare API and stores it in Parquet format. The system is designed to work with different TuShare account tiers (积分/points) and automatically adapts its data access based on the user's account level. The system features enhanced configuration with priority-based scheduling, advanced caching, and improved error handling.

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
14. **Enhanced Config** (`app/enhanced_download_config.py`): Advanced configuration options with priorities, retry settings, rate limits, caching, and API parameters
15. **Parameter Adapters** (`app/parameter_adapters.py`): Interface for adapting API parameters across different data interfaces
16. **Configuration Adapter** (`app/config_adapter.py`): Unifies old and new config access while maintaining backward compatibility
17. **Enhanced Download Config** (`app/enhanced_download_config.py`): Supports priority-based scheduling and advanced interface settings
18. **Stock List Manager** (`app/stock_list_manager.py`): Singleton pattern implementation to prevent duplicate stock_basic API calls
19. **Cache Key Generator** (`app/cache_key_generator.py`): Standardized cache key and path generation for consistent caching
20. **Cache Manager** (`app/cache_manager.py`): Cache management with preheating, cleanup, and monitoring capabilities
21. **Cache Monitor** (`app/cache_monitor.py`): Cache performance monitoring with hit rate tracking
22. **Download Strategies** (`app/download_strategies.py`): Strategy pattern implementation with DailyDataStrategy, FinancialDataStrategy, and StaticDataStrategy
23. **Strategy Factory** (`app/strategy_factory.py`): Provides unified strategy creation and caching with registry management

### Key Modules
- **Main Entry Point**: `app/main.py` - Unified entry point for all data downloads with fallback capability
- **Enhanced Main Downloader**: `app/enhanced_main_downloader.py` - Production-ready enhanced downloader with strategy pattern
- **Score-Based Downloader**: `app/score_based_downloader.py` - Download management based on user积分 levels
- **Configuration**: `app/config.py` - Environment variable loading and API limit configuration
- **Enhanced Configuration**: `app/enhanced_download_config.py` - Advanced interface configuration with priority, retries, rate limits, and caching
- **Configuration Adapter**: `app/config_adapter.py` - Maintains backward compatibility with old config format
- **Task Queue Manager**: `app/task_queue_manager.py` - Task queue management with priority and status tracking
- **Interface Modules**: `app/interfaces/` - Modularized API interfaces for different data types
- **Utils**: `app/utils/` - Helper functions for date handling and other utilities
- **Download Strategies**: `app/download_strategies.py` - Strategy pattern for different download approaches (DailyDataStrategy, FinancialDataStrategy, StaticDataStrategy)
- **Strategy Factory**: `app/strategy_factory.py` - Centralized strategy creation and registration with caching

## Data Categories by Score Level

- **120+ points**: Basic info (trade_cal) - now with HIGH priority and batch download strategy
- **2000+ points**: Stock basics, daily data, financial statements, holders, events, moneyflow - HIGH priority interfaces
- **3000+ points**: ST stock lists and additional holder data - MEDIUM priority interfaces
- **5000+ points**: Advanced data (cyq_chips, cyq_perf, stk_factor), advanced funds flow, and all financial VIP APIs - MEDIUM to LOW priority
- **8000+ points**: Advanced research data - LOW priority interfaces

## Key Features

1. **Token Management**: Automatic token switching between primary and secondary tokens when rate limits are reached
2. **Rate Limiting**: Smart rate limiting with randomization to avoid API detection using token bucket algorithm
3. **Retry Mechanisms**: Comprehensive retry logic with configurable retry counts and exponential backoff
4. **Pagination**: Automatic pagination for large datasets with configurable batch sizes
5. **Data Validation**: Basic data validation and cleaning
6. **Caching**: Data caching with freshness checks and configurable TTL (Time To Live)
7. **Logging**: Comprehensive logging in Chinese with detailed progress tracking
8. **Parallel Processing**: Production-ready parallel download capabilities with task scheduling
9. **Strategy Pattern**: Flexible download strategies for different data types (batch, parallel, sequential, paginated)
10. **Task Prioritization**: Priority-based task scheduling with queue management (HIGH, MEDIUM, LOW priorities)
11. **Configuration Management**: Advanced configuration with backward compatibility and enhanced settings
12. **Producer-Consumer Pattern**: Efficient data pipeline with separate download and storage workers
13. **Enhanced Configuration**: Detailed interface settings including priority, retries, rate limits, concurrency, and caching
14. **Config Adapter Pattern**: Maintains compatibility between old and new configuration formats
15. **Concurrency Control**: Configurable concurrency levels per interface to optimize throughput within API limits
16. **API Parameter Configuration**: Interface-specific API parameters can be set in configuration
17. **Full History Download**: Specialized downloader for interfaces that require ts_code parameters, enabling bulk downloads of all historical data for all stocks
18. **Advanced Caching System**: Multi-layer caching with intelligent cache key generation, TTL management, and cache warming capabilities
19. **Singleton Pattern Implementation**: Stock list manager using singleton pattern to prevent duplicate API calls
20. **Enhanced Error Handling**: Improved retry mechanisms with exponential backoff and adaptive rate limiting
21. **Dependency-Aware Task Queue**: Task queue management with dependency tracking between tasks
22. **Intelligent Cache Matching**: Can extract specific data from more general caches (e.g., single stock data from all-stock cache)
23. **Cache Preheating**: Proactive cache warming for frequently accessed data ranges
24. **Cache Monitoring**: Real-time tracking of cache hit rates and performance metrics
25. **Date Range Optimization**: Smart date range handling with overlap detection and merging
26. **Parameter Validation Framework**: Comprehensive parameter validation and normalization for all interfaces
27. **Configuration Backward Compatibility**: Seamless integration between old boolean config and new detailed interface config
28. **Historical Download Tracking**: Tracks completed historical downloads to avoid redundant processing
29. **Conditional Interface Management**: Automatically disables ts_code-dependent interfaces during date range downloads to prevent conflicts
30. **Strategy Pattern Implementation**: Different download strategies for different data types (DailyDataStrategy, FinancialDataStrategy, StaticDataStrategy)
31. **Strategy Factory Pattern**: Centralized strategy creation and caching with registry management
32. **Parameter Adaptation System**: Interface-specific parameter validation and standardization through adapter pattern

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

# Use legacy mode (skip new scheduler)
python app/main.py --start_date 20230101 --end_date 20231231 --use_legacy

# Enable download of stk_rewards, top10_holders, pledge_detail, fina_audit shareholder data
python app/main.py --start_date 20230101 --end_date 20231231 --holders-data

# Download only pro_bar adjusted price data
python app/main.py --start_date 20230101 --end_date 20231231 --pro-bar-only

# Download full historical data instead of date-range data (for specific interfaces that require ts_code)
python app/main.py --start_date 20230101 --end_date 20231231 --tscode-historical

# The --tscode-historical flag automatically handles ts_code-dependent interfaces like:
# stk_rewards, top10_holders, pledge_detail, fina_audit, and pro_bar
# These interfaces are automatically disabled during date-range downloads to prevent conflicts

# Download with historical download tracking to avoid redundant processing
python app/main.py --start_date 20230101 --end_date 20231231 --track-history

# Force re-download of historically completed interfaces
python app/main.py --start_date 20230101 --end_date 20231231 --force-redownload
```

### Development Tasks
```bash
# To run specific data type downloads, you can import and use the TuShareDownloader
# in custom scripts or interactive sessions

# For testing individual modules:
python app/interfaces/basic_data.py  # Example for testing individual modules
python app/test_enhanced_features.py  # Test the enhanced features

# To check available interfaces for your score level:
python -c "from score_config import get_available_data_types; from config import TUSHARE_POINTS; print(get_available_data_types(TUSHARE_POINTS))"

# Quick interface verification scripts for validating all API endpoints
python app/test_interface_verification.py

# Cache functionality tests demonstrating the enhanced caching system
python app/test_cache_functionality.py

# New comprehensive cache tests (moved to test/ directory)
python -m pytest test/test_cache_functions.py
python -m pytest test/test_cache_integration.py
python -m pytest test/test_cache_verification.py
python -m pytest test/test_cache_verification_clean.py
python -m pytest test/test_cache_holder_data.py
python -m pytest test/test_new_cache_implementation.py
python -m pytest test/test_imports.py

# Full history download tests for ts_code-dependent interfaces
python app/test_full_history_downloads.py
```

## File Structure
```
aspipe_v4/
├── app/                    # Main application code
│   ├── main.py            # Main entry point with fallback
│   ├── enhanced_main_downloader.py  # Production-ready enhanced downloader with strategy pattern
│   ├── score_based_downloader.py  # Score-based download management
│   ├── config.py          # Configuration and token management
│   ├── score_config.py    # Score-based access control
│   ├── tushare_api.py     # Main API integration (Facade Pattern)
│   ├── date_range_downloader.py  # Legacy date range downloader
│   ├── download_config.py  # Original download configuration (backward compatibility)
│   ├── enhanced_download_config.py  # Enhanced download configuration with advanced options
│   ├── config_adapter.py  # Configuration adapter for backward compatibility
│   ├── data_storage.py    # Data storage and caching
│   ├── download_scheduler.py  # Producer-consumer scheduler
│   ├── parallel_downloader.py # Parallel download framework
│   ├── storage_worker.py  # Data storage consumer logic
│   ├── download_strategies.py # Strategy pattern for different download approaches
│   ├── global_rate_limiter.py  # Global rate limiting with token bucket
│   ├── strategy_factory.py    # Strategy management with caching
│   ├── parameter_adapters.py  # API parameter adaptation
│   ├── error_handler.py   # Enhanced error handling with retry mechanisms
│   ├── stock_list_manager.py  # Singleton stock list management
│   ├── cache_key_generator.py # Standardized cache key generation
│   ├── cache_manager.py       # Cache management and preheating
│   ├── cache_monitor.py       # Cache monitoring
│   ├── task_queue_manager.py  # Task queue management with priority and status tracking
│   ├── interfaces/        # Modular interface classes
│   │   ├── base.py        # Base interface functionality
│   │   ├── basic_data.py  # Basic data interface (stock_basic, etc.)
│   │   ├── daily_data.py  # Daily data interface (daily, daily_basic, etc.)
│   │   ├── financial_data.py  # Financial data interface (income, balancesheet, etc.)
│   │   ├── market_flow.py     # Money flow data interface
│   │   ├── holders_data.py    # Stock holders data interface
│   │   ├── holders_data_downloader.py  # Full history holder data downloader
│   │   ├── technical_factors.py  # Technical factors interface
│   │   ├── cyq_chips.py       # CYQ chips data interface
│   │   ├── market_structure.py # Market structure data interface
│   │   └── research_data.py   # Research data interface
│   └── utils/             # Utility functions
│       └── date_utils.py      # Date utility functions
├── test/                  # Test scripts (including new cache functionality tests)
├── data/                  # Output directory for downloaded data
├── log/                   # Log files
├── cache/                 # Temporary cache files
├── requirements.txt       # Dependencies
├── .env                   # Environment variables
├── test/                  # Test scripts
└── p/                     # Documentation
```

## Development Notes

- All logging is in Chinese for better readability
- The system uses pandas for data processing and pyarrow for Parquet storage
- Rate limiting includes randomization to avoid API detection using token bucket algorithm
- Multiple token support allows for increased data access
- Error messages include specific handling for common TuShare API responses
- Data is automatically paginated for large result sets
- New architecture uses producer-consumer pattern for efficient data pipeline
- Strategy pattern enables flexible handling of different data types (DailyDataStrategy, FinancialDataStrategy, StaticDataStrategy)
- Task queue management with priorities optimizes resource usage
- Enhanced configuration system provides granular control over interface settings
- Configuration adapter maintains backward compatibility while adding advanced features
- Priority-based scheduling ensures critical data (like trade_cal) is downloaded first
- Caching mechanism reduces redundant API calls and improves performance
- Advanced retry mechanisms with configurable parameters for different interfaces
- Concurrency controls allow optimized throughput within API rate limits
- Interface-specific API parameters can be configured for fine-grained control
- The system features enhanced error handling, rate limiting, caching, and asynchronous processing
- Asynchronous producer-consumer pattern decouples download and storage operations for better resource utilization
- Intelligent cache matching allows extracting specific data from more general caches
- Cache preheating proactively warms frequently accessed data ranges
- Cache monitoring tracks hit rates and performance metrics in real-time
- Date range optimization intelligently handles overlaps and merges ranges
- Parameter validation framework ensures consistent and valid API parameters
- Configuration backward compatibility seamlessly integrates old and new config formats
- Singleton pattern implementation prevents duplicate stock_basic API calls
- Full history download capabilities enable bulk downloads for ts_code-dependent interfaces
- Dependency-aware task queue management tracks task relationships
- Historical download tracking automatically marks interfaces as completed after full historical downloads
- Conditional interface management automatically disables ts_code-dependent interfaces during date-range downloads to prevent parameter conflicts
- Strategy factory pattern provides centralized strategy creation and caching with registry management
- Download strategies implement different approaches for different data types (DailyDataStrategy, FinancialDataStrategy, StaticDataStrategy)