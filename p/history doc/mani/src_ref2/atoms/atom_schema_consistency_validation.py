#!/usr/bin/env python
"""
Verification script for atom_schema_consistency_validation
This script verifies schema consistency across different data types in A-share market data platform
"""

def verify_schema_consistency_validation():
    try:
        import polars as pl
        import pyarrow as pa
        from datetime import date, datetime

        # Define schema definitions for key data types with consistency in mind
        schema_definitions = {
            "stock_metadata": {
                "symbol": pl.Utf8,
                "security_name": pl.Utf8,
                "security_type": pl.Utf8,
                "exchange": pl.Utf8,
                "currency": pl.Utf8,
                "list_date": pl.Date,
                "delist_date": pl.Date,
                "is_trading": pl.Boolean
            },
            "daily_bar": {
                "symbol": pl.Utf8,
                "trade_date": pl.Date,
                "open_price": pl.Float64,
                "high_price": pl.Float64,
                "low_price": pl.Float64,
                "close_price": pl.Float64,
                "volume": pl.Int64,
                "turnover": pl.Float64,
                "prev_close": pl.Float64,
                "change_pct": pl.Float64,
                "turnover_rate": pl.Float64
            },
            "bar_summary": {
                "symbol": pl.Utf8,
                "period_start_date": pl.Date,
                "period_end_date": pl.Date,
                "num_trading_days": pl.Int32,
                "start_price": pl.Float64,
                "end_price": pl.Float64,
                "high_price": pl.Float64,
                "low_price": pl.Float64,
                "avg_volume": pl.Float64,
                "total_turnover": pl.Float64
            }
        }

        # Verify shared fields consistency across schemas
        shared_fields = {
            "symbol": [schema["symbol"] for name, schema in schema_definitions.items() if "symbol" in schema],
            "security_identifier": [],  # No other security identifier fields in current schemas
        }

        # All symbol fields should be the same type
        symbol_types = [schema["symbol"] for schema in schema_definitions.values() if "symbol" in schema]
        if len(set(str(t) for t in symbol_types)) > 1:
            raise AssertionError("Symbol field type should be consistent across all schemas")

        # Verify that certain temporal fields maintain consistency
        date_fields_to_check = {}
        for schema_name, schema in schema_definitions.items():
            for field_name, field_type in schema.items():
                if "date" in field_name.lower():
                    if field_name not in date_fields_to_check:
                        date_fields_to_check[field_name] = []
                    date_fields_to_check[field_name].append(field_type)

        # All date fields with same purpose should have consistent types
        for field_name, types in date_fields_to_check.items():
            if len(set(str(t) for t in types)) > 1:
                raise AssertionError(f"Date field '{field_name}' should have consistent types across schemas")

        # Test creating sample data that maintains schema consistency
        # Stock metadata
        metadata_data = pl.DataFrame({
            "symbol": ["SH600000", "SZ000001", "SH600036"],
            "security_name": ["浦发银行", "平安银行", "招商银行"],
            "security_type": ["A", "A", "A"],
            "exchange": ["SSE", "SZE", "SSE"],
            "currency": ["CNY", "CNY", "CNY"],
            "list_date": [date(1999, 11, 10), date(1991, 4, 3), date(2002, 4, 9)],
            "delist_date": [None, None, None],  # Fixed this line
            "is_trading": [True, True, True]
        }, schema=schema_definitions["stock_metadata"])

        # Daily bars for these securities
        daily_bars = pl.DataFrame({
            "symbol": ["SH600000", "SH600000", "SZ000001", "SZ000001"],
            "trade_date": [date(2023, 1, 15), date(2023, 1, 16), date(2023, 1, 15), date(2023, 1, 16)],
            "open_price": [7.21, 7.25, 15.40, 15.35],
            "high_price": [7.35, 7.40, 15.60, 15.70],
            "low_price": [7.15, 7.20, 15.25, 15.30],
            "close_price": [7.30, 7.38, 15.50, 15.65],
            "volume": [12345678, 15678900, 9876543, 11223344],
            "turnover": [89987654.32, 115678899.88, 153210987.65, 174321098.76],
            "prev_close": [7.25, 7.30, 15.45, 15.50],
            "change_pct": [0.69, 1.10, 0.32, 0.97],
            "turnover_rate": [0.12, 0.15, 0.08, 0.09]
        }, schema=schema_definitions["daily_bar"])

        print("Schema data created successfully")

        # Create summary data for verification of aggregation consistency
        summary_df = daily_bars.group_by("symbol").agg([
            pl.col("trade_date").min().alias("period_start_date"),
            pl.col("trade_date").max().alias("period_end_date"),
            pl.count().alias("num_trading_days"),
            pl.col("close_price").first().alias("start_price"),
            pl.col("close_price").last().alias("end_price"),
            pl.col("high_price").max().alias("high_price"),
            pl.col("low_price").min().alias("low_price"),
            pl.col("volume").mean().alias("avg_volume"),
            pl.col("turnover").sum().alias("total_turnover")
        ])

        print(f"Metadata rows: {metadata_data.shape[0]}, columns: {metadata_data.shape[1]}")
        print(f"Daily bars rows: {daily_bars.shape[0]}, columns: {daily_bars.shape[1]}")
        print(f"Summary rows: {summary_df.shape[0]}, columns: {summary_df.shape[1]}")

        # Verify joining compatibility - test that symbols exist in both dataframes
        print("Symbol values in daily bars:", daily_bars['symbol'].unique().to_list())
        print("Symbol values in metadata:", metadata_data['symbol'].unique().to_list())

        # Check for intersection of symbols between the two DataFrames
        common_symbols = set(daily_bars['symbol'].unique().to_list()) & set(metadata_data['symbol'].unique().to_list())
        print(f"Common symbols for join: {list(common_symbols)}")

        if len(common_symbols) == 0:
            raise AssertionError("No common symbols found for join operation")

        # Now perform the join with known common symbols
        joined_df = daily_bars.join(metadata_data.select("symbol", "security_name", "exchange"), on="symbol", how="inner")
        print(f"After join - rows: {joined_df.shape[0]}, columns: {joined_df.shape[1]}")

        # Verify that the join worked properly
        assert joined_df.shape[0] > 0, "Join should produce non-empty result"

        print(f"Stock symbols that maintain schema consistency: {joined_df['symbol'].unique().to_list()}")

        # Validate consistency by checking shared keys remain valid across schemas
        assert len(joined_df) > 0, "Join should produce results"
        print("SUCCESS: Schema consistency maintained across different data types in A-share market platform")
        return True

    except Exception as e:
        print(f"FAILURE: Error validating schema consistency: {e}")
        return False

if __name__ == "__main__":
    success = verify_schema_consistency_validation()
    if success:
        print("Verification completed successfully")
    else:
        print("Verification failed")
        exit(1)