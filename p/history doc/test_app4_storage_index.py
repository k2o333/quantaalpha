import os
import tempfile
import unittest
import polars as pl
from unittest.mock import Mock, patch
from app4.core.storage import StorageManager

class TestStorageManagerIndex(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config = {
            'batch_size': 10000,
            'index_cache_ttl': 3600
        }
        self.storage_manager = StorageManager(self.temp_dir, self.config)

    def tearDown(self):
        # 清理临时目录
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_get_interface_index_path(self):
        """测试获取接口索引路径"""
        path = self.storage_manager._get_interface_index_path('daily')
        expected_path = os.path.join(self.temp_dir, 'daily', '_index.parquet')
        self.assertEqual(path, expected_path)

    def test_get_interface_index_not_exists(self):
        """测试获取不存在的索引"""
        result = self.storage_manager._get_interface_index('nonexistent')
        self.assertIsNone(result)

    def test_update_and_get_interface_index(self):
        """测试更新和获取接口索引"""
        # 创建测试数据
        df = pl.DataFrame({
            'trade_date': ['20230101', '20230102', '20230103'],
            'ts_code': ['000001.SZ', '000001.SZ', '000001.SZ'],
            'close': [10.0, 11.0, 12.0]
        })

        file_path = os.path.join(self.temp_dir, 'test.parquet')

        # 更新索引
        self.storage_manager._update_interface_index('daily', file_path, df)

        # 获取索引
        index = self.storage_manager._get_interface_index('daily')

        self.assertIsNotNone(index)
        self.assertEqual(len(index), 1)
        self.assertEqual(index['file_path'][0], file_path)

    def test_update_after_write(self):
        """测试update_after_write方法"""
        df = pl.DataFrame({
            'trade_date': ['20230101', '20230102'],
            'ts_code': ['000001.SZ', '000001.SZ'],
            'close': [10.0, 11.0]
        })

        file_path = os.path.join(self.temp_dir, 'test.parquet')

        # 调用update_after_write
        self.storage_manager.update_after_write('daily', file_path, df)

        # 验证索引已更新
        index = self.storage_manager._get_interface_index('daily')

        self.assertIsNotNone(index)

if __name__ == '__main__':
    unittest.main()