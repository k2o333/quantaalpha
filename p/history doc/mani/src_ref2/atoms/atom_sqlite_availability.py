#!/usr/bin/env python
"""
Verification script for atom_sqlite_availability
This script verifies that the SQLite library can be imported and used for basic database operations.
"""

def verify_sqlite_availability():
    try:
        import sqlite3
        print("SQLite3 imported successfully")

        # Create an in-memory database
        conn = sqlite3.connect(':memory:')
        cursor = conn.cursor()

        # Create a sample table
        cursor.execute('''
            CREATE TABLE stocks (
                id INTEGER PRIMARY KEY,
                symbol VARCHAR(10),
                price REAL,
                volume INTEGER
            )
        ''')

        # Insert sample data
        cursor.execute("INSERT INTO stocks (symbol, price, volume) VALUES (?, ?, ?)", ('AAPL', 150.0, 1000))
        cursor.execute("INSERT INTO stocks (symbol, price, volume) VALUES (?, ?, ?)", ('GOOGL', 2500.0, 500))
        cursor.execute("INSERT INTO stocks (symbol, price, volume) VALUES (?, ?, ?)", ('MSFT', 300.0, 800))

        # Commit the changes
        conn.commit()

        # Query the data
        cursor.execute("SELECT symbol, price, volume FROM stocks ORDER BY symbol")
        results = cursor.fetchall()
        print("Query results:", results)

        # Test aggregation
        cursor.execute("SELECT AVG(price) as avg_price, SUM(volume) as total_volume FROM stocks")
        agg_result = cursor.fetchone()
        print(f"Average price: {agg_result[0]}, Total volume: {agg_result[1]}")

        # Close the connection
        conn.close()

        print("SUCCESS: SQLite library is available and functional")
        return True

    except ImportError as e:
        print(f"FAILURE: Could not import SQLite: {e}")
        return False
    except Exception as e:
        print(f"FAILURE: Error testing SQLite functionality: {e}")
        return False

if __name__ == "__main__":
    success = verify_sqlite_availability()
    if success:
        print("Verification completed successfully")
    else:
        print("Verification failed")
        exit(1)