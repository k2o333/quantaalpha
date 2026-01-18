#!/usr/bin/env python3
"""
Test script to verify that all modules can be imported correctly after cache optimizations
"""

import sys
import os
from pathlib import Path

# Add the project root, app, and test directories to the Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'app'))
sys.path.insert(0, str(project_root / 'test'))

def test_imports():
    """Test importing all key modules"""
    print("Testing imports...")

    # Test importing key modules
    try:
        from data_storage import get_interface_cache_path, save_interface_data_to_cache
        print("✓ data_storage module imported successfully")
    except Exception as e:
        print(f"✗ Failed to import data_storage: {e}")
        import traceback
        traceback.print_exc()
        return False

    try:
        from download_strategies import get_strategy, DailyDataStrategy
        print("✓ download_strategies module imported successfully")
    except Exception as e:
        print(f"✗ Failed to import download_strategies: {e}")
        import traceback
        traceback.print_exc()
        return False

    try:
        from download_scheduler import DownloadScheduler, run_download_schedule
        print("✓ download_scheduler module imported successfully")
    except Exception as e:
        print(f"✗ Failed to import download_scheduler: {e}")
        import traceback
        traceback.print_exc()
        return False

    try:
        from config_adapter import get_interface_cache_settings
        print("✓ config_adapter module imported successfully")
    except Exception as e:
        print(f"✗ Failed to import config_adapter: {e}")
        import traceback
        traceback.print_exc()
        return False

    print("All imports successful!")
    return True

if __name__ == "__main__":
    success = test_imports()
    if success:
        print("\n✓ All modules imported correctly after cache optimizations!")
    else:
        print("\n✗ Some imports failed")
        sys.exit(1)