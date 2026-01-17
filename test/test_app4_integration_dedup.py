"""
app4架构下存储去重功能的集成测试
"""
import pytest
import tempfile
import os
from app4.core.storage import StorageManager
from app4.core.processor import DataProcessor


def test_storage_deduplication_integration():
    """测试存储模块去重功能的完整集成"""
    with tempfile.TemporaryDirectory() as temp_dir:
        # 1. 初始化存储管理器
        storage_manager = StorageManager(temp_dir)

        # 启动写入线程以处理队列中的数据
        storage_manager.start_writer()

        # 2. 用测试接口名创建初始数据
        interface_name = "test_integration"

        # 3. 模拟初始数据
        initial_data = [
            {"ts_code": "000001.SZ", "trade_date": "20230101", "price": 100.0},
            {"ts_code": "000002.SZ", "trade_date": "20230101", "price": 200.0}
        ]

        # 4. 使用新的去重保存方法保存初始数据
        dedup_config = {
            "enabled": True,
            "strategy": "primary_key",
            "columns": ["ts_code", "trade_date"]
        }

        # 使用同步保存方式，避免异步队列问题
        storage_manager.save_data_with_dedup(interface_name, initial_data, dedup_config, async_write=False)

        # 5. 准备包含重复数据的新数据
        new_data = [
            {"ts_code": "000001.SZ", "trade_date": "20230101", "price": 100.0},  # 重复
            {"ts_code": "000002.SZ", "trade_date": "20230101", "price": 200.0},  # 重复
            {"ts_code": "000003.SZ", "trade_date": "20230101", "price": 300.0}   # 新数据
        ]

        # 6. 再次使用去重保存，应只保存新数据
        storage_manager.save_data_with_dedup(interface_name, new_data, dedup_config, async_write=False)

        # 7. 验证最终结果
        result_df = storage_manager.read_interface_data(interface_name)

        # 应该只包含3条记录：原来的2条 + 新的1条
        assert len(result_df) == 3

        # 验证所有记录都唯一
        unique_records = result_df.select(["ts_code", "trade_date"]).unique()
        assert len(unique_records) == 3

        # 停止写入线程
        storage_manager.stop_writer()


def test_process_and_save_data_with_dedup():
    """测试完整的数据处理和保存流程"""
    with tempfile.TemporaryDirectory() as temp_dir:
        from app4.core.storage import StorageManager
        from app4.core.processor import DataProcessor

        storage_manager = StorageManager(temp_dir)
        processor = DataProcessor()

        # 接口配置包含去重设置
        interface_config = {
            "output": {
                "primary_key": ["ts_code", "trade_date"],
                "sort_by": ["trade_date"]
            },
            "dedup": {
                "enabled": True,
                "strategy": "primary_key",
                "columns": ["ts_code", "trade_date"]
            }
        }

        # 模拟初始数据
        initial_data = [
            {"ts_code": "000001.SZ", "trade_date": "20230101", "price": 100.0}
        ]

        # 在main.py中实现process_and_save_data函数
        def process_and_save_data(data, interface_name, interface_config, processor, storage_manager):
            """处理并保存数据的通用函数 - 重构后"""
            if not data:
                print(f"No data to process for {interface_name}")
                return None

            # 处理数据 - 这里简化处理流程
            import polars as pl
            df = pl.DataFrame(data)

            # 从接口配置获取去重配置
            dedup_config = interface_config.get('dedup', {})

            # 保存数据（内部处理去重逻辑）
            storage_manager.save_data_with_dedup(interface_name, df.to_dicts(), dedup_config, async_write=False)

            print(f"Saved {len(df)} processed records for {interface_name}")
            return df

        # 保存初始数据
        process_and_save_data(initial_data, "integration_test", interface_config, processor, storage_manager)

        # 尝试保存重复数据
        duplicate_data = [
            {"ts_code": "000001.SZ", "trade_date": "20230101", "price": 100.0},  # 重复
            {"ts_code": "000002.SZ", "trade_date": "20230101", "price": 200.0}   # 新数据
        ]

        process_and_save_data(duplicate_data, "integration_test", interface_config, processor, storage_manager)

        # 验证结果
        result_df = storage_manager.read_interface_data("integration_test")

        # 应该包含2条记录：1条原始 + 1条新数据
        assert len(result_df) == 2

        # 验证所有记录都唯一
        unique_records = result_df.select(["ts_code", "trade_date"]).unique()
        assert len(unique_records) == 2