#!/usr/bin/env python3
"""
Primary Key测试数据下载脚本
下载16个接口的数据到test/prim/data目录
"""
import os
import sys
import argparse
import logging
from datetime import datetime

# 添加app4到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'app4'))

from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), '.env')
load_dotenv(env_path)

from core.config_loader import ConfigLoader
from core.downloader import GenericDownloader
from core.storage import StorageManager
from core.processor import DataProcessor
from core.scheduler import TaskScheduler, RateLimiter
import polars as pl

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 16个待测试接口
INTERFACES = [
    "balancesheet_vip",
    "cashflow_vip", 
    "disclosure_date",
    "dividend",
    "express_vip",
    "fina_audit",
    "fina_indicator_vip",
    "fina_mainbz_vip",
    "forecast_vip",
    "income_vip",
    "pledge_detail",
    "pledge_stat",
    "stk_factor_pro",
    "stk_rewards",
    "top10_floatholders",
    "top10_holders"
]

# 数据存储目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')

def setup_test_storage():
    """设置测试专用的存储目录"""
    os.makedirs(DATA_DIR, exist_ok=True)
    logger.info(f"数据存储目录: {DATA_DIR}")
    return DATA_DIR

def download_interface_data(interface_name: str, ts_code: str = None, max_stocks: int = 100) -> str:
    """
    下载指定接口的数据
    
    Args:
        interface_name: 接口名称
        ts_code: 指定股票代码，None则下载前max_stocks只股票
        max_stocks: 最大下载股票数量
    
    Returns:
        parquet文件路径
    """
    output_file = os.path.join(DATA_DIR, f"{interface_name}.parquet")
    
    # 如果已存在且不为空，直接返回
    if os.path.exists(output_file):
        try:
            df = pl.read_parquet(output_file)
            if len(df) > 0:
                logger.info(f"[{interface_name}] 数据已存在，跳过下载 ({len(df)} 条记录)")
                return output_file
        except:
            pass
    
    # 初始化配置
    config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'app4', 'config')
    config_loader = ConfigLoader(config_dir=config_dir)
    
    interface_config = config_loader.get_interface_config(interface_name)
    
    # 初始化组件
    processor = DataProcessor()
    storage_manager = StorageManager(
        processor=processor,
        config_loader=config_loader,
        storage_dir=DATA_DIR,
        format='parquet',
        batch_size=10000
    )
    
    downloader = GenericDownloader(
        config_loader=config_loader,
        storage_manager=storage_manager,
        force_download=True
    )
    
    logger.info(f"[{interface_name}] 开始下载数据...")
    
    # 获取分页模式
    pagination_config = interface_config.get('pagination', {})
    mode = pagination_config.get('mode', 'offset') if pagination_config.get('enabled', False) else 'none'
    
    all_data = []
    
    if mode == 'stock_loop':
        # 股票循环模式：获取股票列表并下载
        stock_list = downloader._get_stock_list()
        if stock_list:
            if ts_code:
                # 指定股票代码
                stock_list = [s for s in stock_list if s['ts_code'] == ts_code]
            else:
                # 限制股票数量
                stock_list = stock_list[:max_stocks]
            
            logger.info(f"[{interface_name}] 将下载 {len(stock_list)} 只股票的数据")
            
            for i, stock in enumerate(stock_list):
                try:
                    stock_data = downloader.download_single_stock(
                        interface_config, stock, {}
                    )
                    if stock_data:
                        all_data.extend(stock_data)
                    
                    if (i + 1) % 10 == 0:
                        logger.info(f"[{interface_name}] 已处理 {i+1}/{len(stock_list)} 只股票")
                        
                except Exception as e:
                    logger.error(f"[{interface_name}] 下载股票 {stock['ts_code']} 失败: {e}")
                    continue
    elif mode == 'date_range':
        # 日期范围模式：下载最近365天数据
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now().replace(year=datetime.now().year-1)).strftime('%Y%m%d')
        
        params = {'start_date': start_date, 'end_date': end_date}
        data = downloader.download(interface_name, params)
        if data:
            all_data.extend(data)
    else:
        # 其他模式：offset或不分页
        params = {}
        if ts_code:
            params['ts_code'] = ts_code
        data = downloader.download(interface_name, params)
        if data:
            all_data.extend(data)
    
    # 保存原始数据到parquet（不去重，保留完整数据用于primary key测试）
    if all_data:
        # 直接转换为DataFrame，不经过processor的去重处理
        import pandas as pd
        df = pd.DataFrame(all_data)
        df.to_parquet(output_file, index=False)
        logger.info(f"[{interface_name}] 下载完成，保存 {len(df)} 条原始记录到 {output_file}")
        return output_file
    else:
        logger.warning(f"[{interface_name}] 没有下载到数据")
        return None

def download_all_interfaces(ts_code: str = None, max_stocks: int = 100):
    """下载所有测试接口的数据"""
    setup_test_storage()
    
    results = {}
    for interface_name in INTERFACES:
        try:
            file_path = download_interface_data(interface_name, ts_code, max_stocks)
            results[interface_name] = file_path
        except Exception as e:
            logger.error(f"[{interface_name}] 下载失败: {e}")
            results[interface_name] = None
    
    return results

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='下载Primary Key测试数据')
    parser.add_argument('--ts_code', type=str, default='000002.SZ', help='指定股票代码 (默认: 000002.SZ)')
    parser.add_argument('--max_stocks', type=int, default=1, help='最大下载股票数量 (默认1)')
    parser.add_argument('--interface', type=str, help='指定单个接口下载')
    
    args = parser.parse_args()
    
    if args.interface:
        # 下载单个接口
        if args.interface in INTERFACES:
            download_interface_data(args.interface, args.ts_code, args.max_stocks)
        else:
            logger.error(f"接口 {args.interface} 不在测试列表中")
            logger.info(f"可用接口: {', '.join(INTERFACES)}")
    else:
        # 下载所有接口
        download_all_interfaces(args.ts_code, args.max_stocks)
