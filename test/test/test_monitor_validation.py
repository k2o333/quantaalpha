#!/usr/bin/env python
"""
验证存储监控器功能是否正常工作
"""

import tempfile
import polars as pl
from app4.core.storage import StorageManager, StorageMonitor


def test_storage_monitor_integration():
    """测试存储监控器集成"""
    print("Testing storage monitor integration...")

    with tempfile.TemporaryDirectory() as temp_dir:
        # 创建存储管理器实例
        storage_manager = StorageManager(storage_dir=temp_dir, format="parquet")
        storage_manager.start_writer()

        # 创建测试数据
        test_data = pl.DataFrame({
            "ts_code": ["000001.SZ", "000002.SZ"],
            "trade_date": ["20230101", "20230102"],
            "close": [10.0, 11.0]
        })

        interface_name = "test_interface"

        # 第一次保存
        print("Performing first save...")
        storage_manager.save_data(interface_name, test_data)

        # 等待写入完成
        import time
        time.sleep(0.5)

        print(f"Successful saves after first save: {storage_manager.monitor.successful_saves}")
        print(f"Total records saved: {storage_manager.monitor.total_records_saved}")

        # 第二次保存（会创建新文件，但不会被识别为重复，因为文件名包含时间戳）
        print("Performing second save...")
        storage_manager.save_data(interface_name, test_data)

        # 等待写入完成
        time.sleep(0.5)

        print(f"Successful saves after second save: {storage_manager.monitor.successful_saves}")
        print(f"Total records saved: {storage_manager.monitor.total_records_saved}")
        print(f"Duplicate saves: {storage_manager.monitor.duplicate_saves}")

        # 检查监控摘要
        summary = storage_manager.monitor.get_summary()
        print("\nStorage Operation Summary:")
        print(summary)

        # 停止写入器
        storage_manager.stop_writer()
        print("\nStorage monitor integration test completed successfully!")


def test_storage_monitor_features():
    """测试存储监控器功能"""
    print("\nTesting storage monitor features...")

    monitor = StorageMonitor()

    # 测试记录成功保存
    monitor.record_successful_save(100)
    monitor.record_successful_save(50)

    # 测试记录错误
    monitor.record_error("Test error")

    # 测试记录重复保存
    monitor.record_duplicate_save()

    # 检查指标
    print(f"Successful saves: {monitor.successful_saves}")
    print(f"Failed saves: {monitor.failed_saves}")
    print(f"Duplicate saves: {monitor.duplicate_saves}")
    print(f"Total records saved: {monitor.total_records_saved}")

    # 检查摘要
    summary = monitor.get_summary()
    print("\nMonitor Summary:")
    print(summary)

    # 重置监控器
    monitor.reset()
    print(f"\nAfter reset - Successful saves: {monitor.successful_saves}")

    print("Storage monitor features test completed successfully!")


if __name__ == "__main__":
    test_storage_monitor_integration()
    test_storage_monitor_features()