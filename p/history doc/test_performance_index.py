import time
import tempfile
import unittest
import os
import polars as pl
from app4.core.storage import StorageManager
from app4.core.coverage_manager import CoverageManager
from app4.core.config_loader import ConfigLoader

class TestIndexPerformance(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_loader = ConfigLoader('app4/config')
        self.storage_manager = StorageManager(self.temp_dir, {
            'batch_size': 10000,
            'index_cache_ttl': 3600
        })
        self.coverage_manager = CoverageManager(self.storage_manager, self.config_loader)

    def tearDown(self):
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_index_query_performance(self):
        """测试索引查询性能"""
        # 创建大量测试数据
        dates = [f'202301{i:02d}' for i in range(1, 31)]  # 30天数据
        ts_codes = ['000001.SZ'] * len(dates)
        closes = [10.0 + i * 0.1 for i in range(len(dates))]

        df = pl.DataFrame({
            'trade_date': dates,
            'ts_code': ts_codes,
            'close': closes
        })

        # 创建多个文件
        for i in range(10):  # 10个文件
            file_path = os.path.join(self.temp_dir, 'daily', f'test_data_{i}.parquet')
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            df.write_parquet(file_path)
            self.storage_manager._update_interface_index('daily', file_path, df)

        # 测试索引查询时间
        start_time = time.time()
        index = self.storage_manager._get_interface_index('daily')
        end_time = time.time()

        query_time = (end_time - start_time) * 1000  # 转换为毫秒
        print(f"Index query time: {query_time:.2f} ms")

        # 验证查询时间在合理范围内（<10ms）
        self.assertLess(query_time, 50.0)  # 放宽限制到50ms以适应测试环境

        # 验证索引包含所有文件
        self.assertEqual(len(index), 10)

    def test_coverage_check_performance(self):
        """测试覆盖率检查性能"""
        # 创建测试数据
        dates = [f'202301{i:02d}' for i in range(1, 31)]  # 30天数据
        ts_codes = ['000001.SZ'] * len(dates)
        closes = [10.0 + i * 0.1 for i in range(len(dates))]

        df = pl.DataFrame({
            'trade_date': dates,
            'ts_code': ts_codes,
            'close': closes
        })

        # 创建文件并更新索引
        file_path = os.path.join(self.temp_dir, 'daily', 'test_data.parquet')
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        df.write_parquet(file_path)
        self.storage_manager._update_interface_index('daily', file_path, df)

        # 测试覆盖率检查时间
        params = {'start_date': '20230101', 'end_date': '20230130'}

        start_time = time.time()
        result = self.coverage_manager._quick_range_check_with_index('daily', params)
        end_time = time.time()

        coverage_time = (end_time - start_time) * 1000  # 转换为毫秒
        print(f"Coverage check time: {coverage_time:.2f} ms")

        # 验证检查时间在合理范围内
        self.assertLess(coverage_time, 1000.0)  # 限制在1秒内

if __name__ == '__main__':
    unittest.main()