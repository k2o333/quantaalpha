#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试下载速度的脚本
比较逐日下载和批量下载的性能差异
"""

import time
import logging
import pandas as pd
import sys
import os

# 添加当前目录到Python路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from date_range_downloader import DateRangeDownloader
from tushare_api import TuShareDownloader

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_original_method(start_date: str, end_date: str, data_type: str = 'daily'):
    """
    测试原始的逐日下载方法
    """
    logger.info("开始测试原始逐日下载方法...")
    start_time = time.time()

    downloader = DateRangeDownloader(start_date, end_date)
    trading_days = downloader.get_trading_days()

    results = {}
    total_records = 0

    # 限制测试天数以节省时间
    test_days = trading_days[:5]  # 只测试前5个交易日

    for i, trade_date in enumerate(test_days):
        try:
            logger.info(f"正在下载 {data_type} - {trade_date} ({i+1}/{len(test_days)})")

            if data_type == 'daily':
                df = downloader.downloader.download_daily_data(ts_code=None, start_date=trade_date, end_date=trade_date)
            elif data_type == 'moneyflow':
                df = downloader.downloader.download_moneyflow(trade_date=trade_date)
            else:
                logger.warning(f"不支持的数据类型: {data_type}")
                continue

            if not df.empty:
                results[trade_date] = len(df)
                total_records += len(df)
                logger.info(f"成功下载 {data_type}_{trade_date}: {len(df)} 条记录")
            else:
                results[trade_date] = 0
                logger.warning(f"{data_type} - {trade_date} 无数据")

        except Exception as e:
            logger.error(f"下载 {data_type} - {trade_date} 失败: {e}")
            results[trade_date] = 0
            continue

    end_time = time.time()
    elapsed_time = end_time - start_time

    logger.info(f"原始方法下载完成，总耗时: {elapsed_time:.2f}秒，总记录数: {total_records}")
    return elapsed_time, total_records, results

def test_optimized_method(start_date: str, end_date: str, data_type: str = 'daily'):
    """
    测试优化的批量下载方法
    """
    logger.info("开始测试优化批量下载方法...")
    start_time = time.time()

    downloader = DateRangeDownloader(start_date, end_date)

    # 直接调用优化后的下载方法
    try:
        if data_type == 'daily':
            results = downloader._download_daily_type_for_range('daily')
        elif data_type == 'moneyflow':
            results = downloader._download_daily_type_for_range('moneyflow')
        else:
            logger.warning(f"不支持的数据类型: {data_type}")
            return 0, 0, {}

        total_records = sum(results.values())

    except Exception as e:
        logger.error(f"优化方法下载失败: {e}")
        return 0, 0, {}

    end_time = time.time()
    elapsed_time = end_time - start_time

    logger.info(f"优化方法下载完成，总耗时: {elapsed_time:.2f}秒，总记录数: {total_records}")
    return elapsed_time, total_records, results

def compare_download_methods(start_date: str, end_date: str, data_type: str = 'daily'):
    """
    比较两种下载方法的性能
    """
    logger.info(f"开始比较下载方法性能，数据类型: {data_type}，日期范围: {start_date} 到 {end_date}")

    # 测试原始方法
    orig_time, orig_records, orig_results = test_original_method(start_date, end_date, data_type)

    # 等待一段时间避免API限制
    time.sleep(5)

    # 测试优化方法
    opt_time, opt_records, opt_results = test_optimized_method(start_date, end_date, data_type)

    # 输出比较结果
    logger.info("=" * 50)
    logger.info("性能比较结果:")
    logger.info(f"原始方法耗时: {orig_time:.2f}秒，记录数: {orig_records}")
    logger.info(f"优化方法耗时: {opt_time:.2f}秒，记录数: {opt_records}")

    if orig_time > 0:
        speedup = orig_time / opt_time if opt_time > 0 else float('inf')
        logger.info(f"性能提升: {speedup:.2f}倍")

    logger.info("=" * 50)

if __name__ == "__main__":
    # 测试日期范围（可以根据需要调整）
    start_date = "20231201"
    end_date = "20231231"

    # 比较daily数据下载
    compare_download_methods(start_date, end_date, 'daily')

    # 等待一段时间避免API限制
    time.sleep(10)

    # 比较moneyflow数据下载
    compare_download_methods(start_date, end_date, 'moneyflow')