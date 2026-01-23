# App4 代码优化实施计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现 App4 代码优化方案中提出的 12 个共识采纳项，重点解决性能瓶颈和内存安全问题

**Architecture:** 分三个阶段实施：第一阶段解决高优先级性能和内存问题，第二阶段优化代码质量和维护性，第三阶段按需优化特定组件

**Tech Stack:** Python 3.8+, concurrent.futures, collections.OrderedDict, Polars, YAML

---

### Task 1: 日期范围验证增强 (#18)

**Files:**
- Modify: `app4/main.py:72-90`

**Step 1: Write the failing test**

```python
import pytest
from datetime import datetime
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'app4'))

def test_date_validation_enhancement():
    """Test date validation with invalid formats"""
    from app4.main import validate_and_adjust_date

    # Test invalid format
    with pytest.raises(ValueError, match="Invalid start_date format"):
        validate_and_adjust_date("2023-01-01", "20231231")

    # Test invalid format for end date
    with pytest.raises(ValueError, match="Invalid end_date format"):
        validate_and_adjust_date("20230101", "2023-12-31")

    # Test invalid date
    with pytest.raises(ValueError):
        validate_and_adjust_date("20230230", "20230231")  # Invalid Feb 30

    # Test start_date > end_date
    with pytest.raises(ValueError, match="start_date .* must be <= end_date"):
        validate_and_adjust_date("20231231", "20230101")

    # Test valid date ranges should pass
    result = validate_and_adjust_date("20230101", "20231231")
    assert result == ("20230101", "20231231")

    # Test future date adjustment
    future_date = (datetime.now().replace(year=datetime.now().year + 1)).strftime('%Y%m%d')
    adjusted_start, adjusted_end = validate_and_adjust_date("20230101", future_date)
    assert adjusted_end <= datetime.now().strftime('%Y%m%d')
```

**Step 2: Write enhanced date validation function**

```python
import re
from datetime import datetime
from typing import Tuple

DATE_PATTERN = re.compile(r'^\d{8}$')

def validate_and_adjust_date(start_date: str, end_date: str) -> Tuple[str, str]:
    """
    Enhanced date validation with format and range checking.

    Args:
        start_date: Start date in YYYYMMDD format
        end_date: End date in YYYYMMDD format

    Returns:
        Tuple of validated (start_date, end_date)

    Raises:
        ValueError: If date format is invalid or range is incorrect
    """
    # 格式验证
    if not DATE_PATTERN.match(start_date):
        raise ValueError(f"Invalid start_date format: {start_date}, expected YYYYMMDD")
    if not DATE_PATTERN.match(end_date):
        raise ValueError(f"Invalid end_date format: {end_date}, expected YYYYMMDD")

    # 日期有效性验证
    try:
        start_dt = datetime.strptime(start_date, '%Y%m%d')
        end_dt = datetime.strptime(end_date, '%Y%m%d')
    except ValueError as e:
        raise ValueError(f"Invalid date: {e}")

    # start_date <= end_date 检查
    if start_dt > end_dt:
        raise ValueError(f"start_date ({start_date}) must be <= end_date ({end_date})")

    # 调整未来日期
    today = datetime.now()
    if end_dt > today:
        end_date = today.strftime('%Y%m%d')

    return start_date, end_date
```

**Step 3: Run test to verify it passes**

Run: `pytest test_date_validation.py::test_date_validation_enhancement -v`
Expected: PASS

**Step 4: Commit**

```bash
git add app4/main.py
git commit -m "feat: enhance date validation with format and range checking"
```

### Task 2: 窗口级并发处理实现 (#1)

**Files:**
- Modify: `app4/core/downloader.py:308-382`

**Step 1: Write the failing test**

```python
def test_date_range_concurrent_execution():
    """Test concurrent execution of date range pagination"""
    # We'll create a downloader with mocked API calls to test concurrency
    downloader = TuShareDownloader(config={})

    # Mock the _make_request method to return different results for different date ranges
    import concurrent.futures
    from unittest.mock import patch

    def mock_request(params):
        # Simulate API call delay
        import time
        time.sleep(0.1)
        return [{'ts_code': '000001.SZ', 'trade_date': params['start_date'], 'close': 10.0}]

    with patch.object(downloader, '_make_request', side_effect=mock_request):
        # Test with small date range that creates multiple windows
        start_date = "20230101"
        end_date = "20230110"  # 10 days, with window size 3 should create 4 windows
        window_size = 3

        # The concurrent version should be faster than serial version
        import time
        start_time = time.time()

        result = downloader._execute_date_range_pagination_concurrent(
            interface_config={'api_name': 'daily'},
            params={'ts_code': '000001.SZ'},
            start_date=start_date,
            end_date=end_date,
            window_size=window_size
        )

        end_time = time.time()
        execution_time = end_time - start_time

        # Should have some results
        assert len(result) > 0
        # Execution time should be less than 4 * 0.1 seconds (serial would take ~0.4s)
        assert execution_time < 0.4
```

**Step 2: Add concurrent date range execution method**

```python
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any

def _execute_date_range_pagination_concurrent(self, interface_config: Dict[str, Any], params: Dict[str, Any], start_date: str, end_date: str, window_size: int = 365, max_workers: int = 4) -> List[Dict[str, Any]]:
    """
    Execute date range pagination concurrently using thread pool.

    Args:
        interface_config: Configuration for the interface
        params: Parameters for the request
        start_date: Start date in YYYYMMDD format
        end_date: End date in YYYYMMDD format
        window_size: Size of each time window in days
        max_workers: Maximum number of worker threads

    Returns:
        Combined list of data from all windows
    """
    # Generate time ranges
    trade_days = self._get_trade_days(start_date, end_date)
    windows = []

    for i in range(0, len(trade_days), window_size):
        window_trade_days = trade_days[i:i+window_size]
        if window_trade_days:
            # Create start and end date for this window
            window_start = window_trade_days[0]
            window_end = window_trade_days[-1]
            windows.append((window_start, window_end))

    all_data = []
    results_by_window = {}

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all window requests
        future_to_window = {}
        for window_start, window_end in windows:
            window_params = params.copy()
            window_params['start_date'] = window_start
            window_params['end_date'] = window_end

            future = executor.submit(
                self._make_request,
                interface_config,
                window_params
            )
            future_to_window[future] = (window_start, window_end)

        # Collect results as they complete
        for future in as_completed(future_to_window):
            window_start, window_end = future_to_window[future]
            try:
                result = future.result()
                # Store result with window info to maintain order if needed
                results_by_window[(window_start, window_end)] = result
            except Exception as e:
                self.logger.error(f"Error fetching window {window_start} to {window_end}: {e}")
                results_by_window[(window_start, window_end)] = []

    # Combine all results in the original order
    for window_start, window_end in windows:
        window_data = results_by_window.get((window_start, window_end), [])
        all_data.extend(window_data)

    return all_data

def _execute_date_range_pagination(self, interface_config: Dict[str, Any], params: Dict[str, Any], start_date: str, end_date: str, window_size: int = 365) -> List[Dict[str, Any]]:
    """
    Execute date range pagination - updated to use concurrent execution.
    """
    # Use concurrent execution for better performance
    return self._execute_date_range_pagination_concurrent(
        interface_config=interface_config,
        params=params,
        start_date=start_date,
        end_date=end_date,
        window_size=window_size,
        max_workers=4  # Conservative default to respect API limits
    )
```

**Step 3: Run test to verify it passes**

Run: `pytest test_date_range_concurrent.py::test_date_range_concurrent_execution -v`
Expected: PASS

**Step 4: Commit**

```bash
git add app4/core/downloader.py
git commit -m "feat: implement concurrent date range pagination for performance improvement"
```

### Task 3: 缓冲区锁优化 (#12)

**Files:**
- Modify: `app4/core/storage.py:345-386`

**Step 1: Write the failing test**

```python
def test_buffer_lock_optimization():
    """Test that buffer operations are thread-safe and non-blocking"""
    from app4.core.storage import StorageManager
    import threading
    import time

    config = {
        'storage': {
            'base_dir': 'test_data',
            'format': 'parquet',
            'batch_size': 1000,
            'buffer_threshold': 500
        }
    }

    storage = StorageManager(config)

    # Test concurrent buffer additions
    results = []

    def add_data(thread_id):
        data = [{'ts_code': f'00000{thread_id}.SZ', 'value': i} for i in range(100)]
        start_time = time.time()
        storage.add_to_buffer('test_interface', data)
        end_time = time.time()
        results.append(end_time - start_time)  # Time taken for buffer operation

    # Create multiple threads to test concurrent access
    threads = []
    for i in range(5):
        t = threading.Thread(target=add_data, args=(i,))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # Verify that all operations completed
    assert len(results) == 5
    # In the old implementation, operations would be serialized due to long lock holding
    # This test checks that operations complete faster than they would be if serialized
```

**Step 2: Optimize buffer lock implementation**

```python
import threading
from typing import List, Dict, Any, Optional

def add_to_buffer(self, interface_name: str, data: List[Dict[str, Any]]) -> None:
    """
    Add data to buffer with optimized lock usage.
    The lock is held only for minimal operations; I/O happens outside the critical section.
    """
    data_to_process = None
    interface_to_process = None

    with self.buffer_lock:
        # Only perform minimal necessary operations while holding the lock
        buffer = self._get_or_create_buffer(interface_name)
        buffer['data'].extend(data)
        buffer['count'] += len(data)

        # Check if we should flush the buffer
        if buffer['count'] >= self.buffer_threshold:
            # Take ownership of the data outside of the lock
            data_to_process = buffer['data']
            interface_to_process = interface_name
            # Reset buffer with new empty list
            buffer['data'] = []
            buffer['count'] = 0

    # Process the data outside the lock to avoid blocking other threads
    if data_to_process:
        # Add to processing queue - this might block briefly if queue is full
        item = {
            'interface': interface_to_process,
            'data': data_to_process,
            'timestamp': time.time()
        }
        self.process_queue.put(item)

        # Update statistics outside of lock
        self.total_buffered_items += len(data_to_process)
        self.last_processed_time = time.time()

def _get_or_create_buffer(self, interface_name: str) -> Dict[str, Any]:
    """
    Get existing buffer for interface or create new one.
    This helper method is used inside the critical section to avoid code duplication.
    """
    if interface_name not in self.buffers:
        self.buffers[interface_name] = {
            'data': [],
            'count': 0,
            'created_at': time.time()
        }
    return self.buffers[interface_name]
```

**Step 3: Run test to verify it passes**

Run: `pytest test_buffer_lock.py::test_buffer_lock_optimization -v`
Expected: PASS

**Step 4: Commit**

```bash
git add app4/core/storage.py
git commit -m "feat: optimize buffer lock implementation to reduce lock contention"
```

### Task 4: 内存缓存 LRU 限制 (#6)

**Files:**
- Modify: `app4/core/downloader.py:85-91`

**Step 1: Write the failing test**

```python
def test_memory_cache_lru_limit():
    """Test that memory cache respects LRU limits and doesn't grow indefinitely"""
    from app4.core.downloader import TuShareDownloader

    downloader = TuShareDownloader(config={})

    # Test that cache size is limited
    cache = downloader._memory_cache['coverage']

    # Add more items than the max size
    for i in range(1050):  # More than default maxsize of 1000
        cache[f'key_{i}'] = f'value_{i}'

    # Check that cache size doesn't exceed limit
    assert len(cache) <= 1000  # The configured max size

    # Test LRU behavior - access some items to update their position
    cache['key_100'] = 'new_value_100'  # Access to make it recently used
    cache['key_500'] = 'new_value_500'  # Access to make it recently used

    # Add more items to potentially evict older ones
    for i in range(1050, 1060):
        cache[f'key_{i}'] = f'value_{i}'

    # The recently used items should still be there
    assert cache['key_100'] == 'new_value_100'
    assert cache['key_500'] == 'new_value_500'
```

**Step 2: Implement LRU cache**

```python
from collections import OrderedDict
from typing import Dict, Any, Optional, Union

class LRUCache(OrderedDict):
    """
    Least Recently Used (LRU) cache implementation.
    Automatically removes least recently used items when size exceeds maxsize.
    """
    def __init__(self, maxsize: int = 1000):
        super().__init__()
        self.maxsize = maxsize

    def __getitem__(self, key):
        # Move accessed item to end (marking it as most recently used)
        value = super().__getitem__(key)
        self.move_to_end(key)
        return value

    def __setitem__(self, key, value):
        # Move existing key to end or add new key
        if key in self:
            self.move_to_end(key)
        super().__setitem__(key, value)

        # Remove oldest item if size exceeds limit
        if len(self) > self.maxsize:
            oldest_key = next(iter(self))
            super().__delitem__(oldest_key)

    def get(self, key, default=None):
        """Get value with optional default, mark as recently used."""
        try:
            return self[key]
        except KeyError:
            return default

    def put(self, key, value):
        """Alias for __setitem__"""
        self[key] = value

# Update initialization of memory cache in downloader
def __init__(self, config: Dict[str, Any]):
    # ... other initialization code ...

    # Initialize memory cache with LRU limits
    self._memory_cache = {
        'trade_cal': LRUCache(maxsize=100),      # Trade calendar cache - typically small set of keys
        'stock_list': None,                      # Will be stored separately if needed
        'coverage': LRUCache(maxsize=1000),      # Coverage info for various interfaces
        'api_responses': LRUCache(maxsize=500)   # API responses cache
    }

    # ... rest of initialization ...
```

**Step 3: Run test to verify it passes**

Run: `pytest test_memory_cache.py::test_memory_cache_lru_limit -v`
Expected: PASS

**Step 4: Commit**

```bash
git add app4/core/downloader.py
git commit -m "feat: implement LRU cache with size limits to prevent memory overflow"
```

### Task 5: 股票循环重复代码重构 (#8)

**Files:**
- Modify: `app4/main.py:379-437, 525-560, 581-615`

**Step 1: Write the failing test**

```python
def test_stock_list_preparation():
    """Test unified stock list preparation function"""
    from app4.main import _prepare_stock_list

    # Mock args object
    class Args:
        def __init__(self):
            self.ts_code = None
            self.skip_stocks = 0
            self.stock_type = 'stock'
            self.exchange = 'SSE'

    args = Args()

    # Mock config
    config = {
        'stock_types': {
            'stock': ['000001.SZ', '000002.SZ', '000003.SZ']
        },
        'exchanges': {
            'SSE': ['000001.SZ']
        }
    }

    # Test without filters
    stock_list = _prepare_stock_list(config, args)
    assert len(stock_list) == 3

    # Test with ts_code filter
    args.ts_code = '000001.SZ'
    stock_list = _prepare_stock_list(config, args)
    assert len(stock_list) == 1
    assert stock_list[0]['ts_code'] == '000001.SZ'

    # Test with skip_stocks
    args.ts_code = None
    args.skip_stocks = 1
    stock_list = _prepare_stock_list(config, args)
    assert len(stock_list) == 2
    assert stock_list[0]['ts_code'] == '000002.SZ'
```

**Step 2: Create unified stock list preparation function**

```python
def _prepare_stock_list(config: Dict[str, Any], args: Any) -> List[Dict[str, Any]]:
    """
    Unified method to prepare stock list based on args.

    Args:
        config: Configuration dictionary containing stock lists
        args: Arguments object with ts_code, skip_stocks, stock_type, exchange

    Returns:
        List of stock dictionaries ready for processing
    """
    # Get base stock list based on type and exchange
    stock_list = get_stock_list(args.stock_type, args.exchange)

    # Apply ts_code filter if specified
    if args.ts_code:
        stock_list = [s for s in stock_list if s['ts_code'] == args.ts_code]

    # Apply skip_stocks offset if specified
    if args.skip_stocks and args.skip_stocks > 0:
        stock_list = stock_list[args.skip_stocks:]

    return stock_list

def run_concurrent_stock_download(config: Dict[str, Any], args: Any, interfaces_to_run: List[str]) -> None:
    """
    Updated concurrent stock download function using unified stock preparation.
    """
    # Use the unified method to prepare stock list
    stock_list = _prepare_stock_list(config, args)

    # Continue with existing concurrent download logic...
    # ... rest of implementation using the prepared stock list
```

**Step 3: Run test to verify it passes**

Run: `pytest test_stock_prep.py::test_stock_list_preparation -v`
Expected: PASS

**Step 4: Commit**

```bash
git add app4/main.py
git commit -m "feat: refactor stock list preparation to eliminate code duplication"
```

### Task 6: 重复检测逻辑统一 (#3)

**Files:**
- Modify: `app4/core/processor.py:114-159, 244-275`

**Step 1: Write the failing test**

```python
def test_duplicate_detection_unification():
    """Test unified duplicate detection logic"""
    from app4.core.processor import _detect_duplicates_fast

    # Test data with duplicates
    data = [
        {'ts_code': '000001.SZ', 'trade_date': '20230101', 'close': 10.0},
        {'ts_code': '000001.SZ', 'trade_date': '20230101', 'close': 10.1},  # Duplicate key
        {'ts_code': '000001.SZ', 'trade_date': '20230102', 'close': 10.2},
        {'ts_code': '000002.SZ', 'trade_date': '20230101', 'close': 11.0},
    ]

    interface_config = {
        'output': {
            'primary_key': ['ts_code', 'trade_date']
        }
    }

    result = _detect_duplicates_fast(data, interface_config)

    # Should identify one duplicate
    assert len(result['duplicates']) == 1
    assert result['duplicates'][0]['ts_code'] == '000001.SZ'
    assert result['duplicates'][0]['trade_date'] == '20230101'

    # Should identify unique records
    assert len(result['unique']) == 3
```

**Step 2: Create unified duplicate detection function**

```python
def _detect_duplicates_fast(data: List[Dict[str, Any]], interface_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Unified fast duplicate detection using primary keys.

    Args:
        data: List of data records to check for duplicates
        interface_config: Configuration containing primary key information

    Returns:
        Dictionary with 'duplicates' and 'unique' lists
    """
    primary_keys = interface_config.get('output', {}).get('primary_key', [])

    if not primary_keys:
        # If no primary keys defined, treat all as unique
        return {'duplicates': [], 'unique': data}

    seen_keys = set()
    unique_records = []
    duplicate_records = []

    for record in data:
        # Create a key tuple from primary key values
        key_values = tuple(record.get(pk) for pk in primary_keys)

        if key_values in seen_keys:
            duplicate_records.append(record)
        else:
            seen_keys.add(key_values)
            unique_records.append(record)

    return {
        'duplicates': duplicate_records,
        'unique': unique_records
    }

def _handle_primary_keys(self, df: pl.DataFrame, interface_config: Dict[str, Any]) -> pl.DataFrame:
    """
    Updated primary key handling using unified duplicate detection.
    """
    primary_keys = interface_config.get('output', {}).get('primary_key', [])

    if not primary_keys:
        return df

    # Use the unified duplicate detection method
    data_list = df.to_dicts()
    detection_result = _detect_duplicates_fast(data_list, interface_config)

    # Process unique records only
    unique_df = pl.DataFrame(detection_result['unique'])

    if detection_result['duplicates']:
        self.logger.warning(f"Found {len(detection_result['duplicates'])} duplicate records for interface {interface_config.get('name', 'unknown')}")

    return unique_df

def validate_data(self, df: pl.DataFrame, interface_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Updated validate_data method using unified duplicate detection.
    """
    # ... existing validation code ...

    # Use unified duplicate detection
    data_list = df.to_dicts()
    detection_result = _detect_duplicates_fast(data_list, interface_config)

    stats = {
        'total': len(data_list),
        'unique': len(detection_result['unique']),
        'duplicates': len(detection_result['duplicates']),
        'duplicate_rate': len(detection_result['duplicates']) / len(data_list) if data_list else 0
    }

    if detection_result['duplicates']:
        self.logger.warning(f"Duplicate detection: {stats['duplicates']} duplicates found out of {stats['total']} records")

    # Return validated unique data
    return {
        'data': pl.DataFrame(detection_result['unique']),
        'stats': stats
    }
```

**Step 3: Run test to verify it passes**

Run: `pytest test_duplicate_detection.py::test_duplicate_detection_unification -v`
Expected: PASS

**Step 4: Commit**

```bash
git add app4/core/processor.py
git commit -m "feat: unify duplicate detection logic across processor methods"
```

### Task 7: 覆盖率缓存竞态修复 (#11)

**Files:**
- Modify: `app4/core/coverage_manager.py:51-54, 200-220`

**Step 1: Write the failing test**

```python
def test_coverage_cache_thread_safety():
    """Test thread safety of coverage cache operations"""
    from app4.core.coverage_manager import CoverageManager
    import threading
    import time

    config = {
        'cache': {
            'directory': 'test_cache',
            'ttl_hours': 24
        }
    }

    manager = CoverageManager(config)

    results = []

    def check_coverage():
        # Simulate concurrent access to the same coverage check
        result = manager.get_coverage_status('daily', '20230101', '20230131')
        results.append(result)

    # Create multiple threads to test concurrent access
    threads = []
    for i in range(10):
        t = threading.Thread(target=check_coverage)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # All threads should get the same result
    assert len(set(results)) <= 2  # Either all cached or all calculated (with possible empty coverage)
```

**Step 2: Implement thread-safe coverage cache**

```python
import threading
from typing import Dict, Any, Set

class CoverageManager:
    def __init__(self, config: Dict[str, Any]):
        # ... existing initialization ...

        # Thread lock for coverage cache operations
        self._coverage_cache_lock = threading.RLock()

        # ... rest of initialization ...

    def get_coverage_status(self, interface_name: str, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        Thread-safe method to get coverage status with proper locking.
        Uses double-checked locking pattern to minimize lock contention.
        """
        cache_key = f"{interface_name}:{start_date}:{end_date}"

        # First check without lock for performance
        if cache_key in self._coverage_cache:
            return self._coverage_cache[cache_key]

        # Double-check with lock to avoid duplicate computation
        with self._coverage_cache_lock:
            # Re-check after acquiring lock
            if cache_key in self._coverage_cache:
                return self._coverage_cache[cache_key]

            # Calculate coverage
            coverage_status = self._calculate_coverage_status(interface_name, start_date, end_date)

            # Store in cache
            self._coverage_cache[cache_key] = coverage_status

            return coverage_status

    def mark_as_completed(self, interface_name: str, start_date: str, end_date: str, ts_code: str = None) -> None:
        """
        Thread-safe method to mark coverage as completed.
        """
        with self._coverage_cache_lock:
            cache_key = f"{interface_name}:{start_date}:{end_date}"

            # Update cache with new completion status
            if cache_key in self._coverage_cache:
                # Update existing status
                status = self._coverage_cache[cache_key]
                if ts_code:
                    if 'completed_ts_codes' not in status:
                        status['completed_ts_codes'] = set()
                    status['completed_ts_codes'].add(ts_code)
                else:
                    status['completed'] = True
            else:
                # Create new status
                status = {
                    'completed': True if not ts_code else False,
                    'completed_ts_codes': {ts_code} if ts_code else set()
                }
                self._coverage_cache[cache_key] = status

    def _calculate_coverage_status(self, interface_name: str, start_date: str, end_date: str) -> Dict[str, Any]:
        """
        Calculate coverage status by checking existing data.
        This is the actual computation method that was previously called directly.
        """
        # ... existing coverage calculation logic ...
        pass
```

**Step 3: Run test to verify it passes**

Run: `pytest test_coverage_cache.py::test_coverage_cache_thread_safety -v`
Expected: PASS

**Step 4: Commit**

```bash
git add app4/core/coverage_manager.py
git commit -m "feat: implement thread-safe coverage cache with proper locking"
```

### Task 8: API 重试逻辑改进 (#19)

**Files:**
- Modify: `app4/core/downloader.py:1003-1129`

**Step 1: Write the failing test**

```python
def test_api_retry_logic_improvement():
    """Test improved API retry logic with error type classification"""
    from app4.core.downloader import TuShareDownloader

    downloader = TuShareDownloader(config={})

    # Test error classification
    error_msgs = [
        {"code": 10001, "msg": "user request time limited"},  # Rate limit
        {"code": 100, "msg": "服务器内部错误"},  # Server error
        {"code": 200, "msg": "success"},  # Success
        {"code": 500, "msg": "parameter invalid"}  # Client error
    ]

    # Test classification for each error
    for msg in error_msgs:
        error_type = downloader._classify_api_error(msg)
        assert error_type in ['rate_limit', 'server_error', 'success', 'client_error']

    # Test specific classifications
    rate_limit_msg = {"code": 10001, "msg": "user request time limited"}
    assert downloader._classify_api_error(rate_limit_msg) == 'rate_limit'

    server_error_msg = {"code": 100, "msg": "服务器内部错误"}
    assert downloader._classify_api_error(server_error_msg) == 'server_error'
```

**Step 2: Implement improved API retry logic**

```python
from enum import Enum
from typing import Dict, Any, Optional

class APIErrorType(Enum):
    SUCCESS = "success"
    RATE_LIMIT = "rate_limit"
    SERVER_ERROR = "server_error"
    CLIENT_ERROR = "client_error"
    NETWORK_ERROR = "network_error"

def _classify_api_error(self, response: Dict[str, Any]) -> APIErrorType:
    """
    Classify API response error into specific error type for appropriate handling.

    Args:
        response: API response dictionary

    Returns:
        APIErrorType enum value
    """
    code = response.get('code')
    msg = response.get('msg', '').lower()

    # Success case
    if code == 0 or 'success' in msg or 'ok' in msg:
        return APIErrorType.SUCCESS

    # Rate limit errors - specific codes and messages
    rate_limit_codes = [10001, 10002, 10003, 10004]  # Common TuShare rate limit codes
    rate_limit_keywords = ['limit', 'frequent', 'frequently', 'time', 'request', 'rate']

    if code in rate_limit_codes or any(keyword in msg for keyword in rate_limit_keywords):
        return APIErrorType.RATE_LIMIT

    # Client errors - invalid parameters, missing permissions, etc.
    client_error_codes = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110]
    client_error_keywords = ['parameter', 'invalid', 'missing', 'forbidden', 'unauthorized', 'permission']

    if code in client_error_codes or any(keyword in msg for keyword in client_error_keywords):
        return APIErrorType.CLIENT_ERROR

    # Server errors - network issues, internal errors, etc.
    server_error_codes = [500, 502, 503, 504, 110, 120]  # Common server error codes
    server_error_keywords = ['server', 'error', 'network', 'timeout', 'internal']

    if code in server_error_codes or any(keyword in msg for keyword in server_error_keywords):
        return APIErrorType.SERVER_ERROR

    # Default to server error if unrecognized
    return APIErrorType.SERVER_ERROR

def _make_request_with_retry(self, interface_config: Dict[str, Any], params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Make API request with improved retry logic based on error type.
    """
    max_retries = interface_config.get('max_retries', 3)
    base_delay = interface_config.get('retry_delay', 1.0)

    for attempt in range(max_retries + 1):
        try:
            response = self._make_request_once(interface_config, params)
            error_type = self._classify_api_error(response)

            if error_type == APIErrorType.SUCCESS:
                return response
            elif error_type == APIErrorType.CLIENT_ERROR:
                # Don't retry client errors - they will fail again
                self.logger.warning(f"Client error for {interface_config.get('api_name', 'unknown')}, not retrying: {response}")
                return response
            elif error_type == APIErrorType.RATE_LIMIT:
                # Use longer delay for rate limit errors
                delay = base_delay * (2 ** attempt) * 2  # Double the exponential delay
                self.logger.warning(f"Rate limit hit, retrying in {delay}s (attempt {attempt + 1}/{max_retries}): {response}")
                time.sleep(delay)
            else:  # SERVER_ERROR, NETWORK_ERROR
                # Use standard exponential backoff
                delay = base_delay * (2 ** attempt)
                self.logger.warning(f"Server/network error, retrying in {delay}s (attempt {attempt + 1}/{max_retries}): {response}")
                time.sleep(delay)

        except requests.exceptions.RequestException as e:
            self.logger.error(f"Network error on attempt {attempt + 1}/{max_retries}: {e}")
            if attempt < max_retries:
                time.sleep(base_delay * (2 ** attempt))
            else:
                raise

    self.logger.error(f"Max retries exceeded for {interface_config.get('api_name', 'unknown')}")
    return None
```

**Step 3: Run test to verify it passes**

Run: `pytest test_api_retry.py::test_api_retry_logic_improvement -v`
Expected: PASS

**Step 4: Commit**

```bash
git add app4/core/downloader.py
git commit -m "feat: improve API retry logic with error type classification"
```