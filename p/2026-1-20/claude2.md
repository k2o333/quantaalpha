# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

aspipe_v4 is a configuration-driven financial data pipeline for downloading Chinese stock market data from TuShare API and storing it efficiently in Parquet format. The system implements a **zero-code extensibility** pattern where new data interfaces can be added simply by creating YAML configuration files.

**Key Innovation**: A single generic downloader replaces dozens of interface-specific classes through declarative configuration.

## Core Architecture

The system follows a configuration-driven design with these key principles:
- **Configuration over code**: All interface behavior defined in YAML files
- **Universal generic downloader**: One downloader handles all 56+ interfaces
- **Asynchronous producer-consumer pattern**: Non-blocking I/O for high throughput
- **High-performance processing**: Uses Polars for 2-5x speedup over Pandas
- **Intelligent caching**: TTL-based caching with trade calendar derivation
- **Coverage management**: Duplicate detection to avoid redundant downloads

## Core Components

### 1. Generic Downloader (`app4/core/downloader.py`)
Universal download engine that processes any interface based on YAML configuration.

**Key Features**:
- Session management with HTTP retry (exponential backoff, connection pooling)
- Multiple pagination modes:
  - `date_range`: Time-series data with sliding windows
  - `stock_loop`: Per-stock iteration
  - `offset`: Traditional offset/limit pagination
  - `period_range`: Quarterly/periodic financial data
  - `periodic_range`: Fixed period cycles (day/week/month/quarter/year)
- Performance monitoring with alert thresholds
- Memory-efficient runtime caching
- Thread-safe operations

### 2. Configuration Loader (`app4/core/config_loader.py`)
Loads and validates YAML configurations for global settings and 56+ interfaces.

**Features**:
- Environment variable substitution using `${VAR}` syntax
- Comprehensive validation and integrity checks
- Supports per-interface configuration overrides

### 3. Data Processor (`app4/core/processor.py`)
High-performance data validation and transformation using Polars.

**Processing Pipeline**:
1. Apply derived fields (date conversions, boolean types)
2. Filter null primary keys
3. Validate primary key integrity
4. Remove duplicates
5. Data cleaning and validation

**Key Design**: Raw API data is preserved; optimized types (dates, booleans) created as derived fields for better query performance.

### 4. Storage Manager (`app4/core/storage.py`)
Asynchronous data persistence with producer-consumer pattern.

**Features**:
- Non-blocking I/O with queue management
- Batch processing (default: 10,000 records)
- Interface-level buffering (5,000 record threshold)
- Dataset-mode Parquet storage
- Deduplication against existing data
- Thread-safe operations

### 5. Coverage Manager (`app4/core/coverage_manager.py`)
Intelligent duplicate detection to avoid redundant downloads.

**Detection Strategies**:
- `date_range`: Check date coverage with threshold
- `period`: Check period existence (quarterly data)
- `stock`: Check stock-specific data existence

### 6. Deduplication Module (`app4/core/dedup.py`)
Unified data deduplication with statistics tracking.

**Features**:
- Flexible primary key configuration
- Multiple keep strategies (first/last/latest_date)
- Performance metrics (processing time, dedup rate)
- Hash-based duplicate detection

### 7. Task Scheduler (`app4/core/scheduler.py`)
Concurrent task execution with rate limiting.

**Features**:
- ThreadPoolExecutor for parallel tasks
- Token bucket algorithm for API rate limiting
- Randomized delay jitter to avoid detection

### 8. Cache Manager (`app4/core/cache_manager.py`)
TTL-based data caching with intelligent cache derivation.

**Features**:
- Hash-based filenames for cache storage
- Pickle and Parquet format support
- Atomic write operations prevent corruption
- Trade calendar derivation for optimized cache hits

### 9. Schema Manager (`app4/core/schema_manager.py`)
Pre-defined data type schemas to avoid runtime inference overhead.

### 10. Date Converter (`app4/core/date_converter.py`)
Date handling utilities for TuShare API date formats.

## Configuration Structure

### Global Configuration (`app4/config/settings.yaml`)
Defines system-wide settings:
- TuShare API credentials and points thresholds
- Concurrency limits (default: 4 workers)
- Request retry and timeout settings
- Cache configuration (TTL: 24 hours, max: 10GB)
- Storage settings (Parquet format, batch size: 10,000)
- Logging configuration
- Interface groups for batch operations

**Important**: Use environment variables for credentials:
```yaml
tushare:
  token: "${TUSHARE_TOKEN}"
  # Will be loaded from .env file
```

### Interface Configuration (`app4/config/interfaces/*.yaml`)
Each of 56 interfaces has a YAML file defining:

**Required Sections**:
- `api_name`: TuShare API endpoint name
- `description`: Interface purpose (Chinese)
- `permissions`: min_points, rate_limit, query_limit
- `pagination`: mode, parameters, window sizes
- `parameters`: API parameter definitions with types and validation
- `output`: primary_key, sort_by, columns, dedup settings

**Optional Sections**:
- `derived_fields`: Type conversions (dates, booleans) for optimized queries
- `duplicate_detection`: Coverage check settings
- `special_handling`: Interface-specific logic flags

**Example** (`app4/config/interfaces/daily.yaml`):
```yaml
api_name: daily
description: 日线行情

permissions:
  min_points: 0
  rate_limit: 120
  query_limit: 10000

pagination:
  enabled: true
  mode: date_range
  window_size_days: 1

parameters:
  ts_code: {type: string, required: false}
  start_date: {type: string, required: false}
  end_date: {type: string, required: false}

output:
  primary_key: [ts_code, trade_date]
  sort_by: [trade_date]
  dedup_enabled: true

derived_fields:
  trade_date_dt:
    source: trade_date
    type: date
    format: '%Y%m%d'
```

## Interface Groups

The system organizes 56 interfaces into logical groups:

- **tscode_historical** (17): Requires stock code loops (e.g., stk_rewards, income_vip, top10_holders)
- **holders** (9): Shareholder data
- **financial_vip** (7): VIP financial statements
- **financial_basic** (8): Basic financial data
- **daily** (8): Daily market data
- **moneyflow** (7): Capital flow indicators
- **features** (5): Technical indicators (cyq_chips, stk_factor)
- **company_info** (5): Basic company information
- **others** (12): Miscellaneous data types

## Data Flow

**Standard Download Flow**:
```
CLI Entry → Config Loader → Task Scheduler → Generic Downloader
                                                    ↓
                                            API Request
                                                    ↓
                                            Data Processor
                                                    ↓
                                            Coverage Check
                                                    ↓
                                            Storage Manager
                                                    ↓
                                            Parquet Files
```

**Asynchronous Storage**:
```
Downloader → Buffer (5k records) → Process Queue → Writer Thread → Disk
```

## Development Commands

### Environment Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file with required environment variables:
TUSHARE_TOKEN=your_token_here
TUSHARE_POINTS=your_points_here
# Optional secondary token:
# TUSHARE2_TOKEN=secondary_token
# TUSHARE2_POINTS=secondary_points
```

**Required Dependencies**:
- `tushare>=1.2.61` - TuShare API client
- `polars>=0.18.0` - High-performance DataFrame
- `pandas>=1.5.0` - Legacy support
- `pyarrow>=11.0.0` - Parquet format
- `python-dotenv>=1.0.0` - Environment config
- `requests>=2.28.0` - HTTP client

### Running the System

**Basic Usage**:
```bash
# Download all available interfaces for date range
python app4/main.py --start_date 20230101 --end_date 20231231

# Download specific interface
python app4/main.py --interface daily --start_date 20230101 --end_date 20231231

# Download interface group
python app4/main.py --group financial --start_date 20230101 --end_date 20231231

# Download with specific stock code
python app4/main.py --interface daily --ts_code 000001.SZ --start_date 20230101 --end_date 20231231
```

**Configuration & Debugging**:
```bash
# List all available interfaces
python app4/main.py --list-interfaces

# Show configuration for specific interface
python app4/main.py --show-config daily

# Set log level
python app4/main.py --log-level DEBUG --interface daily

# Set concurrency level (default: 4)
python app4/main.py --concurrency 8 --group daily
```

**Special Modes**:
```bash
# Download stock loop interfaces (holders data)
python app4/main.py --holders-data --start_date 20230101 --end_date 20231231

# Download pro_bar data only (adjusted prices)
python app4/main.py --pro-bar-only --start_date 20230101 --end_date 20231231

# Download full historical data for ts_code-dependent interfaces
python app4/main.py --tscode-historical --start_date 20230101 --end_date 20231231
```

### Adding New Interfaces

To add a new TuShare interface:

1. Create a YAML file in `app4/config/interfaces/` (e.g., `new_interface.yaml`)
2. Define all required sections (see configuration structure above)
3. Add interface name to appropriate group in `app4/config/settings.yaml`
4. Run the system - the generic downloader handles everything else

**No code changes required!**

## File Structure

```
aspipe_v4/
├── app4/                       # Main application
│   ├── __init__.py            # Version: 4.0.0
│   ├── main.py                # CLI entry point (~800 lines)
│   ├── README.md              # Chinese documentation
│   ├── requirements.txt       # App4 dependencies
│   ├── core/                  # Core components (10 modules, ~3500 lines)
│   │   ├── cache_manager.py   # TTL-based caching
│   │   ├── config_loader.py   # YAML loader with validation
│   │   ├── coverage_manager.py # Duplicate detection
│   │   ├── date_converter.py  # Date utilities
│   │   ├── dedup.py           # Unified deduplication
│   │   ├── downloader.py      # Generic downloader (~1200 lines)
│   │   ├── processor.py       # Polars data processing
│   │   ├── scheduler.py       # Task scheduling & rate limiting
│   │   ├── schema_manager.py  # Schema definitions
│   │   └── storage.py         # Async storage manager
│   ├── config/                # Configuration files
│   │   ├── settings.yaml      # Global configuration
│   │   └── interfaces/        # 56 interface YAML files
│   └── utils/                 # Utility functions
│       └── config_converter.py # Legacy config conversion
├── requirements.txt           # Main dependencies
├── .env                       # Environment variables (create this)
├── .gitignore                 # Git ignore rules
├── CLAUDE.md                  # This file
├── data/                      # Output directory (auto-created)
├── cache/                     # Cache directory (auto-created)
└── log/                       # Log directory (auto-created)
```

## Data Categories by TuShare Points Level

Access to interfaces depends on your TuShare points level:

- **120+ points**: Basic info (trade_cal, stock_basic)
- **2000+ points**: Daily data, basic financial statements, basic holders data
- **3000+ points**: ST stock lists, additional holder data
- **5000+ points**: Advanced data (cyq_chips, stk_factor), advanced money flow, VIP financial APIs
- **8000+ points**: Advanced research data (broker_recommend, concept_detail)

Check your available interfaces:
```bash
python app4/main.py --list-interfaces
```

## Key Design Patterns

**Configuration-Driven Architecture**:
- All interface behavior defined declaratively in YAML
- Single generic downloader replaces dozens of specific classes
- Zero-code extensibility for new interfaces

**Producer-Consumer Pattern**:
- Download tasks produced by scheduler
- Storage operations consume from queue
- Non-blocking I/O for high throughput

**Token Bucket Rate Limiting**:
- API rate limit protection
- Randomized jitter to avoid detection
- Per-interface rate limit configuration

**Derived Fields Pattern**:
- Raw API data preserved unchanged
- Optimized types (dates, booleans) created as derived fields
- Better query performance without data loss

**Coverage Management**:
- Multiple detection strategies (date_range, period, stock)
- Memory caching for efficient lookups
- Avoids redundant downloads

## Performance Optimizations

1. **Polars over Pandas**: 2-5x performance improvement for data processing
2. **Async I/O**: Non-blocking storage operations
3. **Connection Pooling**: Reuse HTTP connections (10 pool, 20 max)
4. **Batch Processing**: Default 10,000 records per batch
5. **Memory Caching**: Runtime cache for frequently accessed data
6. **Parquet Dataset Mode**: Efficient columnar storage format
7. **Trade Calendar Derivation**: Smart cache hit optimization

## Development Notes

- All logging is in Chinese for better readability
- The system uses Polars for high-performance data processing
- Rate limiting includes randomization to avoid API detection
- Supports multiple TuShare tokens for increased access
- Atomic write operations prevent data corruption during concurrent access
- Thread-safe operations throughout the codebase
- Comprehensive error handling with retry mechanisms
- Failed interfaces tracked separately for debugging

## Common Patterns

**Adding a derived date field**:
```yaml
derived_fields:
  trade_date_dt:
    source: trade_date
    type: date
    format: '%Y%m%d'
```

**Configuring pagination for daily data**:
```yaml
pagination:
  enabled: true
  mode: date_range
  window_size_days: 1
```

**Configuring pagination for quarterly financial data**:
```yaml
pagination:
  enabled: true
  mode: period_range
  period_type: quarterly
  max_periods_per_request: 10
```

**Configuring stock loop for holder data**:
```yaml
pagination:
  enabled: true
  mode: stock_loop
  window_size_days: 3650  # 10 years of historical data
```

## Troubleshooting

**Rate Limit Errors**:
- Check your TuShare points level
- Verify interface permissions in YAML config
- Reduce concurrency with `--concurrency 2`

**Missing Data**:
- Check if interface requires specific TuShare points
- Verify date range is valid for the interface
- Check logs in `log/app4.log` for API errors

**Performance Issues**:
- Increase batch size in `settings.yaml` (storage.batch_size)
- Increase concurrency for CPU-bound tasks
- Check cache hit rates in logs
- Monitor memory usage with large datasets

**Configuration Errors**:
- Validate YAML syntax
- Check required fields are present
- Use `--show-config <interface>` to debug

## Architecture Benefits

- **Zero-code extensibility**: Add interfaces without code changes
- **Declarative configuration**: Behavior defined in readable YAML
- **Type safety**: Comprehensive parameter validation
- **High performance**: Polars, async I/O, connection pooling
- **Production ready**: Error handling, monitoring, rate limiting
- **Maintainability**: Single downloader vs. dozens of classes
- **Flexibility**: Easy to modify interface behavior via config
