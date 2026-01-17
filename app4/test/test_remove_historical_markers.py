import unittest
import os
import sys
import json
from pathlib import Path

# Add the app4 directory to the path so we can import the modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.cleanup_historical_markers import remove_historical_download_markers


class TestRemoveHistoricalMarkers(unittest.TestCase):
    def test_remove_historical_markers(self):
        """测试清理脚本功能"""
        # The script looks for cache in app4/cache based on its file location
        # So we need to create the file where the script expects to find it
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

        # Test the function from the script
        result = remove_historical_download_markers()
        self.assertTrue(result)

        # 验证文件已被删除
        self.assertFalse(os.path.exists(marker_path))


if __name__ == '__main__':
    unittest.main()