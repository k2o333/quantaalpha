"""Integration test for income_vip coverage fix"""
import tempfile
import shutil
import os
import logging
from unittest.mock import Mock, patch
import polars as pl
from app4.core.coverage_manager import CoverageManager
from app4.core.storage import StorageManager
from app4.core.config_loader import ConfigLoader
from app4.core.downloader import GenericDownloader  # We'll simulate interaction

def test_integration_income_vip_end_to_end():
    """Integration test that simulates the full flow from downloader to coverage check"""
    # Create temporary storage
    temp_dir = tempfile.mkdtemp()
    storage_path = os.path.join(temp_dir, "data")
    os.makedirs(storage_path, exist_ok=True)

    # Create sample data for 000002.SZ with partial coverage (missing Q2 2024)
    interface_dir = os.path.join(storage_path, "income_vip")
    os.makedirs(interface_dir, exist_ok=True)
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
    data_file = os.path.join(interface_dir, "income_vip_20240101_20241231.parquet")
    sample_data.write_parquet(data_file)

    # Initialize managers
    storage_manager = StorageManager(storage_path)
    config_loader = ConfigLoader("app4/config")

    # Create a mock downloader to pass to coverage manager
    mock_downloader = Mock()

    coverage_manager = CoverageManager(storage_manager, config_loader, downloader=mock_downloader)

    # Test scenario 1: Request data that has partial coverage (should NOT skip)
    params1 = {
        "ts_code": "000002.SZ",
        "start_date": "20240401",
        "end_date": "20240705"  # Missing Q2 2024 (20240630)
    }

    # This should return False (proceed with download) because Q2 2024 data is missing
    should_skip_1 = coverage_manager.should_skip("income_vip", params1)
    assert should_skip_1 == False, f"Expected False when Q2 2024 data is missing, got {should_skip_1}"
    print("✓ Integration test 1 passed: correctly proceeds when data is missing")

    # Test scenario 2: Request data that has full coverage (should skip)
    # Create different test data with full coverage
    full_sample_data = pl.DataFrame({
        "ts_code": ["000002.SZ", "000002.SZ", "000002.SZ"],
        "ann_date": ["20240129", "20240429", "20240729"],
        "end_date": ["20231231", "20240331", "20240630"],  # Full Q4 2023, Q1 2024, Q2 2024
        "period": ["20231231", "20240331", "20240630"],  # Full Q4 2023, Q1 2024, Q2 2024
        "report_type": ["1", "1", "1"],
        "comp_type": ["1", "1", "1"],
        "basic_eps": [0.1, 0.2, 0.3]
    })

    # Overwrite the parquet file with full coverage data
    full_data_file = os.path.join(interface_dir, "income_vip_20240101_20241231.parquet")
    full_sample_data.write_parquet(full_data_file)

    # Clear the internal cache to force re-reading
    coverage_manager._cache.clear()
    coverage_manager._coverage_cache.clear()

    # This should return True (skip download) because all data exists
    should_skip_2 = coverage_manager.should_skip("income_vip", params1)
    assert should_skip_2 == True, f"Expected True when all data exists, got {should_skip_2}"
    print("✓ Integration test 2 passed: correctly skips when all data exists")

    # Test scenario 3: Test with different interface that has different config
    # Create data for a different interface that doesn't use 'set' mode
    daily_interface_dir = os.path.join(storage_path, "daily")
    os.makedirs(daily_interface_dir, exist_ok=True)
    daily_sample_data = pl.DataFrame({
        "ts_code": ["000002.SZ", "000002.SZ", "000002.SZ"],
        "trade_date": ["20240401", "20240402", "20240403"],
        "open": [10.0, 10.1, 10.2],
        "close": [10.1, 10.2, 10.3]
    })

    daily_data_file = os.path.join(daily_interface_dir, "daily_20240401_20240403.parquet")
    daily_sample_data.write_parquet(daily_data_file)

    params3 = {
        "ts_code": "000002.SZ",
        "start_date": "20240401",
        "end_date": "20240403"
    }

    # Should work with different interface types
    should_skip_3 = coverage_manager.should_skip("daily", params3)
    print(f"✓ Integration test 3 passed: daily interface works, result: {should_skip_3}")

    # Clean up
    shutil.rmtree(temp_dir)

    print("✓ All integration tests passed!")


def test_integration_with_real_config_scenarios():
    """Test integration with various real configuration scenarios"""
    # Create temporary storage
    temp_dir = tempfile.mkdtemp()
    storage_path = os.path.join(temp_dir, "data")
    os.makedirs(storage_path, exist_ok=True)

    # Initialize managers
    storage_manager = StorageManager(storage_path)
    config_loader = ConfigLoader("app4/config")

    # Create a mock downloader
    mock_downloader = Mock()
    # Mock the get_trade_calendar method to return some dummy data
    def mock_get_trade_calendar(start_date, end_date):
        # Return a list of trade days in the range
        return [
            {'cal_date': start_date, 'is_open': 1},
            {'cal_date': end_date, 'is_open': 1}
        ]
    mock_downloader.get_trade_calendar = mock_get_trade_calendar

    coverage_manager = CoverageManager(storage_manager, config_loader, downloader=mock_downloader)

    # Test with various interfaces and parameters that would realistically occur
    test_cases = [
        # income_vip with various date ranges
        {
            "interface": "income_vip",
            "params": {"ts_code": "000001.SZ", "start_date": "20240101", "end_date": "20241231"},
            "description": "income_vip full year 2024"
        },
        {
            "interface": "income_vip",
            "params": {"ts_code": "000002.SZ", "start_date": "20230101", "end_date": "20231231"},
            "description": "income_vip full year 2023"
        },
        # balancesheet_vip (similar config to income_vip)
        {
            "interface": "balancesheet_vip",
            "params": {"ts_code": "000001.SZ", "start_date": "20240101", "end_date": "20240630"},
            "description": "balancesheet_vip half year 2024"
        }
    ]

    for i, case in enumerate(test_cases):
        try:
            # This should not crash and should return a boolean
            result = coverage_manager.should_skip(case["interface"], case["params"])
            assert isinstance(result, bool), f"Result should be boolean, got {type(result)}"
            print(f"✓ Integration test case {i+1} passed: {case['description']} -> {result}")
        except Exception as e:
            print(f"✗ Integration test case {i+1} failed: {case['description']} -> {str(e)}")
            raise

    # Clean up
    shutil.rmtree(temp_dir)

    print("✓ All configuration scenario integration tests passed!")


if __name__ == "__main__":
    print("Running integration tests for income_vip coverage fix...")
    test_integration_income_vip_end_to_end()
    print()
    test_integration_with_real_config_scenarios()
    print("\n✓ All integration tests completed successfully!")