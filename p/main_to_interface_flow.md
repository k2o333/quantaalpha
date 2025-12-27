# Complete Call Flow from main.py to Interface Scripts with Updated Architecture

```mermaid
flowchart TD
    A[main.py] --> B[download_all_data_from_date]
    A --> C[download_with_legacy_fallback]
    C --> B
    C --> D[download_with_legacy_method]

    B --> E[download_scheduler.py run_download_schedule]
    B --> F[DownloadScheduler]
    E --> F

    F --> G[schedule_download_tasks]
    G --> H[get_available_interfaces via config_adapter]
    H --> I[config_adapter.get_all_available_interfaces]

    F --> J[execute_scheduled_tasks]
    J --> K[_task_consumer_loop]
    K --> L[Task Manager gets next task]

    L --> M[Download Task Execution]
    M --> N[download_strategies.get_strategy]
    N --> O[Facade-TuShareDownloader]

    %% Facade pattern implementation in TuShareDownloader
    O --> O1[TuShareDownloader Main Class<br/>with __getattr__ delegation]
    O1 --> O2[BasicDataDownloader Module]
    O1 --> O3[DailyDataDownloader Module]
    O1 --> O4[FinancialDataDownloader Module]
    O1 --> O5[MarketFlowDownloader Module]
    O1 --> O6[HoldersDataDownloader Module]
    O1 --> O7[TechnicalFactorsDownloader Module]
    O1 --> O8[CyqChipsDownloader Module]
    O1 --> O9[MarketStructureDownloader Module]
    O1 --> O10[ResearchDataDownloader Module]
    O1 --> O11[BaseDownloader Module]
    O1 --> O12[HoldersDataFullHistoryDownloader Module]

    %% Producer-Consumer pattern for storage
    M --> P1[Check for data download results]
    P1 --> P2[If successful, create storage task<br/>via task_manager.add_storage_task]
    P2 --> Q1[Storage Task Queue<br/>in TaskQueueManager]

    Q1 --> R1[StorageWorker Consumer Thread]
    R1 --> R2[Process Storage Task]
    R2 --> R3[Write to Parquet via data_storage.py]

    %% Direct storage path for comparison
    D --> Z[date_range_downloader.py]
    Z --> AA[DateRangeDownloader]
    AA --> AB[TuShareDownloader<br/>Instantiated with delegation]
    AB --> AC[Download via modules<br/>O2 through O12]
    AC --> AD[Direct save_to_parquet call]

    %% Task management and queuing
    B --> AE[Download Task Creation]
    AE --> AF[TaskQueueManager with priority queues]
    AF --> AG[Download Workers process<br/>tasks via consumer loop]
    AG --> P1

    %% Task completion and result handling
    P1 --> AH[Original download task completes<br/>without waiting for storage]
    P2 --> AI[Storage completion<br/>handled separately]

    %% Configuration and Priority System
    I --> AJ[ConfigAdapter.get_all_available_interfaces<br/>based on user points]
    AJ --> AK[InterfaceConfig with priority, retries, rate limits]
    AK --> AL[get_interface_priority, get_max_retries, get_rate_limit]
    AL --> AM[TaskQueue with Priority-based processing]

    %% Enhanced features
    AM --> AN[Global Rate Limiter<br/>Token Bucket Algorithm]
    AN --> AO[Parallel Downloader<br/>with concurrency controls]
    AO --> AP[Enhanced Config<br/>with advanced settings]

    %% Missing components from analysis
    AP --> AQ[ParameterAdapterManager<br/>for parameter validation and adaptation]
    AQ --> AR[DailyDataParameterAdapter, FinancialDataParameterAdapter, etc.]

    O12 --> AS[HoldersDataFullHistoryDownloader<br/>for ts_code-dependent interfaces]
    AS --> O2[BasicDataDownloader for stock_basic]
    AS --> O4[FinancialDataDownloader for fina_audit]
    AS --> O3[DailyDataDownloader for pro_bar]

    AQ --> O
    AR --> O

    %% Cache components
    O --> AT[cache_key_generator.py<br/>Standardized cache key generation]
    AT --> AU[cache_manager.py<br/>Cache preheating, cleaning and monitoring]
    AU --> AV[cache_monitor.py<br/>Cache hit rate tracking]
    AV --> AW[data_storage.py integration<br/>for caching system]

    %% Error handling components
    O1 --> AX[error_handler.py<br/>Enhanced error handling and retry mechanisms]
    AX --> AX1[retry_on_failure decorator<br/>with exponential backoff]
    AX1 --> AX2[ErrorHandler.handle_api_error<br/>with specific error handling]

    %% Stock List Manager - Singleton pattern
    O --> AY[stock_list_manager.py<br/>Singleton stock list manager]
    AY --> AY1[Prevents duplicate stock_basic API calls]

    %% Strategy Factory pattern
    N --> AZ[strategy_factory.py<br/>Strategy creation and caching]
    AZ --> BA[StrategyFactory.get_strategy<br/>with caching mechanism]

    %% Date utilities
    AW --> BB[utils/date_utils.py<br/>Date validation and conversion tools]

    %% Error handling integration
    O --> AX
    M --> AX
    AX --> BA

    %% Cache integration in download process
    AW --> M
    AU --> F
    AV --> N

    %% Stock List Manager integration
    AY --> AS
    AY --> O4
    AY --> O3
    AY --> O2

    subgraph "Main Entry"
        A
    end

    %% New Historical Download Marker System
    A --> A1[get_historical_download_marker_path]
    A1 --> A2[mark_interfaces_as_historical_downloaded]
    A2 --> A3[get_historical_downloaded_interfaces]
    A --> A4[disable_tscode_dependent_interfaces_for_date_range]
    A4 --> A5[Check for ts_code-dependent interfaces<br/>['stk_rewards', 'top10_holders', 'pledge_detail', 'fina_audit', 'pro_bar']]
    A5 --> A6[Temporarily disable interfaces<br/>during date-range downloads]
    A6 --> A7[Save original interface state<br/>with _original_enabled attribute]
    A7 --> A8[Restore original interface states<br/>after download completion]
    A8 --> A9[Historical Download Tracking<br/>to avoid redundant processing]

    %% TSCODE Historical Mode Implementation
    A --> A10[tscode_historical mode - Full History Downloads]
    A10 --> A11[Uses DownloadScheduler with mode='tscode_historical']
    A11 --> A12[_schedule_tscode_interface for batch processing by ts_code]
    A12 --> A13[_execute_tscode_download for parallel processing]
    A13 --> A14[ParallelDownloader.batch_download for efficiency]

    %% New Cache Integration Features
    O --> A15[Enhanced Cache System]
    A15 --> A16[CacheKeyGenerator for standardized paths]
    A15 --> A17[Cache Monitor for hit rate tracking]
    A15 --> A18[Intelligent Cache Matching and extraction]
    A15 --> A19[Cache Preheating capabilities]

    %% New Configuration and Strategy Features
    O --> A20[ConfigAdapter.get_interface_cache_settings]
    O --> A21[ParameterAdapterManager integration]
    O --> A22[Enhanced InterfaceConfig with detailed settings]

    %% Download Scheduling with New Features
    A --> A23[Enhanced Download Scheduler]
    A23 --> A24[TaskQueueManager.add_storage_task]
    A24 --> A25[StorageWorker.submit_data]
    A25 --> A26[Asynchronous Storage Operations]
    A26 --> A27[Batch Storage Worker (optional)]

    subgraph "Download Scheduling"
        B
        E
        F
        G
        H
        I
        J
        K
        L
    end

    subgraph "Facade Pattern Implementation"
        O
        O1
        O2
        O3
        O4
        O5
        O6
        O7
        O8
        O9
        O10
        O11
        O12
    end

    subgraph "Producer-Consumer Storage Pattern"
        Q1
        R1
        R2
        R3
    end

    subgraph "Legacy Fallback"
        C
        D
        Z
        AA
        AB
        AC
        AD
    end

    subgraph "Task Management"
        AE
        AF
        AG
        AH
        AI
    end

    subgraph "Configuration System"
        AJ
        AK
        AL
        AM
    end

    subgraph "Enhanced Features"
        AN
        AO
        AP
        AQ
        AR
        AZ
        BA
    end

    subgraph "Caching System"
        AT
        AU
        AV
        AW
    end

    subgraph "Error Handling"
        AX
        AX1
        AX2
    end

    subgraph "Specialized Components"
        AS
    end

    subgraph "Stock Management"
        AY
        AY1
    end

    subgraph "Utilities"
        BB
    end

    subgraph "Historical Download System"
        A4
        A5
        A6
        A7
        A8
        A9
        A10
        A11
        A12
        A13
        A14
    end

    subgraph "Enhanced Cache System"
        A15
        A16
        A17
        A18
        A19
    end
```

## Call Flow Description

### Primary Flow (New Scheduler - Recommended):
1. `main.py` → `download_all_data_from_date()`
2. → Conditional interface management: `disable_tscode_dependent_interfaces_for_date_range()` temporarily disables ts_code-dependent interfaces during date-range downloads
   - Identifies interfaces requiring ts_code parameter: ['stk_rewards', 'top10_holders', 'pledge_detail', 'fina_audit', 'pro_bar']
   - Saves original interface states with `_original_enabled` attribute
   - Restores original states after download completion (in both success and error scenarios)
3. → Historical download tracking: checks `get_historical_downloaded_interfaces()` to avoid redundant processing
4. → `download_scheduler.run_download_schedule()`
5. → `DownloadScheduler` class initialization and task scheduling
6. → `config_adapter.get_all_available_interfaces()` to get user-accessible interfaces based on points
7. → `DownloadScheduler.schedule_download_tasks()` creates tasks based on score and priority
8. → `DownloadScheduler.execute_scheduled_tasks()` executes the tasks in parallel
9. → `DownloadScheduler._task_consumer_loop()` processes tasks via task queue manager
10. → `download_strategies.get_strategy()` gets the appropriate download strategy
11. → `strategy_factory.get_strategy()` provides cached strategy instances with configuration
12. → `TuShareDownloader` main class that orchestrates the interface usage (Facade Pattern)
    - Implements facade pattern with `__getattr__` delegation to individual interface modules
    - Maintains unified interface while delegating to specialized modules
13. → Individual interface classes from `app/interfaces/`:
    - `BasicDataDownloader` (basic_data.py)
    - `DailyDataDownloader` (daily_data.py)
    - `FinancialDataDownloader` (financial_data.py)
    - `MarketFlowDownloader` (market_flow.py)
    - `HoldersDataDownloader` (holders_data.py)
    - `TechnicalFactorsDownloader` (technical_factors.py)
    - `CyqChipsDownloader` (cyq_chips.py)
    - `MarketStructureDownloader` (market_structure.py) - 注意：文件存在但目录为空
    - `ResearchDataDownloader` (research_data.py)
    - `BaseDownloader` (base.py) - base functionality for all interfaces
    - `HoldersDataFullHistoryDownloader` (holders_data_downloader.py) - for ts_code-dependent interfaces requiring full history
14. → Parameter validation and adaptation via `parameter_adapters.py`:
    - `ParameterAdapterManager` routes to appropriate adapter
    - `DailyDataParameterAdapter`, `FinancialDataParameterAdapter`, etc.
    - Standardized parameter validation and date formatting
15. → Error handling via `error_handler.py`:
    - `retry_on_failure` decorator with exponential backoff
    - `ErrorHandler.handle_api_error` with specific error type handling
16. → Advanced caching system via `cache_key_generator.py`, `cache_manager.py`, `cache_monitor.py`:
    - Standardized cache key generation with intelligent matching
    - Cache preheating and monitoring capabilities
    - Cache hit rate tracking and statistics
17. → Stock list management via `stock_list_manager.py` singleton pattern:
    - Prevents duplicate stock_basic API calls
    - Cached stock list with configurable TTL
18. → API calls executed via interface-specific classes
19. → Downloaded data processed via Asynchronous Producer-Consumer Pattern:
    - Download task completes and creates storage task via `task_manager.add_storage_task()`
    - Storage task placed in queue managed by `TaskQueueManager`
    - Independent `StorageWorker` threads consume storage tasks from queue
    - Storage tasks executed separately from download tasks, enabling parallel processing
20. → Data saved as Parquet files via `data_storage.py`
21. → Historical download completion: `mark_interfaces_as_historical_downloaded()` records completed interfaces

### TSCODE Historical Mode Implementation:
When using `--tscode-historical`, `--holders-data`, or `--pro-bar-only` flags, the system uses a specialized approach:
1. `main.py` → `run_download_schedule()` with `mode='tscode_historical'`
2. → `DownloadScheduler.schedule_download_tasks()` with `tscode_historical` mode
3. → `_schedule_tscode_interface()` for batch processing by ts_code
4. → `_execute_tscode_download()` for parallel processing of ts_code-dependent interfaces
5. → `ParallelDownloader.batch_download()` for efficient processing of multiple ts_code values
6. → Storage tasks submitted to `task_manager.add_storage_task()` with specific subdirectory structure for full history data

### Fallback Flow (Legacy System):
1. `main.py` → `download_with_legacy_method()`
2. → Conditional interface management: `disable_tscode_dependent_interfaces_for_date_range()` temporarily disables ts_code-dependent interfaces during date-range downloads (same as primary flow)
3. → Historical download tracking: checks `get_historical_downloaded_interfaces()` to avoid redundant processing (same as primary flow)
4. → `date_range_downloader.DateRangeDownloader`
5. → `TuShareDownloader` class (shared logic with facade pattern)
6. → Individual interface classes (same as above)
7. → Parameter validation and adaptation (same as above)
8. → Advanced error handling (same as above)
9. → Caching system integration (same as above)
10. → Stock list management (same as above)
11. → Data saved directly via synchronous `data_storage.py` calls within download methods
12. → Historical download completion: `mark_interfaces_as_historical_downloaded()` records completed interfaces (same as primary flow)

### Configuration and Strategy Layer:
- `config_adapter.py` provides interface configurations based on `DOWNLOAD_PIPELINE_CONFIG` with enhanced features
- `enhanced_download_config.py` provides detailed interface configurations with priority, retry, rate limit, and caching settings
- Score-based access control via `score_config.py` determines which interfaces are available to the user
- `task_queue_manager.py` handles priority-based task scheduling with producer-consumer pattern
- `global_rate_limiter.py` manages API call rate limiting using token bucket algorithm
- `parallel_downloader.py` enables parallel downloads of multiple interfaces with concurrency controls
- `storage_worker.py` implements consumer threads for asynchronous data storage
- `download_strategies.py` provides different download strategies for different data types (batch, parallel, sequential, paginated)
- `strategy_factory.py` manages strategy instantiation with caching
- `parameter_adapters.py` provides parameter validation and normalization for all interfaces
- `cache_key_generator.py`, `cache_manager.py`, `cache_monitor.py` provide advanced caching capabilities
- `stock_list_manager.py` implements singleton pattern to prevent duplicate stock API calls
- `error_handler.py` provides enhanced error handling with retry mechanisms and API-specific error handling
- `utils/date_utils.py` provides date validation and conversion utilities

### Key Architectural Patterns:

1. **Facade Pattern**: `TuShareDownloader` acts as a unified interface delegating to specialized modules via `__getattr__`
2. **Producer-Consumer Pattern**: Download tasks and storage tasks are decoupled with independent processing threads
3. **Strategy Pattern**: Different download approaches are implemented via `download_strategies.py` and `DownloadStrategy` classes
4. **Strategy Factory Pattern**: Strategy instantiation and caching via `strategy_factory.py`
5. **Task Queue Management**: Priority-based task scheduling implemented in `task_queue_manager.py`
6. **Asynchronous Processing**: Storage operations are handled asynchronously to avoid blocking download threads
7. **Configuration Adapter Pattern**: New configuration system maintains compatibility with old format while adding advanced features
8. **Rate Limiting with Token Bucket**: Global rate limiting prevents API throttling across all interfaces
9. **Parameter Adapter Pattern**: Standardized parameter validation and adaptation per interface type
10. **Caching System**: Multi-layer caching with intelligent cache key generation, TTL management, and cache warming capabilities
11. **Singleton Pattern**: Stock list management uses singleton pattern to prevent duplicate API calls
12. **Enhanced Error Handling**: Improved retry mechanisms with exponential backoff and adaptive rate limiting
13. **Historical Download Tracking**: Tracks completed historical downloads to avoid redundant processing (JSON-based marker system)
14. **Conditional Interface Management**: Automatically disables ts_code-dependent interfaces during date-range downloads to prevent parameter conflicts
15. **Intelligent Cache Matching**: Can extract specific data from more general caches (e.g., single stock data from all-stock cache)
16. **Batch Operations**: For ts_code-dependent interfaces, processes multiple stocks in parallel batches

### New Enhanced Features:

1. **Priority-based Interface Configuration**: Interfaces are categorized by priority (HIGH, MEDIUM, LOW) to optimize download order
2. **Advanced Download Strategies**: Different strategies available (DailyDataStrategy, FinancialDataStrategy, StaticDataStrategy) for optimal data retrieval
3. **Concurrency Control**: Configurable concurrency levels per interface to maximize throughput within API limits
4. **Advanced Caching Mechanism**: Multi-layer caching with intelligent cache key generation, TTL management, and cache warming capabilities
5. **Token Bucket Rate Limiting**: Sophisticated rate limiting across all API calls with global control
6. **Enhanced Error Handling**: Improved retry mechanisms with configurable retry counts and backoff strategies with API-specific error handling
7. **Parameter Adaptation System**: Interface-specific parameter validation and standardization through adapter pattern
8. **Backward Compatibility**: New configuration system maintains compatibility with the original DOWNLOAD_CONFIG format
9. **Stock List Management**: Singleton pattern implementation for efficient stock list access
10. **Strategy Caching**: Factory pattern with caching to optimize strategy instantiation
11. **Full History Download Capability**: Specialized downloader for interfaces requiring ts_code parameters for bulk historical data
12. **Cache Monitoring**: Real-time cache performance tracking with hit rate statistics
13. **Historical Download Tracking**: Tracks completed historical downloads to avoid redundant processing using JSON-based marker files
14. **Conditional Interface Management**: Automatically disables ts_code-dependent interfaces during date-range downloads to prevent parameter conflicts
15. **Intelligent Cache Matching**: Can extract specific data from more general caches (e.g., single stock data from all-stock cache)
16. **Batch Processing**: For ts_code-dependent interfaces, processes multiple stocks in parallel batches for efficiency

This enhanced architecture enables modular, extensible data download functionality with proper error handling, retry logic, rate limiting, caching, and asynchronous processing, all orchestrated through the entry point in main.py. The decoupled nature of download and storage operations allows for better resource utilization and system responsiveness. The new configuration system provides granular control over download behavior while maintaining backward compatibility with the original system structure.

The integrated caching system with standardized cache key generation, parameter validation system with interface-specific adapters, error handling with API-specific logic, singleton stock list manager, historical download tracking, conditional interface management, intelligent cache matching, and batch processing all contribute to a more robust and efficient architecture.

## Application Structure and Key Components

### Directory Structure

```
aspipe_v4/
├── app/                    # Main application code
│   ├── main.py            # Main entry point with fallback
│   ├── enhanced_main_downloader.py  # Production-ready enhanced downloader
│   ├── score_based_downloader.py  # Score-based download management
│   ├── config.py          # Configuration and token management
│   ├── score_config.py    # Score-based access control
│   ├── tushare_api.py     # Main API integration (Facade Pattern)
│   ├── date_range_downloader.py  # Legacy date range downloader
│   ├── download_config.py  # Original download configuration
│   ├── enhanced_download_config.py  # Enhanced configuration with advanced options
│   ├── config_adapter.py  # Configuration adapter for backward compatibility
│   ├── data_storage.py    # Data storage and caching
│   ├── download_scheduler.py  # Producer-consumer scheduler
│   ├── parallel_downloader.py # Parallel download framework
│   ├── storage_worker.py  # Storage consumer logic
│   ├── download_strategies.py # Strategy pattern for different download approaches
│   ├── global_rate_limiter.py  # Rate limiting with token bucket
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
│   │   ├── basic_data.py
│   │   ├── daily_data.py
│   │   ├── financial_data.py
│   │   ├── market_flow.py
│   │   ├── holders_data.py
│   │   ├── holders_data_downloader.py  # Full history holder data downloader
│   │   ├── technical_factors.py
│   │   ├── cyq_chips.py
│   │   └── research_data.py
│   └── utils/             # Utility functions
│       ├── __init__.py    # Package initialization file
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

### Core Design Patterns

#### 1. Facade Pattern
- **File**: `app/tushare_api.py`
- **Implementation**: `TuShareDownloader` class acts as a unified interface
- **Delegation**: Uses `__getattr__` to delegate to specialized modules
- **Benefits**: Provides simple interface while hiding complexity

The `TuShareDownloader` class implements the Facade pattern through `__getattr__` method:

```python
def __getattr__(self, name):
    """
    代理到各个子模块的方法
    保持向后兼容性
    """
    # 检查各个子模块是否包含该方法
    for module in [
        self.basic_data,
        self.daily_data,
        self.financial_data,
        self.market_flow,
        self.holders_data,
        self.technical_factors,
        # 注意：market_structure.py 作为独立文件存在但对应的目录为空
        self.research_data
    ]:
        if hasattr(module, name):
            return getattr(module, name)
```

This allows external code to call methods like `downloader.download_stock_basic()` which gets delegated to the appropriate submodule.

#### 2. Producer-Consumer Pattern
- **Files**: `app/download_scheduler.py`, `app/storage_worker.py`, `app/task_queue_manager.py`
- **Implementation**: Download tasks produce data, storage workers consume for writing
- **Benefits**: Decoupled processing, parallel execution, better resource utilization

The new scheduler implements a true producer-consumer pattern:
- **Producer**: Download tasks create data and submit storage tasks to the queue
- **Consumer**: StorageWorker processes storage tasks from the queue independently
- **Decoupling**: Download and storage operations are completely separated

Example from `download_scheduler.py`:
```python
# After download completes, create storage task instead of immediate storage
if result is not None and not result.empty:
    filename = f"{interface_name}_{start_date}_{end_date}"
    subdir = f"daily/{start_date[:4]}/{start_date[4:6]}"

    self.task_manager.add_storage_task(
        data=result,
        filename=filename,
        subdir=subdir,
        priority=TaskPriority.MEDIUM
    )
```

#### 3. Strategy Pattern
- **File**: `app/download_strategies.py`
- **Implementation**: Different download strategies for different data types
- **Benefits**: Flexible approach selection, easy extension

#### 4. Strategy Factory Pattern
- **File**: `app/strategy_factory.py`
- **Implementation**: Strategy creation and caching
- **Benefits**: Optimized strategy instantiation, centralized management

#### 5. Configuration Adapter Pattern
- **File**: `app/config_adapter.py`
- **Implementation**: Unifies access to old and new configuration formats
- **Benefits**: Maintains backward compatibility while adding advanced features

#### 6. Parameter Adapter Pattern
- **File**: `app/parameter_adapters.py`
- **Implementation**: Standardized parameter validation and adaptation per interface
- **Benefits**: Consistent parameter handling across different interfaces

#### 7. Task Queue Management
- **File**: `app/task_queue_manager.py`
- **Implementation**: Priority-based task scheduling with dependency management
- **Benefits**: Efficient resource management, controlled execution order

The `TaskQueueManager` uses priority queues to manage both download and storage tasks:
- **Priority-based scheduling**: Critical tasks execute first
- **Dependency management**: Tasks can wait for other tasks to complete
- **Retry logic**: Failed tasks can be retried automatically
- **Statistics tracking**: Monitor task execution metrics

#### 10. Historical Download Tracking
- **Files**: `app/main.py`, `app/task_queue_manager.py`
- **Implementation**: JSON-based marker system to track completed historical downloads
- **Benefits**: Prevents redundant processing of full history downloads

#### 11. Conditional Interface Management
- **File**: `app/main.py`
- **Implementation**: Automatically disables ts_code-dependent interfaces during date-range downloads
- **Benefits**: Prevents parameter conflicts between different download modes

#### 12. Parameter Validation Framework
- **File**: `app/parameter_adapters.py`
- **Implementation**: Comprehensive parameter validation and normalization for all interfaces
- **Benefits**: Ensures consistent and valid API parameters

#### 13. Cache Monitoring
- **Files**: `app/cache_monitor.py`, `app/cache_manager.py`
- **Implementation**: Real-time tracking of cache hit rates and performance metrics
- **Benefits**: Provides insights into cache effectiveness and performance

#### 14. Date Range Optimization
- **File**: `app/download_scheduler.py`
- **Implementation**: Smart date range handling with overlap detection and merging
- **Benefits**: Optimizes date range processing for better performance

#### 15. Intelligent Cache Matching
- **Files**: `app/data_storage.py`, `app/cache_key_generator.py`
- **Implementation**: Can extract specific data from more general caches
- **Benefits**: Reduces redundant downloads by leveraging existing cached data

#### 16. Batch Processing for TSCODE interfaces
- **Files**: `app/download_scheduler.py`, `app/parallel_downloader.py`
- **Implementation**: Efficient batch processing of ts_code-dependent interfaces
- **Benefits**: Reduces API calls by processing multiple stock codes in parallel

### Data Flow Architecture

#### New Scheduler Flow:
1. **Main Entry** → `main.py`
2. **Task Scheduling** → `DownloadScheduler.schedule_download_tasks()`
3. **Strategy Selection** → `strategy_factory.get_strategy()` with caching
4. **Parameter Adaptation** → `parameter_adapters.adapt_parameters()`
5. **Task Execution** → `_task_consumer_loop()` processes download tasks
6. **Strategy Selection** → `download_strategies.get_strategy()`
7. **Facade Delegation** → `TuShareDownloader.__getattr__()` → Interface modules
8. **Error Handling** → `error_handler.py` with retry mechanisms
9. **API Calling** → Individual interface modules
10. **Caching** → `cache_manager.py` integration for data caching
11. **Storage Task Creation** → `task_manager.add_storage_task()`
12. **Storage Processing** → `StorageWorker` consumer threads
13. **Data Storage** → `data_storage.save_to_parquet()`

#### Legacy Flow:
1. **Fallback Entry** → `date_range_downloader.DateRangeDownloader`
2. **Direct Processing** → Synchronous download and storage
3. **Facade Use** → `TuShareDownloader` delegation still applies
4. **Immediate Storage** → Direct `save_to_parquet()` calls

### TSCODE Historical Mode Flow:
1. **Main Entry** → `main.py` with `--tscode-historical` flag
2. **Task Scheduling** → `DownloadScheduler.schedule_download_tasks(mode='tscode_historical')`
3. **Batch Scheduling** → `_schedule_tscode_interface()` for batch processing
4. **Parallel Execution** → `_execute_tscode_download()` with batch processing
5. **Strategy Selection** → Specialized processing for ts_code-dependent interfaces
6. **Facade Delegation** → `TuShareDownloader.__getattr__()` → Interface modules
7. **Error Handling** → `error_handler.py` with retry mechanisms
8. **API Calling** → Individual interface modules with ts_code parameter
9. **Storage Task Creation** → `task_manager.add_storage_task()` with specific subdirectory
10. **Storage Processing** → `StorageWorker` consumer threads
11. **Data Storage** → `data_storage.save_to_parquet()` with specific path structure

### Key Classes and Responsibilities

| Class | Pattern | Responsibility |
|-------|---------|----------------|
| `TuShareDownloader` | Facade | Unified API access, delegation to interface modules |
| `DownloadScheduler` | Orchestrator | Task scheduling, producer-consumer coordination |
| `StorageWorker` | Consumer | Asynchronous data storage processing |
| `TaskQueueManager` | Manager | Priority-based task queue management |
| `DownloadStrategy` classes | Strategy | Data download approach selection per interface type |
| `StrategyFactory` | Factory | Strategy creation and caching |
| `ConfigAdapter` | Adapter | Unifies old and new configuration access |
| `ParameterAdapter` classes | Adapter | Parameter validation and standardization |
| `CacheManager` | Manager | Cache preheating, cleaning, monitoring |
| `StockListManager` | Singleton | Stock list management, prevents duplicate calls |
| `ErrorHandler` | Handler | Error handling and retry mechanisms |
| `InterfaceConfig` | Configuration | Enhanced interface settings with priority, retries, etc. |
| Interface modules | Implementation | Specific data interface implementations |
| `CacheKeyGenerator` | Generator | Standardized cache key and path generation |
| `CacheMonitor` | Monitor | Cache hit rate tracking and performance metrics |
| `ParallelDownloader` | Processor | Batch processing of multiple ts_code values |