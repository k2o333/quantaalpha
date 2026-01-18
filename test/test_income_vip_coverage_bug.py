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

    # Save to parquet file in the correct directory structure
    data_file = os.path.join(interface_dir, "income_vip_20240101_20241231.parquet")
    sample_data.write_parquet(data_file)

    # Initialize managers
    storage_manager = StorageManager(storage_path)
    config_loader = ConfigLoader("app4/config")

    coverage_manager = CoverageManager(storage_manager, config_loader)

    # Test the bug scenario: request 20240401 to 20240705 (should need Q2 2024 data)
    params = {
        "ts_code": "000002.SZ",
        "start_date": "20240401",
        "end_date": "20240705"
    }

    # This should return False (should NOT skip) because Q2 2024 data is missing
    # But currently it returns True (incorrectly skips) for stock_loop interfaces
    # when stock exists but date range coverage is incomplete
    should_skip = coverage_manager.should_skip("income_vip", params)

    print(f"Current behavior: should_skip = {should_skip}")
    print("Expected: False (should download since Q2 2024 data is missing)")
    print("This demonstrates the bug where _check_stock_existence only checks if stock exists,")
    print("ignoring whether the required date range is fully covered.")

    # Clean up
    shutil.rmtree(temp_dir)

    # The bug is that _check_stock_existence returns True (skip) because stock exists,
    # even if the date range is not fully covered
    if should_skip:
        print("BUG CONFIRMED: System incorrectly skips download when partial data exists")
    else:
        print("No bug detected - download will proceed as expected")

if __name__ == "__main__":
    test_income_vip_partial_data_coverage()
    print("Test completed")