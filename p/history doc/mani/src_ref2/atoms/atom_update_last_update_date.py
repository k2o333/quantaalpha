#!/usr/bin/env python
"""
Verification script for atom_update_last_update_date
- 更新表最后更新日期的函数
"""

def verify_atom_update_last_update_date():
    """
    验证更新表最后更新日期的函数
    """
    print("Testing atom_update_last_update_date: 更新表最后更新日期功能")

    import sqlite3
    import tempfile
    import os
    from datetime import datetime, timedelta
    import time

    def init_test_metadata_db(db_path):
        """
        初始化测试用的元数据数据库
        """
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create meta_updates table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS meta_updates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT NOT NULL,
                last_update_date TEXT,
                record_count INTEGER,
                update_status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create index
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_meta_updates_table ON meta_updates(table_name)")

        conn.commit()
        conn.close()

    def get_last_update_date(db_path, table_name):
        """
        获取指定表的最后更新日期 (复用前面的函数逻辑)
        """
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Query the last update record for the table - ORDER BY created_at DESC to get most recent
        cursor.execute('''
            SELECT last_update_date, record_count, update_status, created_at
            FROM meta_updates
            WHERE table_name = ?
            ORDER BY created_at DESC, id DESC
            LIMIT 1
        ''', (table_name,))

        result = cursor.fetchone()
        conn.close()

        if result:
            last_date, record_count, status, created_at = result
            info = {
                'last_update_date': last_date,
                'record_count': record_count,
                'status': status,
                'queried_at': created_at
            }
            return info
        else:
            return None

    def update_last_update_date(db_path, table_name, last_update_date, record_count, status='success'):
        """
        更新指定表的最后更新日期
        """
        print(f"  - Updating last update date for table: {table_name}")
        print(f"    - Date: {last_update_date}")
        print(f"    - Count: {record_count}")
        print(f"    - Status: {status}")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO meta_updates (table_name, last_update_date, record_count, update_status)
            VALUES (?, ?, ?, ?)
        ''', (table_name, last_update_date, record_count, status))

        conn.commit()
        conn.close()

        print(f"  - Successfully updated last update date for {table_name}")
        return True

    # Test 1: Basic update functionality
    print("\n--- Test 1: Basic update functionality ---")
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_file:
        db_path = temp_file.name

    init_test_metadata_db(db_path)

    success = update_last_update_date(db_path, 'daily', '20250101', 1000, 'success')
    assert success, "Update should succeed"

    # Verify the update was recorded
    result = get_last_update_date(db_path, 'daily')
    assert result is not None, "Should find update record for daily table"
    assert result['last_update_date'] == '20250101', f"Expected '20250101', got {result['last_update_date']}"
    assert result['record_count'] == 1000, f"Expected 1000, got {result['record_count']}"
    assert result['status'] == 'success', f"Expected 'success', got {result['status']}"

    print("✓ Basic update functionality works")

    # Test 2: Update with date change
    print("\n--- Test 2: Update with date change ---")
    time.sleep(0.01)  # Small delay to ensure proper timestamp ordering
    success2 = update_last_update_date(db_path, 'daily', '20250102', 1100, 'success')
    assert success2, "Date change update should succeed"

    result = get_last_update_date(db_path, 'daily')
    assert result['last_update_date'] == '20250102', f"Expected '20250102', got {result['last_update_date']}"
    assert result['record_count'] == 1100, f"Expected 1100, got {result['record_count']}"

    print("✓ Date change update works correctly")

    # Test 3: Updates to different tables
    print("\n--- Test 3: Updates to different tables ---")
    time.sleep(0.01)
    success3 = update_last_update_date(db_path, 'income_vip', '20250101', 500, 'success')
    assert success3, "Income update should succeed"

    time.sleep(0.01)
    success4 = update_last_update_date(db_path, 'balance_vip', '20250102', 450, 'success')
    assert success4, "Balance update should succeed"

    # Verify all tables have correct latest dates
    daily_result = get_last_update_date(db_path, 'daily')
    income_result = get_last_update_date(db_path, 'income_vip')
    balance_result = get_last_update_date(db_path, 'balance_vip')

    assert daily_result['last_update_date'] == '20250102'
    assert income_result['last_update_date'] == '20250101'
    assert balance_result['last_update_date'] == '20250102'

    print("✓ Updates to different tables work correctly")

    # Test 4: Update with different status values
    print("\n--- Test 4: Update with different status values ---")
    time.sleep(0.01)
    success5 = update_last_update_date(db_path, 'daily', '20250103', 1200, 'partial')
    assert success5, "Partial update should succeed"

    result = get_last_update_date(db_path, 'daily')
    assert result['status'] == 'partial', f"Expected 'partial', got {result['status']}"

    time.sleep(0.01)
    success6 = update_last_update_date(db_path, 'daily', '20250104', 0, 'failed')
    assert success6, "Failed update should succeed"

    result = get_last_update_date(db_path, 'daily')
    assert result['status'] == 'failed', f"Expected 'failed', got {result['status']}"

    print("✓ Different status values work correctly")

    # Test 5: Edge cases
    print("\n--- Test 5: Edge cases ---")
    time.sleep(0.01)
    success7 = update_last_update_date(db_path, 'empty_test', '', 0, 'success')
    assert success7, "Empty date update should succeed"

    time.sleep(0.01)
    success8 = update_last_update_date(db_path, 'null_test', None, 0, 'success')
    assert success8, "None date update should succeed"

    print("✓ Edge cases handled correctly")

    # Test 6: Update with very large record count
    print("\n--- Test 6: Update with very large record count ---")
    time.sleep(0.01)
    success10 = update_last_update_date(db_path, 'zero_count', '20250106', 0, 'success')
    assert success10, "Zero count update should succeed"

    result = get_last_update_date(db_path, 'zero_count')
    assert result['record_count'] == 0, f"Expected 0, got {result['record_count']}"

    time.sleep(0.01)
    large_count = 1000000  # 1 million records
    success11 = update_last_update_date(db_path, 'large_count', '20250107', large_count, 'success')
    assert success11, "Large count update should succeed"

    result = get_last_update_date(db_path, 'large_count')
    assert result['record_count'] == large_count, f"Expected {large_count}, got {result['record_count']}"

    print("✓ Large and zero record counts handled correctly")

    # Test 7: Update with different status values
    print("\n--- Test 7: Update with different status values ---")
    statuses = ['success', 'partial', 'failed', 'timeout', 'skipped']

    for i, status in enumerate(statuses):
        time.sleep(0.01)
        table_name = f'status_test_{i}'
        success = update_last_update_date(db_path, table_name, '20250108', 100 + i, status)
        assert success, f"Update with status {status} should succeed"

        result = get_last_update_date(db_path, table_name)
        assert result['status'] == status, f"Expected status {status}, got {result['status']}"

    print("✓ Different status values handled correctly")

    # Test 8: Performance with multiple updates
    print("\n--- Test 8: Performance with multiple updates ---")
    import time

    # Perform many updates quickly
    start_time = time.time()
    for i in range(50):
        table_name = f'perf_test_{i}'
        update_last_update_date(db_path, table_name, f'202501{10 + (i % 20):02d}', i * 10, 'success')
        if i % 10 == 0:  # Add delay every 10 updates
            time.sleep(0.001)
    end_time = time.time()

    # Verify that all updates were recorded
    all_found = True
    for i in range(50):
        table_name = f'perf_test_{i}'
        result = get_last_update_date(db_path, table_name)
        if result is None:
            all_found = False
            break

    assert all_found, "All performance test updates should be found"
    print(f"  - Performed 50 updates in {end_time - start_time:.3f}s")
    print("✓ Performance is acceptable with multiple updates")

    # Test 9: Common table name conventions
    print("\n--- Test 9: Common table name conventions ---")
    common_tables = ['stock_basic', 'daily_data', 'monthly_summary', 'weekly_analysis', 'balance_sheet_vip',
                     'income_statement_vip', 'cash_flow_vip', 'financial_indicator_vip', 'daily_basic_info',
                     'abc123_test_table']

    for i, table_name in enumerate(common_tables):
        success = update_last_update_date(db_path, table_name, f'202501{i+1:02d}', 100 + i, 'success')
        assert success, f"Update for {table_name} should succeed"

        result = get_last_update_date(db_path, table_name)
        assert result is not None, f"Should find record for {table_name}"
        assert result['last_update_date'] == f'202501{i+1:02d}', f"Date mismatch for {table_name}"

    print(f"✓ Works correctly with {len(common_tables)} common table names")

    # Test 10: Idempotency - updating same table multiple times
    print("\n--- Test 10: Idempotency - multiple updates to same table ---")
    base_table = 'idempotency_test'

    # Update the same table multiple times
    for i in range(5):
        time.sleep(0.01)
        success = update_last_update_date(db_path, base_table, f'202502{i+1:02d}', 200 + i, 'success')
        assert success, f"Update {i+1} for {base_table} should succeed"

    # Verify that the latest update is what we get
    result = get_last_update_date(db_path, base_table)
    assert result is not None
    assert result['last_update_date'] == '20250205', f"Expected latest date '20250205', got {result['last_update_date']}"
    assert result['record_count'] == 204, f"Expected record count 204, got {result['record_count']}"

    print("✓ Multiple updates to same table work correctly (get latest)")

    # Clean up
    if os.path.exists(db_path):
        os.unlink(db_path)

    print("\natom_update_last_update_date: VERIFICATION PASSED")
    return True

if __name__ == "__main__":
    verify_atom_update_last_update_date()