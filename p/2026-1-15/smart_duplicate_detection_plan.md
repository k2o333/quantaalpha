# 智能数据下载重复检测 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 实现智能重复检测功能，使下载命令能够跳过已存在的数据，仅下载缺失部分。

**Architecture:** 在App4架构中增强CoverageManager，通过Parquet索引检测已有数据范围，实现增量下载。

**Tech Stack:** Python, Polars, App4 core components

---

### Task 1: 分析现有覆盖管理机制

**Files:**
- Read: `app4/core/coverage_manager.py`
- Read: `app4/core/downloader.py`
- Read: `app4/core/storage.py`

**Step 1: 研究CoverageManager实现**

查看现有的重复检测逻辑，了解当前的date_range、period和stock策略实现。

**Step 2: 分析存储管理机制**

查看StorageManager如何保存数据到Parquet文件，了解文件结构和索引机制。

**Step 3: 分析下载器逻辑**

查看Downloader如何与CoverageManager交互，了解数据下载和存储流程。

**Step 4: 记录当前实现限制**

记录现有实现的问题和改进空间。

**Step 5: 提交**

```bash
git add docs/plans/2026-01-15-smart-duplicate-detection.md
git commit -m "docs: analyze current coverage manager implementation"
```

### Task 2: 设计索引查询功能

**Files:**
- Create: `app4/core/index_query.py`

**Step 1: 编写索引查询功能的测试**

```python
import pytest
from pathlib import Path
import polars as pl


def test_get_existing_date_range():
    """Test getting existing date range from parquet file"""
    pass


def test_get_existing_stock_codes():
    """Test getting existing stock codes from parquet file"""
    pass


def test_get_existing_periods():
    """Test getting existing periods from parquet file"""
    pass
```

**Step 2: 运行测试验证失败**

运行: `pytest tests/test_index_query.py -v`
预期: 失败，因为文件不存在

**Step 3: 编写最小实现**

```python
import polars as pl
from pathlib import Path
from typing import Optional, List, Dict, Any


class IndexQuery:
    """Query existing data from parquet files to determine what needs to be downloaded"""

    @staticmethod
    def get_existing_date_range(file_path: Path, date_column: str = "trade_date") -> Optional[tuple]:
        """
        Get the min and max date range from existing parquet file

        Args:
            file_path: Path to parquet file
            date_column: Name of date column

        Returns:
            Tuple of (min_date, max_date) or None if file doesn't exist
        """
        if not file_path.exists():
            return None

        try:
            # Read only the date column to get min/max efficiently
            df = pl.read_parquet(file_path, columns=[date_column])
            if df.is_empty():
                return None

            min_date = df[date_column].min()
            max_date = df[date_column].max()
            return (min_date, max_date)
        except Exception:
            return None

    @staticmethod
    def get_existing_stock_codes(file_path: Path, stock_column: str = "ts_code") -> List[str]:
        """
        Get all existing stock codes from parquet file

        Args:
            file_path: Path to parquet file
            stock_column: Name of stock code column

        Returns:
            List of existing stock codes
        """
        if not file_path.exists():
            return []

        try:
            df = pl.read_parquet(file_path, columns=[stock_column])
            if df.is_empty():
                return []

            return df[stock_column].unique().to_list()
        except Exception:
            return []

    @staticmethod
    def get_existing_periods(file_path: Path, period_column: str = "period") -> List[str]:
        """
        Get all existing periods from parquet file

        Args:
            file_path: Path to parquet file
            period_column: Name of period column

        Returns:
            List of existing period values
        """
        if not file_path.exists():
            return []

        try:
            df = pl.read_parquet(file_path, columns=[period_column])
            if df.is_empty():
                return []

            return df[period_column].unique().to_list()
        except Exception:
            return []

    @staticmethod
    def get_existing_primary_keys(file_path: Path, primary_key_columns: List[str]) -> List[Dict[str, Any]]:
        """
        Get all existing primary key combinations from parquet file

        Args:
            file_path: Path to parquet file
            primary_key_columns: List of primary key column names

        Returns:
            List of dictionaries containing primary key combinations
        """
        if not file_path.exists() or not primary_key_columns:
            return []

        try:
            df = pl.read_parquet(file_path, columns=primary_key_columns)
            if df.is_empty():
                return []

            # Create list of dictionaries for primary key combinations
            result = []
            for row in df.iter_rows(named=True):
                result.append({col: row[col] for col in primary_key_columns})
            return result
        except Exception:
            return []
```

**Step 4: 运行测试验证通过**

运行: `pytest tests/test_index_query.py -v`
预期: 通过

**Step 5: 提交**

```bash
git add app4/core/index_query.py
git commit -m "feat: add index query functionality for parquet files"
```

### Task 3: 增强CoverageManager

**Files:**
- Modify: `app4/core/coverage_manager.py`

**Step 1: 为CoverageManager编写更新测试**

```python
def test_get_existing_date_coverage():
    """Test getting existing date coverage from storage"""
    pass


def test_get_missing_date_ranges():
    """Test calculating missing date ranges for download"""
    pass


def test_get_missing_stock_codes():
    """Test identifying missing stock codes for download"""
    pass
```

**Step 2: 运行测试验证失败**

运行: `pytest tests/test_coverage_manager.py -v`
预期: 失败

**Step 3: 更新CoverageManager实现**

```python
import os
import json
import hashlib
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Set
from pathlib import Path
import polars as pl

from .index_query import IndexQuery


class CoverageManager:
    """Manages duplicate detection to avoid redundant downloads"""

    def __init__(self, storage_dir: str, interface_config: Dict[str, Any]):
        self.storage_dir = Path(storage_dir)
        self.interface_config = interface_config
        self.index_query = IndexQuery()

    def get_storage_path(self, interface_name: str, **params) -> Path:
        """Get the storage path for the given interface and parameters"""
        # Construct path based on interface name and parameters
        # This should match the logic in StorageManager
        filename_parts = [interface_name]

        # Add parameter-specific suffixes if needed
        if params.get('ts_code'):
            filename_parts.append(params['ts_code'])

        filename = '_'.join(filename_parts) + '.parquet'
        return self.storage_dir / interface_name / filename

    def is_date_range_covered(self, interface_name: str, start_date: str, end_date: str, **params) -> bool:
        """
        Check if the date range is already covered by existing data
        """
        if not self.interface_config.get('duplicate_detection', {}).get('enabled', False):
            return False

        storage_path = self.get_storage_path(interface_name, **params)
        existing_range = self.index_query.get_existing_date_range(
            storage_path,
            self.interface_config.get('duplicate_detection', {}).get('date_column', 'trade_date')
        )

        if existing_range is None:
            return False

        existing_start, existing_end = existing_range

        # Convert to datetime for comparison
        start_dt = datetime.strptime(start_date, '%Y%m%d')
        end_dt = datetime.strptime(end_date, '%Y%m%d')
        existing_start_dt = datetime.strptime(str(existing_start), '%Y%m%d')
        existing_end_dt = datetime.strptime(str(existing_end), '%Y%m%d')

        # Check if requested range is fully covered by existing range
        return start_dt >= existing_start_dt and end_dt <= existing_end_dt

    def get_missing_date_ranges(self, interface_name: str, start_date: str, end_date: str, **params) -> List[tuple]:
        """
        Calculate missing date ranges that need to be downloaded

        Returns list of (start_date, end_date) tuples for missing ranges
        """
        if not self.interface_config.get('duplicate_detection', {}).get('enabled', False):
            return [(start_date, end_date)]

        storage_path = self.get_storage_path(interface_name, **params)
        existing_range = self.index_query.get_existing_date_range(
            storage_path,
            self.interface_config.get('duplicate_detection', {}).get('date_column', 'trade_date')
        )

        if existing_range is None:
            return [(start_date, end_date)]

        existing_start, existing_end = existing_range

        # Convert to datetime for comparison
        start_dt = datetime.strptime(start_date, '%Y%m%d')
        end_dt = datetime.strptime(end_date, '%Y%m%d')
        existing_start_dt = datetime.strptime(str(existing_start), '%Y%m%d')
        existing_end_dt = datetime.strptime(str(existing_end), '%Y%m%d')

        # Calculate missing ranges
        missing_ranges = []

        # Check if we need to download earlier dates
        if start_dt < existing_start_dt:
            missing_start = start_dt.strftime('%Y%m%d')
            missing_end = (existing_start_dt - datetime.timedelta(days=1)).strftime('%Y%m%d')
            if datetime.strptime(missing_end, '%Y%m%d') >= start_dt:
                missing_ranges.append((missing_start, missing_end))

        # Check if we need to download later dates
        if end_dt > existing_end_dt:
            missing_start = (existing_end_dt + datetime.timedelta(days=1)).strftime('%Y%m%d')
            missing_end = end_dt.strftime('%Y%m%d')
            if datetime.strptime(missing_start, '%Y%m%d') <= end_dt:
                missing_ranges.append((missing_start, missing_end))

        # If no missing ranges, return empty list
        if not missing_ranges:
            return []

        return missing_ranges

    def is_stock_code_covered(self, interface_name: str, ts_code: str, **params) -> bool:
        """
        Check if the stock code is already covered by existing data
        """
        if not self.interface_config.get('duplicate_detection', {}).get('enabled', False):
            return False

        storage_path = self.get_storage_path(interface_name, **params)
        existing_codes = self.index_query.get_existing_stock_codes(
            storage_path,
            self.interface_config.get('duplicate_detection', {}).get('stock_column', 'ts_code')
        )

        return ts_code in existing_codes

    def get_missing_stock_codes(self, interface_name: str, stock_codes: List[str], **params) -> List[str]:
        """
        Get stock codes that are missing from existing data
        """
        if not self.interface_config.get('duplicate_detection', {}).get('enabled', False):
            return stock_codes

        storage_path = self.get_storage_path(interface_name, **params)
        existing_codes = set(self.index_query.get_existing_stock_codes(
            storage_path,
            self.interface_config.get('duplicate_detection', {}).get('stock_column', 'ts_code')
        ))

        return [code for code in stock_codes if code not in existing_codes]

    def is_period_covered(self, interface_name: str, period: str, **params) -> bool:
        """
        Check if the period is already covered by existing data
        """
        if not self.interface_config.get('duplicate_detection', {}).get('enabled', False):
            return False

        storage_path = self.get_storage_path(interface_name, **params)
        existing_periods = self.index_query.get_existing_periods(
            storage_path,
            self.interface_config.get('duplicate_detection', {}).get('period_column', 'period')
        )

        return period in existing_periods

    def is_primary_key_covered(self, interface_name: str, primary_key_values: Dict[str, Any], **params) -> bool:
        """
        Check if the primary key combination is already covered by existing data
        """
        if not self.interface_config.get('duplicate_detection', {}).get('enabled', False):
            return False

        storage_path = self.get_storage_path(interface_name, **params)
        primary_key_columns = self.interface_config.get('output', {}).get('primary_key', [])

        if not primary_key_columns:
            return False

        existing_primary_keys = self.index_query.get_existing_primary_keys(storage_path, primary_key_columns)

        # Check if the given primary key combination exists
        for existing_pk in existing_primary_keys:
            if all(existing_pk[col] == primary_key_values.get(col) for col in primary_key_columns):
                return True

        return False
```

**Step 4: 运行测试验证通过**

运行: `pytest tests/test_coverage_manager.py -v`
预期: 通过

**Step 5: 提交**

```bash
git add app4/core/coverage_manager.py
git commit -m "feat: enhance coverage manager with smart duplicate detection"
```

### Task 4: 更新下载器逻辑以使用新的覆盖管理

**Files:**
- Modify: `app4/core/downloader.py`

**Step 1: 为下载器新功能编写测试**

```python
def test_download_with_coverage_check():
    """Test downloading with coverage check to skip existing data"""
    pass


def test_calculate_missing_date_ranges():
    """Test calculating missing date ranges for download"""
    pass
```

**Step 2: 运行测试验证失败**

运行: `pytest tests/test_downloader.py -v`
预期: 失败

**Step 3: 更新下载器实现**

```python
# 在downloader.py中添加必要的导入
from .coverage_manager import CoverageManager
from .index_query import IndexQuery


# 在Downloader类中更新download接口方法
class Downloader:
    # ... 现有代码 ...

    def __init__(self, config_loader, cache_manager, storage_manager):
        self.config_loader = config_loader
        self.cache_manager = cache_manager
        self.storage_manager = storage_manager
        self.coverage_manager = CoverageManager(
            storage_dir=config_loader.settings['storage']['base_dir'],
            interface_config={}
        )

    def download_interface(self, interface_name, **params):
        """Download data for a specific interface with smart duplicate detection"""
        interface_config = self.config_loader.get_interface_config(interface_name)
        self.coverage_manager = CoverageManager(
            storage_dir=self.config_loader.settings['storage']['base_dir'],
            interface_config=interface_config
        )

        start_date = params.get('start_date')
        end_date = params.get('end_date')
        ts_code = params.get('ts_code')

        # Handle different pagination modes with coverage checking
        if (interface_config.get('pagination', {}).get('mode') == 'date_range' and
            start_date and end_date):
            # Check for missing date ranges
            missing_ranges = self.coverage_manager.get_missing_date_ranges(
                interface_name, start_date, end_date, **params
            )

            if not missing_ranges:
                print(f"Data already exists for {interface_name} from {start_date} to {end_date}, skipping download")
                return {'status': 'skipped', 'message': 'Data already exists'}

            # Download only missing ranges
            results = []
            for start, end in missing_ranges:
                print(f"Downloading missing date range: {start} to {end}")
                result = self._download_date_range(interface_name, start, end, **params)
                results.append(result)

            return results

        elif interface_config.get('pagination', {}).get('mode') == 'stock_loop' and ts_code:
            # Check if stock code is already covered
            if self.coverage_manager.is_stock_code_covered(interface_name, ts_code, **params):
                print(f"Data already exists for {interface_name} with ts_code {ts_code}, skipping download")
                return {'status': 'skipped', 'message': f'Data for {ts_code} already exists'}

        # For other modes, use original download logic
        return self._download_original(interface_name, **params)

    def _download_date_range(self, interface_name, start_date, end_date, **params):
        """Download data for a specific date range"""
        # Update params with new date range
        download_params = params.copy()
        download_params['start_date'] = start_date
        download_params['end_date'] = end_date

        return self._download_original(interface_name, **download_params)

    def _download_original(self, interface_name, **params):
        """Original download logic without coverage checking"""
        # ... 现有下载逻辑 ...
        pass
```

**Step 4: 运行测试验证通过**

运行: `pytest tests/test_downloader.py -v`
预期: 通过

**Step 5: 提交**

```bash
git add app4/core/downloader.py
git commit -m "feat: update downloader to use smart duplicate detection"
```

### Task 5: 更新主入口点以支持新的覆盖检测

**Files:**
- Modify: `app4/main.py`

**Step 1: 为main.py更新编写测试**

```python
def test_main_with_coverage_detection():
    """Test main entry point with coverage detection"""
    pass
```

**Step 2: 运行测试验证失败**

运行: `pytest tests/test_main.py -v`
预期: 失败

**Step 3: 更新main.py实现**

```python
# 在main.py中，确保下载器使用新的覆盖检测逻辑
# 更新Downloader的初始化和调用逻辑

# 在命令行参数中添加相关选项
parser.add_argument(
    '--skip-existing',
    action='store_true',
    help='Skip downloading data that already exists in storage'
)

# 在主函数中处理新的参数
args = parser.parse_args()

if args.skip_existing:
    print("Smart duplicate detection enabled - only downloading missing data")
```

**Step 4: 运行测试验证通过**

运行: `pytest tests/test_main.py -v`
预期: 通过

**Step 5: 提交**

```bash
git add app4/main.py
git commit -m "feat: update main entry point to support smart duplicate detection"
```

### Task 6: 创建测试用例验证功能

**Files:**
- Create: `tests/test_smart_coverage.py`

**Step 1: 编写覆盖检测功能测试**

```python
import pytest
import tempfile
from pathlib import Path
import polars as pl

from app4.core.index_query import IndexQuery
from app4.core.coverage_manager import CoverageManager


def test_date_range_coverage_detection():
    """Test date range coverage detection functionality"""
    # Create a temporary parquet file with test data
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test_data.parquet"

        # Create test data with date range 20240101 to 20240103
        df = pl.DataFrame({
            "ts_code": ["000001.SZ"] * 3,
            "trade_date": ["20240101", "20240102", "20240103"]
        })
        df.write_parquet(test_file)

        # Test index query
        index_query = IndexQuery()
        date_range = index_query.get_existing_date_range(test_file, "trade_date")

        assert date_range == ("20240101", "20240103")

        # Test coverage manager
        config = {
            'duplicate_detection': {
                'enabled': True,
                'date_column': 'trade_date'
            }
        }
        coverage_manager = CoverageManager(tmpdir, config)

        # Test fully covered range
        assert coverage_manager.is_date_range_covered(
            "test", "20240101", "20240103", ts_code="000001.SZ"
        )

        # Test partially covered range
        missing_ranges = coverage_manager.get_missing_date_ranges(
            "test", "20240101", "20240105", ts_code="000001.SZ"
        )
        assert missing_ranges == [("20240104", "20240105")]


def test_stock_code_coverage_detection():
    """Test stock code coverage detection functionality"""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test_data.parquet"

        # Create test data with multiple stock codes
        df = pl.DataFrame({
            "ts_code": ["000001.SZ", "000002.SZ", "000003.SZ"],
            "trade_date": ["20240101", "20240101", "20240101"]
        })
        df.write_parquet(test_file)

        # Test coverage manager
        config = {
            'duplicate_detection': {
                'enabled': True,
                'stock_column': 'ts_code'
            }
        }
        coverage_manager = CoverageManager(tmpdir, config)

        # Test existing stock code
        assert coverage_manager.is_stock_code_covered("test", "000001.SZ")

        # Test missing stock code
        assert not coverage_manager.is_stock_code_covered("test", "000004.SZ")

        # Test missing stock codes
        missing_codes = coverage_manager.get_missing_stock_codes(
            "test", ["000001.SZ", "000004.SZ", "000005.SZ"]
        )
        assert "000004.SZ" in missing_codes
        assert "000005.SZ" in missing_codes
        assert "000001.SZ" not in missing_codes
```

**Step 2: 运行测试验证失败**

运行: `pytest tests/test_smart_coverage.py -v`
预期: 失败

**Step 3: 确保实现支持测试**

确认前面的实现能够支持测试用例。

**Step 4: 运行测试验证通过**

运行: `pytest tests/test_smart_coverage.py -v`
预期: 通过

**Step 5: 提交**

```bash
git add tests/test_smart_coverage.py
git commit -m "test: add comprehensive tests for smart duplicate detection"
```

### Task 7: 文档更新和示例

**Files:**
- Modify: `app4/README.md`

**Step 1: 更新README文档**

添加关于新功能的说明和使用示例。

**Step 2: 添加使用示例**

在README中添加智能重复检测的使用示例。

**Step 3: 添加配置说明**

说明如何配置重复检测功能。

**Step 4: 运行文档验证**

确认文档格式正确。

**Step 5: 提交**

```bash
git add app4/README.md
git commit -m "docs: update documentation with smart duplicate detection feature"
```