"""
测试app4存储模块的去重功能
"""
import pytest
import polars as pl
from unittest.mock import Mock, patch, MagicMock
import tempfile
import os
from app4.core.storage import StorageManager


def test_filter_new_records_no_dedup():
    """测试禁用去重时的行为"""
    storage_manager = StorageManager(tempfile.mkdtemp())
    test_data = [
        {"ts_code": "000001.SZ", "trade_date": "20230101", "value": 100},
        {"ts_code": "000002.SZ", "trade_date": "20230101", "value": 200}
    ]
    dedup_config = {"enabled": False}

    result = storage_manager.filter_new_records("test_interface", test_data, dedup_config)
    assert result == test_data


def test_filter_new_records_empty_existing_data():
    """测试现有数据为空时的行为"""
    storage_manager = StorageManager(tempfile.mkdtemp())
    test_data = [
        {"ts_code": "000001.SZ", "trade_date": "20230101", "value": 100},
        {"ts_code": "000002.SZ", "trade_date": "20230101", "value": 200}
    ]
    dedup_config = {
        "enabled": True,
        "strategy": "primary_key",
        "columns": ["ts_code", "trade_date"]
    }

    result = storage_manager.filter_new_records("test_interface", test_data, dedup_config)
    assert result == test_data


def test_filter_new_records_with_duplicates():
    """测试存在重复数据时的过滤行为"""
    # 这个测试需要更复杂的mock逻辑来模拟现有数据
    storage_manager = StorageManager(tempfile.mkdtemp())

    # 模拟已有的数据
    existing_data = pl.DataFrame([
        {"ts_code": "000001.SZ", "trade_date": "20230101", "value": 100}
    ])

    # 模拟新数据，其中包含重复项
    new_data = [
        {"ts_code": "000001.SZ", "trade_date": "20230101", "value": 100},  # 重复
        {"ts_code": "000002.SZ", "trade_date": "20230101", "value": 200}   # 新项
    ]

    dedup_config = {
        "enabled": True,
        "strategy": "primary_key",
        "columns": ["ts_code", "trade_date"]
    }

    # 使用mock来控制read_interface_data的行为
    with patch.object(storage_manager, 'read_interface_data', return_value=existing_data):
        result = storage_manager.filter_new_records("test_interface", new_data, dedup_config)
        assert len(result) == 1
        assert result[0]["ts_code"] == "000002.SZ"


def test_save_data_with_dedup_calls_filter():
    """测试save_data_with_dedup方法调用filter_new_records"""
    storage_manager = StorageManager(tempfile.mkdtemp())
    mock_filtered_data = [{"ts_code": "000002.SZ", "trade_date": "20230101", "value": 200}]

    # 创建mock来验证filter_new_records被调用
    with patch.object(storage_manager, 'filter_new_records', return_value=mock_filtered_data) as mock_filter:
        with patch.object(storage_manager, 'save_data') as mock_save:
            test_data = [{"ts_code": "000001.SZ", "trade_date": "20230101", "value": 100}]
            dedup_config = {
                "enabled": True,
                "strategy": "primary_key",
                "columns": ["ts_code", "trade_date"]
            }

            storage_manager.save_data_with_dedup("test_interface", test_data, dedup_config)

            # 验证filter_new_records被正确调用
            mock_filter.assert_called_once_with("test_interface", test_data, dedup_config)
            # 验证save_data被调用（如果过滤后有数据）
            mock_save.assert_called_once()


def test_save_data_with_dedup_no_new_data():
    """测试没有新数据时save_data不被调用"""
    storage_manager = StorageManager(tempfile.mkdtemp())

    with patch.object(storage_manager, 'filter_new_records', return_value=[]) as mock_filter:
        with patch.object(storage_manager, 'save_data') as mock_save:
            test_data = [{"ts_code": "000001.SZ", "trade_date": "20230101", "value": 100}]
            dedup_config = {
                "enabled": True,
                "strategy": "primary_key",
                "columns": ["ts_code", "trade_date"]
            }

            storage_manager.save_data_with_dedup("test_interface", test_data, dedup_config)

            # 验证filter_new_records被调用
            mock_filter.assert_called_once_with("test_interface", test_data, dedup_config)
            # 但save_data不被调用，因为没有新数据
            mock_save.assert_not_called()