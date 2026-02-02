#!/usr/bin/env python3
"""
使用反向日期范围分页模式的示例
"""
import argparse
import logging
import os
import sys
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config_loader import ConfigLoader
from core.downloader import GenericDownloader
from core.storage import StorageManager
from core.processor import DataProcessor

def main():
    parser = argparse.ArgumentParser(description="使用反向日期范围分页模式下载数据")
    parser.add_argument('--interface', type=str, required=True, help='接口名称')
    parser.add_argument('--start_date', type=str, default='20230101', help='开始日期')
    parser.add_argument('--end_date', type=str, default=None, help='结束日期')
    parser.add_argument('--ts_code', type=str, help='股票代码')
    parser.add_argument('--force', action='store_true', help='强制下载')
    
    args = parser.parse_args()
    
    if args.end_date is None:
        args.end_date = datetime.now().strftime('%Y%m%d')
    
    # 设置日志
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # 初始化组件
    config_dir = os.path.join(os.path.dirname(__file__), "config")
    config_loader = ConfigLoader(config_dir=config_dir)
    
    processor = DataProcessor()
    storage_manager = StorageManager(
        processor=processor,
        config_loader=config_loader,
        storage_dir=config_loader.get_global_config().get('storage', {}).get('base_dir', '../data'),
        format=config_loader.get_global_config().get('storage', {}).get('format', 'parquet')
    )
    
    downloader = GenericDownloader(
        config_loader=config_loader,
        storage_manager=storage_manager,
        force_download=args.force
    )
    
    # 准备参数
    params = {
        'start_date': args.start_date,
        'end_date': args.end_date
    }
    
    if args.ts_code:
        params['ts_code'] = args.ts_code
    
    print(f"正在使用反向日期范围分页模式下载数据...")
    print(f"接口: {args.interface}")
    print(f"日期范围: {args.start_date} 到 {args.end_date}")
    if args.ts_code:
        print(f"股票代码: {args.ts_code}")
    
    # 执行下载
    result = downloader.download(args.interface, params)
    
    if result:
        print(f"下载完成！共获取 {len(result)} 条记录")
    else:
        print("下载完成，但没有获取到数据（可能是API认证或其他问题）")

if __name__ == "__main__":
    main()