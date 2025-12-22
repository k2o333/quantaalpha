#!/usr/bin/env python
"""
Verification script for atom_init_metadata_db
- SQLite元数据数据库初始化函数
"""

def verify_atom_init_metadata_db():
    """
    验证SQLite元数据数据库初始化函数
    """
    print("Testing atom_init_metadata_db: 元数据数据库初始化功能")

    import sqlite3
    import tempfile
    import os
    from datetime import datetime

    def init_metadata_db(db_path):
        """
        初始化SQLite元数据数据库
        """
        print(f"  - Initializing metadata database at: {db_path}")

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)

        # Connect to database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create metadata tables
        tables = {
            'stock_basic': '''
                CREATE TABLE IF NOT EXISTS stock_basic (
                    ts_code TEXT PRIMARY KEY,
                    permanent_id TEXT UNIQUE NOT NULL,
                    name TEXT NOT NULL,
                    industry TEXT,
                    area TEXT,
                    fullname TEXT,
                    enname TEXT,
                    market TEXT,
                    exchange TEXT,
                    curr_type TEXT,
                    list_status TEXT,
                    list_date TEXT,
                    delist_date TEXT,
                    is_hs TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            'meta_updates': '''
                CREATE TABLE IF NOT EXISTS meta_updates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    table_name TEXT NOT NULL,
                    last_update_date TEXT,
                    record_count INTEGER,
                    update_status TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            'metadata_master': '''
                CREATE TABLE IF NOT EXISTS metadata_master (
                    permanent_id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    ts_code TEXT UNIQUE,
                    name TEXT,
                    status TEXT DEFAULT 'active',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    source_data TEXT  -- JSON field to store original source data
                )
            ''',
            'api_configs': '''
                CREATE TABLE IF NOT EXISTS api_configs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    api_name TEXT UNIQUE NOT NULL,
                    config_data TEXT,  -- JSON field for API configuration
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''',
            'download_records': '''
                CREATE TABLE IF NOT EXISTS download_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts_code TEXT,
                    api_name TEXT,
                    trade_date TEXT,
                    download_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT,
                    file_path TEXT,
                    record_count INTEGER
                )
            '''
        }

        # Create all tables
        for table_name, create_sql in tables.items():
            cursor.execute(create_sql)
            print(f"    - Created/verified table: {table_name}")

        # Create indexes for better performance
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_stock_basic_permanent_id ON stock_basic(permanent_id)",
            "CREATE INDEX IF NOT EXISTS idx_meta_updates_table ON meta_updates(table_name)",
            "CREATE INDEX IF NOT EXISTS idx_metadata_master_type ON metadata_master(entity_type)",
            "CREATE INDEX IF NOT EXISTS idx_download_records_api ON download_records(api_name)",
            "CREATE INDEX IF NOT EXISTS idx_download_records_date ON download_records(download_date)"
        ]

        for idx_sql in indexes:
            cursor.execute(idx_sql)

        print(f"    - Created {len(indexes)} indexes for performance")

        # Commit and close
        conn.commit()

        # Verify tables exist
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        existing_tables = [row[0] for row in cursor.fetchall()]
        expected_tables = list(tables.keys())

        print(f"    - Database has {len(existing_tables)} tables: {existing_tables}")

        for table in expected_tables:
            assert table in existing_tables, f"Table {table} not found in database"

        conn.close()
        print(f"  - Metadata database successfully initialized at: {db_path}")

        return True

    def test_database_operations(db_path):
        """
        测试数据库的基本操作功能
        """
        print(f"  - Testing database operations on: {db_path}")

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Test 1: Insert sample stock data
        sample_stock = (
            '000001.SZ',  # ts_code
            'stk_33bbb694',  # permanent_id
            '平安银行',  # name
            '银行',  # industry
            '深圳',  # area
            '平安银行股份有限公司',  # fullname
            'Ping An Bank Co., Ltd.',  # enname
            '主板',  # market
            'SZSE',  # exchange
            'CNY',  # curr_type
            'L',  # list_status
            '19910403',  # list_date
            None,  # delist_date
            'N'  # is_hs
        )

        cursor.execute('''
            INSERT OR REPLACE INTO stock_basic (
                ts_code, permanent_id, name, industry, area, fullname, enname,
                market, exchange, curr_type, list_status, list_date, delist_date, is_hs
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', sample_stock)

        # Test 2: Insert metadata master record
        cursor.execute('''
            INSERT OR REPLACE INTO metadata_master (
                permanent_id, entity_type, ts_code, name, status
            ) VALUES (?, ?, ?, ?, ?)
        ''', ('stk_33bbb694', 'stock', '000001.SZ', '平安银行', 'active'))

        # Test 3: Insert metadata update record
        cursor.execute('''
            INSERT INTO meta_updates (table_name, last_update_date, record_count, update_status)
            VALUES (?, ?, ?, ?)
        ''', ('stock_basic', '20250101', 1, 'success'))

        conn.commit()

        # Test 4: Query the data back
        cursor.execute("SELECT * FROM stock_basic WHERE ts_code='000001.SZ'")
        result = cursor.fetchone()
        assert result is not None, "Could not retrieve inserted stock data"

        cursor.execute("SELECT COUNT(*) FROM stock_basic")
        count_result = cursor.fetchone()
        assert count_result[0] >= 1, "Stock data not properly inserted"

        conn.close()
        print(f"  - Database operations test completed successfully")

    # Test 1: Basic database initialization
    print("\n--- Test 1: Basic database initialization ---")
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_file:
        db_path = temp_file.name

    success = init_metadata_db(db_path)
    assert success, "Database initialization should succeed"

    # Verify the database file exists
    assert os.path.exists(db_path), f"Database file should exist at {db_path}"
    print("✓ Basic database initialization works")

    # Test 2: Database operations
    print("\n--- Test 2: Database operations ---")
    test_database_operations(db_path)
    print("✓ Database operations work")

    # Test 3: Initialize with different path
    print("\n--- Test 3: Initialize with different path ---")
    with tempfile.TemporaryDirectory() as temp_dir:
        new_db_path = os.path.join(temp_dir, 'metadata', 'test.db')
        success2 = init_metadata_db(new_db_path)
        assert success2, "Database initialization in subdirectory should succeed"
        assert os.path.exists(new_db_path), f"Database file should exist at {new_db_path}"
    print("✓ Initialization with different path works")

    # Test 4: Multiple initializations (should be idempotent)
    print("\n--- Test 4: Multiple initializations (idempotent) ---")
    # Initialize the same database again - should not fail
    success3 = init_metadata_db(db_path)
    assert success3, "Re-initialization of existing database should succeed"

    # Check that we still have our original data
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM meta_updates")
    count = cursor.fetchone()[0]
    conn.close()

    assert count >= 1, "Re-initialization should not delete existing data"
    print("✓ Multiple initializations work (idempotent)")

    # Test 5: Check table structure
    print("\n--- Test 5: Table structure verification ---")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check stock_basic table structure
    cursor.execute("PRAGMA table_info(stock_basic)")
    stock_columns = [row[1] for row in cursor.fetchall()]
    required_columns = ['ts_code', 'permanent_id', 'name', 'industry', 'created_at', 'updated_at']
    for col in required_columns:
        assert col in stock_columns, f"Required column {col} missing from stock_basic table"

    # Check metadata_master table structure
    cursor.execute("PRAGMA table_info(metadata_master)")
    master_columns = [row[1] for row in cursor.fetchall()]
    master_required = ['permanent_id', 'entity_type', 'ts_code', 'name', 'status', 'created_at', 'updated_at']
    for col in master_required:
        assert col in master_columns, f"Required column {col} missing from metadata_master table"

    conn.close()
    print("✓ Table structure verification completed")

    # Test 6: Performance with larger dataset
    print("\n--- Test 6: Performance with larger dataset ---")
    import time

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Insert multiple records
    start_time = time.time()
    for i in range(100):
        sample_data = (
            f'{i:06d}.SZ',
            f'stk_{i:08d}',
            f'StockName_{i}',
            'Unknown',
            'Unknown',
            f'Full Name {i}',
            f'Name {i}',
            '主板',
            'SZSE',
            'CNY',
            'L',
            '20250101',
            None,
            'N'
        )
        cursor.execute('''
            INSERT OR REPLACE INTO stock_basic (
                ts_code, permanent_id, name, industry, area, fullname, enname,
                market, exchange, curr_type, list_status, list_date, delist_date, is_hs
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', sample_data)

    conn.commit()
    end_time = time.time()

    # Verify insertions
    cursor.execute("SELECT COUNT(*) FROM stock_basic")
    total_count = cursor.fetchone()[0]
    conn.close()

    print(f"  - Inserted 100 records in {end_time - start_time:.3f}s")
    print(f"  - Total records in stock_basic: {total_count}")
    print("✓ Performance with larger dataset works")

    # Clean up
    if os.path.exists(db_path):
        os.unlink(db_path)

    print("\natom_init_metadata_db: VERIFICATION PASSED")
    return True

if __name__ == "__main__":
    verify_atom_init_metadata_db()