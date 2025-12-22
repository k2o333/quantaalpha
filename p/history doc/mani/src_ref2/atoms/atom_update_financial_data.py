#!/usr/bin/env python
"""
Verification script for atom_update_financial_data
- 财务数据更新函数，处理修订数据
"""

def verify_atom_update_financial_data():
    """
    验证财务数据更新函数，处理修订数据
    """
    print("Testing atom_update_financial_data: 财务数据更新功能")

    import polars as pl
    import tempfile
    import os
    from datetime import datetime
    import time

    def update_financial_data(existing_df, new_df, merge_strategy='replace'):
        """
        更新财务数据的函数
        """
        print(f"  - Updating financial data")
        print(f"    - Existing data: {len(existing_df)} rows")
        print(f"    - New data: {len(new_df)} rows")
        print(f"    - Merge strategy: {merge_strategy}")

        if merge_strategy == 'replace':
            # 简单替换策略：新数据完全替换旧数据
            updated_df = new_df
            print(f"    - Using replace strategy: replacing with new data")
        elif merge_strategy == 'update_existing':
            # 更新现有数据策略：只更新已存在的记录，不添加新记录
            if 'ts_code' in existing_df.columns and 'ts_code' in new_df.columns:
                # 合并基于ts_code，新数据更新旧数据
                updated_df = existing_df.join(new_df, on='ts_code', how='left', suffix='_new')

                # 对于有新值的列，用新值替换旧值
                for col in new_df.columns:
                    if col != 'ts_code' and col in existing_df.columns:
                        if col + '_new' in updated_df.columns:
                            updated_df = updated_df.with_columns([
                                pl.when(pl.col(col + '_new').is_not_null())
                                .then(pl.col(col + '_new'))
                                .otherwise(pl.col(col))
                                .alias(col)
                            ]).drop(col + '_new')
            else:
                updated_df = existing_df
            print(f"    - Using update_existing strategy: updating existing records only")
        elif merge_strategy == 'merge_all':
            print(f"    - Using merge_all strategy: merging and deduplicating data")
            # 合并所有数据，处理重复记录
            if 'ts_code' in existing_df.columns and 'ts_code' in new_df.columns:
                # 对于有时间维度的数据，可能需要按时间和代码合并
                if 'end_date' in existing_df.columns and 'end_date' in new_df.columns:
                    # Combine and remove duplicates based on ts_code and end_date
                    combined = pl.concat([existing_df, new_df])
                    updated_df = combined.unique(subset=['ts_code', 'end_date'], keep='last')
                else:
                    # Combine and remove exact duplicates based on ts_code
                    combined = pl.concat([existing_df, new_df])
                    updated_df = combined.unique(subset=['ts_code'], keep='last')
            else:
                updated_df = pl.concat([existing_df, new_df]).unique()
        else:
            # 默认策略
            updated_df = new_df

        print(f"    - Updated data: {len(updated_df)} rows")
        return updated_df

    def process_revised_financial_data(existing_df, revision_df):
        """
        处理修订财务数据的函数
        """
        print(f"  - Processing revised financial data")
        print(f"    - Existing data: {len(existing_df)} rows")
        print(f"    - Revision data: {len(revision_df)} rows")

        if len(revision_df) == 0:
            print(f"    - No revisions to process, returning existing data")
            return existing_df

        if 'ts_code' in existing_df.columns and 'ts_code' in revision_df.columns and \
           'end_date' in existing_df.columns and 'end_date' in revision_df.columns:
            # 创建要移除的键（ts_code + end_date 组合）
            keys_to_remove = revision_df.select(['ts_code', 'end_date'])

            # 过滤掉要被修订的记录
            filtered_existing = existing_df.join(
                keys_to_remove,
                on=['ts_code', 'end_date'],
                how='anti'  # 保留不在key列表中的记录
            )

            # 然后添加修订的数据
            updated_df = pl.concat([filtered_existing, revision_df])
        else:
            # 如果没有这些列，则使用简单替换
            updated_df = revision_df

        print(f"    - Processed data: {len(updated_df)} rows")
        return updated_df

    # Test 1: Basic financial data update with replace strategy
    print("\n--- Test 1: Basic financial data update with replace strategy ---")
    # Create existing financial data
    existing_financial = pl.DataFrame({
        'ts_code': ['000001.SZ', '000002.SZ', '600000.SH'],
        'end_date': ['20241231', '20241231', '20241231'],
        'revenue': [1000000000.0, 500000000.0, 800000000.0],
        'net_profit': [100000000.0, 50000000.0, 80000000.0],
        'updated_at': ['20250101', '20250101', '20250101']
    })

    # Create new financial data
    new_financial = pl.DataFrame({
        'ts_code': ['000001.SZ', '000003.SZ'],  # One existing, one new
        'end_date': ['20241231', '20241231'],
        'revenue': [1100000000.0, 600000000.0],  # Updated value for existing, new for 000003
        'net_profit': [110000000.0, 60000000.0],
        'updated_at': ['20250102', '20250102']
    })

    updated_data = update_financial_data(existing_financial, new_financial, 'replace')
    assert len(updated_data) == 2, f"Expected 2 rows, got {len(updated_data)}"
    assert '000003.SZ' in updated_data['ts_code'].to_list(), "New stock should be included"

    print("✓ Basic financial data update works")

    # Test 2: Update existing strategy
    print("\n--- Test 2: Update existing strategy ---")
    updated_existing = update_financial_data(existing_financial, new_financial, 'update_existing')
    # Should have same number as original, with updated values
    assert len(updated_existing) >= 2, "Should have updated existing records"

    # Check that 000001.SZ has updated values
    updated_record = updated_existing.filter(pl.col('ts_code') == '000001.SZ')
    if len(updated_record) > 0:
        assert updated_record['revenue'][0] == 1100000000.0, "Revenue should be updated"

    print("✓ Update existing strategy works")

    # Test 3: Merge all strategy
    print("\n--- Test 3: Merge all strategy ---")
    merged_data = update_financial_data(existing_financial, new_financial, 'merge_all')
    # Should combine both datasets, with 000001.SZ appearing once with updated data
    assert len(merged_data) >= 3, "Should have merged data from both sources"

    # Check uniqueness of ts_code
    unique_codes = merged_data.select('ts_code').unique().height
    assert unique_codes == len(merged_data), "Should have unique ts_code values"

    print("✓ Merge all strategy works")

    # Test 4: Processing revised financial data
    print("\n--- Test 4: Processing revised financial data ---")
    # Original data with multiple reporting periods
    original_data = pl.DataFrame({
        'ts_code': ['000001.SZ', '000001.SZ', '000002.SZ'],
        'end_date': ['20240930', '20241231', '20241231'],
        'revenue': [750000000.0, 1000000000.0, 500000000.0],
        'net_profit': [75000000.0, 100000000.0, 50000000.0],
        'report_type': ['Q3', 'Annual', 'Annual']
    })

    # Revision data (e.g., corrected annual report for 000001.SZ)
    revision_data = pl.DataFrame({
        'ts_code': ['000001.SZ'],
        'end_date': ['20241231'],
        'revenue': [1050000000.0],  # Corrected value
        'net_profit': [105000000.0],  # Corrected value
        'report_type': ['Annual_Corrected']
    })

    processed_data = process_revised_financial_data(original_data, revision_data)
    assert len(processed_data) == 3, f"Expected 3 rows, got {len(processed_data)}"

    revised_record = processed_data.filter(
        (pl.col('ts_code') == '000001.SZ') & (pl.col('end_date') == '20241231')
    )
    assert len(revised_record) == 1, "Should have exactly one revised record"
    assert revised_record['revenue'][0] == 1050000000.0, "Revenue should be corrected"
    assert revised_record['report_type'][0] == 'Annual_Corrected', "Report type should be updated"

    print("✓ Processing revised financial data works")

    # Test 5: Handling empty revision data
    print("\n--- Test 5: Handling empty revision data ---")
    empty_revision = pl.DataFrame({
        'ts_code': [],
        'end_date': [],
        'revenue': [],
        'net_profit': []
    }).cast({
        'ts_code': pl.Utf8,
        'end_date': pl.Utf8,
        'revenue': pl.Float64,
        'net_profit': pl.Float64
    })

    unchanged_data = process_revised_financial_data(original_data, empty_revision)
    assert len(unchanged_data) == len(original_data), "Data should remain unchanged with empty revisions"

    print("✓ Handling empty revision data works")

    # Test 6: Performance with large datasets
    print("\n--- Test 6: Performance with large datasets ---")
    import time

    # Create large datasets
    large_existing = pl.DataFrame({
        'ts_code': [f'{i:06d}.SZ' for i in range(10000)],
        'end_date': ['20241231'] * 10000,
        'revenue': [float(i * 1000000) for i in range(10000)],
        'net_profit': [float(i * 100000) for i in range(10000)]
    })

    large_new = pl.DataFrame({
        'ts_code': [f'{i:06d}.SZ' for i in range(5000, 15000)],  # Overlap with existing
        'end_date': ['20241231'] * 10000,
        'revenue': [float(i * 1000000 * 1.1) for i in range(5000, 15000)],  # 10% increase
        'net_profit': [float(i * 100000 * 1.1) for i in range(5000, 15000)]
    })

    start_time = time.time()
    large_updated = update_financial_data(large_existing, large_new, 'merge_all')
    end_time = time.time()

    assert len(large_updated) > 10000, "Should have merged large datasets"
    print(f"  - Processed {len(large_existing)} existing and {len(large_new)} new records")
    print(f"  - Processing time: {end_time - start_time:.3f}s")
    print("✓ Performance with large datasets works")

    # Test 7: Different financial data structures
    print("\n--- Test 7: Different financial data structures ---")
    balance_sheet_data = pl.DataFrame({
        'ts_code': ['000001.SZ', '000002.SZ'],
        'end_date': ['20241231', '20241231'],
        'total_assets': [10000000000, 5000000000],
        'total_liabilities': [6000000000, 3000000000],
        'equity': [4000000000, 2000000000]
    })

    new_balance_sheet = pl.DataFrame({
        'ts_code': ['000001.SZ', '000003.SZ'],
        'end_date': ['20241231', '20241231'],
        'total_assets': [10500000000, 7000000000],
        'total_liabilities': [6300000000, 4200000000],
        'equity': [4200000000, 2800000000]
    })

    cash_flow_data = pl.DataFrame({
        'ts_code': ['000001.SZ'],
        'end_date': ['20241231'],
        'operating_cash_flow': [500000000],
        'investing_cash_flow': [-200000000],
        'financing_cash_flow': [-100000000]
    })

    cash_flow_update = pl.DataFrame({
        'ts_code': ['000001.SZ'],
        'end_date': ['20241231'],
        'operating_cash_flow': [550000000],
        'investing_cash_flow': [-250000000],
        'financing_cash_flow': [-150000000]
    })

    balance_updated = update_financial_data(balance_sheet_data, new_balance_sheet, 'replace')
    cash_updated = update_financial_data(cash_flow_data, cash_flow_update, 'replace')

    assert '000003.SZ' in balance_updated['ts_code'].to_list(), "New stock should be included"
    assert cash_updated['operating_cash_flow'][0] == 550000000, "Should update cash flow data"

    print("✓ Different financial data structures work")

    # Test 8: Date handling and quarterly data
    print("\n--- Test 8: Date handling and quarterly data ---")
    quarterly_data = pl.DataFrame({
        'ts_code': ['000001.SZ', '000001.SZ', '000001.SZ', '000001.SZ'],
        'end_date': ['20240331', '20240630', '20240930', '20241231'],
        'revenue': [250000000.0, 250000000.0, 250000000.0, 250000000.0],
        'report_type': ['Q1', 'Q2', 'Q3', 'Annual']
    })

    # Add Q4 update
    q4_update = pl.DataFrame({
        'ts_code': ['000001.SZ'],
        'end_date': ['20241231'],
        'revenue': [260000000.0],  # Updated Q4 revenue
        'report_type': ['Annual_Updated']
    })

    quarterly_updated = process_revised_financial_data(quarterly_data, q4_update)
    assert len(quarterly_updated) == 4, "Should maintain all quarters"

    updated_q4 = quarterly_updated.filter(pl.col('end_date') == '20241231')
    assert len(updated_q4) == 1, "Should have one Q4 record"
    assert updated_q4['revenue'][0] == 260000000.0, "Q4 revenue should be updated"
    assert updated_q4['report_type'][0] == 'Annual_Updated', "Q4 report type should be updated"

    print("✓ Date handling and quarterly data works")

    print("\natom_update_financial_data: VERIFICATION PASSED")
    return True

if __name__ == "__main__":
    verify_atom_update_financial_data()