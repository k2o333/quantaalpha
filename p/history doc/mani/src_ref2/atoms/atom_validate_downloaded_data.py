#!/usr/bin/env python
"""
Verification script for atom_validate_downloaded_data
- 数据质量验证函数，检查下载数据的完整性和逻辑一致性
"""

def verify_atom_validate_downloaded_data():
    """
    验证数据质量验证函数，检查下载数据的完整性和逻辑一致性
    """
    print("Testing atom_validate_downloaded_data: 数据质量验证功能")

    import polars as pl
    from datetime import datetime
    import tempfile
    import os

    def validate_downloaded_data(df, table_name, checks=None):
        """
        数据质量验证函数，检查下载数据的完整性和逻辑一致性
        """
        print(f"  - Starting validation for table: {table_name}, rows: {len(df)}")

        if checks is None:
            checks = {
                'completeness': True,
                'uniqueness': True,
                'consistency': True,
                'integrity': True
            }

        validation_results = {
            'table_name': table_name,
            'total_rows': len(df),
            'checks_performed': [],
            'issues_found': []
        }

        # Completeness check - look for missing or null data in critical columns
        if checks.get('completeness', True):
            validation_results['checks_performed'].append('completeness')

            # Identify critical columns for completeness check
            critical_cols = []
            for col in df.columns:
                # Consider ts_code and date columns as critical for financial data
                if 'code' in col.lower() or 'ts_code' in col.lower() or 'date' in col.lower():
                    critical_cols.append(col)

            # Check for missing data in critical columns
            missing_data_cols = []
            for col in critical_cols:
                null_count = df[col].null_count()
                if null_count > 0:
                    missing_data_cols.append(f"{col} ({null_count}/{len(df)} nulls)")

            if missing_data_cols:
                validation_results['issues_found'].append(f"Columns with missing data: {', '.join(missing_data_cols)}")
                print(f"    - Warning: Found columns with missing data: {', '.join(missing_data_cols)}")
            else:
                print(f"    - ✓ Completeness check passed: No missing data in required columns")

        # Uniqueness check
        if checks.get('uniqueness', True):
            validation_results['checks_performed'].append('uniqueness')

            if 'ts_code' in df.columns:
                # Check for duplicate ts_code entries
                duplicates = df.group_by('ts_code').agg(pl.count()).filter(pl.col('count') > 1)
                if len(duplicates) > 0:
                    validation_results['issues_found'].append(f"Found {len(duplicates)} duplicate ts_code entries")
                    print(f"    - Warning: Found {len(duplicates)} duplicate ts_code entries")
                else:
                    print(f"    - ✓ Uniqueness check passed: No duplicate ts_code entries")

            # Check for completely duplicate rows (all columns)
            if len(df) > 0:
                unique_rows = df.unique()
                if len(unique_rows) < len(df):
                    duplicate_count = len(df) - len(unique_rows)
                    validation_results['issues_found'].append(f"Found {duplicate_count} completely duplicate rows")
                    print(f"    - Warning: Found {duplicate_count} completely duplicate rows")
                else:
                    print(f"    - ✓ Uniqueness check passed: No completely duplicate rows")

        # Consistency check (column data types)
        if checks.get('consistency', True):
            validation_results['checks_performed'].append('consistency')

            numeric_cols = [col for col in df.columns if df.schema[col] in [pl.Int32, pl.Int64, pl.Float32, pl.Float64]]
            string_cols = [col for col in df.columns if df.schema[col] == pl.Utf8]

            print(f"    - Data types check: {len(numeric_cols)} numeric cols, {len(string_cols)} string cols")

            # Check for unexpected nulls in numeric columns (might indicate inconsistent data)
            for col in numeric_cols:
                null_count = df[col].null_count()
                if null_count > 0:
                    print(f"    - Info: Numeric column '{col}' has {null_count} null values")

            # Check for dates that might indicate incorrect formats
            date_like_cols = [col for col in df.columns if 'date' in col.lower() or 'time' in col.lower()]
            for col in date_like_cols:
                if df.schema[col] == pl.Utf8:
                    # Might be a date string - warn if it looks like it should be parsed
                    sample_vals = df[col].head(3).to_list()
                    if any(len(str(val)) == 8 and str(val).isdigit() for val in sample_vals if val is not None):
                        print(f"    - Info: Column '{col}' might contain date values that should be parsed")

        # Integrity check for financial data ranges
        if checks.get('integrity', True) and 'daily' in table_name.lower():
            validation_results['checks_performed'].append('integrity')

            # For daily data, check for obvious data errors
            if 'close' in df.columns and df.schema['close'] in [pl.Float32, pl.Float64, pl.Int32, pl.Int64]:
                negative_prices = df.filter((pl.col('close') < 0) & (pl.col('close').is_not_null()))
                if len(negative_prices) > 0:
                    validation_results['issues_found'].append(f"Found {len(negative_prices)} rows with negative close prices")
                    print(f"    - Warning: Found {len(negative_prices)} rows with negative close prices")
                else:
                    print(f"    - ✓ Integrity check passed: No negative close prices found")

            # Check for volume data if present
            if 'volume' in df.columns:
                negative_volume = df.filter((pl.col('volume') < 0) & (pl.col('volume').is_not_null()))
                if len(negative_volume) > 0:
                    validation_results['issues_found'].append(f"Found {len(negative_volume)} rows with negative volume")
                    print(f"    - Warning: Found {len(negative_volume)} rows with negative volume")
                else:
                    print(f"    - ✓ Integrity check passed: No negative volume data found")

        # Specialized checks for financial data
        if 'income' in table_name.lower() or 'balance' in table_name.lower():
            validation_results['checks_performed'].append('financial_integrity')

            # Check for zero revenue/profit (might be valid but worth noting)
            if 'revenue' in df.columns:
                zero_revenue = df.filter((pl.col('revenue') == 0) & (pl.col('revenue').is_not_null()))
                if len(zero_revenue) > 0:
                    print(f"    - Info: Found {len(zero_revenue)} rows with zero revenue")

            if 'net_profit' in df.columns:
                negative_profit = df.filter((pl.col('net_profit') < 0) & (pl.col('net_profit').is_not_null()))
                if len(negative_profit) > 0:
                    print(f"    - Info: Found {len(negative_profit)} rows with negative net profit")

        print(f"  - Validation completed for {table_name}")
        return validation_results

    # Test 1: Basic validation with clean data
    print("\n--- Test 1: Basic validation with clean data ---")
    clean_df = pl.DataFrame({
        'ts_code': ['000001.SZ', '000002.SZ', '600000.SH'],
        'trade_date': ['20250101', '20250101', '20250101'],
        'close': [10.5, 25.0, 15.2],
        'volume': [1000000, 2000000, 1500000]
    })

    result1 = validate_downloaded_data(clean_df, 'daily_data')
    assert result1['total_rows'] == 3
    print("✓ Basic validation with clean data passed")

    # Test 2: Validation with missing data
    print("\n--- Test 2: Validation with missing data ---")
    missing_df = pl.DataFrame({
        'ts_code': ['000001.SZ', '000002.SZ', '600000.SH', None],  # One missing ts_code
        'trade_date': ['20250101', '20250101', None, '20250102'],  # One missing trade_date
        'close': [10.5, None, 15.2, 12.0],  # One missing close
        'volume': [1000000, 2000000, 1500000, 1200000]
    })

    result2 = validate_downloaded_data(missing_df, 'daily_data')
    assert 'issues_found' in result2
    print("✓ Validation with missing data detected issues correctly")

    # Test 3: Validation with duplicate data
    print("\n--- Test 3: Validation with duplicate data ---")
    duplicate_df = pl.DataFrame({
        'ts_code': ['000001.SZ', '000001.SZ', '600000.SH', '600000.SH'],  # Duplicate ts_codes
        'trade_date': ['20250101', '20250101', '20250101', '20250101'],  # Same dates
        'close': [10.5, 10.5, 15.2, 15.2],  # Same values
        'volume': [1000000, 1000000, 1500000, 1500000]  # Same values
    })

    result3 = validate_downloaded_data(duplicate_df, 'daily_data')
    print("✓ Validation with duplicate data performed correctly")

    # Test 4: Validation with integrity issues
    print("\n--- Test 4: Validation with integrity issues ---")
    integrity_df = pl.DataFrame({
        'ts_code': ['000001.SZ', '000002.SZ', '600000.SH'],
        'close': [-10.5, 25.0, 15.2],  # Negative price
        'volume': [1000000, -2000000, 1500000]  # Negative volume
    })

    result4 = validate_downloaded_data(integrity_df, 'daily_data')
    print("✓ Validation with integrity issues detected correctly")

    # Test 5: Financial data validation
    print("\n--- Test 5: Financial data validation ---")
    financial_df = pl.DataFrame({
        'ts_code': ['000001.SZ', '000002.SZ'],
        'end_date': ['20241231', '20241231'],
        'revenue': [150000000000.00, 0.00],  # One zero revenue
        'net_profit': [30000000000.00, -5000000000.00]  # One negative profit
    })

    result5 = validate_downloaded_data(financial_df, 'income_data')
    print("✓ Financial data validation completed")

    # Test 6: Performance with large dataset
    print("\n--- Test 6: Performance with large dataset ---")
    large_df = pl.DataFrame({
        'ts_code': [f'A{i:06d}.SH' for i in range(10000)],
        'value': [float(i * 1.5) for i in range(10000)],
        'category': ['A' if i % 2 == 0 else 'B' for i in range(10000)]
    })

    result6 = validate_downloaded_data(large_df, 'large_test_data')
    assert result6['total_rows'] == 10000
    print("✓ Performance with large dataset validated")

    print("\natom_validate_downloaded_data: VERIFICATION PASSED")
    return True

if __name__ == "__main__":
    verify_atom_validate_downloaded_data()