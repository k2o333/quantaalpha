#!/usr/bin/env python3
"""
测试StockListManager功能的脚本
"""

import logging
import sys
import os
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from tushare_api import TuShareDownloader
from stock_list_manager import init_stock_manager, StockListManager


def setup_logging():
    """设置日志"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )


def test_stock_manager():
    """测试StockListManager功能"""
    print("=" * 60)
    print("StockListManager 功能测试")
    print("=" * 60)

    # 初始化下载器
    print("1. 初始化TuShare下载器...")
    downloader = TuShareDownloader()

    # 初始化StockListManager
    print("2. 初始化StockListManager...")
    stock_manager = init_stock_manager(
        downloader=downloader,
        cache_dir="cache",
        max_cache_age_hours=24
    )

    # 测试获取股票列表
    print("3. 测试获取股票列表...")
    stock_df = stock_manager.get_stock_basic()
    print(f"   获取到 {len(stock_df)} 只股票")

    if not stock_df.empty:
        print(f"   前5只股票:")
        for i, (_, row) in enumerate(stock_df.head().iterrows()):
            print(f"     {i+1}. {row['ts_code']} - {row['name']}")

    # 测试缓存状态
    print("4. 检查缓存状态...")
    cache_status = stock_manager.get_cache_status()
    print(f"   缓存文件: {cache_status['cache_file']}")
    print(f"   缓存存在: {cache_status['cache_exists']}")
    print(f"   内存缓存: {cache_status['in_memory_cached']}")
    print(f"   记录数量: {cache_status['records_count']}")

    # 测试再次获取（应该使用缓存）
    print("5. 测试缓存命中...")
    stock_df2 = stock_manager.get_stock_basic()
    print(f"   再次获取到 {len(stock_df2)} 只股票")

    # 测试强制刷新
    print("6. 测试强制刷新...")
    stock_df3 = stock_manager.refresh_cache()
    print(f"   刷新后获取到 {len(stock_df3)} 只股票")

    print("=" * 60)
    print("测试完成!")
    print("=" * 60)


if __name__ == "__main__":
    setup_logging()
    test_stock_manager()