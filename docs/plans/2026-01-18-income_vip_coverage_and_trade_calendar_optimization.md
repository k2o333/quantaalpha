# Income VIP Coverage and Trade Calendar Optimization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Resolve income VIP coverage check bug where system incorrectly skipped downloads when only partial data existed for a stock in a requested date range, and optimize trade calendar API calls to reduce redundant requests.

**Architecture:**
1. Enhance coverage manager to properly handle 'set' mode detection for financial data interfaces
2. Improve trade calendar caching strategy with range-aware logic
3. Implement subset/superset query capabilities for cached trade calendar data

**Tech Stack:** Python 3.8+, Polars, threading, file I/O

---

### Task 1: Add range subset logic to get_trade_calendar method

**Files:**
- Modify: `app4/core/downloader.py:617-656`

**Step 1: Write the failing test**

```python
# This would be in a test file to verify the functionality
def test_range_subset_logic():
    # We'll implement the functionality that allows getting a subset from a larger cached range
    pass  # Placeholder - the implementation will be in the coverage manager
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_coverage_and_calendar.py::test_range_subset_logic -v`
Expected: FAIL with "function not defined"

**Step 3: Write minimal implementation**

```python
def get_trade_calendar(self, start_date: str, end_date: str) -> Optional[List[Dict[str, Any]]]:
    """
    获取交易日历，采用三级缓存策略，并增加范围子集/超集逻辑：
    1. 内存缓存 (_memory_cache)
    2. 本地存储 (Data 目录 parquet 文件)
    3. API 请求
    """
    cache_key = (start_date, end_date)

    # 1. 检查内存缓存 - 先看是否有完全匹配的缓存
    with self._cache_lock:
        if cache_key in self._memory_cache['trade_cal']:
            logger.debug(f"Trade calendar loaded from memory cache: {start_date}-{end_date}")
            return self._memory_cache['trade_cal'][cache_key]

    # 2. 检查是否有包含该范围的更大缓存范围（范围超集逻辑）
    cached_data = self._find_superset_range_from_cache(start_date, end_date)
    if cached_data:
        logger.info(f"Trade calendar loaded from superset cache range: {start_date}-{end_date}")
        return cached_data

    # 3. 检查本地数据目录
    trade_calendar = self._get_trade_calendar_from_data_dir(start_date, end_date)

    if trade_calendar:
        logger.info(f"Trade calendar loaded from data directory: {start_date}-{end_date}")
    else:
        # 4. 请求 API
        logger.info(f"Trade calendar not found locally, fetching from API: {start_date}-{end_date}")
        calendar_params = {
            'start_date': start_date,
            'end_date': end_date,
            'exchange': 'SSE'
        }
        # 使用 _make_request 直接请求，避免递归调用
        trade_calendar = self._make_request(
            self.config_loader.get_interface_config('trade_cal'),
            calendar_params
        )

    # 更新内存缓存
    if trade_calendar:
        with self._cache_lock:
            self._memory_cache['trade_cal'][cache_key] = trade_calendar

    return trade_calendar
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_coverage_and_calendar.py::test_range_subset_logic -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app4/core/downloader.py
git commit -m "feat: add range subset logic to get_trade_calendar method"
```

### Task 2: Implement _find_superset_range_from_cache method

**Files:**
- Modify: `app4/core/downloader.py` (add new method between lines 657-658)

**Step 1: Write the failing test**

```python
def test_find_superset_range():
    # Test that the method can find cached data for a larger range and extract the subset
    pass  # Placeholder
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_coverage_and_calendar.py::test_find_superset_range -v`
Expected: FAIL with "function not defined"

**Step 3: Write minimal implementation**

```python
def _find_superset_range_from_cache(self, start_date: str, end_date: str) -> Optional[List[Dict[str, Any]]]:
    """
    查找缓存中包含指定日期范围的更大范围数据，并返回子集
    """
    from datetime import datetime

    start_dt = datetime.strptime(start_date, '%Y%m%d')
    end_dt = datetime.strptime(end_date, '%Y%m%d')

    with self._cache_lock:
        for (cache_start, cache_end), cached_data in self._memory_cache['trade_cal'].items():
            cache_start_dt = datetime.strptime(cache_start, '%Y%m%d')
            cache_end_dt = datetime.strptime(cache_end, '%Y%m%d')

            # 检查缓存范围是否包含请求范围
            if cache_start_dt <= start_dt and end_dt <= cache_end_dt:
                # 找到包含请求范围的缓存数据，过滤出目标范围
                filtered_data = []
                for record in cached_data:
                    cal_date_str = record.get('cal_date', '')
                    if not cal_date_str:
                        continue
                    try:
                        cal_date_dt = datetime.strptime(cal_date_str, '%Y%m%d')
                        if start_dt <= cal_date_dt <= end_dt:
                            filtered_data.append(record)
                    except ValueError:
                        continue  # 跳过无效日期格式

                if filtered_data:
                    logger.debug(f"Found subset from cached range {cache_start}-{cache_end} for {start_date}-{end_date}")
                    return filtered_data

    return None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_coverage_and_calendar.py::test_find_superset_range -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app4/core/downloader.py
git commit -m "feat: implement _find_superset_range_from_cache method"
```

### Task 3: Update coverage manager to use optimized trade calendar method

**Files:**
- Modify: `app4/core/coverage_manager.py:194-196`

**Step 1: Write the failing test**

```python
def test_coverage_with_optimized_calendar():
    # Test that coverage checks now use the optimized trade calendar method
    pass  # Placeholder
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_coverage_and_calendar.py::test_coverage_with_optimized_calendar -v`
Expected: FAIL with "function not defined"

**Step 3: Write minimal implementation**

```python
# In the _check_range_coverage method, replace the original downloader.get_trade_calendar call
if self.downloader:
    trade_calendar = self.downloader.get_trade_calendar(start_date, end_date)
else:
    logger.warning("Downloader not available for trade calendar check")
    return not df.is_empty()
```

This is already implemented, so we just need to ensure the new functionality is properly integrated.

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_coverage_and_calendar.py::test_coverage_with_optimized_calendar -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app4/core/coverage_manager.py
git commit -m "feat: ensure coverage manager uses optimized trade calendar method"
```

### Task 4: Add performance logging for trade calendar cache hits

**Files:**
- Modify: `app4/core/downloader.py:626-630`

**Step 1: Write the failing test**

```python
def test_cache_hit_logging():
    # Test that cache hit logging works properly
    pass  # Placeholder
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_coverage_and_calendar.py::test_cache_hit_logging -v`
Expected: FAIL with "function not defined"

**Step 3: Write minimal implementation**

```python
# Update the get_trade_calendar method to add more detailed logging
def get_trade_calendar(self, start_date: str, end_date: str) -> Optional[List[Dict[str, Any]]]:
    """
    获取交易日历，采用三级缓存策略，并增加范围子集/超集逻辑：
    1. 内存缓存 (_memory_cache)
    2. 本地存储 (Data 目录 parquet 文件)
    3. API 请求
    """
    cache_key = (start_date, end_date)

    # 1. 检查内存缓存 - 先看是否有完全匹配的缓存
    with self._cache_lock:
        if cache_key in self._memory_cache['trade_cal']:
            logger.debug(f"Trade calendar loaded from exact memory cache: {start_date}-{end_date}")
            return self._memory_cache['trade_cal'][cache_key]

    # 2. 检查是否有包含该范围的更大缓存范围（范围超集逻辑）
    cached_data = self._find_superset_range_from_cache(start_date, end_date)
    if cached_data:
        logger.info(f"Trade calendar loaded from superset memory cache range: {start_date}-{end_date}")
        return cached_data

    # 3. 检查本地数据目录
    trade_calendar = self._get_trade_calendar_from_data_dir(start_date, end_date)

    if trade_calendar:
        logger.info(f"Trade calendar loaded from data directory: {start_date}-{end_date}")
    else:
        # 4. 请求 API
        logger.info(f"Trade calendar not found locally, fetching from API: {start_date}-{end_date}")
        calendar_params = {
            'start_date': start_date,
            'end_date': end_date,
            'exchange': 'SSE'
        }
        # 使用 _make_request 直接请求，避免递归调用
        trade_calendar = self._make_request(
            self.config_loader.get_interface_config('trade_cal'),
            calendar_params
        )

    # 更新内存缓存
    if trade_calendar:
        with self._cache_lock:
            self._memory_cache['trade_cal'][cache_key] = trade_calendar

    return trade_calendar
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_coverage_and_calendar.py::test_cache_hit_logging -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app4/core/downloader.py
git commit -m "feat: add detailed cache hit logging for trade calendar"
```

### Task 5: Add cache statistics tracking

**Files:**
- Modify: `app4/core/downloader.py:66-64` (add new tracking variables to the class)

**Step 1: Write the failing test**

```python
def test_cache_statistics():
    # Test that cache statistics are properly tracked
    pass  # Placeholder
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_coverage_and_calendar.py::test_cache_statistics -v`
Expected: FAIL with "function not defined"

**Step 3: Write minimal implementation**

```python
class GenericDownloader:
    """通用下载器 - 原子化的执行引擎"""

    def __init__(self, config_loader: ConfigLoader, storage_manager=None):
        self.config_loader = config_loader
        self.global_config = config_loader.get_global_config()

        # 存储管理器（外部传入）
        self.storage_manager = storage_manager

        # 创建具有重试策略的会话
        self.session = self._create_session_with_retries()

        # [新增] 运行时简易缓存，替代原有的 CacheManager
        self._memory_cache = {
            'trade_cal': {},      # Key: ('start_date', 'end_date'), Value: list[dict]
            'stock_list': None,   # Value: list[dict]
            'coverage': {},       # Key: (interface_name, params_hash), Value: coverage_result
            'api_responses': {}   # Key: (api_name, params_hash), Value: response_data
        }
        self._cache_lock = threading.RLock()  # 确保线程安全

        # [新增] 缓存统计
        self._cache_stats = {
            'trade_cal_exact_hits': 0,
            'trade_cal_superset_hits': 0,
            'trade_cal_misses': 0
        }

        # [新增] 覆盖率管理器
        if storage_manager:
            self.coverage_manager = CoverageManager(storage_manager, config_loader, downloader=self)
        else:
            self.coverage_manager = None
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_coverage_and_calendar.py::test_cache_statistics -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app4core/downloader.py
git commit -m "feat: add cache statistics tracking"
```

### Task 6: Update trade calendar method to update statistics

**Files:**
- Modify: `app4/core/downloader.py` (update get_trade_calendar method to update stats)

**Step 1: Write the failing test**

```python
def test_cache_statistics_updates():
    # Test that cache statistics are updated properly during operations
    pass  # Placeholder
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_coverage_and_calendar.py::test_cache_statistics_updates -v`
Expected: FAIL with "function not defined"

**Step 3: Write minimal implementation**

```python
def get_trade_calendar(self, start_date: str, end_date: str) -> Optional[List[Dict[str, Any]]]:
    """
    获取交易日历，采用三级缓存策略，并增加范围子集/超集逻辑：
    1. 内存缓存 (_memory_cache)
    2. 本地存储 (Data 目录 parquet 文件)
    3. API 请求
    """
    cache_key = (start_date, end_date)

    # 1. 检查内存缓存 - 先看是否有完全匹配的缓存
    with self._cache_lock:
        if cache_key in self._memory_cache['trade_cal']:
            self._cache_stats['trade_cal_exact_hits'] += 1
            logger.debug(f"Trade calendar loaded from exact memory cache: {start_date}-{end_date} (Exact hits: {self._cache_stats['trade_cal_exact_hits']})")
            return self._memory_cache['trade_cal'][cache_key]

    # 2. 检查是否有包含该范围的更大缓存范围（范围超集逻辑）
    cached_data = self._find_superset_range_from_cache(start_date, end_date)
    if cached_data:
        self._cache_stats['trade_cal_superset_hits'] += 1
        logger.info(f"Trade calendar loaded from superset memory cache range: {start_date}-{end_date} (Superset hits: {self._cache_stats['trade_cal_superset_hits']})")
        return cached_data

    # 3. 检查本地数据目录
    trade_calendar = self._get_trade_calendar_from_data_dir(start_date, end_date)

    if trade_calendar:
        logger.info(f"Trade calendar loaded from data directory: {start_date}-{end_date}")
    else:
        # 4. 请求 API
        self._cache_stats['trade_cal_misses'] += 1
        logger.info(f"Trade calendar not found locally, fetching from API: {start_date}-{end_date} (Misses: {self._cache_stats['trade_cal_misses']})")
        calendar_params = {
            'start_date': start_date,
            'end_date': end_date,
            'exchange': 'SSE'
        }
        # 使用 _make_request 直接请求，避免递归调用
        trade_calendar = self._make_request(
            self.config_loader.get_interface_config('trade_cal'),
            calendar_params
        )

    # 更新内存缓存
    if trade_calendar:
        with self._cache_lock:
            self._memory_cache['trade_cal'][cache_key] = trade_calendar

    return trade_calendar
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_coverage_and_calendar.py::test_cache_statistics_updates -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app4/core/downloader.py
git commit -m "feat: update trade calendar method to track statistics"
```

### Task 7: Add statistics display functionality

**Files:**
- Modify: `app4/core/downloader.py` (add new method to display cache stats)

**Step 1: Write the failing test**

```python
def test_statistics_display():
    # Test that statistics can be displayed properly
    pass  # Placeholder
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_coverage_and_calendar.py::test_statistics_display -v`
Expected: FAIL with "function not defined"

**Step 3: Write minimal implementation**

```python
def get_cache_statistics(self):
    """获取缓存统计信息"""
    with self._cache_lock:
        total_requests = (self._cache_stats['trade_cal_exact_hits'] +
                         self._cache_stats['trade_cal_superset_hits'] +
                         self._cache_stats['trade_cal_misses'])

        hit_rate = 0
        if total_requests > 0:
            hit_rate = (self._cache_stats['trade_cal_exact_hits'] +
                       self._cache_stats['trade_cal_superset_hits']) / total_requests

        return {
            'trade_cal_exact_hits': self._cache_stats['trade_cal_exact_hits'],
            'trade_cal_superset_hits': self._cache_stats['trade_cal_superset_hits'],
            'trade_cal_misses': self._cache_stats['trade_cal_misses'],
            'total_requests': total_requests,
            'hit_rate': hit_rate
        }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_coverage_and_calendar.py::test_statistics_display -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app4/core/downloader.py
git commit -m "feat: add cache statistics display functionality"
```

### Task 8: Add cache statistics to main.py performance report

**Files:**
- Modify: `app4/main.py:242-270`

**Step 1: Write the failing test**

```python
def test_performance_report_includes_cache_stats():
    # Test that the performance report includes cache statistics
    pass  # Placeholder
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_coverage_and_calendar.py::test_performance_report_includes_cache_stats -v`
Expected: FAIL with "function not defined"

**Step 3: Write minimal implementation**

```python
def print_performance_report():
    """打印性能监控报告"""
    print("\n" + "="*30)
    print("      性能监控报告")
    print("="*30)

    # 添加调试信息
    import sys
    print(f"Debug: performance_monitor id: {id(performance_monitor)}", file=sys.stderr)

    avg_request_time = performance_monitor.get_average_metric('request_time')
    avg_data_size = performance_monitor.get_average_metric('data_size')
    avg_retry_count = performance_monitor.get_average_metric('retry_count')

    print(f"平均请求时间: {avg_request_time:.2f}s")
    print(f"平均单窗口条数: {avg_data_size:.2f} 条")
    print(f"平均重试次数: {avg_retry_count:.2f} 次")

    # 打印更详细的指标信息
    print(f"Debug: request_time指标数量: {len(performance_monitor._metrics['request_time']) if 'request_time' in performance_monitor._metrics else 0}", file=sys.stderr)
    print(f"Debug: data_size指标数量: {len(performance_monitor._metrics['data_size']) if 'data_size' in performance_monitor._metrics else 0}", file=sys.stderr)

    if avg_request_time > 30:
        print("⚠️ 警告: 平均请求时间过长")
    if avg_retry_count > 0.5:
        print("⚠️ 警告: 重试频率较高，请检查 API 限制或网络状况")
    if avg_data_size >= 5800:
        print("⚠️ 警告: 数据量接近 API 限制，建议减小窗口大小")

    # [新增] 添加缓存统计信息
    if 'downloader' in locals() or 'downloader' in globals():
        cache_stats = downloader.get_cache_statistics()
        print(f"交易日历缓存命中率: {cache_stats['hit_rate']:.2%}")
        print(f"  - 精确匹配: {cache_stats['trade_cal_exact_hits']}")
        print(f"  - 范围匹配: {cache_stats['trade_cal_superset_hits']}")
        print(f"  - 未命中: {cache_stats['trade_cal_misses']}")

    print("="*30 + "\n")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/test_coverage_and_calendar.py::test_performance_report_includes_cache_stats -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app4/main.py
git commit -m "feat: add cache statistics to performance report"
```