#!/usr/bin/env python
"""
验证重复保存检测功能
"""

import tempfile
import os
import polars as pl
from app4.core.storage import StorageManager


def test_duplicate_detection():
    """测试重复保存检测功能"""
    print("Testing duplicate detection...")

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

        interface_name = "daily"

        # 第一次保存
        print("Performing first save...")
        storage_manager.save_data(interface_name, test_data)

        # 检查目录中的文件数量
        interface_dir = os.path.join(temp_dir, interface_name)
        if os.path.exists(interface_dir):
            files_after_first = os.listdir(interface_dir)
            print(f"Files after first save: {len(files_after_first)} - {files_after_first}")

        # 等待写入完成
        import time
        time.sleep(0.5)

        print(f"Monitor - Successful saves: {storage_manager.monitor.successful_saves}")
        print(f"Monitor - Duplicate saves: {storage_manager.monitor.duplicate_saves}")

        # 第二次保存 - 这次我们手动创建一个相同日期范围的文件，看是否被检测到重复
        print("\nPerforming second save to test duplicate detection...")

        # 创建另一个相同的数据集
        storage_manager.save_data(interface_name, test_data)

        # 等待写入完成
        time.sleep(0.5)

        print(f"Monitor - Successful saves: {storage_manager.monitor.successful_saves}")
        print(f"Monitor - Duplicate saves: {storage_manager.monitor.duplicate_saves}")

        # 现在检查目录 - 由于时间戳在文件名中，每个保存都会创建新文件
        # 但我们仍然可以验证重复检测逻辑是否被触发
        interface_dir = os.path.join(temp_dir, interface_name)
        if os.path.exists(interface_dir):
            final_files = os.listdir(interface_dir)
            print(f"Files after second save: {len(final_files)} - {final_files}")

        # 现在让我们手动测试重复检测逻辑
        print("\nTesting duplicate detection logic manually...")
        # 创建一个相同日期范围的文件手动，然后再次保存相同范围的数据
        # 创建一个具有相同日期范围的文件
        test_data2 = pl.DataFrame({
            "ts_code": ["000003.SZ", "000004.SZ"],  # 不同的股票代码
            "trade_date": ["20230101", "20230102"],  # 相同的日期
            "close": [12.0, 13.0]
        })

        print("Performing third save with same date range but different data...")
        storage_manager.save_data(interface_name, test_data2)

        time.sleep(0.5)

        print(f"Monitor - Successful saves: {storage_manager.monitor.successful_saves}")
        print(f"Monitor - Duplicate saves: {storage_manager.monitor.duplicate_saves}")

        # 停止写入器
        storage_manager.stop_writer()

        print("\nDuplicate detection test completed!")


if __name__ == "__main__":
    test_duplicate_detection()