#!/usr/bin/env python
"""
Verification script for atom_partitioned_storage_simulation
This script simulates partitioned storage mechanisms appropriate for A-share market data platform
"""

def verify_partitioned_storage_simulation():
    try:
        import polars as pl
        import os
        import tempfile
        from datetime import datetime, date, timedelta
        import json
        import shutil

        # Test various partition strategies commonly needed for A-share market data
        print("Step 1: Setting up partitioned storage directory structures")

        with tempfile.TemporaryDirectory() as base_dir:
            # Strategy 1: Year-Month partitioning (typical for daily OHLCV data)
            print("Testing Year-Month partitioning strategy")
            symbols = ["SH600000", "SZ000001", "SH600036", "SZ300015"]
            months = [("2023", "01"), ("2023", "02"), ("2023", "03")]  # Jan-Mar 2023

            for symbol in symbols:
                for year, month in months:
                    partition_path = os.path.join(base_dir, "by_symbol_year_month", symbol, year, month)
                    os.makedirs(partition_path, exist_ok=True)

                    # Create sample daily data for this partition
                    # Generate a reasonable number of trading days for the month
                    import calendar
                    import random

                    # Approximate trading days in month (excluding weekends)
                    num_days = calendar.monthrange(int(year), int(month))[1]
                    trading_days = []
                    for day in range(1, num_days + 1):
                        current_date = date(int(year), int(month), day)
                        # Skip weekends (Saturday=5, Sunday=6 in Python weekday)
                        if current_date.weekday() < 5:
                            trading_days.append(current_date)

                    # Limit to first 20 trading days for example
                    trading_days = trading_days[:20]

                    sample_data = pl.DataFrame({
                        "symbol": [symbol] * len(trading_days),
                        "trade_date": trading_days,
                        "close_price": [round(30.0 + (j * random.uniform(-0.5, 0.8)), 2) for j in range(len(trading_days))],
                        "volume": [1000000 + i * random.randint(1000, 50000) for i in range(len(trading_days))]
                    })

                    if sample_data.height > 0:
                        parquet_file = os.path.join(partition_path, f"{symbol}_{year}-{month}.parquet")
                        sample_data.write_parquet(parquet_file)
                        print(f"  Created {parquet_file} with {sample_data.height} rows")

            # Strategy 2: Year partitioning (typical for reference data like stock info)
            print("\nTesting Year partitioning strategy")
            for year in ["2020", "2021", "2022", "2023"]:
                partition_path = os.path.join(base_dir, "by_year", year)
                os.makedirs(partition_path, exist_ok=True)

                # Create annual reference data
                ref_data = pl.DataFrame({
                    "symbol": symbols,
                    "listing_date": [date(int(year)-1, m, d) for m, d in [(6, 15), (8, 30), (4, 20), (12, 5)]],
                    "industry": ["Finance", "Finance", "Tech", "Healthcare"],
                    "market_cap": [500e9, 800e9, 300e9, 600e9]
                })

                parquet_file = os.path.join(partition_path, f"stock_reference_{year}.parquet")
                ref_data.write_parquet(parquet_file)
                print(f"  Created {parquet_file} with {ref_data.height} rows")

            # Strategy 3: Date-based partitioning (typical for daily trading snapshots)
            print("\nTesting Date-based partitioning strategy")
            for year, month, day in [("2023", "01", "15"), ("2023", "01", "16"), ("2023", "01", "17")]:
                for exchange in ["SSE", "SZE"]:
                    partition_path = os.path.join(base_dir, "by_date_exchange", year, month, day, exchange)
                    os.makedirs(partition_path, exist_ok=True)

                    daily_exchange_data = pl.DataFrame({
                        "symbol": [f"SH600{i:04d}" if exchange == "SSE" else f"SZ00{i:04d}" for i in range(100, 110)],
                        "close_price": [round(30.0 + (i * 0.25), 2) for i in range(10)],
                        "turnover": [5000000.0 + i * 100000.0 for i in range(10)],
                        "exchange": [exchange] * 10
                    })

                    parquet_file = os.path.join(partition_path, f"daily_{year}-{month}-{day}_{exchange.lower()}.parquet")
                    daily_exchange_data.write_parquet(parquet_file)
                    print(f"  Created {parquet_file} with {daily_exchange_data.height} rows")

            # Step 2: Verify partition structures follow A-share market requirements
            print("\nStep 2: Validating partitioned storage structures")

            # Check if the directory structure looks correct
            symbol_year_month_path = os.path.join(base_dir, "by_symbol_year_month")
            year_path = os.path.join(base_dir, "by_year")
            date_exchange_path = os.path.join(base_dir, "by_date_exchange")

            assert os.path.exists(symbol_year_month_path), "Symbol-year-month partition structure should exist"
            assert os.path.exists(year_path), "Year partition structure should exist"
            assert os.path.exists(date_exchange_path), "Date-exchange partition structure should exist"

            # Check depth constraints for each strategy
            for root, dirs, files in os.walk(symbol_year_month_path):
                depth_from_partition_root = root[len(symbol_year_month_path):].count(os.sep)
                assert depth_from_partition_root <= 3, f"Symbol-year-month structure too deep: {depth_from_partition_root}"

            for root, dirs, files in os.walk(date_exchange_path):
                depth_from_partition_root = root[len(date_exchange_path):].count(os.sep)
                assert depth_from_partition_root <= 4, f"Date-exchange structure too deep: {depth_from_partition_root}"

            # Step 3: Test efficient querying from partition structure (simulated)
            print("\nStep 3: Testing efficient partitioned querying")
            # We test by checking if we can identify which partitions have data for specific queries

            # Find monthly partitions for a specific symbol and date range
            test_symbol = "SH600000"
            symbol_partitions = []

            for symbol_dir in os.listdir(os.path.join(base_dir, "by_symbol_year_month")):
                if symbol_dir.startswith(test_symbol.split()[0]):  # Just get the symbol part
                    year_dirs = os.listdir(os.path.join(base_dir, "by_symbol_year_month", symbol_dir))

                    symbol_partition_dir = os.path.join(base_dir, "by_symbol_year_month", symbol_dir)

                    for year_dir in year_dirs:
                        month_dirs = os.listdir(os.path.join(symbol_partition_dir, year_dir))
                        for month_dir in month_dirs:
                            if any(f.endswith('.parquet') for f in os.listdir(os.path.join(symbol_partition_dir, year_dir, month_dir))):
                                symbol_partitions.append(f"{year_dir}/{month_dir}")

            print(f"  Found {len(symbol_partitions)} partitions for {test_symbol}: {symbol_partitions}")
            assert len(symbol_partitions) > 0, f"Should have found partitions for {test_symbol}"

            # Create and verify a partition manifest for A-share data management
            print("\nCreating partition manifest for A-share data management")
            partition_manifest = {
                "created_at": str(datetime.now()),
                "base_path": base_dir,
                "partition_strategies": [
                    {
                        "name": "by_symbol_year_month",
                        "description": "For daily trading data, partitioned by symbol, year, and month",
                        "path_pattern": "/by_symbol_year_month/<symbol>/<year>/<month>/",
                        "data_type": "daily_bars",
                        "retention": "5_years"
                    },
                    {
                        "name": "by_year",
                        "description": "For reference data, partitioned by year",
                        "path_pattern": "/by_year/<year>/",
                        "data_type": "reference",
                        "retention": "indefinite"
                    },
                    {
                        "name": "by_date_exchange",
                        "description": "For daily snapshots by date and exchange",
                        "path_pattern": "/by_date_exchange/<year>/<month>/<day>/<exchange>/",
                        "data_type": "snapshots",
                        "retention": "2_years"
                    }
                ],
                "total_partitions": len(symbol_partitions),
                "total_symbols_covered": len(symbols)
            }

            manifest_path = os.path.join(base_dir, "partition_manifest.json")

            with open(manifest_path, 'w') as f:
                json.dump(partition_manifest, f, indent=2, ensure_ascii=False, default=str)

            assert os.path.exists(manifest_path), "Manifest should be created"
            print(f"  Manifest created at: {manifest_path}")

        print("SUCCESS: Partitioned storage simulation completed successfully for A-share market platform")
        return True

    except Exception as e:
        print(f"FAILURE: Error in partitioned storage simulation: {e}")
        return False

if __name__ == "__main__":
    success = verify_partitioned_storage_simulation()
    if success:
        print("Verification completed successfully")
    else:
        print("Verification failed")
        exit(1)