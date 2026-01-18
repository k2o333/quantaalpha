"""Comprehensive test suite for income_vip coverage fix"""
import tempfile
import shutil
import os
import logging
import polars as pl
from app4.core.coverage_manager import CoverageManager
from app4.core.storage import StorageManager
from app4.core.config_loader import ConfigLoader

def test_income_vip_full_coverage():
    """Test when all requested data exists (should skip)"""
    # Create temporary storage
    temp_dir = tempfile.mkdtemp()
    storage_path = os.path.join(temp_dir, "data")
    os.makedirs(storage_path, exist_ok=True)

    # Create sample data for 000002.SZ with ALL expected periods in the range 20240401-20240705
    # This includes Q2 2024 (20240630) which should exist for full coverage
    interface_dir = os.path.join(storage_path, "income_vip")
    os.makedirs(interface_dir, exist_ok=True)
    sample_data = pl.DataFrame({
        "ts_code": ["000002.SZ", "000002.SZ", "000002.SZ"],  # Include Q2 2024 data
        "ann_date": ["20240129", "20240429", "20240729"],
        "end_date": ["20231231", "20240331", "20240630"],  # Q4 2023, Q1 2024, Q2 2024
        "period": ["20231231", "20240331", "20240630"],  # Q4 2023, Q1 2024, Q2 2024
        "report_type": ["1", "1", "1"],
        "comp_type": ["1", "1", "1"],
        "basic_eps": [0.1, 0.2, 0.3]
    })

    # Save to parquet file
    data_file = os.path.join(interface_dir, "income_vip_20240101_20241231.parquet")
    sample_data.write_parquet(data_file)

    # Initialize managers
    storage_manager = StorageManager(storage_path)
    config_loader = ConfigLoader("app4/config")

    coverage_manager = CoverageManager(storage_manager, config_loader)

    # Test: request 20240401 to 20240705 (should find Q2 2024 data exists, so skip)
    params = {
        "ts_code": "000002.SZ",
        "start_date": "20240401",
        "end_date": "20240705"
    }

    should_skip = coverage_manager.should_skip("income_vip", params)

    # Clean up
    shutil.rmtree(temp_dir)

    # With full data coverage, should_skip should be True
    assert should_skip == True, f"Expected True when all data exists, but got {should_skip}"
    print("✓ Test full coverage: correctly skips when all data exists")


def test_income_vip_partial_coverage():
    """Test when only partial data exists (should NOT skip)"""
    # Create temporary storage
    temp_dir = tempfile.mkdtemp()
    storage_path = os.path.join(temp_dir, "data")
    os.makedirs(storage_path, exist_ok=True)

    # Create sample data for 000002.SZ with only 20231231 and 20240331 data (missing 20240630)
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

    coverage_manager = CoverageManager(storage_manager, config_loader)

    # Test: request 20240401 to 20240705 (should need Q2 2024 data, so don't skip)
    params = {
        "ts_code": "000002.SZ",
        "start_date": "20240401",
        "end_date": "20240705"
    }

    should_skip = coverage_manager.should_skip("income_vip", params)

    # Clean up
    shutil.rmtree(temp_dir)

    # With partial data coverage, should_skip should be False
    assert should_skip == False, f"Expected False when partial data exists, but got {should_skip}"
    print("✓ Test partial coverage: correctly proceeds when data is missing")


def test_income_vip_different_threshold():
    """Test with different coverage thresholds"""
    # Create temporary storage
    temp_dir = tempfile.mkdtemp()
    storage_path = os.path.join(temp_dir, "data")
    os.makedirs(storage_path, exist_ok=True)

    # Create sample data for multiple stocks
    interface_dir = os.path.join(storage_path, "income_vip")
    os.makedirs(interface_dir, exist_ok=True)
    sample_data = pl.DataFrame({
        "ts_code": ["000002.SZ", "000002.SZ", "000001.SZ", "000001.SZ", "000001.SZ"],
        "ann_date": ["20240129", "20240429", "20240129", "20240429", "20240729"],
        "end_date": ["20231231", "20240331", "20231231", "20240331", "20240630"],
        "period": ["20231231", "20240331", "20231231", "20240331", "20240630"],
        "report_type": ["1", "1", "1", "1", "1"],
        "comp_type": ["1", "1", "1", "1", "1"],
        "basic_eps": [0.1, 0.2, 0.15, 0.25, 0.35]
    })

    # Save to parquet file
    data_file = os.path.join(interface_dir, "income_vip_20240101_20241231.parquet")
    sample_data.write_parquet(data_file)

    # Initialize managers
    storage_manager = StorageManager(storage_path)
    config_loader = ConfigLoader("app4/config")

    coverage_manager = CoverageManager(storage_manager, config_loader)

    # Test: request specific stock 000002.SZ for range that requires all 3 quarterly periods,
    # but it's missing Q2 2024. With default threshold (0.95), should not skip.
    params = {
        "ts_code": "000002.SZ",
        "start_date": "20231201",  # Would expect Q4 2023, Q1 2024, Q2 2024
        "end_date": "20240705"    # So 3 periods expected, only 2 exist = 66.7% coverage < 0.95
    }

    should_skip = coverage_manager.should_skip("income_vip", params)

    # Clean up
    shutil.rmtree(temp_dir)

    # With partial coverage (< 0.95 threshold), should_skip should be False
    assert should_skip == False, f"Expected False when coverage below threshold, but got {should_skip}"
    print("✓ Test coverage threshold: correctly respects threshold setting")


def test_income_vip_no_date_params():
    """Test when no date parameters are provided (should behave like stock check)"""
    # Create temporary storage
    temp_dir = tempfile.mkdtemp()
    storage_path = os.path.join(temp_dir, "data")
    os.makedirs(storage_path, exist_ok=True)

    # Create sample data
    interface_dir = os.path.join(storage_path, "income_vip")
    os.makedirs(interface_dir, exist_ok=True)
    sample_data = pl.DataFrame({
        "ts_code": ["000002.SZ", "000001.SZ"],
        "ann_date": ["20240129", "20240429"],
        "end_date": ["20231231", "20240331"],
        "period": ["20231231", "20240331"],
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

    coverage_manager = CoverageManager(storage_manager, config_loader)

    # Test: request without date params - should check if stock exists
    params = {
        "ts_code": "000002.SZ"
        # No start_date or end_date
    }

    should_skip = coverage_manager.should_skip("income_vip", params)

    # Clean up
    shutil.rmtree(temp_dir)

    # Should return True since stock exists (without date range to check)
    assert should_skip == True, f"Expected True when stock exists and no date range, but got {should_skip}"
    print("✓ Test no date params: correctly handles missing date parameters")


def run_all_tests():
    """Run all comprehensive tests"""
    print("Running comprehensive income_vip coverage tests...")

    test_income_vip_full_coverage()
    test_income_vip_partial_coverage()
    test_income_vip_different_threshold()
    test_income_vip_no_date_params()

    print("\n✓ All comprehensive tests passed!")


if __name__ == "__main__":
    run_all_tests()