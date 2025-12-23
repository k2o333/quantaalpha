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
from typing import List
try:
    from config import TUSHARE_POINTS
except ImportError:
    try:
        from .config import TUSHARE_POINTS
    except ImportError:
        from app.config import TUSHARE_POINTS

try:
    from score_config import get_available_data_types
except ImportError:
    try:
        from .score_config import get_available_data_types
    except ImportError:
        from app.score_config import get_available_data_types
from tushare_api import TuShareDownloader
import pandas as pd
import json

# Set up logging with Chinese characters support
log_dir = Path(__file__).parent.parent / 'log'
log_dir.mkdir(exist_ok=True)  # Ensure log directory exists
log_file = log_dir / 'aspipe_v4.log'

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_historical_download_marker_path():
    """
    获取历史下载标记文件路径
    """
    cache_dir = Path(__file__).parent.parent / 'cache'
    cache_dir.mkdir(exist_ok=True)
    return cache_dir / 'historical_download_marker.json'


def mark_interfaces_as_historical_downloaded(interfaces: List[str]):
    """
    记录哪些接口已完成了全历史下载
    """
    marker_path = get_historical_download_marker_path()
    try:
        # 读取现有的标记
        if marker_path.exists():
            with open(marker_path, 'r', encoding='utf-8') as f:
                markers = json.load(f)
        else:
            markers = {}

        # 更新标记
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        for interface in interfaces:
            markers[interface] = current_time

        # 写入标记
        with open(marker_path, 'w', encoding='utf-8') as f:
            json.dump(markers, f, ensure_ascii=False, indent=2)

        logger.info(f"已标记接口完成历史下载: {interfaces}")
    except Exception as e:
        logger.error(f"记录历史下载标记失败: {e}")


def get_historical_downloaded_interfaces() -> List[str]:
    """
    获取已完成历史下载的接口列表
    """
    marker_path = get_historical_download_marker_path()
    try:
        if marker_path.exists():
            with open(marker_path, 'r', encoding='utf-8') as f:
                markers = json.load(f)
                return list(markers.keys())
        else:
            return []
    except Exception as e:
        logger.error(f"读取历史下载标记失败: {e}")
        return []


def disable_tscode_dependent_interfaces_for_date_range():
    """
    在日期范围下载时禁用需要ts_code参数的接口
    """
    from config_adapter import config_adapter
    from enhanced_download_config import DOWNLOAD_PIPELINE_CONFIG

    # 定义需要ts_code参数的接口（这些接口在日期范围下载时不适用）
    tscode_dependent_interfaces = ['stk_rewards', 'top10_holders', 'pledge_detail', 'fina_audit', 'pro_bar']

    logger.info(f"在日期范围下载时将跳过需要ts_code参数的接口: {tscode_dependent_interfaces}")

    # 临时修改配置以禁用这些接口
    for interface_name in tscode_dependent_interfaces:
        if interface_name in DOWNLOAD_PIPELINE_CONFIG:
            config = DOWNLOAD_PIPELINE_CONFIG[interface_name]
            # 保存原始启用状态
            if not hasattr(config, '_original_enabled'):
                config._original_enabled = config.enabled
            config.enabled = False  # 临时禁用
            logger.info(f"临时禁用接口 {interface_name} 以避免日期范围下载")


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
        # 检查是否是使用日期范围参数的情况（非tscode-historical模式）
        is_date_range_mode = not args.tscode_historical and not args.holders_data and not args.pro_bar_only

        if is_date_range_mode:
            # 在日期范围模式下，禁用需要ts_code参数的接口
            disable_tscode_dependent_interfaces_for_date_range()

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
                    # 恢复临时禁用的接口以允许下载
                    from enhanced_download_config import DOWNLOAD_PIPELINE_CONFIG
                    for interface_name in ['stk_rewards', 'top10_holders', 'pledge_detail', 'fina_audit']:
                        if interface_name in DOWNLOAD_PIPELINE_CONFIG:
                            config = DOWNLOAD_PIPELINE_CONFIG[interface_name]
                            if hasattr(config, '_original_enabled'):
                                config.enabled = config._original_enabled
                                logger.info(f"恢复接口 {interface_name} 以执行历史下载")

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

                    # 标记这些接口为已完成历史下载
                    completed_historical_interfaces = ['stk_rewards', 'top10_holders']
                    if TUSHARE_POINTS >= 5000:
                        completed_historical_interfaces.append('pledge_detail')
                    if TUSHARE_POINTS >= 500:
                        completed_historical_interfaces.append('fina_audit')
                    mark_interfaces_as_historical_downloaded(completed_historical_interfaces)
                else:
                    results = download_with_legacy_fallback(args.start_date, args.end_date)

            if download_pro_bar_only:
                logger.info("下载pro_bar复权行情数据...")
                if args.tscode_historical:
                    # 恢复临时禁用的接口以允许下载
                    from enhanced_download_config import DOWNLOAD_PIPELINE_CONFIG
                    for interface_name in ['pro_bar']:
                        if interface_name in DOWNLOAD_PIPELINE_CONFIG:
                            config = DOWNLOAD_PIPELINE_CONFIG[interface_name]
                            if hasattr(config, '_original_enabled'):
                                config.enabled = config._original_enabled
                                logger.info(f"恢复接口 {interface_name} 以执行历史下载")

                    # 下载全历史数据
                    logger.info("下载pro_bar全历史数据...")
                    # 传递股票列表以提高性能
                    from interfaces.basic_data import BasicDataDownloader
                    basic_downloader = BasicDataDownloader(downloader.pro)
                    stock_list = basic_downloader.download_stock_basic()

                    from interfaces.holders_data_downloader import HoldersDataFullHistoryDownloader
                    full_history_downloader = HoldersDataFullHistoryDownloader(downloader.pro, stock_list)
                    results['pro_bar_full'] = full_history_downloader.download_pro_bar_full_history_all_stocks()

                    # 标记pro_bar为已完成历史下载
                    mark_interfaces_as_historical_downloaded(['pro_bar'])
                else:
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

        # 恢复被临时禁用的接口配置
        from enhanced_download_config import DOWNLOAD_PIPELINE_CONFIG
        for interface_name, config in DOWNLOAD_PIPELINE_CONFIG.items():
            if hasattr(config, '_original_enabled'):
                config.enabled = config._original_enabled
                logger.debug(f"已恢复接口 {interface_name} 的原始启用状态: {config._original_enabled}")
                # 删除临时属性
                delattr(config, '_original_enabled')

        return True

    except Exception as e:
        logger.error(f"❌ 系统执行失败: {e}")
        logger.error(f"📅 失败时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # 恢复被临时禁用的接口配置（即使在异常情况下）
        from enhanced_download_config import DOWNLOAD_PIPELINE_CONFIG
        for interface_name, config in DOWNLOAD_PIPELINE_CONFIG.items():
            if hasattr(config, '_original_enabled'):
                config.enabled = config._original_enabled
                logger.debug(f"已恢复接口 {interface_name} 的原始启用状态: {config._original_enabled}")
                # 删除临时属性
                delattr(config, '_original_enabled')

        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)