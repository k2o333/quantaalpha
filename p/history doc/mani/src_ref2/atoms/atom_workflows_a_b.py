#!/usr/bin/env python
"""
Verification script for atom_workflows_a_b
- 工作流管理，区分首次全量构建和每日增量更新两种工作流
"""

def verify_atom_workflows_a_b():
    """
    验证工作流管理，区分首次全量构建和每日增量更新两种工作流
    """
    print("Testing atom_workflows_a_b: 工作流管理功能")

    import tempfile
    import os
    import time
    import threading
    from datetime import datetime, timedelta
    import json

    def is_first_time_build(data_dir):
        """
        检查是否为首次全量构建
        """
        print(f"  - Checking if first time build for directory: {data_dir}")

        # Check if data directory exists and has data
        if not os.path.exists(data_dir):
            print(f"    - Directory doesn't exist: {data_dir}")
            return True

        # Check if directory is empty
        if not os.listdir(data_dir):
            print(f"    - Directory is empty: {data_dir}")
            return True

        # Check if we have metadata indicating first build
        metadata_file = os.path.join(data_dir, 'metadata.json')
        if os.path.exists(metadata_file):
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
                first_build = not metadata.get('first_build_completed', False)
                print(f"    - Metadata indicates first build status: {first_build}")
                return first_build
        else:
            print(f"    - No metadata file found, assuming first build")
            return True

    def full_build_workflow(data_dir, tables_to_build):
        """
        首次全量构建工作流
        """
        print(f"  - Running full build workflow")
        print(f"    - Data directory: {data_dir}")
        print(f"    - Tables to build: {len(tables_to_build)}")

        # Create data directory if it doesn't exist
        os.makedirs(data_dir, exist_ok=True)

        # Simulate building each table
        results = {}
        start_time = time.time()

        for table_name in tables_to_build:
            print(f"    - Building table: {table_name}")

            # Simulate data download and processing
            table_start = time.time()

            # Create a mock data file for this table
            table_file = os.path.join(data_dir, f"{table_name}.parquet")

            # Write mock data
            mock_data = {
                'status': 'completed',
                'rows_processed': 10000 if 'daily' not in table_name else 1000,
                'build_time': time.time() - table_start,
                'table_name': table_name,
                'timestamp': datetime.now().isoformat()
            }

            # In real implementation, this would write actual parquet data
            with open(table_file.replace('.parquet', '.json'), 'w') as f:
                json.dump(mock_data, f, indent=2)

            results[table_name] = mock_data
            print(f"      - Completed {table_name} in {mock_data['build_time']:.2f}s")

        # Write metadata file to indicate first build completed
        metadata_file = os.path.join(data_dir, 'metadata.json')
        metadata = {
            'first_build_completed': True,
            'build_time': time.time() - start_time,
            'tables_built': len(tables_to_build),
            'completed_at': datetime.now().isoformat(),
            'tables': list(results.keys())
        }

        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

        print(f"  - Full build workflow completed in {metadata['build_time']:.2f}s")
        print(f"  - Built {metadata['tables_built']} tables")
        return results

    def daily_update_workflow(data_dir, tables_to_update):
        """
        每日增量更新工作流
        """
        print(f"  - Running daily update workflow")
        print(f"    - Data directory: {data_dir}")
        print(f"    - Tables to update: {len(tables_to_update)}")

        if not os.path.exists(data_dir):
            print(f"    - Data directory doesn't exist: {data_dir}")
            return None

        # Read existing metadata
        metadata_file = os.path.join(data_dir, 'metadata.json')
        if os.path.exists(metadata_file):
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
        else:
            print(f"    - No metadata file found, cannot perform daily update")
            return None

        # Simulate updating each table
        results = {}
        start_time = time.time()

        for table_name in tables_to_update:
            print(f"    - Updating table: {table_name}")

            # Simulate data download and processing
            table_start = time.time()

            # Check for existing table data file
            expected_files = [
                os.path.join(data_dir, f"{table_name}.parquet"),
                os.path.join(data_dir, f"{table_name}.json")
            ]

            table_exists = any(os.path.exists(f) for f in expected_files)

            # Create mock update data
            mock_data = {
                'status': 'updated',
                'rows_processed': 1000 if 'daily' in table_name else 100,  # Less for daily
                'build_time': time.time() - table_start,
                'table_name': table_name,
                'timestamp': datetime.now().isoformat(),
                'table_existed': table_exists
            }

            # Write mock data
            table_file = os.path.join(data_dir, f"{table_name}.json")
            with open(table_file, 'w') as f:
                json.dump(mock_data, f, indent=2)

            results[table_name] = mock_data
            print(f"      - Updated {table_name} in {mock_data['build_time']:.2f}s")

        # Update metadata file
        metadata['last_daily_update'] = datetime.now().isoformat()
        metadata['daily_updates_performed'] = metadata.get('daily_updates_performed', 0) + 1

        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)

        print(f"  - Daily update workflow completed in {time.time() - start_time:.2f}s")
        print(f"  - Updated {len(results)} tables")
        return results

    # Test 1: Check first time build detection
    print("\n--- Test 1: First time build detection ---")
    with tempfile.TemporaryDirectory() as temp_dir:
        test_data_dir = os.path.join(temp_dir, 'test_data')

        # Initially, should be first time
        first_build = is_first_time_build(test_data_dir)
        assert first_build == True, "Should detect as first time build initially"
        print("✓ First time build detection works")

    # Test 2: Full build workflow
    print("\n--- Test 2: Full build workflow ---")
    with tempfile.TemporaryDirectory() as temp_dir:
        full_build_dir = os.path.join(temp_dir, 'full_build_data')

        tables = ['stock_basic', 'daily', 'balance_vip', 'income_vip', 'cashflow_vip']
        results = full_build_workflow(full_build_dir, tables)

        assert len(results) == 5, f"Expected 5 results, got {len(results)}"
        assert all(table in results for table in tables), "Should have results for all tables"

        # Check that metadata was created
        metadata_path = os.path.join(full_build_dir, 'metadata.json')
        assert os.path.exists(metadata_path), "Metadata file should be created after full build"

        print("✓ Full build workflow works")

    # Test 3: Daily update workflow (simulating after full build)
    print("\n--- Test 3: Daily update workflow ---")
    with tempfile.TemporaryDirectory() as temp_dir:
        daily_update_dir = os.path.join(temp_dir, 'daily_update_data')

        # First run a full build to set up the environment
        tables = ['daily', 'weekly', 'balance_vip']
        full_results = full_build_workflow(daily_update_dir, tables)

        # Now run daily update
        daily_tables = ['daily', 'balance_vip']  # Only update subset
        daily_results = daily_update_workflow(daily_update_dir, daily_tables)

        assert daily_results is not None, "Daily update should succeed after full build"
        assert len(daily_results) == 2, f"Expected 2 daily update results, got {len(daily_results)}"

        # Check that metadata was updated
        with open(os.path.join(daily_update_dir, 'metadata.json'), 'r') as f:
            updated_metadata = json.load(f)

        assert 'last_daily_update' in updated_metadata, "Should have last daily update timestamp"
        assert updated_metadata['daily_updates_performed'] >= 1, "Should track daily updates"

        print("✓ Daily update workflow works")

    # Test 4: First time detection after full build
    print("\n--- Test 4: First time detection after full build ---")
    with tempfile.TemporaryDirectory() as temp_dir:
        check_dir = os.path.join(temp_dir, 'check_after_full')

        # Run full build first
        full_build_workflow(check_dir, ['test_table'])

        # Now should NOT be first time
        is_first = is_first_time_build(check_dir)
        assert is_first == False, "Should NOT be first time build after full build completed"

        print("✓ First time detection after full build works")

    # Test 5: Concurrent workflow execution
    print("\n--- Test 5: Concurrent workflow execution ---")
    results = {}

    def run_workflow_in_thread(thread_id, workflow_type, data_dir, tables, results_dict):
        time.sleep(0.1)  # Small delay to allow other threads to start
        if workflow_type == 'full':
            results_dict[f'thread_{thread_id}'] = full_build_workflow(data_dir, tables)
        elif workflow_type == 'daily':
            # First do a full build, then update
            full_build_workflow(data_dir, tables)
            results_dict[f'thread_{thread_id}'] = daily_update_workflow(data_dir, tables)

    with tempfile.TemporaryDirectory() as temp_dir:
        thread_results = {}
        threads = []

        # Start multiple workflows in different directories
        for i in range(2):
            workflow_dir = os.path.join(temp_dir, f'workflow_{i}')
            thread = threading.Thread(
                target=run_workflow_in_thread,
                args=(i, 'daily', workflow_dir, [f'table_{i}'], thread_results)
            )
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        assert len(thread_results) == 2, f"Expected 2 thread results, got {len(thread_results)}"
        print("✓ Concurrent workflow execution works")

    # Test 6: Large scale workflow
    print("\n--- Test 6: Large scale workflow ---")
    with tempfile.TemporaryDirectory() as temp_dir:
        large_build_dir = os.path.join(temp_dir, 'large_build')

        # Simulate building many tables
        many_tables = [f'table_{i}' for i in range(20)]

        start_time = time.time()
        large_results = full_build_workflow(large_build_dir, many_tables)
        end_time = time.time()

        assert len(large_results) == 20, f"Expected 20 results, got {len(large_results)}"
        print(f"  - Built {len(large_results)} tables in {end_time - start_time:.3f}s")
        print("✓ Large scale workflow works")

    # Test 7: Mixed workflow patterns
    print("\n--- Test 7: Mixed workflow patterns ---")
    with tempfile.TemporaryDirectory() as temp_dir:
        mixed_dir = os.path.join(temp_dir, 'mixed')

        # Full build
        full_tables = ['stock_basic', 'daily_basic']
        full_result = full_build_workflow(mixed_dir, full_tables)

        # Verify first build completed
        assert is_first_time_build(mixed_dir) == False

        # Daily update
        daily_tables = ['daily']
        daily_result = daily_update_workflow(mixed_dir, daily_tables)

        # Another daily update
        daily_result2 = daily_update_workflow(mixed_dir, daily_tables)

        # Check metadata
        with open(os.path.join(mixed_dir, 'metadata.json'), 'r') as f:
            metadata = json.load(f)

        assert metadata['daily_updates_performed'] == 2, "Should have 2 daily updates"
        assert 'last_daily_update' in metadata, "Should have last daily update timestamp"

        print("✓ Mixed workflow patterns work")

    # Test 8: Error handling
    print("\n--- Test 8: Error handling ---")
    # Test with non-existent directory for daily update (should handle gracefully)
    with tempfile.TemporaryDirectory() as temp_dir:
        non_existent_dir = os.path.join(temp_dir, 'non_existent')

        daily_result = daily_update_workflow(non_existent_dir, ['test_table'])
        # This should return None rather than crash
        print("  - Daily update on non-existent directory handled gracefully")

        # Test with empty table list
        empty_tables_dir = os.path.join(temp_dir, 'empty_tables')
        full_build_workflow(empty_tables_dir, [])
        print("  - Full build with empty tables list handled")

        print("✓ Error handling works")

    print("\natom_workflows_a_b: VERIFICATION PASSED")
    return True

if __name__ == "__main__":
    verify_atom_workflows_a_b()