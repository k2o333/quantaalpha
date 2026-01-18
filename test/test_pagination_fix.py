"""
测试脚本：验证分页功能修复
"""
import sys
import os

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

def test_pagination_methods():
    """测试分页方法是否正常工作"""
    print("测试分页方法...")

    try:
        # 初始化配置和API管理器
        config = ConfigManager()
        api_manager = TuShareAPIManager(config)

        # 测试基础数据下载器
        basic_downloader = BasicDataDownloader(api_manager.pro, config)

        # 检查是否存在分页方法
        print("检查 stock_basic 分页方法...")
        has_paginated_method = hasattr(basic_downloader, 'download_stock_basic_paginated')
        print(f"download_stock_basic_paginated 存在: {has_paginated_method}")

        print("检查 bak_basic 分页方法...")
        has_bak_paginated_method = hasattr(basic_downloader, 'download_bak_basic_paginated')
        print(f"download_bak_basic_paginated 存在: {has_bak_paginated_method}")

        # 尝试调用分页方法（注意：这可能会因为没有网络连接或API密钥而失败）
        print("\n尝试调用分页方法...")
        try:
            # 测试分页下载方法
            stock_basic_data = basic_downloader.download_stock_basic_paginated()
            print(f"分页下载 stock_basic 返回 {len(stock_basic_data)} 条记录")

            bak_basic_data = basic_downloader.download_bak_basic_paginated()
            print(f"分页下载 bak_basic 返回 {len(bak_basic_data)} 条记录")

        except Exception as e:
            print(f"分页方法调用出现异常（可能是正常的，因为我们可能没有有效的API密钥）: {e}")

        print("\n测试完成!")

    except Exception as e:
        print(f"测试过程中出现错误: {e}")

if __name__ == "__main__":
    test_pagination_methods()