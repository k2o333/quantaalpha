"""Test the strategy selection in depth"""
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

def test_strategy_selection():
    """Test how the coverage manager selects strategies"""
    # Create temporary storage
    temp_dir = tempfile.mkdtemp()
    storage_path = os.path.join(temp_dir, "data")
    os.makedirs(storage_path, exist_ok=True)

    # Create sample data for 000002.SZ with only 20231231 and 20240331 data
    sample_data = pl.DataFrame({
        "ts_code": ["000002.SZ", "000002.SZ"],
        "ann_date": ["20240129", "20240429"],
        "end_date": ["20231231", "20240331"],
        "period": ["20231231", "20240331"],
        "report_type": ["1", "1"],
        "comp_type": ["1", "1"],
        "basic_eps": [0.1, 0.2]
    })

    # Save to parquet file in the data directory structure
    # The storage manager expects files in the format: base_dir/interface_name/interface_name_*.parquet
    interface_dir = os.path.join(storage_path, "income_vip")
    os.makedirs(interface_dir, exist_ok=True)
    data_file = os.path.join(interface_dir, "income_vip_20240101_20241231.parquet")
    sample_data.write_parquet(data_file)

    # Initialize managers
    storage_manager = StorageManager(storage_path)
    config_loader = ConfigLoader("app4/config")

    coverage_manager = CoverageManager(storage_manager, config_loader)

    # Check income_vip config details
    interface_config = config_loader.get_interface_config("income_vip")
    print(f"Income VIP config details:")
    print(f"Pagination mode: {interface_config.get('pagination', {}).get('mode')}")
    print(f"Duplicate detection enabled: {interface_config.get('duplicate_detection', {}).get('enabled')}")
    print(f"Duplicate detection mode: {interface_config.get('duplicate_detection', {}).get('mode')}")
    print(f"Date column: {interface_config.get('duplicate_detection', {}).get('date_column')}")
    print(f"Primary key: {interface_config.get('output', {}).get('primary_key')}")

    # Test the behavior with auto strategy
    print("\n=== Testing auto strategy selection ===")
    params = {
        "ts_code": "000002.SZ",
        "start_date": "20240401",
        "end_date": "20240705"
    }

    # Manual strategy selection check
    pagination_config = interface_config.get('pagination', {})
    pagination_mode = pagination_config.get('mode', 'offset') if pagination_config.get('enabled', False) else 'none'
    detection_config = interface_config.get('duplicate_detection', {})
    detection_mode = detection_config.get('mode', 'set')

    print(f"Pagination mode: {pagination_mode}")
    print(f"Detection mode: {detection_mode}")

    # Test what happens with the current logic
    # The original strategy selection logic in should_skip:
    # if detection_mode == 'set':
    #     strategy = 'set'  # This strategy doesn't exist!
    # elif pagination_mode == 'stock_loop':
    #     strategy = 'stock'  # This uses the broken _check_stock_existence method

    print(f"According to current logic, strategy would be determined by:")
    print(f"  - detection_mode == 'set': {detection_mode == 'set'}")
    print(f"  - pagination_mode == 'stock_loop': {pagination_mode == 'stock_loop'}")

    # Let's see what should_skip actually does
    should_skip_result = coverage_manager.should_skip("income_vip", params)
    print(f"Actual should_skip result: {should_skip_result}")

    # The issue might be that there's no 'set' strategy in the main method
    print(f"\nIn should_skip, we have if/elif checks for:")
    print(f"  - strategy == 'date_range'")
    print(f"  - strategy == 'period'")
    print(f"  - strategy == 'stock'")
    print(f"But not for 'set'! This explains the bug.")

    # Clean up
    shutil.rmtree(temp_dir)

if __name__ == "__main__":
    test_strategy_selection()
    print("Test completed")