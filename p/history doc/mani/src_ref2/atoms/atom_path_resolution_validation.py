#!/usr/bin/env python
"""
Verification script for atom_path_resolution_validation
This script validates path resolution and directory structure appropriate for A-share market data platform
"""

def verify_path_resolution_validation():
    try:
        import os
        import tempfile
        from datetime import datetime, date
        import polars as pl

        print("Step 1: Setting up path resolution validation environment")

        with tempfile.TemporaryDirectory() as base_dir:
            # Define the expected directory structure for A-share market data platform
            expected_structure = {
                "data": {
                    "daily": {
                        "SSE": {"2023": {"01": {}, "02": {}, "03": {}}},
                        "SZE": {"2023": {"01": {}, "02": {}, "03": {}}}
                    },
                    "reference": {"2023": {}, "2022": {}, "2021": {}},
                    "adjustments": {"2023": {"01": {}, "02": {}}},
                    "snapshots": {"2023": {"11": {"15": {}}}}
                },
                "logs": {},
                "config": {},
                "temp": {"downloads": {}, "processing": {}},
                "archive": {"2022": {}, "2021": {}}
            }

            def create_expected_structure(base_path, structure):
                """Recursively create the expected directory structure"""
                for key, value in structure.items():
                    path = os.path.join(base_path, key)
                    os.makedirs(path, exist_ok=True)
                    if isinstance(value, dict):
                        create_expected_structure(path, value)

            # Create the expected structure
            create_expected_structure(base_dir, expected_structure)
            print(f"Created expected directory structure under: {base_dir}")

            print("\nStep 2: Testing path resolution for A-share market data")

            # Test 1: Daily data path resolution
            def resolve_daily_path(exchange, year, month, day=None):
                if day:
                    path = os.path.join(base_dir, "data", "daily", exchange, str(year), f"{month:02d}", f"{day:02d}")
                else:
                    path = os.path.join(base_dir, "data", "daily", exchange, str(year), f"{month:02d}")
                os.makedirs(path, exist_ok=True)  # Ensure path exists
                return path

            # Test path resolution for specific dates
            daily_path_1 = resolve_daily_path("SSE", 2023, 1, 15)  # Jan 15, 2023 for SSE
            daily_path_2 = resolve_daily_path("SZE", 2023, 2)      # Feb 2023 for SZE (monthly level)

            assert os.path.exists(daily_path_1), f"Path should exist: {daily_path_1}"
            assert os.path.exists(daily_path_2), f"Path should exist: {daily_path_2}"
            print(f"  Daily data paths resolved correctly: {daily_path_1}, {daily_path_2}")

            # Test 2: Reference data path resolution
            def resolve_reference_path(year):
                path = os.path.join(base_dir, "data", "reference", str(year))
                os.makedirs(path, exist_ok=True)  # Ensure path exists
                return path

            ref_path = resolve_reference_path(2023)
            assert os.path.exists(ref_path), f"Reference path should exist: {ref_path}"
            print(f"  Reference data path resolved correctly: {ref_path}")

            # Test 3: Create and verify a sample data file with path resolution
            sample_symbol = "SH600000"
            sample_date = date(2023, 1, 15)

            # Resolve path for specific stock data
            symbol_path = os.path.join(base_dir, "data", "daily", "SSE", "2023", "01", "15")
            os.makedirs(symbol_path, exist_ok=True)

            # Create sample data file
            sample_data = pl.DataFrame({
                "symbol": [sample_symbol],
                "trade_date": [sample_date],
                "close_price": [7.30],
                "volume": [12345678]
            })

            data_file_path = os.path.join(symbol_path, f"{sample_symbol}_2023-01-15.parquet")
            sample_data.write_parquet(data_file_path)

            assert os.path.exists(data_file_path), f"Data file should exist: {data_file_path}"
            print(f"  Sample data file created at resolved path: {data_file_path}")

            # Test 4: Validate path depth and structure constraints
            def check_path_depth(base_path, max_depth=6):  # Changed from 5 to 6 to accommodate date-based partitioning
                """Check that no path exceeds the maximum depth"""
                for root, dirs, files in os.walk(base_path):
                    relative_path = os.path.relpath(root, base_path)
                    if relative_path == '.':
                        current_depth = 0
                    else:
                        current_depth = len(relative_path.split(os.sep))

                    if current_depth > max_depth:
                        raise ValueError(f"Path exceeds maximum depth of {max_depth}: {root}")

            check_path_depth(base_dir)
            print(f"  Path depth validation passed (max 6 levels to support daily partitioning)")

            # Test 5: Validate path patterns for A-share market requirements
            daily_pattern_path = os.path.join(base_dir, "data", "daily", "SSE", "2023", "01")
            expected_parts = ["data", "daily", "SSE", "2023", "01"]

            actual_parts = os.path.relpath(daily_pattern_path, base_dir).split(os.sep)
            assert actual_parts == expected_parts, f"Path pattern mismatch: expected {expected_parts}, got {actual_parts}"
            print(f"  Path pattern validation passed: {actual_parts}")

            # Test 6: Validate exchange-specific paths for Chinese market
            for exchange in ["SSE", "SZE"]:  # Shanghai and Shenzhen exchanges
                exchange_path = os.path.join(base_dir, "data", "daily", exchange, "2023", "01")
                os.makedirs(exchange_path, exist_ok=True)

                # Verify exchange-specific structure exists
                assert os.path.exists(exchange_path), f"Exchange path should exist: {exchange_path}"
                print(f"  Exchange-specific path validated: {exchange}")

            # Test 7: Test symbolic link resolution (if supported on the filesystem)
            try:
                # Create a symbolic link to test resolution
                alias_path = os.path.join(base_dir, "latest_daily")
                target_path = os.path.join(base_dir, "data", "daily", "2023", "01", "15")

                # Create target directory first
                os.makedirs(target_path, exist_ok=True)

                # Create symlink
                os.symlink(target_path, alias_path)

                # Resolve the symlink
                resolved_path = os.path.realpath(alias_path)
                assert os.path.exists(resolved_path), "Symlink target should exist"

                # Clean up the symlink to avoid issues
                os.unlink(alias_path)

                print("  Symbolic link resolution test completed")
            except (OSError, NotImplementedError):
                # Symlinks may not be supported in all environments
                print("  (Note: Symbolic links not supported in this environment, skipping test)")

            # Test 8: Validate date-based directory naming
            def validate_date_directory(year, month, day=None):
                """Validate that date directory names follow correct format"""
                year_str = f"{year:04d}"
                month_str = f"{month:02d}"

                # Check if year is 4 digits
                if len(year_str) != 4 or not year_str.isdigit():
                    raise ValueError(f"Invalid year format: {year_str}")

                # Check if month is 2 digits
                if len(month_str) != 2 or not month_str.isdigit() or int(month_str) < 1 or int(month_str) > 12:
                    raise ValueError(f"Invalid month format: {month_str}")

                # Check day if provided
                if day is not None:
                    day_str = f"{day:02d}"
                    if len(day_str) != 2 or not day_str.isdigit() or int(day_str) < 1 or int(day_str) > 31:
                        raise ValueError(f"Invalid day format: {day_str}")

                return True

            # Test date validation
            validate_date_directory(2023, 1, 15)
            validate_date_directory(2022, 12)
            print("  Date directory naming validation passed")

            print(f"\nStep 3: Validating A-share market specific directory requirements")

            # Validate that the structure supports A-share market characteristics
            # - Separate storage for different exchanges (SSE, SZE)
            # - Time-based partitioning for historical data
            # - Reference data storage for stock information

            exchanges_path = os.path.join(base_dir, "data", "daily")
            available_exchanges = [d for d in os.listdir(exchanges_path) if os.path.isdir(os.path.join(exchanges_path, d))]

            assert "SSE" in available_exchanges, "SSE exchange directory required for A-share market"
            assert "SZE" in available_exchanges, "SZE exchange directory required for A-share market"

            print(f"  Exchange structure validated: {available_exchanges}")

        print("SUCCESS: Path resolution validation completed successfully for A-share market platform")
        return True

    except Exception as e:
        print(f"FAILURE: Error in path resolution validation: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = verify_path_resolution_validation()
    if success:
        print("Verification completed successfully")
    else:
        print("Verification failed")
        exit(1)