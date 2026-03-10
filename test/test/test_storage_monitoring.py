import pytest
import os
import tempfile
from unittest.mock import Mock, patch
import polars as pl
from datetime import datetime

from app4.core.storage import StorageManager, StorageMonitor


def test_duplicate_save_monitoring():
    """测试重复保存监控和其他性能指标"""

    # 创建临时目录用于测试
    with tempfile.TemporaryDirectory() as temp_dir:
        # 创建存储管理器实例
        storage_manager = StorageManager(storage_dir=temp_dir, format="parquet")
        storage_manager.start_writer()  # 启动写入线程

        # 创建测试数据
        test_data = pl.DataFrame({
            "ts_code": ["000001.SZ", "000002.SZ"],
            "trade_date": ["20230101", "20230102"],
            "close": [10.0, 11.0]
        })

        interface_name = "test_interface"
        date_range = ("20230101", "20230102")

        # 第一次保存
        storage_manager.save_data(interface_name, test_data)

        # 等待写入操作完成
        import time
        time.sleep(0.5)

        # 验证第一次保存后监控指标
        assert storage_manager.monitor.successful_saves == 1
        assert storage_manager.monitor.failed_saves == 0
        assert storage_manager.monitor.total_records_saved == len(test_data)
        assert storage_manager.monitor.duplicate_saves == 0

        # 尝试保存相同的数据（这应该被识别为重复）
        storage_manager.save_data(interface_name, test_data)

        # 等待写入操作完成
        time.sleep(0.5)

        # 验证重复保存被正确计数
        assert storage_manager.monitor.successful_saves == 2  # 两次保存都成功
        assert storage_manager.monitor.failed_saves == 0
        assert storage_manager.monitor.total_records_saved == len(test_data) * 2  # 两倍记录数
        assert storage_manager.monitor.duplicate_saves == 1  # 一个重复保存

        # 测试监控摘要
        summary = storage_manager.monitor.get_summary()
        assert "Storage Operation Summary" in summary
        assert "Successful Saves: 2" in summary
        assert "Failed Saves: 0" in summary
        assert "Duplicate Saves: 1" in summary
        assert "Total Records Saved: 4" in summary
        assert "Average Records per Save" in summary

        # 验证监控器重置功能
        storage_manager.monitor.reset()
        reset_summary = storage_manager.monitor.get_summary()
        assert "Successful Saves: 0" in reset_summary
        assert "Failed Saves: 0" in reset_summary
        assert "Duplicate Saves: 0" in reset_summary
        assert "Total Records Saved: 0" in reset_summary

        # 停止写入器
        storage_manager.stop_writer()


def test_storage_monitor_initialization():
    """测试存储监控器初始化"""
    monitor = StorageMonitor()

    # 验证初始值
    assert monitor.successful_saves == 0
    assert monitor.failed_saves == 0
    assert monitor.duplicate_saves == 0
    assert monitor.total_records_saved == 0
    assert monitor.save_times == []
    assert monitor.errors == []


def test_storage_monitor_error_tracking():
    """测试存储监控器错误跟踪"""
    monitor = StorageMonitor()

    # 模拟错误记录
    error_msg = "Test error occurred"
    monitor.record_error(error_msg)

    assert monitor.failed_saves == 1
    assert len(monitor.errors) == 1
    assert monitor.errors[0]['message'] == error_msg


def test_storage_monitor_duplicate_tracking():
    """测试存储监控器重复保存跟踪"""
    monitor = StorageMonitor()

    # 记录重复保存
    monitor.record_duplicate_save()

    assert monitor.duplicate_saves == 1


def test_storage_monitor_performance_metrics():
    """测试存储监控器性能指标"""
    monitor = StorageMonitor()

    # 记录成功的保存操作
    monitor.record_successful_save(100)  # 保存100条记录
    monitor.record_successful_save(200)  # 保存200条记录

    assert monitor.successful_saves == 2
    assert monitor.total_records_saved == 300

    # 验证摘要中的性能指标
    summary = monitor.get_summary()
    assert "Average Records per Save: 150.0" in summary