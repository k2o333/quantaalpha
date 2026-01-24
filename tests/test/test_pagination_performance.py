"""
性能测试脚本：检查分页功能是否改善了下载性能
"""
import sys
import os
import time

# 添加项目路径，模仿main.py的设置
project_root = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, project_root)

# 为模块添加路径，模仿main.py的设置
app_dir = os.path.join(project_root, 'app')
sys.path.insert(0, app_dir)

utils_dir = os.path.join(app_dir, 'utils')
sys.path.insert(0, utils_dir)

interfaces_dir = os.path.join(app_dir, 'interfaces')
sys.path.insert(0, interfaces_dir)

from app.config_manager import ConfigManager
from app.api_manager import TuShareAPIManager
from app.interfaces.basic_data import BasicDataDownloader

def test_pagination_performance():
    """测试分页功能的性能"""
    print("开始测试分页功能性能...")

    try:
        # 初始化配置和API管理器
        config = ConfigManager()
        api_manager = TuShareAPIManager(config)

        # 测试基础数据下载器
        basic_downloader = BasicDataDownloader(api_manager.pro, config)

        # 测试 stock_st 的普通下载
        print("\n1. 测试 stock_st 普通下载...")
        start_time = time.time()
        try:
            stock_st_data = basic_downloader.download_stock_st()
            normal_time = time.time() - start_time
            print(f"   普通下载耗时: {normal_time:.2f} 秒")
            print(f"   下载记录数: {len(stock_st_data)}")
        except Exception as e:
            print(f"   普通下载失败: {e}")
            normal_time = float('inf')

        # 测试 stock_st 的分页下载
        print("\n2. 测试 stock_st 分页下载...")
        start_time = time.time()
        try:
            stock_st_paginated_data = basic_downloader.download_stock_st_paginated()
            paginated_time = time.time() - start_time
            print(f"   分页下载耗时: {paginated_time:.2f} 秒")
            print(f"   下载记录数: {len(stock_st_paginated_data)}")
        except Exception as e:
            print(f"   分页下载失败: {e}")
            paginated_time = float('inf')

        # 比较性能
        print("\n3. 性能比较:")
        if normal_time != float('inf') and paginated_time != float('inf'):
            if paginated_time < normal_time:
                improvement = (normal_time - paginated_time) / normal_time * 100
                print(f"   分页下载更快，性能提升 {improvement:.1f}%")
            elif normal_time < paginated_time:
                degradation = (paginated_time - normal_time) / paginated_time * 100
                print(f"   普通下载更快，分页下载慢 {degradation:.1f}%")
            else:
                print("   两种方法性能相当")
        else:
            print("   无法比较性能，某些方法失败")

        print("\n测试完成!")

    except Exception as e:
        print(f"测试过程中出现错误: {e}")

if __name__ == "__main__":
    test_pagination_performance()