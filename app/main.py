"""
统一数据下载入口 - 基于积分自动下载所有可用数据
从指定起始日期到今天
"""
import logging
import time
from datetime import datetime, date
from pathlib import Path
import argparse
from enhanced_main_downloader import EnhancedMainDownloader
from config import TUSHARE_POINTS
from score_config import get_available_data_types
from tushare_api import TuShareDownloader
import pandas as pd

# Set up logging with Chinese characters support
log_dir = Path(__file__).parent.parent / 'log'
log_dir.mkdir(exist_ok=True)  # Ensure log directory exists
log_file = log_dir / 'aspipe_v4.log'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def download_all_data_from_date(start_date: str, end_date: str = None):
    """
    Download all data types available for the user's score from start_date to end_date
    """
    if end_date is None:
        end_date = datetime.now().strftime('%Y%m%d')

    logger.info(f"🚀 开始下载数据：从 {start_date} 到 {end_date}")
    logger.info(f"积分: {TUSHARE_POINTS}")

    # Show what's available based on user's score
    available_types = get_available_data_types(TUSHARE_POINTS)
    total_available = sum(len(types) for types in available_types.values() if types)
    logger.info(f"可用数据类型: {total_available} 种")

    for cat, types in available_types.items():
        if types:
            logger.info(f"  {cat}: {len(types)} 种")
            for t in types:
                logger.info(f"    - {t}")

    # Use the date range downloader for comprehensive download
    from date_range_downloader import DateRangeDownloader
    downloader = DateRangeDownloader(start_date, end_date)

    start_time = time.time()

    try:
        # Download all score-appropriate data for the date range
        results = downloader.download_all_available_data()

        elapsed_time = time.time() - start_time
        logger.info(f"✅ 数据下载完成！")
        logger.info("📊 下载统计:")
        for data_type, result in results.items():
            if isinstance(result, dict):
                logger.info(f"   • {data_type}: {len(result)} 个时间分区")
                total = sum(result.values()) if result else 0
                logger.info(f"     总记录数: {total}")
            else:
                logger.info(f"   • {data_type}: {result} 条记录")
        logger.info(f"   • 总运行时间: {elapsed_time:.2f} 秒")

        return results

    except Exception as e:
        logger.error(f"❌ 数据下载失败: {e}")
        raise


def main():
    """
    Main function - unified entry point for all data downloads
    """
    parser = argparse.ArgumentParser(description='统一数据下载系统')
    parser.add_argument('--start_date', type=str, default='20230101',
                        help='起始日期 (YYYYMMDD格式，默认: 20230101)')
    parser.add_argument('--end_date', type=str, default=None,
                        help='结束日期 (YYYYMMDD格式，默认: 今天)')

    args = parser.parse_args()

    start_time = time.time()
    logger.info("="*60)
    logger.info("🚀 统一数据下载系统启动")
    logger.info(f"📅 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # Download all data
        results = download_all_data_from_date(args.start_date, args.end_date)

        # Generate final summary
        elapsed_time = time.time() - start_time

        # Calculate total records properly by checking data types
        total_records = 0
        for result in results.values():
            if isinstance(result, dict):
                # If result is a dictionary, sum its values
                total_records += sum(result.values()) if result else 0
            elif isinstance(result, (int, float)):
                # If result is a number, add directly
                total_records += result
            else:
                # For other types, skip or treat as 0
                continue

        logger.info("="*60)
        logger.info("🎉 系统运行完成！")
        logger.info(f"📊 最终统计:")
        logger.info(f"   • 总记录数: {total_records}")
        logger.info(f"   • 总运行时间: {elapsed_time:.2f} 秒")
        logger.info(f"   • 数据保存目录: {Path(__file__).parent.parent / 'data'}")
        logger.info(f"📅 完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("="*60)

        return True

    except Exception as e:
        logger.error(f"❌ 系统执行失败: {e}")
        logger.error(f"📅 失败时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        raise


if __name__ == "__main__":
    main()