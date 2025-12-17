#!/usr/bin/env python
"""
Verification script for atom_atomic_write_simulation
This script simulates atomic write mechanisms appropriate for A-share market data platform
"""

def verify_atomic_write_simulation():
    try:
        import polars as pl
        import os
        import tempfile
        import shutil
        import time
        from datetime import datetime, date
        import threading
        import multiprocessing as mp

        print("Step 1: Setting up atomic write simulation environment")

        with tempfile.TemporaryDirectory() as base_dir:
            # Define paths for atomic operations
            source_data_path = os.path.join(base_dir, "temp_daily_data.csv")
            target_partition_path = os.path.join(base_dir, "partitioned_data", "2023", "01")
            staging_area = os.path.join(base_dir, "staging")
            final_target = os.path.join(target_partition_path, "daily_bars_2023-01-15.parquet")

            # Create source data
            source_data = pl.DataFrame({
                "symbol": ["SH600000", "SZ000001", "SH600036", "SZ300015", "SH601398"],
                "trade_date": [date(2023, 1, 15)] * 5,
                "open_price": [7.21, 15.40, 38.45, 32.10, 4.56],
                "high_price": [7.35, 15.65, 39.20, 32.80, 4.65],
                "low_price": [7.15, 15.25, 38.20, 31.90, 4.50],
                "close_price": [7.30, 15.50, 39.05, 32.50, 4.60],
                "volume": [12345678, 9876543, 5432109, 6789012, 23456789],
                "turnover": [89987654.32, 153210987.65, 210987654.56, 219876543.21, 107936542.10]
            })

            # Write initial source data
            source_data.write_csv(source_data_path)
            print(f"Created source data with {source_data.height} rows at {source_data_path}")

            # Create target directories
            os.makedirs(target_partition_path, exist_ok=True)
            os.makedirs(staging_area, exist_ok=True)

            print("\nStep 2: Simulating atomic write operations")

            # Simulate atomic write using a staging area and move operation
            staging_file = os.path.join(staging_area, f"temp_{int(time.time())}.parquet")

            # Write to staging area first
            source_data.write_parquet(staging_file)
            print(f"Data written to staging area: {staging_file}")

            # Verify staging file integrity
            staging_data = pl.read_parquet(staging_file)
            assert staging_data.height == source_data.height, "Staging data should match source data height"
            assert list(staging_data.columns) == list(source_data.columns), "Column names should match"

            # Atomic move operation (the actual atomic part)
            final_target_dir = os.path.dirname(final_target)
            if not os.path.exists(final_target_dir):
                os.makedirs(final_target_dir, exist_ok=True)

            # Perform the atomic move (on POSIX systems, this is atomic if both files are on same filesystem)
            shutil.move(staging_file, final_target)
            print(f"Atomic move completed: {final_target}")

            # Verify final file
            assert os.path.exists(final_target), "Final target file should exist"
            final_data = pl.read_parquet(final_target)
            assert final_data.height == source_data.height, "Final data should match source data height"
            assert list(final_data.columns) == list(source_data.columns), "Final column names should match"

            print(f"Final file verified: {final_target} with {final_data.height} rows")

            # Test concurrent write safety by having multiple threads attempt to write
            print("\nStep 3: Testing concurrent write safety")

            def write_data_thread(thread_id):
                # Each thread writes to its own file name to avoid conflicts
                thread_file = os.path.join(staging_area, f"thread_data_{thread_id}.parquet")
                thread_data = pl.DataFrame({
                    "symbol": [f"SH600{thread_id:04d}"],
                    "trade_date": [date(2023, 1, 15)],
                    "close_price": [30.0 + thread_id],
                    "volume": [1000000 + thread_id * 10000]
                })
                # Write to staging area
                thread_data.write_parquet(thread_file)
                # Atomic move to final location
                final_thread_file = os.path.join(target_partition_path, f"daily_bars_thread_{thread_id}.parquet")
                shutil.move(thread_file, final_thread_file)
                return final_thread_file

            # Run multiple threads to simulate concurrent writes
            threads = []
            for i in range(3):
                thread = threading.Thread(target=lambda i=i: write_data_thread(i))
                threads.append(thread)
                thread.start()

            # Wait for all threads to complete
            for thread in threads:
                thread.join()

            print("All concurrent write operations completed successfully")

            # Verify that all files were written to the target directory
            target_files = [f for f in os.listdir(target_partition_path) if f.endswith('.parquet')]
            print(f"Total files in target partition: {len(target_files)}")

            # Test rollback mechanism by simulating a failed write
            print("\nStep 4: Testing atomic write rollback mechanism")

            # Create a file that should be "rolled back" if validation fails
            rollback_test_file = os.path.join(staging_area, "rollback_test.parquet")
            invalid_data = pl.DataFrame({
                "symbol": ["SH600000"],
                "trade_date": [date(2023, 1, 15)],
                "close_price": [0.001],  # Invalid price - too low for A-share market
                "volume": [1000000]
            })
            invalid_data.write_parquet(rollback_test_file)

            # Validate before move - if validation fails, we shouldn't move
            rollback_data = pl.read_parquet(rollback_test_file)
            valid_prices = all(price >= 0.01 for price in rollback_data["close_price"])  # A-share minimum price

            if not valid_prices:
                print("Validation failed - invalid data detected, rollback simulated")
                # Don't move the file, just remove it (simulating rollback)
                os.remove(rollback_test_file)
                print("Invalid file was removed (rollback)")
            else:
                # Move would happen here if valid
                rollback_final = os.path.join(target_partition_path, "rollback_test.parquet")
                shutil.move(rollback_test_file, rollback_final)
                print("Data was valid, moved to final location")

            # Final validation: check target directory contents
            final_files = [f for f in os.listdir(target_partition_path) if f.endswith('.parquet')]
            print(f"Final count of files in target partition: {len(final_files)}")

            # Ensure that the core file (from our main atomic operation) is present
            assert any("daily_bars_2023-01-15" in f for f in final_files), "Main data file should be present"
            print("SUCCESS: Atomic write simulation completed successfully for A-share market platform")
            return True

    except Exception as e:
        print(f"FAILURE: Error in atomic write simulation: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = verify_atomic_write_simulation()
    if success:
        print("Verification completed successfully")
    else:
        print("Verification failed")
        exit(1)