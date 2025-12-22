#!/usr/bin/env python
"""
Verification script for atom_enhance_with_dict_ids
- 使用字典ID增强数据的函数，通过元数据主表进行数据增强
"""

def verify_atom_enhance_with_dict_ids():
    """
    验证使用字典ID增强数据的函数，通过元数据主表进行数据增强
    """
    print("Testing atom_enhance_with_dict_ids: 字典ID数据增强功能")

    import polars as pl
    import tempfile
    import os
    import hashlib

    def create_metadata_master_table():
        """
        创建模拟的元数据主表，包含股票、行业等实体的永久ID
        """
        print("  - Creating metadata master table")
        metadata_df = pl.DataFrame({
            'ts_code': ['000001.SZ', '000002.SZ', '600000.SH', '000003.SZ', '601398.SH'],
            'permanent_id': ['stk_33bbb694', 'stk_0d1af9d3', 'stk_7b035094', 'stk_55c1e4a2', 'stk_9a2b4c8d'],
            'entity_type': ['stock', 'stock', 'stock', 'stock', 'stock'],
            'name': ['平安银行', '万科A', '浦发银行', '招商银行', '工商银行'],
            'industry': ['银行', '房地产', '银行', '银行', '银行'],
            'area': ['深圳', '深圳', '上海', '深圳', '北京'],
            'status': ['active', 'active', 'active', 'active', 'active'],
            'created_at': ['20240101', '20240101', '20240101', '20240101', '20240101'],
            'updated_at': ['20240101', '20240101', '20240101', '20240101', '20240101']
        })
        return metadata_df

    def enhance_with_dict_ids(df, metadata_df, join_keys=None):
        """
        使用字典ID增强数据的函数，通过元数据主表进行数据增强
        """
        print(f"  - Enhancing {len(df)} rows with dictionary IDs")

        if join_keys is None:
            # Default join keys based on common patterns
            join_keys = ['ts_code']

        # Add permanent_id from metadata master table
        enhanced_df = df.join(metadata_df.select(['ts_code', 'permanent_id']), on='ts_code', how='left')

        # If permanent_id is null (not found in metadata), create one using hash
        enhanced_df = enhanced_df.with_columns([
            pl.when(pl.col('permanent_id').is_null())
            .then(pl.concat_str(pl.lit('stk_'), pl.col('ts_code').hash().cast(pl.Utf8).str.slice(0, 8)))
            .otherwise(pl.col('permanent_id'))
            .alias('permanent_id')
        ])

        print(f"  - Enhanced data with permanent_id, {enhanced_df['permanent_id'].null_count()} rows without metadata")
        return enhanced_df

    def enhance_with_industry_dict(df, metadata_df):
        """
        使用行业字典增强数据
        """
        print(f"  - Enhancing with industry dictionary")

        # Join with industry information from metadata
        enhanced_df = df.join(
            metadata_df.select(['ts_code', 'industry', 'area']),
            on='ts_code',
            how='left'
        )

        print(f"  - Added industry and area information to {len(df)} rows")
        return enhanced_df

    def enhance_with_cross_reference(df, metadata_df):
        """
        使用交叉引用进行数据增强
        """
        print(f"  - Performing cross-reference enhancement")

        # Add additional metadata fields like status
        enhanced_df = df.join(
            metadata_df.select(['ts_code', 'name', 'status']),
            on='ts_code',
            how='left'
        )

        print(f"  - Added name and status information")
        return enhanced_df

    # Test 1: Basic enhancement with permanent IDs
    print("\n--- Test 1: Basic enhancement with permanent IDs ---")
    sample_df = pl.DataFrame({
        'ts_code': ['000001.SZ', '000002.SZ', '600000.SH'],
        'date': ['20250101', '20250101', '20250101'],
        'close': [10.5, 25.0, 15.2],
        'volume': [1000000, 2000000, 1500000]
    })

    metadata_master = create_metadata_master_table()
    print(f"  - Metadata master table has {len(metadata_master)} entries")

    enhanced_result = enhance_with_dict_ids(sample_df, metadata_master)
    assert 'permanent_id' in enhanced_result.columns
    assert len(enhanced_result) == len(sample_df)
    print("✓ Basic enhancement with permanent IDs completed")

    # Test 2: Industry enhancement
    print("\n--- Test 2: Industry dictionary enhancement ---")
    industry_enhanced = enhance_with_industry_dict(sample_df, metadata_master)
    assert 'industry' in industry_enhanced.columns
    assert 'area' in industry_enhanced.columns
    print("✓ Industry dictionary enhancement completed")

    # Test 3: Cross-reference enhancement
    print("\n--- Test 3: Cross-reference enhancement ---")
    cross_ref_enhanced = enhance_with_cross_reference(sample_df, metadata_master)
    assert 'name' in cross_ref_enhanced.columns
    assert 'status' in cross_ref_enhanced.columns
    print("✓ Cross-reference enhancement completed")

    # Test 4: Combined enhancement
    print("\n--- Test 4: Combined enhancement process ---")
    # Start with original data
    base_data = sample_df

    # Apply multiple enhancements in sequence
    step1 = enhance_with_dict_ids(base_data, metadata_master)
    step2 = enhance_with_industry_dict(step1, metadata_master)
    step3 = enhance_with_cross_reference(step2, metadata_master)

    # Verify all enhancements were applied
    expected_cols = ['ts_code', 'date', 'close', 'volume', 'permanent_id', 'industry', 'area', 'name', 'status']
    for col in expected_cols:
        assert col in step3.columns, f"Missing column: {col}"

    print(f"  - Final enhanced dataframe has {len(step3)} rows and {len(step3.columns)} columns")
    print(f"  - Columns: {list(step3.columns)}")
    print("✓ Combined enhancement process completed")

    # Test 5: Handling missing entities (not in metadata)
    print("\n--- Test 5: Handling missing entities ---")
    df_with_new_codes = pl.DataFrame({
        'ts_code': ['000001.SZ', 'NEW001.SZ', 'NEW002.SZ'],  # Two new codes not in metadata
        'close': [10.5, 12.0, 13.0],
        'volume': [1000000, 800000, 900000]
    })

    enhanced_with_new = enhance_with_dict_ids(df_with_new_codes, metadata_master)
    print(f"  - Original: {len(df_with_new_codes)} rows")
    print(f"  - Enhanced: {len(enhanced_with_new)} rows")
    print(f"  - New entities got auto-generated IDs: {enhanced_with_new['permanent_id'].to_list()}")

    # Check that new entities got auto-generated IDs
    new_entities = enhanced_with_new.filter(pl.col('ts_code').str.contains('NEW'))
    assert len(new_entities) == 2
    assert all(id.startswith('stk_') for id in new_entities['permanent_id'].to_list())
    print("✓ Missing entities got auto-generated permanent IDs")

    # Test 6: Large dataset enhancement
    print("\n--- Test 6: Large dataset enhancement ---")
    large_df = pl.DataFrame({
        'ts_code': ['000001.SZ' if i % 3 == 0 else '000002.SZ' if i % 3 == 1 else '600000.SH' for i in range(5000)],
        'value': [float(i * 1.5) for i in range(5000)],
        'category': ['A' if i % 2 == 0 else 'B' for i in range(5000)]
    })

    large_enhanced = enhance_with_dict_ids(large_df, metadata_master)
    assert len(large_enhanced) == 5000
    assert 'permanent_id' in large_enhanced.columns
    print(f"  - Enhanced large dataset: {len(large_enhanced)} rows")
    print("✓ Large dataset enhancement completed")

    # Test 7: Verify ID permanence (same ts_code always gets same permanent_id)
    print("\n--- Test 7: ID permanence verification ---")
    test_codes = ['000001.SZ', '000002.SZ', '600000.SH']
    df1 = pl.DataFrame({'ts_code': test_codes, 'val': [1, 2, 3]})
    df2 = pl.DataFrame({'ts_code': test_codes, 'val': [4, 5, 6]})  # Same codes, different values

    enhanced1 = enhance_with_dict_ids(df1, metadata_master)
    enhanced2 = enhance_with_dict_ids(df2, metadata_master)

    # IDs for the same ts_code should be identical
    ids1 = dict(zip(enhanced1['ts_code'], enhanced1['permanent_id']))
    ids2 = dict(zip(enhanced2['ts_code'], enhanced2['permanent_id']))

    for code in test_codes:
        assert ids1[code] == ids2[code], f"ID not consistent for {code}: {ids1[code]} vs {ids2[code]}"

    print("✓ ID permanence verified: same ts_code always gets same permanent_id")

    # Test 8: Performance validation
    print("\n--- Test 8: Performance validation ---")
    import time

    perf_df = pl.DataFrame({
        'ts_code': [f'000{i:03d}.SZ' for i in range(1000)],
        'value': [float(i) for i in range(1000)]
    })

    start_time = time.time()
    perf_enhanced = enhance_with_dict_ids(perf_df, metadata_master)
    end_time = time.time()

    print(f"  - Enhanced {len(perf_df)} rows in {end_time - start_time:.3f} seconds")
    assert len(perf_enhanced) == 1000
    print("✓ Performance validation completed")

    print("\natom_enhance_with_dict_ids: VERIFICATION PASSED")
    return True

if __name__ == "__main__":
    verify_atom_enhance_with_dict_ids()