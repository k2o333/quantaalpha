#!/usr/bin/env python
"""
Verification script for atom_duckdb_availability
This script verifies that the DuckDB library can be imported and used for basic SQL operations.
"""

def verify_duckdb_availability():
    try:
        import duckdb
        print("DuckDB imported successfully")

        # Test basic functionality by creating an in-memory database and performing operations
        conn = duckdb.connect(database=':memory:')

        # Create a sample table
        conn.execute("CREATE TABLE stocks (symbol VARCHAR, price DECIMAL, volume INTEGER)")
        conn.execute("INSERT INTO stocks VALUES ('AAPL', 150.0, 1000), ('GOOGL', 2500.0, 500), ('MSFT', 300.0, 800)")

        # Query the data
        result = conn.execute("SELECT symbol, AVG(price) as avg_price FROM stocks GROUP BY symbol ORDER BY symbol").fetchall()
        print("Query result:", result)

        # Test aggregation
        total_volume = conn.execute("SELECT SUM(volume) as total FROM stocks").fetchone()[0]
        print(f"Total volume: {total_volume}")

        print("SUCCESS: DuckDB library is available and functional")
        return True

    except ImportError as e:
        print(f"FAILURE: Could not import DuckDB: {e}")
        return False
    except Exception as e:
        print(f"FAILURE: Error testing DuckDB functionality: {e}")
        return False

if __name__ == "__main__":
    success = verify_duckdb_availability()
    if success:
        print("Verification completed successfully")
    else:
        print("Verification failed")
        exit(1)