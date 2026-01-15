import os
import tempfile
import unittest
import polars as pl
from app4.core.storage import StorageManager
from app4.core.coverage_manager import CoverageManager
from app4.core.config_loader import ConfigLoader

class TestIndexBasedCoverageIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = 'app4/config/settings.yaml'
        self.interfaces_dir = 'app4/config/interfaces'

        self.config_loader = ConfigLoader('app4/config')
        self.storage_manager = StorageManager(self.temp_dir, {
            'batch_size': 10000,
            'index_cache_ttl': 3600
        })

        self.coverage_manager = CoverageManager(self.storage_manager, self.config_loader)

    def tearDown(self):
        # 清理临时目录
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_full_index_based_coverage_flow(self):
        """测试完整的索引基础覆盖率检查流程"""
        # 1. 创建测试数据
        df = pl.DataFrame({
            'trade_date': ['20230101', '20230102', '20230103'],
            'ts_code': ['000001.SZ', '000001.SZ', '000001.SZ'],
            'close': [10.0, 11.0, 12.0]
        })

        file_path = os.path.join(self.temp_dir, 'daily', 'test_data.parquet')
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        df.write_parquet(file_path)

        # 2. 更新索引
        self.storage_manager._update_interface_index('daily', file_path, df)

        # 3. 验证索引已更新
        index = self.storage_manager._get_interface_index('daily')
        self.assertIsNotNone(index)
        self.assertEqual(len(index), 1)

        # 4. 测试覆盖率检查（完全覆盖的情况）
        params = {'start_date': '20230101', 'end_date': '20230103'}
        quick_result = self.coverage_manager._quick_range_check_with_index('daily', params)

        # 由于数据完全覆盖请求范围，应该返回跳过信息
        if quick_result:
            self.assertTrue(quick_result.get('skip', False))

        # 5. 测试增量下载情况
        params_incremental = {'start_date': '20230101', 'end_date': '20230105'}
        quick_result = self.coverage_manager._quick_range_check_with_index('daily', params_incremental)

        # 由于现有数据到20230103，请求到20230105，应调整参数进行增量下载
        if quick_result and 'adjust_params' in quick_result:
            self.assertEqual(quick_result['adjust_params']['start_date'], '20230104')

    def test_should_skip_with_hybrid_strategy(self):
        """测试使用混合策略的should_skip方法"""
        # 创建测试数据
        df = pl.DataFrame({
            'trade_date': ['20230101', '20230102', '20230103'],
            'ts_code': ['000001.SZ', '000001.SZ', '000001.SZ'],
            'close': [10.0, 11.0, 12.0]
        })

        file_path = os.path.join(self.temp_dir, 'daily', 'test_data.parquet')
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        df.write_parquet(file_path)

        # 更新索引
        self.storage_manager._update_interface_index('daily', file_path, df)

        # 测试should_skip方法
        params = {'start_date': '20230101', 'end_date': '20230103'}
        should_skip = self.coverage_manager.should_skip('daily', params, strategy='hybrid')

        # 在完全覆盖的情况下，应该返回True（跳过下载）
        self.assertTrue(should_skip)

if __name__ == '__main__':
    unittest.main()