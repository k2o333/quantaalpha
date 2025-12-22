#!/usr/bin/env python
"""
Verification script for atom_etl_pipeline_simulation
This script simulates ETL processes appropriate for A-share market data platform
"""

def verify_etl_pipeline_simulation():
    try:
        import polars as pl
        from datetime import datetime, date
        import random
        import tempfile
        import os

        # Step 1: Extract - Generate mock source data (simulating external data source)
        print("Step 1: Extract - Simulating data extraction from external source")

        # Generate raw data that might come from external API/DB
        raw_data = {
            "sec_code": ["600000", "600036", "000001", "000858", "300015"],
            "sec_name": ["浦发银行", "招商银行", "平安银行", "五粮液", "爱尔眼科"],
            "trade_date": ["2023-01-15", "2023-01-15", "2023-01-15", "2023-01-15", "2023-01-15"],
            "open": ["7.21", "38.45", "15.40", "175.50", "32.10"],
            "high": ["7.35", "39.20", "15.65", "178.80", "32.80"],
            "low": ["7.15", "38.20", "15.25", "174.20", "31.90"],
            "close": ["7.30", "39.05", "15.50", "177.60", "32.50"],
            "volume": ["12345678", "5432109", "9876543", "2345678", "6789012"],
            "amount": ["89987654.32", "210987654.56", "153210987.65", "415678899.10", "219876543.21"],
            "pre_close": ["7.25", "38.80", "15.45", "176.20", "32.30"]
        }

        # Convert to DataFrame with string types initially (as we might get from external source)
        raw_df = pl.DataFrame(raw_data)
        print(f"Raw data extracted: {raw_df.shape[0]} rows, {raw_df.shape[1]} columns")

        # Step 2: Transform - Process the data to match our internal schema
        print("\nStep 2: Transform - Processing and cleaning data")

        # Transform the data to our internal schema
        transformed_df = raw_df.with_columns([
            # Add exchange prefix to make proper symbols
            pl.when(pl.col("sec_code").str.starts_with("6"))
            .then(pl.lit("SH") + pl.col("sec_code"))
            .otherwise(pl.lit("SZ") + pl.col("sec_code"))
            .alias("symbol"),

            # Proper data types conversion
            pl.col("trade_date").str.strptime(pl.Date, "%Y-%m-%d").alias("trade_date"),
            pl.col("open").cast(pl.Float64).alias("open_price"),
            pl.col("high").cast(pl.Float64).alias("high_price"),
            pl.col("low").cast(pl.Float64).alias("low_price"),
            pl.col("close").cast(pl.Float64).alias("close_price"),
            pl.col("pre_close").cast(pl.Float64).alias("prev_close"),
            pl.col("volume").cast(pl.Int64).alias("volume"),
            pl.col("amount").cast(pl.Float64).alias("turnover")
        ]).select([
            "symbol",
            "trade_date",
            "open_price",
            "high_price",
            "low_price",
            "close_price",
            "prev_close",
            "volume",
            "turnover"
        ])

        # Add additional calculated fields
        transformed_df = transformed_df.with_columns([
            ((pl.col("close_price") - pl.col("prev_close")) / pl.col("prev_close") * 100).alias("change_pct"),
            (pl.col("turnover") / pl.col("volume")).alias("avg_price") if all(v > 0 for v in transformed_df["volume"]) else pl.lit(0.0).alias("avg_price")
        ])

        print(f"Data transformed: {transformed_df.shape[0]} rows, {transformed_df.shape[1]} columns")
        print(f"Columns after transformation: {list(transformed_df.columns)}")

        # Data validation steps during transform
        # Check for nulls
        null_counts = transformed_df.null_count()
        total_nulls = sum(null_counts[row] for row in range(null_counts.shape[0]) for col in range(null_counts.shape[1]))
        print(f"Null values after transformation: {total_nulls}")

        # Validate price ranges (should be realistic for A-share market)
        assert all(0.01 <= p <= 10000 for p in transformed_df["close_price"]), "Prices should be within reasonable range"
        assert all(0 <= v <= 1e10 for v in transformed_df["volume"]), "Volumes should be non-negative and reasonable"

        print("Data validation passed")

        # Step 3: Load - Simulate loading to our data store
        print("\nStep 3: Load - Simulating data loading to data store")

        # Simulate partitioned storage location
        with tempfile.TemporaryDirectory() as temp_dir:
            # Simulate partition path based on date
            partition_date = transformed_df["trade_date"][0]
            year = partition_date.year
            month = partition_date.month

            partition_path = os.path.join(temp_dir, f"{year:04d}", f"{month:02d}")
            os.makedirs(partition_path, exist_ok=True)

            # Save as parquet (our target format)
            output_file = os.path.join(partition_path, f"daily_bars_{partition_date.isoformat()}.parquet")
            transformed_df.write_parquet(output_file)

            # Verify that file was written
            assert os.path.exists(output_file), f"Output file should exist: {output_file}"

            # Read it back to verify data integrity
            loaded_df = pl.read_parquet(output_file)

            # Check that loaded data matches our transformed data
            assert loaded_df.shape == transformed_df.shape, "Loaded data should have same shape as transformed data"
            assert list(loaded_df.columns) == list(transformed_df.columns), "Column names should match"

            print(f"Data loaded to: {output_file}")
            print(f"Data integrity check passed: {loaded_df.shape[0]} rows loaded successfully")

        # Additional ETL simulation: simulate daily aggregation
        print("\nSimulating additional ETL processes...")

        # Aggregate data to create summary statistics
        summary_stats = transformed_df.select([
            pl.col("symbol").n_unique().alias("unique_symbols"),
            pl.col("trade_date").n_unique().alias("trading_days"),
            pl.col("volume").sum().alias("total_volume"),
            pl.col("turnover").sum().alias("total_turnover"),
            pl.col("close_price").mean().alias("avg_close_price")
        ])

        print(f"Summary statistics: {dict(zip(summary_stats.columns, [summary_stats[col][0] for col in summary_stats.columns]))}")

        print("SUCCESS: ETL pipeline simulation completed successfully for A-share market platform")
        return True

    except Exception as e:
        print(f"FAILURE: Error in ETL pipeline simulation: {e}")
        return False

if __name__ == "__main__":
    success = verify_etl_pipeline_simulation()
    if success:
        print("Verification completed successfully")
    else:
        print("Verification failed")
        exit(1)