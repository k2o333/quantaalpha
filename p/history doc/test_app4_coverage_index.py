import os
import tempfile
import unittest
import polars as pl
from unittest.mock import Mock, patch
from app4.core.coverage_manager import CoverageManager
from app4.core.config_loader import ConfigLoader

class TestCoverageManagerIndex(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_loader = ConfigLoader('app4/config')
        self.storage_manager = Mock()

        self.coverage_manager = CoverageManager(self.storage_manager, self.config_loader)

    def tearDown(self):
        # 清理临时目录
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_quick_range_check_with_index_no_params(self):
        """测试没有日期参数的索引快速检查"""
        # 没有start_date和end_date参数
        params = {'ts_code': '000001.SZ'}
        result = self.coverage_manager._quick_range_check_with_index('daily', params)

        self.assertIsNone(result)

    def test_quick_range_check_with_index_no_index(self):
        """测试没有索引数据的快速检查"""
        self.storage_manager._get_interface_index.return_value = None

        params = {'start_date': '20230101', 'end_date': '20230103'}
        result = self.coverage_manager._quick_range_check_with_index('daily', params)

        self.assertIsNone(result)

    def test_find_continuous_ranges(self):
        """测试查找连续范围方法"""
        date_list = ['20230101', '20230102', '20230103', '20230105', '20230106']
        ranges = self.coverage_manager._find_continuous_ranges(date_list)

        self.assertEqual(len(ranges), 2)
        self.assertEqual(ranges[0], ('20230101', '20230103'))
        self.assertEqual(ranges[1], ('20230105', '20230106'))

    def test_check_fast_coverage_empty_dates(self):
        """测试空日期列表的快速覆盖检查"""
        params = {'start_date': '20230101', 'end_date': '20230103'}
        df = pl.DataFrame({
            'file_path': [],
            'min_date': [],
            'max_date': [],
            'row_count': [],
            'update_time': [],
        })

        result = self.coverage_manager._check_fast_coverage('daily', params, df, 'trade_date')

        self.assertFalse(result['fully_covered'])
        self.assertEqual(result['covered_ratio'], 0.0)

if __name__ == '__main__':
    unittest.main()