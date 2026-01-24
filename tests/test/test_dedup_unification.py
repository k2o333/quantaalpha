"""测试主键去重统一化功能的测试用例"""
import pytest
import polars as pl
from app4.core.dedup import DataDeduplicator, DedupStats
import tempfile
import os


def test_basic_deduplication_functionality():
    """测试基本去重功能（在单个DataFrame内去重）"""
    df = pl.DataFrame({
        'ts_code': ['000001', '000002', '000001'],  # 重复的ts_code+trade_date
        'trade_date': ['20230101', '20230101', '20230101'],
        'close': [10.0, 11.0, 10.1]  # 不同的价格但相同日期，应只保留第一个
    })

    dedup = DataDeduplicator()
    result_df, stats = dedup.deduplicate(df, primary_keys=['ts_code', 'trade_date'])

    # 应该只剩2条记录（000001保留第一个，000002保留）
    assert len(result_df) == 2
    assert stats.removed_rows == 1  # 1个重复被移除
    # The actual behavior based on testing: the first occurrence (with close=10.0) is kept
    # Filter to find the row with ts_code='000001' and check its close value
    filtered = result_df.filter(pl.col('ts_code') == '000001')
    assert len(filtered) == 1
    assert filtered['close'][0] == 10.0  # first occurrence kept


def test_null_key_handling():
    """测试空主键值处理"""
    df = pl.DataFrame({
        'ts_code': ['000001', None, '000002'],
        'trade_date': ['20230101', '20230101', None],  # 一个有值一个为空
        'close': [10.0, 11.0, 12.0]
    })

    dedup = DataDeduplicator()
    result_df, stats = dedup.deduplicate(df, primary_keys=['ts_code', 'trade_date'])

    # Polars unique() does NOT remove rows with nulls - it treats them as distinct values
    # So all 3 rows should remain since all key combinations are different:
    # ('000001', '20230101'), (None, '20230101'), ('000002', None)
    assert len(result_df) == 3  # All rows kept because nulls are treated as distinct values
    # Verify all original combinations exist
    ts_codes = result_df['ts_code'].to_list()
    trade_dates = result_df['trade_date'].to_list()
    assert '000001' in ts_codes
    assert '000002' in ts_codes
    assert None in ts_codes
    assert '20230101' in trade_dates
    assert None in trade_dates


def test_disabled_deduplication():
    """测试去重策略的影响（虽然没有直接的禁用选项，但通过策略来测试）"""
    df = pl.DataFrame({
        'ts_code': ['000001', '000001', '000002'],
        'trade_date': ['20230101', '20230101', '20230101'],
        'close': [10.0, 10.1, 12.0]
    })

    # 使用不同策略测试差异
    dedup_first = DataDeduplicator({'keep_strategy': 'first'})
    result_first, stats_first = dedup_first.deduplicate(df, primary_keys=['ts_code', 'trade_date'])

    dedup_last = DataDeduplicator({'keep_strategy': 'last'})
    result_last, stats_last = dedup_last.deduplicate(df, primary_keys=['ts_code', 'trade_date'])

    # both should have same number of output rows but different values for the duplicated key
    assert len(result_first) == 2
    assert len(result_last) == 2

    # Find the record with ts_code='000001' in both results
    first_filtered = result_first.filter(pl.col('ts_code') == '000001')
    last_filtered = result_last.filter(pl.col('ts_code') == '000001')

    # first strategy keeps the first occurrence (close=10.0)
    assert first_filtered['close'][0] == 10.0
    # last strategy keeps the last occurrence (close=10.1)
    assert last_filtered['close'][0] == 10.1


def test_empty_data_conditions():
    """测试空数据情况"""
    df = pl.DataFrame(schema={'ts_code': pl.Utf8, 'trade_date': pl.Utf8, 'close': pl.Float64})

    dedup = DataDeduplicator()
    result_df, stats = dedup.deduplicate(df, primary_keys=['ts_code', 'trade_date'])

    # 空输入应该返回空结果
    assert result_df.is_empty()
    assert stats.input_rows == 0
    assert stats.output_rows == 0


def test_no_primary_keys():
    """测试无主键配置情况"""
    df = pl.DataFrame({
        'ts_code': ['000001', '000001', '000002'],
        'trade_date': ['20230101', '20230101', '20230101'],
        'close': [10.0, 11.0, 12.0]
    })

    dedup = DataDeduplicator()
    # Test with no primary keys specified - should use default
    result_df_default, stats_default = dedup.deduplicate(df)

    # Should use default primary keys ['ts_code', 'trade_date']
    assert len(result_df_default) == 2  # Expect deduplication to occur with defaults
    assert stats_default.removed_rows == 1


def test_missing_primary_key_fields():
    """测试主键字段缺失"""
    df = pl.DataFrame({
        'ts_code': ['000001', '000002', '000003'],
        'close': [10.0, 11.0, 12.0]
    })  # 缺少trade_date字段

    dedup = DataDeduplicator()
    # Attempt to use a primary key that doesn't exist
    result_df, stats = dedup.deduplicate(df, primary_keys=['ts_code', 'trade_date'])  # trade_date doesn't exist

    # When primary key doesn't exist, it should return original data with an error
    assert len(result_df) == 3  # Original data returned
    assert len(stats.errors) > 0  # Should have error about missing primary key