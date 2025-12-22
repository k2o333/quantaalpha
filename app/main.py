"""
统一数据下载入口 - 基于积分自动下载所有可用数据
从指定起始日期到今天
使用新的生产者-消费者模式和策略模式优化下载流程
"""
import logging
import time
from datetime import datetime, date
from pathlib import Path
import argparse
import sys
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
    Using the new download scheduler with producer-consumer pattern
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

    # Use the new download scheduler with enhanced features
    from download_scheduler import run_download_schedule

    start_time = time.time()

    try:
        # Run download using the new scheduler
        results = run_download_schedule(start_date, end_date)

        elapsed_time = time.time() - start_time
        logger.info(f"✅ 数据下载完成！")
        logger.info("📊 下载统计:")

        # Log detailed results from the scheduler
        logger.info(f"   • 总下载记录数: {results.get('total_downloaded', 0)}")
        logger.info(f"   • 总存储记录数: {results.get('total_stored', 0)}")
        logger.info(f"   • 总运行时间: {elapsed_time:.2f} 秒")
        logger.info(f"   • 活跃下载数: {results.get('active_downloads', 0)}")
        logger.info(f"   • 活跃存储数: {results.get('active_storages', 0)}")
        logger.info(f"   • 完成任务数: {results.get('completed_tasks', 0)}")
        logger.info(f"   • 失败任务数: {results.get('failed_tasks', 0)}")

        return results

    except Exception as e:
        logger.error(f"❌ 数据下载失败: {e}")
        raise


def download_with_legacy_fallback(start_date: str, end_date: str = None):
    """
    Download data with fallback to legacy system if new scheduler fails
    """
    if end_date is None:
        end_date = datetime.now().strftime('%Y%m%d')

    logger.info("尝试使用新的调度器下载...")

    try:
        # Try new scheduler first
        results = download_all_data_from_date(start_date, end_date)
        return results
    except Exception as new_scheduler_error:
        logger.warning(f"新调度器下载失败: {new_scheduler_error}")
        logger.info("回退到传统下载方式...")

        # Fallback to legacy code
        return download_with_legacy_method(start_date, end_date)


def download_with_legacy_method(start_date: str, end_date: str = None):
    """
    Legacy download method for fallback
    """
    if end_date is None:
        end_date = datetime.now().strftime('%Y%m%d')

    logger.info(f"🚀 开始下载数据（传统方式）：从 {start_date} 到 {end_date}")
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

    # Initialize StockListManager to avoid duplicate stock_basic calls
    from stock_list_manager import init_stock_manager
    tushare_downloader = TuShareDownloader()
    stock_manager = init_stock_manager(
        downloader=tushare_downloader,
        cache_dir="cache",
        max_cache_age_hours=24
    )

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
    Now uses the enhanced download scheduler with fallback capability
    """
    parser = argparse.ArgumentParser(description='统一数据下载系统（增强版）')
    parser.add_argument('--start_date', type=str, default='20230101',
                        help='起始日期 (YYYYMMDD格式，默认: 20230101)')
    parser.add_argument('--end_date', type=str, default=None,
                        help='结束日期 (YYYYMMDD格式，默认: 今天)')
    parser.add_argument('--use_legacy', action='store_true',
                        help='使用传统下载方式（跳过新调度器）')
    parser.add_argument('--holders-data', dest='holders_data', action='store_true',
                        help='启用stk_rewards, top10_holders, pledge_detail, fina_audit等股东数据下载')
    parser.add_argument('--pro-bar-only', dest='pro_bar_only', action='store_true',
                        help='仅启用pro_bar复权行情下载')
    parser.add_argument('--tscode-historical', dest='tscode_historical', action='store_true',
                        help='下载全历史数据而非指定日期范围（仅适用于指定接口）')

    args = parser.parse_args()

    start_time = time.time()
    logger.info("="*60)
    logger.info("🚀 统一数据下载系统（增强版）启动")
    logger.info(f"📅 启动时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        # 如果指定了holders_data或pro_bar_only参数，或只指定了tscode_historical参数，则只下载特定数据
        if args.holders_data or args.pro_bar_only or (args.tscode_historical and not (args.holders_data or args.pro_bar_only)):
            logger.info("开始下载指定的全历史数据...")
            # 初始化TuShareDownloader
            from tushare_api import TuShareDownloader
            downloader = TuShareDownloader()

            results = {}

            # 如果只指定了tscode_historical参数（没有指定holders_data或pro_bar_only），则默认下载所有5个接口
            download_holders_data = args.holders_data or (args.tscode_historical and not (args.holders_data or args.pro_bar_only))
            download_pro_bar_only = args.pro_bar_only or (args.tscode_historical and not (args.holders_data or args.pro_bar_only))

            if download_holders_data:
                logger.info("下载股东相关全历史数据...")
                # 下载stk_rewards, top10_holders, pledge_detail, fina_audit数据
                if args.tscode_historical:
                    # 下载全历史数据
                    # 先获取股票列表以提高性能
                    from interfaces.basic_data import BasicDataDownloader
                    basic_downloader = BasicDataDownloader(downloader.pro)
                    stock_list = basic_downloader.download_stock_basic()

                    # 创建全历史下载器实例
                    from interfaces.holders_data_downloader import HoldersDataFullHistoryDownloader
                    full_history_downloader = HoldersDataFullHistoryDownloader(downloader.pro, stock_list)

                    logger.info("下载stk_rewards全历史数据...")
                    results['stk_rewards_full'] = full_history_downloader.download_stk_rewards_full_history()

                    logger.info("下载top10_holders全历史数据...")
                    results['top10_holders_full'] = full_history_downloader.download_top10_holders_full_history()

                    if TUSHARE_POINTS >= 5000:
                        logger.info("下载pledge_detail全历史数据...")
                        results['pledge_detail_full'] = full_history_downloader.download_pledge_detail_full_history()

                    if TUSHARE_POINTS >= 500:
                        logger.info("下载fina_audit全历史数据...")
                        # 对于fina_audit，直接从FinancialDataDownloader调用
                        from interfaces.financial_data import FinancialDataDownloader
                        financial_downloader = FinancialDataDownloader(downloader.pro)
                        results['fina_audit_full'] = financial_downloader.download_fina_audit_full_history()
                else:
                    # 使用传统方式下载指定日期范围
                    results = download_with_legacy_fallback(args.start_date, args.end_date)

            if download_pro_bar_only:
                logger.info("下载pro_bar复权行情数据...")
                if args.tscode_historical:
                    # 下载全历史数据
                    logger.info("下载pro_bar全历史数据...")
                    # 传递股票列表以提高性能
                    from interfaces.basic_data import BasicDataDownloader
                    basic_downloader = BasicDataDownloader(downloader.pro)
                    stock_list = basic_downloader.download_stock_basic()

                    from interfaces.holders_data_downloader import HoldersDataFullHistoryDownloader
                    full_history_downloader = HoldersDataFullHistoryDownloader(downloader.pro, stock_list)
                    results['pro_bar_full'] = full_history_downloader.download_pro_bar_full_history_all_stocks()
                else:
                    # 使用传统方式下载指定日期范围
                    if 'results' not in locals():
                        results = download_with_legacy_fallback(args.start_date, args.end_date)

        else:
            # Download all data using the appropriate method
            if args.use_legacy:
                logger.info("使用传统下载方式")
                results = download_with_legacy_method(args.start_date, args.end_date)
            else:
                results = download_with_legacy_fallback(args.start_date, args.end_date)

        # Generate final summary
        elapsed_time = time.time() - start_time

        # Calculate total records properly by checking data types
        total_records = 0
        if isinstance(results, dict):
            # Handle results from new scheduler or custom downloads
            if 'total_downloaded' in results:
                # Handle results from new scheduler
                total_records = results.get('total_downloaded', 0)
            else:
                # Handle results from custom downloads (pandas DataFrames)
                for key, result in results.items():
                    if isinstance(result, pd.DataFrame):
                        # If result is a DataFrame, count its rows
                        total_records += len(result) if result is not None else 0
                    elif isinstance(result, dict):
                        # If result is a dictionary, sum its values
                        total_records += sum(result.values()) if result else 0
                    elif isinstance(result, (int, float)):
                        # If result is a number, add directly
                        total_records += result
                    else:
                        # For other types, skip or treat as 0
                        continue
        else:
            # Handle results from legacy method
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
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)