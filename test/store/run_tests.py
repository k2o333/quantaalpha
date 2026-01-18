#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试脚本，验证项目优化后的功能是否正常工作
"""
import sys
import os

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
app_path = os.path.join(project_root, 'app')
sys.path.insert(0, project_root)
sys.path.insert(0, app_path)

def test_imports():
    """测试基本导入功能"""
    print("测试基本导入功能...")

    try:
        from app.date_range_downloader import DateRangeDownloader
        print("✓ DateRangeDownloader 导入成功")
    except Exception as e:
        print(f"✗ DateRangeDownloader 导入失败: {e}")
        return False

    try:
        from app.tushare_api import TuShareDownloader
        print("✓ TuShareDownloader 导入成功")
    except Exception as e:
        print(f"✗ TuShareDownloader 导入失败: {e}")
        return False

    try:
        from app.interfaces.technical_factors import TechnicalFactorsDownloader
        print("✓ TechnicalFactorsDownloader 导入成功")
    except Exception as e:
        print(f"✗ TechnicalFactorsDownloader 导入失败: {e}")
        return False

    try:
        from app.interfaces.market_flow import MarketFlowDownloader
        print("✓ MarketFlowDownloader 导入成功")
    except Exception as e:
        print(f"✗ MarketFlowDownloader 导入失败: {e}")
        return False

    try:
        from app.utils.pagination_utils import PaginationDownloader
        print("✓ PaginationDownloader 导入成功")
    except Exception as e:
        print(f"✗ PaginationDownloader 导入失败: {e}")
        return False

    return True

def test_pagination_utils():
    """测试分页下载工具"""
    print("\n测试分页下载工具...")

    try:
        from app.utils.pagination_utils import PaginationDownloader
        downloader = PaginationDownloader()

        # 创建一个模拟的API函数用于测试
        def mock_api_func(offset=0, limit=100):
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

        if len(result) == 300:
            print("✓ 基本分页下载功能正常")
        else:
            print(f"✗ 基本分页下载功能异常: 期望300条记录，实际得到{len(result)}条")
            return False

        # 测试智能分页下载
        result2 = downloader.download_with_smart_pagination(
            mock_api_func,
            initial_limit=50,
            max_limit=200
        )

        if len(result2) == 500:
            print("✓ 智能分页下载功能正常")
        else:
            print(f"✗ 智能分页下载功能异常: 期望500条记录，实际得到{len(result2)}条")
            return False

        return True

    except Exception as e:
        print(f"✗ 分页下载工具测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("aspipe_v4 项目优化后功能测试")
    print("=" * 40)

    # 测试导入功能
    if not test_imports():
        print("\n❌ 导入测试失败")
        return 1

    print("\n✓ 所有模块导入成功")

    # 测试分页工具
    if not test_pagination_utils():
        print("\n❌ 分页工具测试失败")
        return 1

    print("\n✓ 分页工具测试通过")

    print("\n🎉 所有测试通过！项目优化完成。")
    return 0

if __name__ == "__main__":
    sys.exit(main())