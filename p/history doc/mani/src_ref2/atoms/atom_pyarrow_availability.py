#!/usr/bin/env python
"""
Verification script for atom_pyarrow_availability
This script verifies that the PyArrow library can be imported and used for basic data operations.
"""

def verify_pyarrow_availability():
    try:
        import pyarrow as pa
        import pyarrow.csv as csv
        import pyarrow.json as json
        import pyarrow.compute as pc

        print("PyArrow imported successfully")

        # Create sample data using PyArrow arrays
        symbol_array = pa.array(["AAPL", "GOOGL", "MSFT"])
        price_array = pa.array([150.0, 2500.0, 300.0], type=pa.float64())
        volume_array = pa.array([1000, 500, 800], type=pa.int32())

        # Create a table
        table = pa.table({
            'symbol': symbol_array,
            'price': price_array,
            'volume': volume_array
        })

        print(f"Table created with {table.num_rows} rows and {table.num_columns} columns")
        print("Column names:", table.column_names)

        # Test basic operations
        avg_price = pc.mean(table['price']).as_py()
        print(f"Average price: {avg_price}")

        total_volume = pc.sum(table['volume']).as_py()
        print(f"Total volume: {total_volume}")

        # Get unique symbols as an alternative to value_counts
        unique_symbols = pc.unique(table['symbol']).to_pylist()
        print("Unique symbols:", unique_symbols)

        print("SUCCESS: PyArrow library is available and functional")
        return True

    except ImportError as e:
        print(f"FAILURE: Could not import PyArrow: {e}")
        return False
    except Exception as e:
        print(f"FAILURE: Error testing PyArrow functionality: {e}")
        return False

if __name__ == "__main__":
    success = verify_pyarrow_availability()
    if success:
        print("Verification completed successfully")
    else:
        print("Verification failed")
        exit(1)