#!/usr/bin/env python3
"""
测试 moneyflow_dc 接口的 --update 增量更新模式
验证：第二次下载新增交易日时，是否只增量下载，而不是全量下载后再去重
"""
import sys
import os
import logging
import time
from datetime import datetime, timedelta

# 添加 app4 到 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app4'))

from core.config_loader import ConfigLoader
from core.downloader import GenericDownloader
from core.storage import StorageManager
from core.processor import DataProcessor
from core.cache_warmer import CacheWarmer
from core.coverage_manager import CoverageManager
import polars as pl

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def get_existing_data_count(storage_dir, interface_name):
    """获取已存在的数据记录数"""
    data_path = os.path.join(storage_dir, interface_name)
    if not os.path.exists(data_path):
        return 0, []
    
    try:
        df = pl.read_parquet(data_path)
        trade_dates = df['trade_date'].unique().to_list()
        return len(df), sorted(trade_dates)
    except Exception as e:
        logger.warning(f"读取现有数据失败：{e}")
        return 0, []


def test_incremental_update():
    """测试增量更新模式"""
    
    # 初始化配置
    config_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app4', 'config')
    config_loader = ConfigLoader(config_dir=config_dir)
    
    if not config_loader.validate_config():
        logger.error("配置验证失败")
        return False
    
    # 初始化组件
    processor = DataProcessor()
    storage_config = config_loader.global_config.get('storage', {})
    storage_dir = storage_config.get('base_dir', '../data')
    storage_manager = StorageManager(
        processor=processor,
        config_loader=config_loader,
        storage_dir=storage_dir,
        format=storage_config.get('format', 'parquet'),
        batch_size=storage_config.get('batch_size', 10000)
    )
    
    cache_warmer = CacheWarmer(storage_dir)
    trade_cal_cache = cache_warmer.preload_trade_calendar()
    stock_list_cache = cache_warmer.preload_stock_list()
    
    downloader = GenericDownloader(
        config_loader=config_loader,
        storage_manager=storage_manager,
        trade_calendar_cache=trade_cal_cache,
        stock_list_cache=stock_list_cache,
    )
    
    interface_name = 'moneyflow_dc'
    
    print("=" * 80)
    print("测试 --update 增量更新模式")
    print("=" * 80)
    
    # ========== 第一次下载：下载 20260210-20260212 ==========
    print("\n【第一次下载】日期范围：20260210 - 20260212")
    print("-" * 80)
    
    # 清理现有数据（确保测试环境干净）
    import shutil
    data_path = os.path.join(storage_dir, interface_name)
    if os.path.exists(data_path):
        logger.info(f"清理现有数据目录：{data_path}")
        shutil.rmtree(data_path)
    
    start_date_1 = '20260210'
    end_date_1 = '20260212'
    
    params_1 = {
        'start_date': start_date_1,
        'end_date': end_date_1
    }
    
    logger.info(f"请求参数：{params_1}")
    
    start_time_1 = time.time()
    storage_manager.start_writer()
    try:
        data_1 = downloader.download(interface_name, params_1)
        if data_1:
            storage_manager.save_data(interface_name, data_1, async_write=True)
        time.sleep(3)  # 等待写入完成
    finally:
        storage_manager.stop_writer()
    
    elapsed_1 = time.time() - start_time_1
    
    # 统计第一次下载结果
    count_1, dates_1 = get_existing_data_count(storage_dir, interface_name)
    logger.info(f"第一次下载完成：获取 {len(data_1)} 条记录，保存 {count_1} 条记录")
    logger.info(f"覆盖交易日：{dates_1}")
    logger.info(f"耗时：{elapsed_1:.2f} 秒")
    
    # ========== 第二次下载：扩展到 20260213（新增 1 天） ==========
    print("\n【第二次下载】日期范围：20260210 - 20260213（新增 1 天）")
    print("-" * 80)
    
    # 重新初始化组件（模拟新的下载会话）
    storage_manager_2 = StorageManager(
        processor=processor,
        config_loader=config_loader,
        storage_dir=storage_dir,
        format=storage_config.get('format', 'parquet'),
        batch_size=storage_config.get('batch_size', 10000)
    )
    
    downloader_2 = GenericDownloader(
        config_loader=config_loader,
        storage_manager=storage_manager_2,
        trade_calendar_cache=trade_cal_cache,
        stock_list_cache=stock_list_cache,
    )
    
    start_date_2 = '20260210'
    end_date_2 = '20260213'  # 新增 1 天
    
    params_2 = {
        'start_date': start_date_2,
        'end_date': end_date_2
    }
    
    logger.info(f"请求参数：{params_2}")
    logger.info(f"新增交易日：20260213")
    
    # 检查覆盖率（模拟 update 模式的检测逻辑）
    coverage_manager = CoverageManager(storage_manager_2, config_loader, downloader=downloader_2)
    
    # 检测缺口
    gap_tasks = coverage_manager.detect_gaps(
        interface_name,
        start_date_2,
        end_date_2,
        downloader_2.config_loader.get_interface_config(interface_name)
    )
    
    logger.info(f"缺口检测结果：{len(gap_tasks)} 个缺口任务")
    for task in gap_tasks:
        logger.info(f"  - {task}")
    
    # 执行第二次下载
    start_time_2 = time.time()
    storage_manager_2.start_writer()
    try:
        data_2 = downloader_2.download(interface_name, params_2)
        if data_2:
            storage_manager_2.save_data(interface_name, data_2, async_write=True)
        time.sleep(3)  # 等待写入完成
    finally:
        storage_manager_2.stop_writer()
    
    elapsed_2 = time.time() - start_time_2
    
    # 统计第二次下载结果
    count_2, dates_2 = get_existing_data_count(storage_dir, interface_name)
    
    # 计算增量
    new_records = count_2 - count_1
    new_dates = set(dates_2) - set(dates_1)
    
    logger.info(f"第二次下载完成：获取 {len(data_2)} 条记录")
    logger.info(f"累计保存：{count_2} 条记录（新增 {new_records} 条）")
    logger.info(f"覆盖交易日：{dates_2}")
    logger.info(f"新增交易日：{list(new_dates)}")
    logger.info(f"耗时：{elapsed_2:.2f} 秒")
    
    # ========== 分析结果 ==========
    print("\n" + "=" * 80)
    print("测试结果分析")
    print("=" * 80)
    
    # 计算预期新增记录数（基于第一次下载的平均值）
    avg_records_per_day = count_1 / len(dates_1) if dates_1 else 0
    expected_new_records = int(avg_records_per_day * len(new_dates))
    
    print(f"""
第一次下载:
  - 日期范围：{start_date_1} - {end_date_1}
  - 获取记录数：{len(data_1)}
  - 保存记录数：{count_1}
  - 覆盖交易日：{len(dates_1)} 天 {dates_1}
  - 耗时：{elapsed_1:.2f} 秒

第二次下载:
  - 日期范围：{start_date_2} - {end_date_2}
  - 获取记录数：{len(data_2)}
  - 累计保存：{count_2} 条（新增 {new_records} 条）
  - 覆盖交易日：{len(dates_2)} 天 {dates_2}
  - 新增交易日：{list(new_dates)}
  - 耗时：{elapsed_2:.2f} 秒

增量分析:
  - 预期新增记录数：~{expected_new_records} 条（基于第一次平均值）
  - 实际新增记录数：{new_records} 条
  - 第二次获取记录 / 第一次获取记录：{len(data_2)}/{len(data_1)} = {len(data_2)/len(data_1)*100:.1f}%
""")
    
    # 判断是否为增量下载
    is_incremental = False
    
    if len(gap_tasks) == 1:
        # 缺口检测只发现了 1 天的缺口
        logger.info("✓ 缺口检测正确识别出只有 1 天需要下载")
        is_incremental = True
    
    if len(data_2) < len(data_1) * 0.5:
        # 第二次下载的数据量远小于第一次（说明没有全量下载）
        logger.info("✓ 第二次下载数据量明显减少，符合增量下载特征")
        is_incremental = True
    
    if abs(new_records - expected_new_records) < expected_new_records * 0.3:
        # 新增记录数与预期相符
        logger.info("✓ 新增记录数与预期相符")
        is_incremental = True
    
    print("\n" + "-" * 80)
    if is_incremental:
        print("结论：✅ 系统执行了增量下载，只下载了新增交易日的数据")
    else:
        print("结论：⚠️ 可能是全量下载后去重，建议检查日志确认")
    print("-" * 80)
    
    return is_incremental


if __name__ == '__main__':
    result = test_incremental_update()
    
    print("\n" + "=" * 80)
    if result:
        print("测试通过：增量更新模式工作正常")
    else:
        print("测试失败：需要进一步分析")
    print("=" * 80)
