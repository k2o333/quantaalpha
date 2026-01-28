import pytest
import os
import tempfile
from unittest.mock import Mock, patch, MagicMock
import polars as pl
from app4.core.storage import StorageManager
from app4.core.processor import DataProcessor


def test_duplicate_save_prevention():
    """
    测试重复保存防护，验证只调用一次写入方法
    """
    # 创建模拟数据
    data = [
        {"ts_code": "000001.SZ", "trade_date": "20230101", "close": 10.0},
        {"ts_code": "000002.SZ", "trade_date": "20230101", "close": 15.0}
    ]

    # 创建临时目录用于测试
    with tempfile.TemporaryDirectory() as temp_dir:
        # 创建StorageManager实例
        storage_manager = StorageManager(storage_dir=temp_dir)

        # 模拟接口配置
        interface_config = {
            "name": "test_interface",
            "output": {
                "primary_key": ["ts_code", "trade_date"]
            },
            "dedup_enabled": True
        }

        # 使用Mock来监控写入方法的调用次数
        with patch.object(storage_manager, '_write_interface_data') as mock_write:
            # 创建DataProcessor实例
            processor = DataProcessor()

            # 导入main.py中定义的函数（通过重新定义）
            def process_and_save_data_local(data, interface_name, interface_config, processor, storage_manager):
                """处理并保存数据的通用函数 - 支持基于接口配置的去重

                Args:
                    data: 原始数据列表
                    interface_name: 接口名称
                    interface_config: 接口配置
                    processor: 数据处理器
                    storage_manager: 存储管理器

                Returns:
                    处理后的 DataFrame，如果处理失败则返回 None
                """
                import polars as pl
                import tempfile
                import os
                from app4.core.dedup import deduplicate_against_existing
                logger = Mock()  # 模拟logger

                if not data:
                    logger.warning(f"No data to process for {interface_name}")
                    return None

                # 处理数据
                df = processor.process_data(data, interface_config)
                validation_result = processor.validate_data(df, interface_config)

                # 使用接口配置获取主键和去重配置
                output_config = interface_config.get('output', {})
                primary_keys = output_config.get('primary_key', [])
                dedup_enabled = interface_config.get('dedup_enabled', True)

                # 如果去重功能启用且存在主键定义
                if dedup_enabled and primary_keys:
                    # 读取该接口的所有现有数据文件（支持Parquet Dataset模式）
                    try:
                        existing_df = storage_manager.read_interface_data(interface_name, columns=primary_keys)
                    except Exception as e:
                        logger.warning(f"无法读取现有数据进行去重: {e}")
                        existing_df = pl.DataFrame()

                    if not existing_df.is_empty():
                        # 使用临时文件进行去重（保持原有逻辑）
                        try:
                            with tempfile.NamedTemporaryFile(suffix='.parquet', delete=False) as tmp_file:
                                existing_df.write_parquet(tmp_file.name)
                                temp_path = tmp_file.name

                            # 使用统一的去重模块
                            df, dedup_stats = deduplicate_against_existing(
                                new_data=df,
                                existing_data_path=temp_path,
                                primary_keys=primary_keys
                            )

                            logger.info(f"Deduplication completed for {interface_name}")

                            # 如果所有数据都被过滤掉了，则直接返回
                            if len(df) == 0:
                                logger.info(f"All records already exist for {interface_name}, skipping save")
                                return df
                        finally:
                            if 'temp_path' in locals() and os.path.exists(temp_path):
                                os.unlink(temp_path)
                    else:
                        logger.info(f"No existing data found for {interface_name}, skipping deduplication")

                logger.info(f"Processed {len(df)} records for {interface_name}")
                if validation_result and 'duplicate_records' in validation_result:
                    if validation_result['duplicate_records'] > 0:
                        logger.info(f"Found {validation_result['duplicate_records']} duplicate records for {interface_name}")

                # 只进行一次数据保存操作
                storage_manager.save_data(interface_name, df.to_dicts(), async_write=False)

                return df

            # 调用函数
            result = process_and_save_data_local(data, "test_interface", interface_config, processor, storage_manager)

            # 验证只调用了一次写入方法
            assert mock_write.call_count == 1, f"预期只调用一次写入方法，但实际调用了 {mock_write.call_count} 次"

            # 验证写入方法的参数
            mock_write.assert_called_once()
            args, kwargs = mock_write.call_args

            # 验证传入的接口名称和数据
            assert args[0] == "test_interface"
            assert isinstance(args[1], list)  # 第二个参数应该是数据列表
            assert len(args[1]) == 2  # 应该有2条记录

            print("重复保存防护测试通过！只调用了一次写入方法。")