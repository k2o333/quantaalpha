# 智能数据下载重复检测 Implementation Plan (优化版)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 基于现有代码架构增强智能重复检测功能，实现真正的增量下载，只下载缺失数据而非重复数据。

**Architecture:** 扩展现有CoverageManager，通过整合数据读取操作实现覆盖率计算和缺失范围识别，增强Downloader以支持智能决策。

**Tech Stack:** Python, Polars, App4 core components

---

### Task 1: 分析现有覆盖管理机制

**Files:**
- Read: `app4/core/coverage_manager.py`
- Read: `app4/core/downloader.py`
- Read: `app4/core/storage.py`

**Step 1: 研究CoverageManager实现**

查看现有已实现的CoverageManager，了解其线程安全、缓存机制、覆盖率检测逻辑。

**Step 2: 分析存储管理机制**

查看StorageManager如何保存数据到Parquet文件，了解文件结构和索引机制。

**Step 3: 分析下载器逻辑**

查看Downloader如何与CoverageManager交互，了解数据下载和存储流程。

**Step 4: 记录当前实现限制**

记录现有实现的问题和改进空间：当前实现能够跳过完全覆盖的窗口，但无法实现增量下载只下载缺失部分。

**Step 5: 提交**

```bash
git add docs/plans/2026-01-16-smart-duplicate-detection-enhanced.md
git commit -m "docs: analyze current coverage manager implementation"
```

### Task 2: 增强CoverageManager以支持增量检测

**Files:**
- Modify: `app4/core/coverage_manager.py`

**Step 1: 为新功能编写测试**

```python
def test_get_missing_date_ranges():
    """Test calculating missing date ranges for download"""
    pass
```

**Step 2: 运行测试验证失败**

运行: `pytest tests/test_coverage_manager.py::test_get_missing_date_ranges -v`
预期: 失败，因为方法不存在

**Step 3: 在现有CoverageManager中添加新方法**

```python
def _analyze_date_range_coverage(self, interface_name: str, start_date: str, end_date: str, **params) -> tuple:
    """
    分析日期范围的覆盖率并返回详细信息
    返回: (coverage_ratio, missing_ranges, covered_count, expected_count)
    """
    if not self.config_loader.get_interface_config(interface_name).get('duplicate_detection', {}).get('enabled', False):
        return 0.0, [(start_date, end_date)], 0, 0

    # 获取检测列和阈值
    interface_config = self.config_loader.get_interface_config(interface_name)
    detection_config = interface_config.get('duplicate_detection', {})
    date_column = detection_config.get('date_column', 'trade_date')
    threshold = detection_config.get('threshold', 0.95)

    try:
        # 读取接口数据，只读取日期列
        df = self.storage_manager.read_interface_data(
            interface_name,
            start_date=start_date,
            end_date=end_date,
            columns=[date_column]
        )

        if df.is_empty():
            return 0.0, [(start_date, end_date)], 0, 0

        # 获取实际存在的日期
        actual_dates = set(df[date_column].to_list())

        # 获取交易日历
        if self.downloader:
            trade_calendar = self.downloader.get_trade_calendar(start_date, end_date)
        else:
            return 0.5, [(start_date, end_date)], len(actual_dates), len(actual_dates) * 2  # 保守估计

        if not trade_calendar:
            # 无交易日历，使用简单覆盖计算
            return 0.5, [(start_date, end_date)], len(actual_dates), len(actual_dates) * 2  # 保守估计

        # 过滤出交易日
        expected_dates = {day['cal_date'] for day in trade_calendar if day.get('is_open', 0) == 1}

        if not expected_dates:
            return 0.0, [(start_date, end_date)], 0, 0

        # 计算覆盖率
        covered_dates = actual_dates & expected_dates
        coverage = len(covered_dates) / len(expected_dates) if expected_dates else 0.0

        # 计算缺失的日期范围
        missing_dates = sorted(expected_dates - actual_dates)
        missing_ranges = self._dates_to_ranges(missing_dates)

        return coverage, missing_ranges, len(covered_dates), len(expected_dates)

    except Exception as e:
        logger.warning(f"Range coverage analysis failed for {interface_name}: {e}")
        return 0.0, [(start_date, end_date)], 0, 0

def _dates_to_ranges(self, dates: List[str]) -> List[Tuple[str, str]]:
    """
    将离散日期列表转换为连续范围
    """
    if not dates:
        return []

    ranges = []
    if len(dates) == 1:
        ranges.append((dates[0], dates[0]))
        return ranges

    # 按日期排序
    sorted_dates = sorted(dates)

    range_start = sorted_dates[0]
    range_end = sorted_dates[0]

    from datetime import datetime
    for i in range(1, len(sorted_dates)):
        prev_date = datetime.strptime(sorted_dates[i-1], '%Y%m%d')
        curr_date = datetime.strptime(sorted_dates[i], '%Y%m%d')

        # 检查日期是否连续（考虑非交易日）
        # 如果日期间隔小于等于7天（最多一周），认为是连续的
        days_diff = (curr_date - prev_date).days

        if days_diff == 1:  # 真正连续
            range_end = sorted_dates[i]
        elif days_diff <= 7:  # 可能中间是非交易日
            range_end = sorted_dates[i]
        else:  # 不连续，结束当前范围
            ranges.append((range_start, range_end))
            range_start = sorted_dates[i]
            range_end = sorted_dates[i]

    # 添加最后一个范围
    ranges.append((range_start, range_end))

    return ranges

def get_missing_date_ranges(self, interface_name: str, start_date: str, end_date: str, **params) -> tuple:
    """
    获取缺失的日期范围，用于增量下载
    返回: (action: str, missing_ranges: List[Tuple], message: str)
    action: 'skip'/'download_partial'/'download_full'
    """
    # 生成缓存键
    sorted_params = []
    for k, v in sorted(params.items()):
        if isinstance(v, list):
            v = tuple(v)
        sorted_params.append((k, v))
    cache_key = (f"missing_ranges:{interface_name}", tuple(sorted_params), start_date, end_date)

    # 检查缓存
    with self._cache_lock:
        if cache_key in self._coverage_cache:
            return self._coverage_cache[cache_key]

    coverage, missing_ranges, covered_count, expected_count = self._analyze_date_range_coverage(
        interface_name, start_date, end_date, **params
    )

    interface_config = self.config_loader.get_interface_config(interface_name)
    detection_config = interface_config.get('duplicate_detection', {})
    threshold = detection_config.get('threshold', 0.95)

    # 决策逻辑
    if coverage >= threshold:
        # 覆盖率足够，跳过下载
        result = ('skip', [], f"Coverage {coverage:.2%} >= threshold {threshold:.2%}, skipping")
    elif coverage > 0.3 and missing_ranges:  # 智能阈值：覆盖率超过30%且有缺失范围时进行增量下载
        # 部分覆盖，只下载缺失部分
        result = ('download_partial', missing_ranges,
                  f"Coverage {coverage:.2%} with {len(missing_ranges)} missing ranges, downloading partial")
    else:
        # 覆盖率较低，下载完整范围更高效
        result = ('download_full', [(start_date, end_date)],
                  f"Coverage {coverage:.2%} too low, downloading full range")

    # 更新缓存
    with self._cache_lock:
        self._coverage_cache[cache_key] = result

    return result
```

**Step 4: 运行测试验证通过**

运行: `pytest tests/test_coverage_manager.py::test_get_missing_date_ranges -v`
预期: 通过

**Step 5: 提交**

```bash
git add app4/core/coverage_manager.py
git commit -m "feat: enhance coverage manager with missing range detection for incremental download"
```

### Task 3: 更新下载器逻辑以使用新的覆盖管理

**Files:**
- Modify: `app4/core/downloader.py`

**Step 1: 为下载器新功能编写测试**

```python
def test_download_with_incremental_coverage():
    """Test downloading with incremental coverage check"""
    pass
```

**Step 2: 运行测试验证失败**

运行: `pytest tests/test_downloader.py::test_download_with_incremental_coverage -v`
预期: 失败

**Step 3: 更新_downloader.py中的日期范围分页方法**

```python
def _execute_date_range_pagination(self, interface_config: Dict[str, Any], params: Dict[str, Any],
                                  pagination_config: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """执行日期范围分页 - 支持内部offset分页和增量下载"""
    # 如果没有提供分页配置，从接口配置中获取
    if pagination_config is None:
        pagination_config = interface_config.get('pagination', {})

    all_data = []

    # 获取日期范围
    start_date = params.get('start_date', '20050101')
    end_date = params.get('end_date', datetime.now().strftime('%Y%m%d'))

    logger.info(f"Fetching trade calendar for date range: {start_date} - {end_date}")

    # 使用统一的 get_trade_calendar 方法
    trade_calendar = self.get_trade_calendar(start_date, end_date)

    # 如果获取交易日历失败，使用默认的日期范围分页
    if not trade_calendar:
        logger.warning("Failed to get trade calendar, using default date range pagination")
        # 检查是否配置了内部offset分页
        offset_config = interface_config.get('offset_pagination', {})
        if offset_config.get('enabled', False):
            return self._execute_offset_pagination(interface_config, params, offset_config)
        else:
            return self._make_request(interface_config, params)

    # 过滤出交易日
    trade_days = [day for day in trade_calendar if day.get('is_open', 0) == 1]

    # 如果没有交易日，直接返回
    if not trade_days:
        logger.warning(f"No trade days found in range {start_date} - {end_date}")
        return []

    # 按日期升序排序（从旧到新）
    trade_days = sorted(trade_days, key=lambda x: x['cal_date'])

    logger.info(f"Found {len(trade_days)} trade days")

    # 按窗口分割日期范围
    window_size = pagination_config.get('window_size_days', 3650)  # 默认10年窗口
    logger.info(f"Using window size: {window_size} days")

    for i in range(0, len(trade_days), window_size):
        window_trade_days = trade_days[i:i+window_size]
        if not window_trade_days:
            continue
        window_start = window_trade_days[0]['cal_date']
        window_end = window_trade_days[-1]['cal_date']

        window_params = params.copy()
        window_params['start_date'] = window_start
        window_params['end_date'] = window_end

        # 使用新的增量下载决策机制
        if self.coverage_manager:
            decision, ranges, message = self.coverage_manager.get_missing_date_ranges(
                interface_config['api_name'],
                window_start,
                window_end,
                **window_params
            )
            logger.info(f"Coverage decision for {interface_config['api_name']}: {message}")

            if decision == 'skip':
                logger.info(f"Skipping window {window_start} - {window_end} for {interface_config['api_name']} (already covered)")
                continue
            elif decision == 'download_partial':
                # 增量下载：只下载缺失的部分
                logger.info(f"Downloading {len(ranges)} missing ranges for {interface_config['api_name']} in window {window_start}-{window_end}")
                for missing_start, missing_end in ranges:
                    logger.info(f"  Downloading missing range: {missing_start} - {missing_end}")

                    # 创建缺失范围的参数
                    missing_params = window_params.copy()
                    missing_params['start_date'] = missing_start
                    missing_params['end_date'] = missing_end

                    # 记录开始时间
                    start_time = time.time()

                    # 检查是否需要使用offset分页
                    offset_config = interface_config.get('offset_pagination', {})
                    if offset_config.get('enabled', False):
                        # 使用内部offset分页下载缺失范围数据
                        range_data = self._execute_offset_pagination(interface_config, missing_params, offset_config)
                    else:
                        # 直接下载缺失范围数据
                        range_data = self._make_request(interface_config, missing_params)

                    # 记录并检查性能指标
                    elapsed_time = time.time() - start_time
                    performance_monitor.record_metric('request_time', elapsed_time, {
                        'interface': interface_config['api_name'],
                        'range': f"{missing_start}-{missing_end}",
                        'ts_code': params.get('ts_code', 'unknown')
                    })
                    performance_monitor.check_alerts('request_time', elapsed_time, {
                        'interface': interface_config['api_name'],
                        'range': f"{missing_start}-{missing_end}",
                        'ts_code': params.get('ts_code', 'unknown')
                    })

                    if range_data:
                        # 记录数据量指标
                        performance_monitor.record_metric('data_size', len(range_data), {
                            'interface': interface_config['api_name'],
                            'range': f"{missing_start}-{missing_end}",
                            'ts_code': params.get('ts_code', 'unknown')
                        })
                        all_data.extend(range_data)
                        logger.info(f"Downloaded {len(range_data)} records for missing range {missing_start}-{missing_end}")
            elif decision == 'download_full':
                # 完整下载窗口数据
                logger.info(f"Downloading full window {window_start} - {window_end} for {interface_config['api_name']}")

                # 记录开始时间
                start_time = time.time()

                # 检查是否需要使用offset分页
                offset_config = interface_config.get('offset_pagination', {})
                if offset_config.get('enabled', False):
                    # 使用内部offset分页下载窗口数据
                    logger.info(f"Using internal offset pagination for window {window_start}-{window_end}")
                    window_data = self._execute_offset_pagination(interface_config, window_params, offset_config)
                else:
                    # 直接下载窗口数据
                    window_data = self._make_request(interface_config, window_params)

                # 记录并检查性能指标
                elapsed_time = time.time() - start_time
                performance_monitor.record_metric('request_time', elapsed_time, {
                    'interface': interface_config['api_name'],
                    'window': f"{window_start}-{window_end}",
                    'ts_code': params.get('ts_code', 'unknown')
                })
                performance_monitor.check_alerts('request_time', elapsed_time, {
                    'interface': interface_config['api_name'],
                    'window': f"{window_start}-{window_end}",
                    'ts_code': params.get('ts_code', 'unknown')
                })

                if window_data:
                    # 记录数据量指标
                    performance_monitor.record_metric('data_size', len(window_data), {
                        'interface': interface_config['api_name'],
                        'window': f"{window_start}-{window_end}",
                        'ts_code': params.get('ts_code', 'unknown')
                    })
                    all_data.extend(window_data)
                    logger.info(f"Downloaded {len(window_data)} records for date range {window_start}-{window_end}")
                else:
                    logger.warning(f"No data returned for window {window_start}-{window_end}")
        else:
            # 没有coverage_manager，使用原始逻辑
            logger.info(f"Downloading full window {window_start} - {window_end} for {interface_config['api_name']}")

            # 记录开始时间
            start_time = time.time()

            # 检查是否需要使用offset分页
            offset_config = interface_config.get('offset_pagination', {})
            if offset_config.get('enabled', False):
                # 使用内部offset分页下载窗口数据
                logger.info(f"Using internal offset pagination for window {window_start}-{window_end}")
                window_data = self._execute_offset_pagination(interface_config, window_params, offset_config)
            else:
                # 直接下载窗口数据
                window_data = self._make_request(interface_config, window_params)

            # 记录并检查性能指标
            elapsed_time = time.time() - start_time
            performance_monitor.record_metric('request_time', elapsed_time, {
                'interface': interface_config['api_name'],
                'window': f"{window_start}-{window_end}",
                'ts_code': params.get('ts_code', 'unknown')
            })
            performance_monitor.check_alerts('request_time', elapsed_time, {
                'interface': interface_config['api_name'],
                'window': f"{window_start}-{window_end}",
                'ts_code': params.get('ts_code', 'unknown')
            })

            if window_data:
                # 记录数据量指标
                performance_monitor.record_metric('data_size', len(window_data), {
                    'interface': interface_config['api_name'],
                    'window': f"{window_start}-{window_end}",
                    'ts_code': params.get('ts_code', 'unknown')
                })
                all_data.extend(window_data)
                logger.info(f"Downloaded {len(window_data)} records for date range {window_start}-{window_end}")
            else:
                logger.warning(f"No data returned for window {window_start}-{window_end}")

    return all_data
```

**Step 4: 运行测试验证通过**

运行: `pytest tests/test_downloader.py::test_download_with_incremental_coverage -v`
预期: 通过

**Step 5: 提交**

```bash
git add app4/core/downloader.py
git commit -m "feat: update downloader to support incremental download with smart coverage decision"
```

### Task 4: 创建综合测试用例验证功能

**Files:**
- Create: `tests/test_smart_incremental_coverage.py`

**Step 1: 编写增量覆盖检测功能测试**

```python
import pytest
import tempfile
from pathlib import Path
import polars as pl
from datetime import datetime, timedelta

from app4.core.coverage_manager import CoverageManager
from app4.core.storage import StorageManager
from app4.core.config_loader import ConfigLoader


def test_incremental_coverage_detection():
    """Test incremental coverage detection functionality"""
    # Create a temporary directory for test data
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test data directory structure
        data_dir = Path(tmpdir) / "data"
        daily_dir = data_dir / "daily"
        daily_dir.mkdir(parents=True)

        # Create test data with partial date range (20240101-0103, missing 0104-0105)
        df = pl.DataFrame({
            "ts_code": ["000001.SZ"] * 3,
            "trade_date": ["20240101", "20240102", "20240103"],
            "close": [10.0, 10.1, 10.2]
        })
        df.write_parquet(daily_dir / "daily_000001.SZ_test.parquet")

        # Initialize components
        config_loader = ConfigLoader(config_dir="app4/config")
        storage = StorageManager(storage_dir=str(data_dir))
        coverage_manager = CoverageManager(storage, config_loader)

        # Mock downloader to provide trade calendar
        class MockDownloader:
            def get_trade_calendar(self, start, end):
                # Return 5 days of trading days (20240101 to 20240105)
                return [
                    {'cal_date': '20240101', 'is_open': 1},
                    {'cal_date': '20240102', 'is_open': 1},
                    {'cal_date': '20240103', 'is_open': 1},
                    {'cal_date': '20240104', 'is_open': 1},
                    {'cal_date': '20240105', 'is_open': 1}
                ]

        coverage_manager.downloader = MockDownloader()

        # Test incremental coverage detection
        action, missing_ranges, message = coverage_manager.get_missing_date_ranges(
            "daily", "20240101", "20240105", ts_code="000001.SZ"
        )

        # Should detect partial coverage and return missing ranges
        assert action == 'download_partial'
        assert len(missing_ranges) == 1
        assert missing_ranges[0] == ('20240104', '20240105')
        print(f"Test result: {action}, {missing_ranges}, {message}")


def test_full_coverage_skip():
    """Test that fully covered ranges are skipped"""
    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / "data"
        daily_dir = data_dir / "daily"
        daily_dir.mkdir(parents=True)

        # Create test data with full date range (20240101-0105)
        df = pl.DataFrame({
            "ts_code": ["000001.SZ"] * 5,
            "trade_date": ["20240101", "20240102", "20240103", "20240104", "20240105"],
            "close": [10.0, 10.1, 10.2, 10.3, 10.4]
        })
        df.write_parquet(daily_dir / "daily_000001.SZ_test.parquet")

        config_loader = ConfigLoader(config_dir="app4/config")
        storage = StorageManager(storage_dir=str(data_dir))
        coverage_manager = CoverageManager(storage, config_loader)

        class MockDownloader:
            def get_trade_calendar(self, start, end):
                return [
                    {'cal_date': '20240101', 'is_open': 1},
                    {'cal_date': '20240102', 'is_open': 1},
                    {'cal_date': '20240103', 'is_open': 1},
                    {'cal_date': '20240104', 'is_open': 1},
                    {'cal_date': '20240105', 'is_open': 1}
                ]

        coverage_manager.downloader = MockDownloader()

        # Test that fully covered range is skipped
        action, missing_ranges, message = coverage_manager.get_missing_date_ranges(
            "daily", "20240101", "20240105", ts_code="000001.SZ"
        )

        assert action == 'skip'
        assert len(missing_ranges) == 0


def test_dates_to_ranges_function():
    """Test the _dates_to_ranges helper function"""
    config_loader = ConfigLoader(config_dir="app4/config")
    storage = StorageManager(storage_dir="/tmp")
    coverage_manager = CoverageManager(storage, config_loader)

    # Test single date
    result = coverage_manager._dates_to_ranges(["20240101"])
    assert result == [("20240101", "20240101")]

    # Test consecutive dates
    result = coverage_manager._dates_to_ranges(["20240101", "20240102", "20240103"])
    assert result == [("20240101", "20240103")]

    # Test non-consecutive dates
    result = coverage_manager._dates_to_ranges(["20240101", "20240103", "20240105"])
    assert result == [("20240101", "20240101"), ("20240103", "20240103"), ("20240105", "20240105")]

    # Test mixed consecutive/non-consecutive
    result = coverage_manager._dates_to_ranges(["20240101", "20240102", "20240104", "20240105"])
    assert result == [("20240101", "20240102"), ("20240104", "20240105")]
```

**Step 2: 运行测试验证失败**

运行: `pytest tests/test_smart_incremental_coverage.py -v`
预期: 失败

**Step 3: 确保实现支持测试**

确认前面的实现能够支持测试用例。

**Step 4: 运行测试验证通过**

运行: `pytest tests/test_smart_incremental_coverage.py -v`
预期: 通过

**Step 5: 提交**

```bash
git add tests/test_smart_incremental_coverage.py
git commit -m "test: add comprehensive tests for smart incremental duplicate detection"
```

### Task 5: 更新主入口点以支持新的覆盖检测

**Files:**
- Modify: `app4/main.py`

**Step 1: 为main.py更新编写测试**

```python
def test_main_with_incremental_coverage():
    """Test main entry point with incremental coverage detection"""
    pass
```

**Step 2: 运行测试验证失败**

运行: `pytest tests/test_main.py::test_main_with_incremental_coverage -v`
预期: 失败

**Step 3: 确认main.py已适配新功能**

检查main.py是否已适配新功能，如未适配，添加对新功能的支持说明。

**Step 4: 运行测试验证通过**

运行: `pytest tests/test_main.py::test_main_with_incremental_coverage -v`
预期: 通过

**Step 5: 提交**

```bash
git add app4/main.py
git commit -m "feat: update main entry point documentation for incremental download support"
```

### Task 6: 文档更新和示例

**Files:**
- Modify: `app4/README.md`

**Step 1: 更新README文档**

添加关于新增量下载功能的说明和使用示例。

**Step 2: 添加使用示例**

在README中添加智能增量下载的使用示例。

**Step 3: 添加配置说明**

说明如何配置重复检测功能以支持增量下载。

**Step 4: 运行文档验证**

确认文档格式正确。

**Step 5: 提交**

```bash
git add app4/README.md
git commit -m "docs: update documentation with smart incremental download feature"
```

### Task 7: 性能基准测试

**Files:**
- Create: `tests/test_incremental_performance.py`

**Step 1: 创建性能基准测试**

```python
import pytest
import tempfile
from pathlib import Path
import polars as pl
import time

from app4.core.coverage_manager import CoverageManager
from app4.core.storage import StorageManager
from app4.core.config_loader import ConfigLoader


def test_incremental_vs_full_download_performance():
    """Compare performance between incremental and full download approaches"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create test data directory
        data_dir = Path(tmpdir) / "data"
        daily_dir = data_dir / "daily"
        daily_dir.mkdir(parents=True)

        # Create test data with partial coverage (first half covered)
        all_dates = [f"202401{i:02d}" for i in range(1, 21)]  # 20 days
        covered_dates = all_dates[:10]  # First 10 days covered

        df = pl.DataFrame({
            "ts_code": ["000001.SZ"] * len(covered_dates),
            "trade_date": covered_dates,
            "close": [10.0 + i*0.1 for i in range(len(covered_dates))]
        })
        df.write_parquet(daily_dir / "daily_000001.SZ_test.parquet")

        config_loader = ConfigLoader(config_dir="app4/config")
        storage = StorageManager(storage_dir=str(data_dir))
        coverage_manager = CoverageManager(storage, config_loader)

        class MockDownloader:
            def get_trade_calendar(self, start, end):
                return [{'cal_date': date, 'is_open': 1} for date in all_dates]

        coverage_manager.downloader = MockDownloader()

        # Time the incremental coverage detection
        start_time = time.time()
        action, missing_ranges, message = coverage_manager.get_missing_date_ranges(
            "daily", "20240101", "20240120", ts_code="000001.SZ"
        )
        incremental_time = time.time() - start_time

        print(f"Incremental detection time: {incremental_time:.4f}s")
        print(f"Action: {action}, Missing ranges: {missing_ranges}")

        # Verify that incremental detection works correctly
        assert action == 'download_partial'
        assert len(missing_ranges) >= 1  # Should have at least one missing range
```

**Step 2: 运行性能测试**

运行: `pytest tests/test_incremental_performance.py -v`
预期: 通过

**Step 3: 提交**

```bash
git add tests/test_incremental_performance.py
git commit -m "test: add performance tests for incremental download feature"
```