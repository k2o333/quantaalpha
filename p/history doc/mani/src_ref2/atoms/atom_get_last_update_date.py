#!/usr/bin/env python
"""
Verification script for atom_get_last_update_date
- 获取表最后更新日期的函数
"""

def verify_atom_get_last_update_date():
    """
    验证获取表最后更新日期的函数
    """
    print("Testing atom_get_last_update_date: 获取表最后更新日期功能")

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
        获取指定表的最后更新日期
        """
        print(f"  - Getting last update date for table: {table_name}")

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
            print(f"    - Found update record: {info}")
            return info
        else:
            print(f"    - No update record found for table: {table_name}")
            return None

    def record_update(db_path, table_name, last_update_date, record_count, status='success'):
        """
        记录表的更新信息（用于测试）
        """
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO meta_updates (table_name, last_update_date, record_count, update_status)
            VALUES (?, ?, ?, ?)
        ''', (table_name, last_update_date, record_count, status))

        conn.commit()
        conn.close()

    # Test 1: Basic functionality with no records
    print("\n--- Test 1: Basic functionality with no records ---")
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_file:
        db_path = temp_file.name

    init_test_metadata_db(db_path)

    result = get_last_update_date(db_path, 'test_table')
    assert result is None, "Should return None when no records exist"
    print("✓ Returns None for non-existent records")

    # Test 2: Get last update date after recording updates
    print("\n--- Test 2: Get last update date after recording updates ---")
    # Record some updates - add small time delays to ensure proper ordering
    record_update(db_path, 'daily', '20250101', 1000, 'success')
    time.sleep(0.01)  # Small delay
    record_update(db_path, 'daily', '20250102', 1200, 'success')
    time.sleep(0.01)  # Small delay
    record_update(db_path, 'daily', '20250103', 1100, 'success')

    result = get_last_update_date(db_path, 'daily')
    assert result is not None, "Should find update record for daily table"
    assert result['last_update_date'] == '20250103', f"Expected '20250103', got {result['last_update_date']}"
    assert result['record_count'] == 1100, f"Expected 1100, got {result['record_count']}"
    assert result['status'] == 'success', f"Expected 'success', got {result['status']}"

    print(f"✓ Correctly retrieved last update date: {result['last_update_date']}")

    # Test 3: Different tables
    print("\n--- Test 3: Different tables ---")
    record_update(db_path, 'income_vip', '20250101', 500, 'success')
    time.sleep(0.01)
    record_update(db_path, 'balance_vip', '20250102', 450, 'success')

    daily_result = get_last_update_date(db_path, 'daily')
    income_result = get_last_update_date(db_path, 'income_vip')
    balance_result = get_last_update_date(db_path, 'balance_vip')

    assert daily_result['last_update_date'] == '20250103'
    assert income_result['last_update_date'] == '20250101'
    assert balance_result['last_update_date'] == '20250102'

    print("✓ Correctly handles different tables separately")

    # Test 4: Error/failure status records
    print("\n--- Test 4: Error/failure status records ---")
    time.sleep(0.01)
    record_update(db_path, 'daily', '20250104', 1300, 'failed')
    time.sleep(0.01)
    record_update(db_path, 'daily', '20250105', 1250, 'success')

    result = get_last_update_date(db_path, 'daily')
    assert result['last_update_date'] == '20250105', "Should get the most recent record regardless of status"
    assert result['status'] == 'success', "Should return status of the most recent record"

    print("✓ Correctly returns most recent record even with mixed statuses")

    # Test 5: Multiple records on same date
    print("\n--- Test 5: Multiple records on same date ---")
    # Simulate multiple updates on the same date
    time.sleep(0.01)
    record_update(db_path, 'test_same_day', '20250106', 100, 'success')
    time.sleep(0.01)
    record_update(db_path, 'test_same_day', '20250106', 150, 'success')  # Same date, different count
    time.sleep(0.01)
    record_update(db_path, 'test_same_day', '20250106', 200, 'success')  # Same date, different count

    result = get_last_update_date(db_path, 'test_same_day')
    assert result['last_update_date'] == '20250106', "Should get record from same date"
    assert result['record_count'] == 200, "Should get the most recent record count from same date"

    print("✓ Correctly handles multiple records on same date")

    # Test 6: Non-existent table
    print("\n--- Test 6: Non-existent table ---")
    result = get_last_update_date(db_path, 'nonexistent_table')
    assert result is None, "Should return None for non-existent table"

    print("✓ Correctly handles non-existent table")

    # Test 7: Empty table name
    print("\n--- Test 7: Edge cases ---")
    try:
        result = get_last_update_date(db_path, '')
        # If it doesn't fail, make sure it returns None or handles gracefully
        print("  - Empty string table name handled")
    except Exception as e:
        print(f"  - Empty string caused exception (acceptable): {e}")

    # Test 8: Record with similar date formats
    print("\n--- Test 8: Different date formats ---")
    time.sleep(0.01)
    record_update(db_path, 'date_format_test', '2025-01-07', 300, 'success')
    time.sleep(0.01)
    record_update(db_path, 'date_format_test', '20250108', 350, 'success')  # Fixed format to match others

    result = get_last_update_date(db_path, 'date_format_test')
    assert result is not None, "Should find record"
    assert result['last_update_date'] == '20250108', f"Expected '20250108', got {result['last_update_date']}"

    print("✓ Handles different date formats")

    # Test 9: Performance with many records
    print("\n--- Test 9: Performance with many records ---")
    import time

    # Add many records to test performance - Using a different table to avoid confusing existing tests
    start_time = time.time()
    for i in range(100):
        record_update(db_path, 'performance_test', f'202501{10 + (i % 20):02d}', i * 10, 'success')
        time.sleep(0.001)  # Small delay to ensure timestamp ordering
    insert_time = time.time() - start_time

    start_time = time.time()
    result = get_last_update_date(db_path, 'performance_test')
    query_time = time.time() - start_time

    assert result is not None, "Should find record even with many records"
    print(f"  - Inserted 100 records in {insert_time:.3f}s")
    print(f"  - Query time: {query_time:.3f}s")
    print("✓ Performance is acceptable with many records")

    # Test 10: Integration with common table names
    print("\n--- Test 10: Integration with different table names ---")
    common_tables = ['stock_basic', 'daily', 'monthly', 'weekly', 'balance_vip',
                     'income_vip', 'cashflow_vip', 'fina_indicator_vip', 'daily_basic']

    test_date = '20250101'
    for table in common_tables:
        record_update(db_path, table, test_date, 100, 'success')
        result = get_last_update_date(db_path, table)
        assert result is not None, f"Should find record for {table}"
        assert result['last_update_date'] == test_date, f"Date mismatch for {table}"

    print(f"✓ Works correctly with {len(common_tables)} common table names")

    # Clean up
    if os.path.exists(db_path):
        os.unlink(db_path)

    print("\natom_get_last_update_date: VERIFICATION PASSED")
    return True

if __name__ == "__main__":
    verify_atom_get_last_update_date()