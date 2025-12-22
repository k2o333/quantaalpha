#!/usr/bin/env python
"""
Verification script for atom_polars_availability
This script verifies that the Polars library can be imported and used for basic functionality.
"""

def verify_polars_availability():
    try:
        import polars as pl
        print("Polars imported successfully")

        # Test basic functionality by creating a simple DataFrame
        df = pl.DataFrame({
            "symbol": ["AAPL", "GOOGL", "MSFT"],
            "price": [150.0, 2500.0, 300.0],
            "volume": [1000, 500, 800]
        })

        print("DataFrame created:", df.shape)
        print("Columns:", df.columns)

        # Perform a basic operation
        avg_price = df.select(pl.col("price").mean()).item()
        print(f"Average price: {avg_price}")

        print("SUCCESS: Polars library is available and functional")
        return True

    except ImportError as e:
        print(f"FAILURE: Could not import Polars: {e}")
        return False
    except Exception as e:
        print(f"FAILURE: Error testing Polars functionality: {e}")
        return False

if __name__ == "__main__":
    success = verify_polars_availability()
    if success:
        print("Verification completed successfully")
    else:
        print("Verification failed")
        exit(1)