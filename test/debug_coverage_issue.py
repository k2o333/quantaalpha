"""Debug the coverage issue in depth"""
import tempfile
import shutil
import os
import logging
import polars as pl
from app4.core.coverage_manager import CoverageManager
from app4.core.storage import StorageManager
from app4.core.config_loader import ConfigLoader

# Enable logging to see debug output
logging.basicConfig(level=logging.DEBUG)

def debug_income_vip_coverage():
    """Debug the income_vip coverage issue"""
    # Create temporary storage
    temp_dir = tempfile.mkdtemp()
    storage_path = os.path.join(temp_dir, "data")
    os.makedirs(storage_path, exist_ok=True)

    # Create sample data for 000002.SZ with only 20231231 and 20240331 data (missing 20240630)
    # This simulates the case where we have partial data but not complete coverage
    sample_data = pl.DataFrame({
        "ts_code": ["000002.SZ", "000002.SZ"],  # Only one stock
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
    config_loader = ConfigLoader("app4/config")

    coverage_manager = CoverageManager(storage_manager, config_loader)

    # Test 1: Original bug scenario - request 20240401 to 20240705 (should need Q2 2024 data)
    print("=== Test 1: Original bug scenario ===")
    params1 = {
        "ts_code": "000002.SZ",
        "start_date": "20240401",
        "end_date": "20240705"
    }
    should_skip1 = coverage_manager.should_skip("income_vip", params1)
    print(f"Requesting 20240401-20240705 for 000002.SZ, should_skip = {should_skip1}")
    print("Expected: False (should NOT skip, because Q2 2024 data is missing)")

    # Test 2: Check if existing stock data is detected properly
    print("\n=== Test 2: Check stock existence detection ===")
    result_stock = coverage_manager._check_stock_existence("income_vip", params1)
    print(f"Stock existence check result: {result_stock}")

    # Test 3: Check what strategy is being used
    print("\n=== Test 3: Check strategy used ===")
    interface_config = config_loader.get_interface_config("income_vip")
    print(f"Pagination mode: {interface_config.get('pagination', {}).get('mode')}")
    print(f"Duplicate detection mode: {interface_config.get('duplicate_detection', {}).get('mode')}")

    # Test 4: Simulate scenario where stock has some data but not for requested date range
    print("\n=== Test 4: Full data scenario ===")
    # If we had all the data for the required date range, should_skip should be True
    # But we're missing 20240630 (Q2 2024), so it should be False

    # Clean up
    shutil.rmtree(temp_dir)

if __name__ == "__main__":
    debug_income_vip_coverage()
    print("Debug test completed")