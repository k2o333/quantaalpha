#!/usr/bin/env python3
"""
测试 moneyflow_dc 接口 - reverse_date_range 模式，仅使用日期参数
窗口大小：1 天
开始日期：20260210
"""
import sys
import os
import logging
from datetime import datetime

# 添加 app4 到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app4'))

from core.config_loader import ConfigLoader
from core.downloader import GenericDownloader
from core.storage import StorageManager
from core.processor import DataProcessor
from core.cache_warmer import CacheWarmer

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_moneyflow_dc_reverse_date_range():
    """测试 moneyflow_dc 接口 reverse_date_range 模式，仅使用日期参数"""
    
    # 初始化配置
    config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app4', 'config')
    config_loader = ConfigLoader(config_dir=config_dir)
    
    if not config_loader.validate_config():
        logger.error("配置验证失败")
        return None
    
    # 初始化组件
    processor = DataProcessor()
    storage_config = config_loader.global_config.get('storage', {})
    storage_manager = StorageManager(
        processor=processor,
        config_loader=config_loader,
        storage_dir=storage_config.get('base_dir', '../data'),
        format=storage_config.get('format', 'parquet'),
        batch_size=storage_config.get('batch_size', 10000)
    )
    
    cache_warmer = CacheWarmer(storage_config.get('base_dir', '../data'))
    trade_cal_cache = cache_warmer.preload_trade_calendar()
    stock_list_cache = cache_warmer.preload_stock_list()
    
    downloader = GenericDownloader(
        config_loader=config_loader,
        storage_manager=storage_manager,
        trade_calendar_cache=trade_cal_cache,
        stock_list_cache=stock_list_cache,
    )
    
    # 测试参数：仅使用日期，从 2026 年 2 月 10 日开始
    start_date = '20260210'
    end_date = datetime.now().strftime('%Y%m%d')
    
    # 如果结束日期早于开始日期，使用开始日期作为结束日期
    if end_date < start_date:
        end_date = start_date
    
    logger.info(f"测试 moneyflow_dc 接口 (reverse_date_range 模式)，日期范围：{start_date} - {end_date}")
    logger.info(f"窗口大小：1 天")
    
    # 仅使用日期参数调用接口
    params = {
        'start_date': start_date,
        'end_date': end_date
    }
    
    logger.info(f"请求参数：{params}")
    
    try:
        # 调用 download 方法
        data = downloader.download('moneyflow_dc', params)
        
        if data:
            logger.info(f"✓ 成功获取数据，共 {len(data)} 条记录")
            
            # 显示前几条数据
            if len(data) > 0:
                logger.info("\n前 5 条数据示例:")
                for i, record in enumerate(data[:5]):
                    logger.info(f"  记录 {i+1}: {record}")
            
            # 统计日期分布
            trade_dates = set()
            for record in data:
                trade_dates.add(record.get('trade_date'))
            
            logger.info(f"\n数据覆盖的交易日数量：{len(trade_dates)}")
            logger.info(f"交易日列表：{sorted(trade_dates)}")
            
            # 保存数据
            logger.info("\n正在保存数据...")
            storage_manager.start_writer()
            try:
                storage_manager.save_data('moneyflow_dc', data, async_write=True)
                # 等待写入完成
                import time
                time.sleep(2)
                logger.info("数据保存成功")
            finally:
                storage_manager.stop_writer()
            
            return data
        else:
            logger.warning("未能获取到数据")
            return None
            
    except Exception as e:
        logger.exception(f"测试过程中发生错误：{e}")
        import traceback
        logger.debug(traceback.format_exc())
        return None


if __name__ == '__main__':
    print("=" * 70)
    print("测试 moneyflow_dc 接口 - reverse_date_range 模式")
    print("窗口大小：1 天")
    print("开始日期：20260210")
    print("仅传递日期参数 (start_date, end_date)")
    print("=" * 70)
    
    result = test_moneyflow_dc_reverse_date_range()
    
    print("\n" + "=" * 70)
    if result:
        print(f"测试成功！获取到 {len(result)} 条记录")
    else:
        print("测试失败，未能获取数据")
    print("=" * 70)
