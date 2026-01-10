# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

aspipe_v4 is a comprehensive financial data pipeline system that downloads stock market data from TuShare API and stores it in Parquet format. The system features two parallel architectures:

1. **Legacy Architecture (app/)**: Traditional code-driven approach with modular interface classes
2. **App4 Architecture (app4/)**: Modern configuration-driven approach with zero-code interface addition capability

The App4 architecture represents a paradigm shift from code-driven to configuration-driven data downloading, offering higher flexibility, stronger performance, and better maintainability.

## Architecture Comparison

### Legacy Architecture (app/) - Traditional Code-Driven
- Modular interface classes for each data category
- Strategy pattern implementation for different download approaches
- Producer-consumer pattern with task prioritization
- Advanced caching and error handling mechanisms

### App4 Architecture (app4/) - Modern Configuration-Driven
- **Zero-code interface addition**: Add new interfaces by creating YAML configuration files
- **Universal downloader**: Single generic downloader handles all interfaces based on configuration
- **Multi-strategy pagination**: Supports offset, date_range, stock_loop, period_range, quarterly_range, and periodic_range pagination modes
- **Asynchronous architecture**: Producer-consumer pattern with non-blocking I/O
- **High-performance processing**: Uses Polars for data processing and validation
- **Coverage management**: Intelligent duplicate detection to avoid redundant downloads
- **Performance monitoring**: Built-in metrics collection and alerting system

## App4 Configuration-Driven Architecture

### Core Components

1. **Configuration Loader** (`app4/core/config_loader.py`)
   - Loads global settings and interface configurations from YAML files
   - Supports environment variable substitution with `${VAR}` syntax
   - Performs configuration validation and integrity checks

2. **Generic Downloader** (`app4/core/downloader.py`)
   - Universal download engine that processes any interface based on configuration
   - Implements multiple pagination strategies (offset, date_range, stock_loop, period_range)
   - Features intelligent caching with trade calendar derivation strategy
   - Monitors performance metrics (request time, data size, retry count)

3. **Task Scheduler** (`app4/core/scheduler.py`)
   - Manages thread pool for concurrent task execution
   - Implements token bucket algorithm for API rate limiting
   - Supports batch task submission with randomized delays

4. **Cache Manager** (`app4/core/cache_manager.py`)
   - TTL-based data caching with hash-based filenames
   - Supports pickle and parquet storage formats
   - Atomic write operations prevent concurrent file corruption
   - Smart trade calendar derivation for optimized cache hits

5. **Storage Manager** (`app4/core/storage.py`)
   - Asynchronous data persistence using producer-consumer pattern
   - Batch processing and append operations to existing parquet files
   - Thread-safe operations with queue management

6. **Data Processor** (`app4/core/processor.py`)
   - High-performance data validation and transformation using Polars
   - Primary key processing and deduplication
   - Data quality checks and type conversion

7. **Schema Manager** (`app4/core/schema_manager.py`)
   - Pre-defined data type schemas to avoid runtime inference overhead
   - Optimized schemas for high-frequency financial data interfaces

8. **Coverage Manager** (`app4/core/coverage_manager.py`)
   - Implements duplicate detection to avoid redundant downloads
   - Supports multiple strategies: date_range, period, and stock-based detection
   - Uses memory caching for efficient coverage checks

### Configuration Structure

#### Global Configuration (`app4/config/settings.yaml`)
```yaml
app:
  name: "aspipe_v4"
  version: "4.0.0"

tushare:
  token: "${TUSHARE_TOKEN}"
  base_url: "http://api.tushare.pro"
  points_thresholds: # 积分权限映射
    basic: 120
    standard: 2000
    advanced: 5000
    professional: 8000

concurrency:
  max_workers: 4  # [修改] 从 8 改为 4
  max_queue_size: 1000

request:
  max_retries: 3
  retry_delay: 1.0
  timeout: 30

cache:
  directory: "cache"
  ttl_hours: 24
  max_size_gb: 10

storage:
  base_dir: "../data"  # [修改] 从 "data" 改为 "../data"
  format: "parquet"
  batch_size: 10000  # [优化] 从 1000 增大到 10000

logging:
  level: "INFO"
  file: "log/app4.log"
  max_size_mb: 100
  backup_count: 5

groups:
  tscode_historical:
    - "stk_rewards"
    - "top10_holders"
    - "pledge_detail"
    - "fina_audit"
    - "top10_floatholders"
    - "stk_holdertrade"
  holders:
    - "top10_holders"
    - "top10_floatholders"
    - "stk_rewards"
    - "pledge_detail"
    - "fina_audit"
    - "stk_holdertrade"
  daily:
    - "daily"
    - "daily_basic"
    - "adj_factor"
    - "moneyflow"
  financial:
    - "income"
    - "balancesheet"
    - "cashflow"
    - "fina_indicator"
    - "fina_audit"
    - "fina_mainbz"
  basic:
    - "stock_basic"
    - "trade_cal"
    - "namechange"
    - "stock_company"
```

#### Interface Configuration (`app4/config/interfaces/*.yaml`)
Each interface has its own YAML configuration defining:
- API metadata (name, description, permissions)
- Request parameters and validation rules
- Pagination strategy and parameters
- Output schema and primary keys
- Rate limiting and caching settings

Example interface configuration:
```yaml
name: daily
api_name: daily
description: "日线行情"

permissions:
  min_points: 0
  rate_limit: 120
  query_limit: 10000

pagination:
  enabled: true
  mode: "date_range"
  window_size_days: 365

parameters:
  ts_code:
    type: string
    required: false
    description: "证券代码"

output:
  primary_key: ["ts_code", "trade_date"]
  sort_by: ["trade_date"]
  columns:
    ts_code: {type: string, required: true}
    trade_date: {type: date, format: "%Y%m%d", required: true}

duplicate_detection:
  enabled: true
  date_column: "trade_date"
  threshold: 0.95
```

### Key Features

1. **Zero-Code Interface Addition**: New interfaces can be added by simply creating YAML configuration files
2. **Declarative Configuration**: All interface behavior defined in configuration files
3. **Flexible Pagination**: Multiple pagination modes to handle different API behaviors
4. **Asynchronous Storage**: Non-blocking I/O operations for improved throughput
5. **Intelligent Caching**: Trade calendar derivation strategy for optimal cache utilization
6. **Performance Monitoring**: Real-time tracking of key metrics with alerting
7. **Backward Compatibility**: Maintains compatibility with legacy CLI parameters
8. **High Concurrency**: Thread-pool based concurrent processing
9. **Rate Limit Protection**: Token bucket algorithm prevents API throttling
10. **Type Safety**: Comprehensive parameter validation and type checking
11. **Coverage Management**: Intelligent duplicate detection to avoid redundant downloads
12. **Memory-Efficient Caching**: Runtime cache for frequently accessed data
13. **Dataset-Mode Storage**: Efficient storage using Parquet dataset format

### Interface Groups

App4 organizes interfaces into logical groups for easier management:
- **daily**: Daily market data (daily, daily_basic, adj_factor, moneyflow)
- **financial**: Financial statements (income, balancesheet, cashflow, fina_indicator, fina_audit, fina_mainbz)
- **holders**: Shareholder data (top10_holders, top10_floatholders, stk_rewards, pledge_detail, stk_holdertrade)
- **market**: Market indicators (moneyflow, cyq_chips, stk_factor, moneyflow_ind_dc, moneyflow_cnt_ths)
- **basic**: Basic information (stock_basic, trade_cal, namechange, stock_company)
- **tscode_historical**: Interfaces requiring stock code loops (stk_rewards, top10_holders, pledge_detail, fina_audit, top10_floatholders, stk_holdertrade)

## Legacy Architecture (app/) - Reference

For reference, the legacy architecture includes:
- **TuShare API Integration**: Handles authentication and rate limiting
- **Modular Interface System**: Separate modules for different data categories
- **Download Strategies**: Strategy pattern for different data types
- **Advanced Caching**: Multi-layer caching with intelligent matching
- **Task Queue Management**: Priority-based task scheduling

See the original file structure and components in the appendix below.

### Key Modules
- **Main Entry Point**: `app/main.py` - Unified entry point for all data downloads with fallback capability
- **Enhanced Main Downloader**: `app/enhanced_main_downloader.py` - Production-ready enhanced downloader with strategy pattern
- **App4 Main Module**: `app4/main.py` - Configuration-driven architecture with enhanced optimizations
- **App4 Config Loader**: `app4/core/config_loader.py` - Configuration-driven approach with global and interface-specific settings
- **App4 Core Components**: `app4/core/` - New architecture with GenericDownloader, CacheManager, TaskScheduler, StorageManager, DataProcessor, CoverageManager
- **App4 Storage Manager**: `app4/core/storage.py` - Enhanced storage management with async operations and batch processing
- **App4 Cache Manager**: `app4/core/cache_manager.py` - Enhanced caching with atomic writes, derivation strategy, and performance optimization
- **App4 Generic Downloader**: `app4/core/downloader.py` - Enhanced downloader with data validation, network retry optimization, and performance monitoring

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

#### App4 (Recommended - Configuration-Driven)
```bash
# Basic usage - download all available interfaces
python app4/main.py --start_date 20230101 --end_date 20231231

# Download specific interface
python app4/main.py --start_date 20230101 --end_date 20231231 --interface daily

# Download interface group
python app4/main.py --start_date 20230101 --end_date 20231231 --group financial

# Set concurrency level
python app4/main.py --concurrency 4  # [修改] 默认并发数从 8 改为 4

# Set log level
python app4/main.py --log-level DEBUG

# List available interfaces
python app4/main.py --list-interfaces

# Check interface configuration
python app4/main.py --show-config daily

# Download with ts_code specified
python app4/main.py --start_date 20230101 --end_date 20231231 --interface daily --ts_code 000001.SZ

# Download stock loop interfaces (holders data)
python app4/main.py --holders-data

# Download pro_bar data only
python app4/main.py --pro-bar-only

# Download full historical data for stock loop interfaces
python app4/main.py --tscode-historical
```

#### Legacy Architecture (app/)
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

# Download with historical download tracking to avoid redundant processing
python app/main.py --start_date 20230101 --end_date 20231231 --track-history

# Force re-download of historically completed interfaces
python app/main.py --start_date 20230101 --end_date 20231231 --force-redownload
```

### Development Tasks
```bash
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

# App4 specific tests
python -m pytest test/test_app4_config_loader.py
python -m pytest test/test_app4_downloader.py
python -m pytest test/test_app4_integration.py
```

## File Structure

```
aspipe_v4/
├── app4/                  # Modern configuration-driven architecture (Recommended)
│   ├── __init__.py        # Package initialization with version info
│   ├── README.md          # Detailed App4 design documentation
│   ├── main.py            # CLI entry point with enhanced features
│   ├── core/              # Core components
│   │   ├── __init__.py
│   │   ├── config_loader.py    # YAML configuration loader
│   │   ├── downloader.py       # Universal download engine with performance monitoring
│   │   ├── processor.py        # Data processing with Polars
│   │   ├── storage.py          # Asynchronous storage manager with dataset mode
│   │   ├── cache_manager.py    # Intelligent cache management
│   │   ├── scheduler.py        # Task scheduler with rate limiting
│   │   ├── schema_manager.py   # Pre-defined data schemas
│   │   └── coverage_manager.py # Duplicate detection and coverage management
│   ├── config/            # Configuration files
│   │   ├── settings.yaml  # Global settings and defaults
│   │   └── interfaces/    # Interface definitions (40+ YAML files)
│   │       ├── daily.yaml
│   │       ├── stock_basic.yaml
│   │       ├── income.yaml
│   │       ├── balancesheet.yaml
│   │       ├── cashflow.yaml
│   │       ├── top10_holders.yaml
│   │       ├── stk_rewards.yaml
│   │       ├── pledge_detail.yaml
│   │       ├── fina_audit.yaml
│   │       ├── moneyflow.yaml
│   │       ├── trade_cal.yaml
│   │       ├── pro_bar.yaml
│   │       └── ... (30+ more interfaces)
│   ├── requirements.txt   # App4 specific dependencies
│   └── utils/             # Utility functions (currently empty)
├── app/                   # Legacy code-driven architecture
│   ├── main.py            # Main entry point
│   ├── enhanced_main_downloader.py  # Enhanced downloader
│   ├── interfaces/        # Modular interface classes
│   └── ... (other legacy modules)
├── test/                  # Test scripts
├── data/                  # Output directory for downloaded data
├── cache/                 # Temporary cache files
├── log/                   # Log files
├── requirements.txt       # Main dependencies
├── .env                   # Environment variables
└── p/                     # Documentation
```

## Data Categories by Score Level

- **120+ points**: Basic info (trade_cal) - now with HIGH priority and batch download strategy
- **2000+ points**: Stock basics, daily data, financial statements, holders, events, moneyflow - HIGH priority interfaces
- **3000+ points**: ST stock lists and additional holder data - MEDIUM priority interfaces
- **5000+ points**: Advanced data (cyq_chips, cyq_perf, stk_factor), advanced funds flow, and all financial VIP APIs - MEDIUM to LOW priority
- **8000+ points**: Advanced research data - LOW priority interfaces

## Development Notes

### App4 Architecture Benefits
- **Zero-code extensibility**: Add interfaces without writing code
- **Declarative configuration**: All behavior defined in YAML files
- **Type safety**: Comprehensive parameter validation
- **High performance**: Polars for data processing, async I/O
- **Intelligent caching**: Trade calendar derivation strategy
- **Production ready**: Comprehensive error handling and monitoring
- **Coverage management**: Avoid redundant downloads with duplicate detection
- **Memory-efficient**: Runtime caching for frequently accessed data
- **Dataset storage**: Efficient data access using Parquet dataset format

### Legacy Architecture Notes
- All logging is in Chinese for better readability
- The system uses pandas for data processing and pyarrow for Parquet storage
- Rate limiting includes randomization to avoid API detection
- Multiple token support allows for increased data access
- Error messages include specific handling for common TuShare API responses

## Migration Guide

When migrating from legacy (app/) to App4 architecture:

1. **Configuration Migration**: Legacy boolean flags are automatically converted to App4 configurations
2. **CLI Compatibility**: App4 maintains backward compatibility with most legacy CLI arguments
3. **Data Format**: Both architectures produce identical parquet file formats
4. **Performance**: App4 offers 2-5x performance improvement through async processing and Polars

## Appendix: Legacy Architecture Details

For detailed information about the legacy architecture components, refer to the Git history or contact the development team.
- **Enhanced Configuration**: `app/enhanced_download_config.py` - Advanced interface configuration with priority, retries, rate limits, and caching
- **Configuration Adapter**: `app/config_adapter.py` - Maintains backward compatibility with old config format
- **App4 Core Components**: `app4/core/` - New architecture with GenericDownloader, CacheManager, TaskScheduler, StorageManager, DataProcessor, CoverageManager
- **Task Queue Manager**: `app/task_queue_manager.py` - Task queue management with priority and status tracking
- **Interface Modules**: `app/interfaces/` - Modularized API interfaces for different data types
- **Utils**: `app/utils/` - Helper functions for date handling and other utilities
- **Download Strategies**: `app/download_strategies.py` - Strategy pattern for different download approaches (DailyDataStrategy, FinancialDataStrategy, StaticDataStrategy)
- **Strategy Factory**: `app/strategy_factory.py` - Centralized strategy creation and registration with caching
- **Parameter Adapters**: `app/parameter_adapters.py` - Standardized parameter validation and adaptation for all interfaces
- **Data Storage**: `app/data_storage.py` - Data storage and caching with intelligent cache matching
- **App4 Storage Manager**: `app4/core/storage.py` - Enhanced storage management with async operations and batch processing
- **Cache Key Generator**: `app/cache_key_generator.py` - Standardized cache key and path generation
- **App4 Cache Manager**: `app4/core/cache_manager.py` - Enhanced caching with atomic writes, derivation strategy, and performance optimization
- **Cache Monitor**: `app/cache_monitor.py` - Cache performance monitoring with hit rate tracking
- **Stock List Manager**: `app/stock_list_manager.py` - Singleton pattern implementation to prevent duplicate API calls
- **App4 Generic Downloader**: `app4/core/downloader.py` - Enhanced downloader with data validation, network retry optimization, and performance monitoring
- **App4 Coverage Manager**: `app4/core/coverage_manager.py` - Duplicate detection to avoid redundant downloads
- **Error Handler**: `app/error_handler.py` - Enhanced error handling with retry mechanisms and API-specific error handling

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
33. **Batch Processing for TSCODE interfaces**: Efficient batch processing of ts_code-dependent interfaces for better performance
34. **Asynchronous Storage Operations**: Storage operations handled asynchronously to avoid blocking download threads
35. **Enhanced Interface Configuration**: Detailed interface settings including cache settings, API parameters, and concurrency controls
36. **App4 Configuration-Driven Architecture**: New architecture in app4/ using configuration files for interface definitions, global settings, and performance parameters
37. **Advanced Data Validation**: Comprehensive data validation and deduplication with automatic detection and removal of duplicate records using (ts_code, trade_date) as unique keys
38. **Enhanced Network Retry Mechanism**: Smart retry strategy using HTTPAdapter with connection pooling, exponential backoff, and status-specific error handling (429, 500, 502, 503, 504)
39. **Optimized Cache Strategy**: Intelligent cache derivation system that preloads global trade calendars and derives date-range subsets to improve cache hit rates significantly
40. **Performance Monitoring System**: Built-in performance metrics collection with monitoring of request times, data sizes, retry counts, and alert thresholds
41. **Thread-Safe Operations**: Thread-safe cache operations with atomic writes to prevent data corruption during concurrent access
42. **Enhanced Error Handling**: Comprehensive error handling with graceful degradation and isolated failure handling for individual stock downloads
43. **Coverage Management**: Intelligent duplicate detection to avoid redundant downloads with multiple strategies (date_range, period, stock)
44. **Memory-Efficient Caching**: Runtime cache for frequently accessed data with thread-safe operations
45. **Dataset-Mode Storage**: Efficient storage using Parquet dataset format for better performance
46. **Quarterly and Periodic Range Pagination**: Support for financial data with period_range, quarterly_range, and periodic_range pagination modes
47. **Broker Recommendation Handling**: Special handling for broker_recommend interface with month-based requests

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

# For enhanced download using production ready features (app4)
python app4/main.py --start_date 20230101 --end_date 20231231

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

# App4 specific commands with enhanced optimizations:
python app4/main.py --start_date 20230101 --end_date 20231231 --interface daily  # Download specific interface
python app4/main.py --start_date 20230101 --end_date 20231231 --group daily     # Download interface group
python app4/main.py --concurrency 4                                            # Set concurrency level (default now 4)
python app4/main.py --log-level DEBUG                                         # Set log level
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
│   │   ├── __init__.py    # Package initialization file
│   │   ├── base.py        # Base interface functionality
│   │   ├── basic_data.py  # Basic data interface (stock_basic, etc.)
│   │   ├── daily_data.py  # Daily data interface (daily, daily_basic, etc.)
│   │   ├── financial_data.py  # Financial data interface (income, balancesheet, etc.)
│   │   ├── market_flow.py     # Money flow data interface
│   │   ├── holders_data.py    # Stock holders data interface
│   │   ├── holders_data_downloader.py  # Full history holder data downloader
│   │   ├── technical_factors.py  # Technical factors interface
│   │   ├── cyq_chips.py       # CYQ chips data interface
│   │   └── research_data.py   # Research data interface
│   └── utils/             # Utility functions
│       ├── __init__.py    # Package initialization file
│       └── date_utils.py      # Date utility functions
├── app4/                  # New configuration-driven architecture (App4)
│   ├── main.py            # New main entry point with enhanced optimizations
│   ├── core/              # Core components with enhanced features
│   │   ├── __init__.py    # Package initialization
│   │   ├── config_loader.py  # Configuration loader with global and interface configs
│   │   ├── downloader.py     # Enhanced downloader with data validation and performance monitoring
│   │   ├── cache_manager.py  # Optimized cache manager with derivation strategy
│   │   ├── scheduler.py      # Task scheduler with concurrency controls
│   │   ├── storage.py        # Enhanced storage manager with async operations
│   │   └── processor.py      # Data processor with validation and transformation
│   ├── config/            # Configuration files for interfaces and global settings
│   │   ├── interfaces/    # Interface-specific configuration files
│   │   │   └── *.yaml     # YAML files for each interface
│   │   └── settings.yaml     # Global settings and defaults
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
- Parameter adaptation system provides interface-specific parameter validation and standardization
- Batch processing for ts_code-dependent interfaces improves performance by processing multiple stocks in parallel
- Asynchronous storage operations prevent blocking of download threads
- Enhanced interface configuration provides detailed settings for cache, API parameters, and concurrency
- App4 introduces configuration-driven architecture with zero-code interface addition capability
- App4 implements multiple pagination strategies: offset, date_range, stock_loop, period_range, quarterly_range, and periodic_range
- App4 features performance monitoring with real-time metrics collection and alerting
- App4 includes coverage management to detect and avoid redundant downloads using multiple strategies
- App4 uses memory-efficient caching for frequently accessed data with thread-safe operations
- App4 implements dataset-mode storage using Parquet format for improved performance
- App4 adds special handling for broker recommendation data with month-based requests