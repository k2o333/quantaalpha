# Income VIP Coverage Check Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the coverage check bug in income_vip interface that incorrectly skips downloads when only partial data exists for a stock in the requested date range.

**Architecture:** Update the CoverageManager to properly handle stock_loop pagination mode with date range coverage checks, using configuration-defined primary keys and detection columns.

**Tech Stack:** Python, Polars, YAML configuration

---

### Task 1: Analyze current coverage manager implementation

**Files:**
- Read: `app4/core/coverage_manager.py:279-326` (current _check_stock_existence method)
- Read: `app4/core/coverage_manager.py:64-76` (strategy determination logic)
- Read: `app4/config/interfaces/income_vip.yaml`

**Step 1: Document current issues**
The current `_check_stock_existence` method only checks if a stock exists at all, ignoring dates and configured primary keys.

**Step 2: Create test to reproduce the issue**
Create a test that demonstrates the bug with income_vip data.

**Step 3: Commit**
```bash
git add super/income_vip_coverage_check_fix_plan.md
git commit -m "docs: add implementation plan for income_vip coverage check bug"
```

### Task 2: Create comprehensive test for the bug

**Files:**
- Create: `test/test_income_vip_coverage_bug.py`

**Step 1: Write the failing test**
```python
"""Test for income_vip coverage bug"""
import tempfile
import shutil
import os
from pathlib import Path
import polars as pl
from app4.core.coverage_manager import CoverageManager
from app4.core.storage import StorageManager
from app4.core.config_loader import ConfigLoader

def test_income_vip_partial_data_coverage():
    """Test that income_vip correctly handles partial data coverage"""
    # Create temporary storage
    temp_dir = tempfile.mkdtemp()
    storage_path = os.path.join(temp_dir, "data")
    os.makedirs(storage_path, exist_ok=True)

    # Create sample data for 000002.SZ with only 20231231 and 20240331 data (missing 20240630)
    sample_data = pl.DataFrame({
        "ts_code": ["000002.SZ", "000002.SZ"],
        "ann_date": ["20240129", "20240429"],
        "end_date": ["20231231", "20240331"],  # Only Q4 2023 and Q1 2024
        "period": ["20231231", "20240331"],  # Only Q4 2023 and Q1 2024
        "report_type": ["1", "1"],
        "comp_type": ["1", "1"],
        "basic_eps": [0.1, 0.2]
    })

    # Save to parquet file
    data_file = os.path.join(storage_path, "income_vip.parquet")
    sample_data.write_parquet(data_file)

    # Initialize managers
    storage_manager = StorageManager(storage_path)
    config_loader = ConfigLoader("app4/config/settings.yaml", "app4/config/interfaces")

    coverage_manager = CoverageManager(storage_manager, config_loader)

    # Test the bug scenario: request 20240401 to 20240705 (should need Q2 2024 data)
    params = {
        "ts_code": "000002.SZ",
        "start_date": "20240401",
        "end_date": "20240705"
    }

    # This should return False (should NOT skip) because Q2 2024 data is missing
    # But currently it returns True (incorrectly skips)
    should_skip = coverage_manager.should_skip("income_vip", params)

    # Clean up
    shutil.rmtree(temp_dir)

    # The test should pass when the bug is fixed
    assert should_skip == False, "Should not skip download when Q2 2024 data is missing"

if __name__ == "__main__":
    test_income_vip_partial_data_coverage()
    print("Test completed")
```

**Step 2: Run test to verify it fails**
Run: `python test/test_income_vip_coverage_bug.py`
Expected: FAIL or skip the download (demonstrating the bug)

**Step 3: Update plan to reflect test**
Update the plan with findings from the test.

**Step 4: Commit**
```bash
git add test/test_income_vip_coverage_bug.py
git commit -m "test: add test case for income_vip coverage check bug"
```

### Task 3: Implement enhanced stock coverage check with date range support

**Files:**
- Modify: `app4/core/coverage_manager.py`

**Step 1: Update the strategy selection logic**
Modify the automatic strategy selection to consider duplicate_detection.mode configuration instead of just pagination mode:
- If duplicate_detection.mode is 'set' and primary_key contains date-related columns, use 'date_range' logic
- If duplicate_detection.mode is 'exact', use more strict checking
- If duplicate_detection.mode is 'custom', allow calling a custom method

**Step 2: Create new method for advanced stock coverage check**
Add a new method that properly handles composite primary keys and date ranges:
```python
def _check_stock_date_range_coverage(self, interface_name: str, params: Dict[str, Any]) -> bool:
    """
    Check stock coverage with date range by considering primary key columns
    This is specifically for stock_loop interfaces like income_vip that need date-aware checking
    """
    target_stock = params.get('ts_code')
    start_date = params.get('start_date')
    end_date = params.get('end_date')

    if not target_stock:
        return False

    interface_config = self.config_loader.get_interface_config(interface_name)
    detection_config = interface_config.get('duplicate_detection', {})
    output_config = interface_config.get('output', {})

    # Get primary keys and detection settings
    primary_keys = output_config.get('primary_key', ['ts_code'])
    date_column = detection_config.get('date_column', 'period')
    detection_mode = detection_config.get('mode', 'set')
    threshold = detection_config.get('threshold', 0.95)

    if not start_date or not end_date:
        # If no date range specified, fall back to basic stock existence
        return self._check_stock_existence(interface_name, params)

    try:
        # Read data for this stock only
        df = self.storage_manager.read_interface_data(
            interface_name,
            ts_code=target_stock,
            columns=primary_keys + [date_column]
        )

        if df.is_empty():
            return False  # No data exists, should download

        # Generate expected periods for the date range based on the pagination mode
        pagination_config = interface_config.get('pagination', {})
        pagination_mode = pagination_config.get('mode', 'offset')

        if pagination_mode == 'stock_loop' and date_column == 'period':
            # For income_vip and similar quarterly data, generate expected quarter-ends
            expected_periods = set(self._generate_quarter_end_dates(start_date, end_date))
            actual_periods = set(df[date_column].to_list())
        else:
            # For other types, use date range logic
            actual_dates = set(df[date_column].to_list())
            # Use trade calendar or simple range depending on date_column type
            if self.downloader:
                trade_calendar = self.downloader.get_trade_calendar(start_date, end_date)
                if trade_calendar:
                    expected_dates = {day['cal_date'] for day in trade_calendar if day.get('is_open', 0) == 1}
                else:
                    expected_dates = set()
            else:
                expected_dates = set()
            # For now, use actual date comparison
            expected_periods = set()
            for date_str in actual_dates:
                if isinstance(date_str, str) and start_date <= date_str <= end_date:
                    expected_periods.add(date_str)
            actual_periods = set(actual_dates)

        # Calculate coverage
        covered_periods = actual_periods & expected_periods
        coverage = len(covered_periods) / len(expected_periods) if expected_periods else 0.0

        should_skip = coverage >= threshold
        return should_skip

    except Exception as e:
        logger.warning(f"Stock date range coverage check failed for {interface_name}: {e}")
        return False  # Fail-safe, continue download
```

**Step 3: Update strategy selection logic**
In the `should_skip` method, update the automatic strategy determination to consider duplicate detection configuration.

**Step 4: Run test to verify fix**
Run: `python test/test_income_vip_coverage_bug.py`
Expected: PASS (no longer incorrectly skips)

**Step 5: Commit**
```bash
git add app4/core/coverage_manager.py
git commit -m "feat: fix income_vip coverage check to handle partial date ranges"
```

### Task 4: Add support for 'set' mode detection in coverage manager

**Files:**
- Modify: `app4/core/coverage_manager.py`

**Step 1: Implement 'set' mode detection**
Add a new method that checks if the required data exists by comparing sets of primary key values:

```python
def _check_set_coverage(self, interface_name: str, params: Dict[str, Any]) -> bool:
    """
    Check coverage using set comparison based on primary keys
    This supports the 'set' mode in duplicate detection configuration
    """
    interface_config = self.config_loader.get_interface_config(interface_name)
    detection_config = interface_config.get('duplicate_detection', {})
    output_config = interface_config.get('output', {})

    primary_keys = output_config.get('primary_key', ['ts_code'])
    date_column = detection_config.get('date_column', 'period')
    threshold = detection_config.get('threshold', 0.95)

    start_date = params.get('start_date')
    end_date = params.get('end_date')
    target_stock = params.get('ts_code')

    # Read existing data
    read_params = {k: v for k, v in params.items() if k in ['ts_code', 'period', 'ann_date', 'end_date']}
    df = self.storage_manager.read_interface_data(interface_name, **read_params)

    if df.is_empty():
        return False  # No data exists, should download

    # Generate expected primary key combinations based on date range
    if start_date and end_date:
        # For income_vip and similar interfaces, we need to generate expected periods
        pagination_config = interface_config.get('pagination', {})
        if pagination_config.get('mode') == 'stock_loop':
            # Generate expected periods for quarterly data
            expected_periods = self._generate_quarter_end_dates(start_date, end_date)

            # Get actual periods for the target stock
            if target_stock:
                actual_periods = set(df.filter(pl.col('ts_code') == target_stock)[date_column].to_list())
            else:
                actual_periods = set(df[date_column].to_list())

            covered_periods = set(expected_periods) & actual_periods
            coverage = len(covered_periods) / len(expected_periods) if expected_periods else 0.0
            return coverage >= threshold
        else:
            # For other modes, use standard date range logic
            return self._check_range_coverage(interface_name, params)
    else:
        # If no date range, just check if stock exists
        if target_stock:
            return target_stock in df['ts_code'].to_list()
        return not df.is_empty()
```

**Step 2: Update should_skip method to handle 'set' mode**
Add logic to detect when duplicate_detection.mode is 'set' and call the new method.

**Step 3: Test the new implementation**
Run the test to ensure it works correctly.

**Step 4: Commit**
```bash
git add app4/core/coverage_manager.py
git commit -m "feat: add 'set' mode coverage detection for income_vip"
```

### Task 5: Update the strategy selection logic to properly handle stock_loop mode

**Files:**
- Modify: `app4/core/coverage_manager.py`

**Step 1: Refactor strategy selection**
Update the automatic strategy selection to read the duplicate_detection.mode from the interface configuration instead of just relying on pagination mode:

```python
# In should_skip method, replace the automatic strategy determination:
if strategy == 'auto':
    interface_config = self.config_loader.get_interface_config(interface_name)
    detection_config = interface_config.get('duplicate_detection', {})
    pagination_config = interface_config.get('pagination', {})

    # First, check duplicate detection mode configuration
    detection_mode = detection_config.get('mode', 'set')  # default to 'set' for better date-aware checking
    pagination_mode = pagination_config.get('mode', 'offset') if pagination_config.get('enabled', False) else 'none'

    if detection_mode == 'date_range':
        strategy = 'date_range'
    elif detection_mode == 'period':
        strategy = 'period'
    elif detection_mode == 'set':
        strategy = 'set'
    elif pagination_mode == 'date_range':
        strategy = 'date_range'
    elif pagination_mode == 'period_range':
        strategy = 'period'
    elif pagination_mode == 'stock_loop':
        # For stock_loop mode, use 'set' mode detection which is more appropriate for financial data
        strategy = 'set'  # Changed from 'stock' to 'set' for proper date range checking
    else:
        return False  # Not supported, don't skip
```

**Step 2: Ensure method dispatch works correctly**
Update the conditional that calls the specific check methods to handle the new 'set' strategy.

**Step 3: Test comprehensive functionality**
Create and run comprehensive tests to make sure all scenarios work.

**Step 4: Commit**
```bash
git add app4/core/coverage_manager.py
git commit -m "feat: improve strategy selection for stock_loop pagination mode"
```

### Task 6: Create comprehensive test suite and run all tests

**Files:**
- Modify: `test/test_income_vip_coverage_bug.py`

**Step 1: Expand test to cover multiple scenarios**
Add tests for different combinations of parameters and configurations.

**Step 2: Test the fix with real data scenario**
Simulate the exact scenario from the bug report.

**Step 3: Run all related tests**
Run the full test suite to make sure no regressions were introduced.

**Step 4: Commit**
```bash
git add test/test_income_vip_coverage_bug.py
git commit -m "test: expand test coverage for income_vip fix"
```

### Task 7: Document the fix and create an integration test

**Files:**
- Create: `test/integration_test_income_vip.py`

**Step 1: Write integration test**
Create an integration test that tests the full flow from the downloader through the coverage manager.

**Step 2: Run integration test**
Verify that the fix works end-to-end.

**Step 3: Update documentation**
Document the changes in the relevant README or documentation files.

**Step 4: Commit**
```bash
git add test/integration_test_income_vip.py
git commit -m "test: add integration test for income_vip coverage fix"
```