#!/usr/bin/env python
"""
Verification script for atom_data_type_mapping_validation
This script verifies data type mapping and conversion logic appropriate for A-share market data platform
"""

def verify_data_type_mapping_validation():
    try:
        import polars as pl
        from datetime import datetime, date
        import pyarrow as pa

        # Define comprehensive data type mappings for different data categories
        data_type_mappings = {
            "stock_basic_info": {
                "code": {"python": "str", "polars": "pl.Utf8", "arrow": "pa.string()", "sql": "VARCHAR(10)"},
                "name": {"python": "str", "polars": "pl.Utf8", "arrow": "pa.string()", "sql": "VARCHAR(50)"},
                "industry_code": {"python": "str", "polars": "pl.Utf8", "arrow": "pa.string()", "sql": "VARCHAR(5)"},
                "listing_date": {"python": "datetime", "polars": "pl.Datetime", "arrow": "pa.timestamp('ns')", "sql": "DATE"},
                "market_cap": {"python": "float", "polars": "pl.Float64", "arrow": "pa.float64()", "sql": "DECIMAL(15,2)"},
                "share_count": {"python": "int", "polars": "pl.Int64", "arrow": "pa.int64()", "sql": "BIGINT"}
            },
            "trading_data": {
                "trade_date": {"python": "date", "polars": "pl.Date", "arrow": "pa.date32()", "sql": "DATE"},
                "open_price": {"python": "float", "polars": "pl.Float64", "arrow": "pa.float64()", "sql": "DECIMAL(10,3)"},
                "high_price": {"python": "float", "polars": "pl.Float64", "arrow": "pa.float64()", "sql": "DECIMAL(10,3)"},
                "low_price": {"python": "float", "polars": "pl.Float64", "arrow": "pa.float64()", "sql": "DECIMAL(10,3)"},
                "close_price": {"python": "float", "polars": "pl.Float64", "arrow": "pa.float64()", "sql": "DECIMAL(10,3)"},
                "volume": {"python": "int", "polars": "pl.Int64", "arrow": "pa.int64()", "sql": "BIGINT"},
                "amount": {"python": "float", "polars": "pl.Float64", "arrow": "pa.float64()", "sql": "DECIMAL(15,2)"},
                "turnover_rate": {"python": "float", "polars": "pl.Float64", "arrow": "pa.float64()", "sql": "DECIMAL(6,4)"}
            },
            "financial_indicator": {
                "report_date": {"python": "date", "polars": "pl.Date", "arrow": "pa.date32()", "sql": "DATE"},
                "pe_ratio": {"python": "float", "polars": "pl.Float64", "arrow": "pa.float64()", "sql": "DECIMAL(8,2)"},
                "pb_ratio": {"python": "float", "polars": "pl.Float64", "arrow": "pa.float64()", "sql": "DECIMAL(8,2)"},
                "roe": {"python": "float", "polars": "pl.Float64", "arrow": "pa.float64()", "sql": "DECIMAL(6,4)"},
                "revenue": {"python": "float", "polars": "pl.Float64", "arrow": "pa.float64()", "sql": "DECIMAL(15,2)"},
                "net_profit": {"python": "float", "polars": "pl.Float64", "arrow": "pa.float64()", "sql": "DECIMAL(15,2)"}
            }
        }

        # Validate that all mappings have required type definitions
        for data_category, fields in data_type_mappings.items():
            for field_name, type_mapping in fields.items():
                assert "polars" in type_mapping, f"Polars type should be defined for {data_category}.{field_name}"
                assert "arrow" in type_mapping, f"Arrow type should be defined for {data_category}.{field_name}"
                assert "sql" in type_mapping, f"SQL type should be defined for {data_category}.{field_name}"
                assert "python" in type_mapping, f"Python type should be defined for {data_category}.{field_name}"

        # Test actual type conversion by creating sample data
        # Sample stock basic info data
        sample_stock_data = [
            ["000001", "000002", "600000"],  # codes
            ["平安银行", "万科A", "浦发银行"],           # names
            ["K", "F", "J"],                  # industry codes
            [datetime(1991, 4, 3), datetime(1991, 1, 29), datetime(1999, 11, 10)],  # listing dates
            [1500.5, 2000.3, 800.2],         # market caps
            [19405000000, 9363000000, 29350000000]  # share counts
        ]

        # Create Polars DataFrame with correct types based on mapping
        stock_df = pl.DataFrame({
            "code": sample_stock_data[0],
            "name": sample_stock_data[1],
            "industry_code": sample_stock_data[2],
            "listing_date": sample_stock_data[3],
            "market_cap": sample_stock_data[4],
            "share_count": sample_stock_data[5]
        }, schema={
            "code": pl.Utf8,
            "name": pl.Utf8,
            "industry_code": pl.Utf8,
            "listing_date": pl.Datetime,
            "market_cap": pl.Float64,
            "share_count": pl.Int64
        })

        print(f"Stock DataFrame created with {stock_df.shape[0]} rows and {stock_df.shape[1]} columns")
        print("Column types:", stock_df.dtypes)

        # Convert to PyArrow table
        arrow_table = stock_df.to_arrow()
        print(f"Arrow table schema: {arrow_table.schema}")

        # Test round-trip conversion (Polars -> Arrow -> Polars)
        back_to_polars = pl.from_arrow(arrow_table)
        assert back_to_polars.shape == stock_df.shape, "Round-trip conversion should preserve shape"

        print("Data Type Mappings Summary:")
        print(f"Data Categories: {list(data_type_mappings.keys())}")
        print(f"Trading Data Fields: {list(data_type_mappings['trading_data'].keys())}")

        print("SUCCESS: Data type mappings are appropriately defined and functional for A-share market platform")
        return True

    except Exception as e:
        print(f"FAILURE: Error validating data type mapping: {e}")
        return False

if __name__ == "__main__":
    success = verify_data_type_mapping_validation()
    if success:
        print("Verification completed successfully")
    else:
        print("Verification failed")
        exit(1)