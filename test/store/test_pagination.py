"""
分页下载工具测试脚本
验证分页下载功能是否正常工作
"""
import sys
import os
import logging

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_pagination_utils():
    """测试分页下载工具"""
    from app.utils.pagination_utils import PaginationDownloader

    # 创建分页下载器
    downloader = PaginationDownloader()

    # 测试基本分页下载功能
    print("测试基本分页下载功能...")

    # 创建一个模拟的API函数用于测试
    def mock_api_func(offset=0, limit=100):
        """模拟API函数"""
        import pandas as pd
        import numpy as np

        # 模拟数据
        data_size = min(limit, 500 - offset)  # 总共500条数据
        if data_size <= 0:
            return pd.DataFrame()

        data = {
            'id': range(offset, offset + data_size),
            'value': np.random.randn(data_size),
            'name': [f"item_{i}" for i in range(offset, offset + data_size)]
        }
        return pd.DataFrame(data)

    # 测试基本分页下载
    result = downloader.download_with_pagination(
        mock_api_func,
        limit_per_call=100,
        max_records=300
    )

    print(f"基本分页下载结果: {len(result)} 条记录")
    assert len(result) == 300, f"期望300条记录，实际得到{len(result)}条"

    # 测试智能分页下载
    print("测试智能分页下载功能...")
    result2 = downloader.download_with_smart_pagination(
        mock_api_func,
        initial_limit=50,
        max_limit=200
    )

    print(f"智能分页下载结果: {len(result2)} 条记录")
    assert len(result2) == 500, f"期望500条记录，实际得到{len(result2)}条"

    print("所有测试通过！")

if __name__ == "__main__":
    test_pagination_utils()