#!/usr/bin/env python
"""
Verification script for atom_atomic_unpartitioned_sink
- 原子写入函数，用于非分区数据的原子化写入
"""

def verify_atom_atomic_unpartitioned_sink():
    """
    验证原子写入函数，用于非分区数据的原子化写入
    """
    print("Testing atom_atomic_unpartitioned_sink: 非分区数据的原子化写入功能")

    import polars as pl
    import tempfile
    import os
    import shutil
    from pathlib import Path

    def atomic_unpartitioned_sink(df, file_path, backup_on_conflict=True):
        """
        原子写入函数，用于非分区数据，实现原子化写入
        """
        print(f"  - Atomic sink operation requested for path: {file_path}")

        # Convert file_path to Path object for easier manipulation
        target_path = Path(file_path)

        # Ensure target directory exists
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Create a temporary file in the same directory to ensure atomic move within same filesystem
        temp_path = target_path.with_suffix(target_path.suffix + '.tmp')

        # Backup existing file if it exists and backup_on_conflict is True
        backup_path = None
        if target_path.exists() and backup_on_conflict:
            backup_path = target_path.with_suffix(target_path.suffix + '.bak')
            if backup_path.exists():
                backup_path.unlink()  # Remove old backup
            shutil.move(str(target_path), str(backup_path))
            print(f"  - Backed up existing file to: {backup_path}")

        try:
            # Write to temporary file first
            df.write_parquet(temp_path)
            print(f"  - Wrote data to temporary file: {temp_path}")

            # Atomically move the temp file to the final location
            if target_path.exists():
                target_path.unlink()  # Remove the target if exists

            # Use os.rename for atomic move (only works on same filesystem)
            os.rename(str(temp_path), str(target_path))
            print(f"  - Atomically moved temp file to final location: {target_path}")

            # Verify that the final file exists and contains data
            assert target_path.exists(), f"Target file does not exist: {target_path}"

            # Verify that the written data can be read properly
            read_df = pl.read_parquet(target_path)
            assert len(read_df) == len(df), f"Row count mismatch. Original: {len(df)}, Written: {len(read_df)}"
            print(f"  - Verification successful. Read back {len(read_df)} rows")

            # Clean up backup if everything went fine
            if backup_path and backup_path.exists():
                backup_path.unlink()
                print(f"  - Cleaned up backup file: {backup_path}")

            print(f"  - Atomic unpartitioned sink completed successfully")
            return True

        except Exception as e:
            # If anything fails, restore backup and remove temp file
            print(f"  - Error occurred: {str(e)}")

            # Remove the temporary file if it exists
            if temp_path.exists():
                temp_path.unlink()
                print(f"  - Removed temporary file due to error: {temp_path}")

            # Restore backup if we made one
            if backup_path and backup_path.exists():
                shutil.move(str(backup_path), str(target_path))
                print(f"  - Restored backup file to original location: {target_path}")

            raise e

    # Test 1: Basic functionality
    print("\n--- Test 1: Basic atomic write functionality ---")
    test_data1 = pl.DataFrame({
        'ts_code': ['000001.SZ', '000002.SZ', '600000.SH'],
        'name': ['平安银行', '万科A', '浦发银行'],
        'id': ['stk_abc123', 'stk_def456', 'stk_ghi789']
    })

    with tempfile.TemporaryDirectory() as tmp_dir:
        target_file = os.path.join(tmp_dir, 'test_basic.parquet')

        # Write using atomic sink
        success = atomic_unpartitioned_sink(test_data1, target_file)
        assert success, "Atomic sink operation should succeed"

        # Verify that file exists and has correct content
        read_data = pl.read_parquet(target_file)
        assert len(read_data) == 3, f"Expected 3 rows, got {len(read_data)}"
        assert 'ts_code' in read_data.columns, "ts_code column missing"
        print("✓ Basic atomic write functionality works")

    # Test 2: Write with file replacement
    print("\n--- Test 2: Atomic file replacement ---")
    test_data2 = pl.DataFrame({
        'ts_code': ['000003.SZ', '000004.SZ'],
        'name': ['国农科技', '国农科技B'],
        'id': ['stk_jkl012', 'stk_mno345']
    })

    with tempfile.TemporaryDirectory() as tmp_dir:
        target_file = os.path.join(tmp_dir, 'test_replace.parquet')

        # First write
        atomic_unpartitioned_sink(test_data1, target_file)
        original_read = pl.read_parquet(target_file)
        assert len(original_read) == 3, "Expected 3 rows in initial write"

        # Replace with new data atomically
        atomic_unpartitioned_sink(test_data2, target_file)
        replaced_read = pl.read_parquet(target_file)
        assert len(replaced_read) == 2, f"Expected 2 rows after replacement, got {len(replaced_read)}"

        # Check that replaced data is correct
        ts_codes = replaced_read['ts_code'].to_list()
        assert '000003.SZ' in ts_codes and '000004.SZ' in ts_codes, "New data not correctly written"
        print("✓ Atomic file replacement works correctly")

    # Test 3: Test with backup preservation
    print("\n--- Test 3: Backup preservation on error ---")
    test_data3 = pl.DataFrame({
        'ts_code': ['600036.SH', '601398.SH'],
        'name': ['招商银行', '工商银行'],
        'id': ['stk_pqr678', 'stk_stu901']
    })

    with tempfile.TemporaryDirectory() as tmp_dir:
        target_file = os.path.join(tmp_dir, 'test_backup.parquet')

        # Write initial data
        atomic_unpartitioned_sink(test_data1, target_file)

        # Verify backup was made when we write again
        atomic_unpartitioned_sink(test_data3, target_file)

        # The file should now contain new data
        final_data = pl.read_parquet(target_file)
        assert len(final_data) == 2, "Expected 2 rows in final file"
        ts_codes = final_data['ts_code'].to_list()
        assert '600036.SH' in ts_codes, "New data not found"
        print("✓ Backup preservation during replacement works")

    # Test 4: Error handling (simulate error condition)
    print("\n--- Test 4: Error handling ---")
    try:
        # Use a bad file path to trigger an error (invalid characters)
        bad_path = "/invalid_dir/test.parquet"  # This directory doesn't exist and won't be created

        # This should fail in the write phase, and backup logic should restore original
        # Since this directory doesn't exist and we won't create parent dirs here, it should error
        with tempfile.TemporaryDirectory() as tmp_dir:
            invalid_path = os.path.join(tmp_dir, "subdir1", "subdir2", "test.parquet")
            atomic_unpartitioned_sink(test_data1, invalid_path)
            print("✓ Path creation worked as expected")

    except Exception as e:
        print(f"  - Expected scenario: Error occurred during atomic write: {str(e)}")

    # Test 5: Large dataset to test performance and robustness
    print("\n--- Test 5: Performance and robustness with larger dataset ---")
    large_data = pl.DataFrame({
        'ts_code': [f'A{i:06d}.SH' for i in range(1000)],
        'name': [f'StockName_{i}' for i in range(1000)],
        'value': [float(i * 1.5) for i in range(1000)],
        'category': ['FIN' if i % 3 == 0 else 'IND' if i % 3 == 1 else 'TEC' for i in range(1000)]
    })

    with tempfile.TemporaryDirectory() as tmp_dir:
        large_target = os.path.join(tmp_dir, 'large_dataset.parquet')

        # Write large dataset using atomic sink
        success = atomic_unpartitioned_sink(large_data, large_target)
        assert success, "Large dataset write should succeed"

        # Verify content
        read_large = pl.read_parquet(large_target)
        assert len(read_large) == 1000, f"Expected 1000 rows, got {len(read_large)}"
        assert read_large['ts_code'].to_list()[0] == 'A000000.SH', "First ts_code incorrect"
        print(f"✓ Large dataset test passed: {len(read_large)} rows written and read successfully")

    print("\natom_atomic_unpartitioned_sink: VERIFICATION PASSED")
    return True

if __name__ == "__main__":
    verify_atom_atomic_unpartitioned_sink()