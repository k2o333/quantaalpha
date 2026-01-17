import unittest
import os
import sys
import json
from pathlib import Path

# Add the app4 directory to the path so we can import the modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.coverage_manager import CoverageManager
from core.storage import StorageManager
from core.config_loader import ConfigLoader


class TestCoverageManager(unittest.TestCase):
    def setUp(self):
        # Create mock components for the test
        storage_manager = StorageManager(
            storage_dir="../data",
            format="parquet",
            batch_size=10000
        )

        import os
        config_dir_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
        config_loader = ConfigLoader(config_dir=config_dir_path)

        self.coverage_manager = CoverageManager(storage_manager, config_loader, None)

    def test_remove_historical_download_marker(self):
        """测试移除历史下载标记功能"""
        # The CoverageManager looks for cache in app4/cache based on its file location
        # So we need to create the file where the CoverageManager expects to find it
        import os
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # app4 directory
        cache_dir = os.path.join(script_dir, 'cache')
        os.makedirs(cache_dir, exist_ok=True)

        marker_path = os.path.join(cache_dir, 'historical_download_marker.json')

        # 创建测试数据
        test_markers = {
            'test_interface': '2024-01-01 12:00:00',
            'daily': '2024-01-01 13:00:00'
        }

        with open(marker_path, 'w', encoding='utf-8') as f:
            json.dump(test_markers, f, ensure_ascii=False, indent=2)

        # 测试移除指定接口的标记
        result = self.coverage_manager.remove_historical_download_marker('test_interface')
        self.assertTrue(result)

        # 验证标记文件内容
        with open(marker_path, 'r', encoding='utf-8') as f:
            remaining_markers = json.load(f)

        self.assertEqual(len(remaining_markers), 1)
        self.assertIn('daily', remaining_markers)
        self.assertNotIn('test_interface', remaining_markers)

        # 清理测试文件
        os.remove(marker_path)

    def test_remove_all_historical_download_markers(self):
        """测试移除所有历史下载标记功能"""
        # The CoverageManager looks for cache in app4/cache based on its file location
        # So we need to create the file where the CoverageManager expects to find it
        import os
        script_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # app4 directory
        cache_dir = os.path.join(script_dir, 'cache')
        os.makedirs(cache_dir, exist_ok=True)

        marker_path = os.path.join(cache_dir, 'historical_download_marker.json')

        # 创建测试数据
        test_markers = {
            'test_interface': '2024-01-01 12:00:00',
            'daily': '2024-01-01 13:00:00'
        }

        with open(marker_path, 'w', encoding='utf-8') as f:
            json.dump(test_markers, f, ensure_ascii=False, indent=2)

        # 测试移除所有标记
        result = self.coverage_manager.remove_all_historical_download_markers()
        self.assertTrue(result)

        # 验证文件已被删除
        self.assertFalse(os.path.exists(marker_path))


if __name__ == '__main__':
    unittest.main()